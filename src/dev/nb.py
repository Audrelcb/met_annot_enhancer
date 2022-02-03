# Required libraries
import pandas as pd
import yaml
import json
from pandas import json_normalize



# Loading helpers functions

from helpers import gnps_job_fetcher
from helpers import paths_generator


# for debug ony should be commented later 
from pathlib import Path
p = Path(__file__).parents[2]
print(p)
os.chdir(p)


# Loading the parameters from yaml file


if not os.path.exists('configs/user_defined/default.yaml'):
    print('No configs/user_defined/default.yaml: copy from configs/default/default.yaml and modify according to your needs')
with open (r'configs/user_defined/default.yaml') as file:    
    params_list = yaml.load(file, Loader=yaml.FullLoader)

# Parameters can now be accessed using params_list['level1']['level2'] e. g. arams_list['options']['download_gnps_job']

# Downloading GNPS files
if params_list['options']['download_gnps_job'] == True:

    gnps_job_fetcher(gnps_job_id = params_list['paths']['gnps_job_id'], input_folder = params_list['paths']['input_folder'])

# Generating pathes
# The pathes are stored in a dictionary and can then be accesed by paths_dic['value']

paths_dic = paths_generator(params_list = params_list)



# Writing used parameters 
params_suffix = '.yaml'

with open(os.path.join(path_to_results_folders, gnps_job_id + params_suffix), 'w') as file:  
    documents = yaml.dump(params_list, file)

print('''
Parameters used are stored in '''
+ str(os.path.join(path_to_results_folders, gnps_job_id + params_suffix))
)


# timer is started
start_time = time.time()

# Import MS1 list

if polarity == 'pos':
    adducts_df = pd.read_csv(
        adducts_pos_path, compression='gzip', sep='\t')
else:
    adducts_df = pd.read_csv(
        adducts_neg_path, compression='gzip', sep='\t')

adducts_df['min'] = adducts_df['adduct_mass'] - \
    int(ppm_tol) * (adducts_df['adduct_mass'] / 1000000)
adducts_df['max'] = adducts_df['adduct_mass'] + \
    int(ppm_tol) * (adducts_df['adduct_mass'] / 1000000)


# Spectral matching stage

if do_spectral_match == True:

    print('''
    Proceeding to spectral matching ...
    ''')

    spectral_lib_matcher.main(query_file_path,
                            db_file_path,
                            parent_mz_tol,
                            msms_mz_tol,
                            min_cos,
                            min_peaks,
                            isdb_results_path
                            )
    print('''
    Spectral matching done !
    ''')


# Loading the files

dt_isdb_results = pd.read_csv(isdb_results_path,
                              sep='\t',
                              usecols=['msms_score', 'feature_id', 'reference_id', 'inchikey'],
                              error_bad_lines=False, low_memory=True)

## we add a fixed libname (to be changed later on) 

dt_isdb_results['libname'] = 'ISDB'

dt_isdb_results.rename(columns={
    'row ID': 'feature_id',
    'componentindex': 'component_id',
    'parent mass': 'mz',
    'inchikey': 'short_inchikey',
    'msms_score': 'score_input'}, inplace=True)

## In fact we can directly start here
## we get the networks info (cluster id, component index and parent mass form the downloaded folder)


clusterinfo_summary = pd.read_csv(clusterinfo_summary_path + str(os.listdir(clusterinfo_summary_path)[0]),
                                  sep='\t',
                                  usecols=['cluster index', 'componentindex', 'parent mass'],
                                  error_bad_lines=False, low_memory=True)

clusterinfo_summary.rename(columns={'cluster index': 'feature_id', 'componentindex': 'component_id',
                                'parent mass': 'mz', 'msms_score': 'score_input'}, inplace=True)

cluster_count = clusterinfo_summary.drop_duplicates(
    subset=['feature_id', 'component_id']).groupby("component_id").count()
cluster_count = cluster_count[['feature_id']].rename(
    columns={'feature_id': 'ci_count'}).reset_index()

# ## we now merge this back with the isdb matched results 
dt_isdb_results = pd.merge(dt_isdb_results, clusterinfo_summary, on='feature_id')

# ## we drop the duplicated ['cluster index'] column
#dt_isdb_results.drop(columns=['cluster index'], inplace=True)

# ## we return a short_inchikey column

# dt_isdb_results['short_inchikey'] = dt_isdb_results['inchikey'].str.split("-", n=1, expand=True)[0]

db_metadata = pd.read_csv(metadata_path,
                        sep=',', error_bad_lines=False, low_memory=False)

db_metadata['short_inchikey'] = db_metadata.structure_inchikey.str.split(
    "-", expand=True)[0]
db_metadata.reset_index(inplace=True)

# at this step we can only keep unique short_ik - organisms pairs

db_metadata.drop_duplicates(subset=['short_inchikey', 'organism_wikidata'], keep='first', inplace=True, ignore_index=True)



print('Number of features: ' + str(len(clusterinfo_summary)))
print('Number of MS2 annotation: ' + str(len(dt_isdb_results)))

# Now we directly do the MS1 matching stage on the cluster_summary. No need to have MS2 annotations

print('''
Proceeding to MS1 annotation ...
''')
super_df = []

for i, row in tqdm(clusterinfo_summary.iterrows(), total=clusterinfo_summary.shape[0]):
    par_mass = clusterinfo_summary.loc[i, 'mz']
    df_0 = clusterinfo_summary.loc[[i], ['feature_id', 'mz', 'component_id']]
    df_1 = adducts_df[(adducts_df['min'] <= par_mass) & (adducts_df['max'] >= par_mass)]
    df_1['key'] = i
    df_1.drop(['min', 'max'], axis=1, inplace=True)
    df_tot = pd.merge(df_0, df_1, left_index=True, right_on='key', how='left')
    super_df.append(df_tot)

df_MS1 = pd.concat(super_df, axis=0)
del super_df

df_MS1 = df_MS1.drop(['key'], axis=1).drop_duplicates(
    subset=['feature_id', 'adduct'])

df_MS1['libname'] = 'MS1_match'

print('''
MS1 annotation done !
''')

df_meta_2 = db_metadata[['short_inchikey', 'structure_exact_mass']]
df_meta_2 = df_meta_2.dropna(subset=['structure_exact_mass'])
df_meta_2 = df_meta_2.drop_duplicates(
    subset=['short_inchikey', 'structure_exact_mass'])

df_meta_2 = df_meta_2.round({'structure_exact_mass': 5})
df_MS1 = df_MS1.round({'exact_mass': 5})

df_MS1_merge = pd.merge(df_MS1, df_meta_2, left_on='exact_mass',
                        right_on='structure_exact_mass', how='left')
df_MS1_merge = df_MS1_merge.dropna(subset=['short_inchikey'])

df_MS1_merge['match_mzerror_MS1'] = df_MS1_merge['mz'] - \
    df_MS1_merge['adduct_mass']
df_MS1_merge = df_MS1_merge.round({'match_mzerror_MS1': 5}).astype({
    'match_mzerror_MS1': 'str'})

df_MS1_merge = df_MS1_merge.drop(
    ['structure_exact_mass', 'adduct_mass', 'exact_mass'], axis=1)
df_MS1_merge['score_input'] = 0

# Merge MS1 results with MS2 annotations
dt_isdb_results = pd.concat([dt_isdb_results, df_MS1_merge])

print('Number of annotated features after MS1: ' +
      str(len(df_MS1_merge['feature_id'].unique())))

print('Total number of MS1 and MSMS annotations: ' + str(len(dt_isdb_results)))

# Rank annotations based on the spectral score

dt_isdb_results["score_input"] = pd.to_numeric(
    dt_isdb_results["score_input"], downcast="float")
dt_isdb_results['rank_spec'] = dt_isdb_results[['feature_id', 'score_input']].groupby(
    'feature_id')['score_input'].rank(method='dense', ascending=False)

dt_isdb_results.reset_index(inplace=True, drop=True)

# now we merge with the Occurences DB metadata after selection of our columns of interest

cols_to_use = ['structure_inchikey', 'structure_inchi',
            'structure_smiles', 'structure_molecular_formula',
            'structure_exact_mass', 'short_inchikey', 'structure_taxonomy_npclassifier_01pathway', 
            'structure_taxonomy_npclassifier_02superclass', 'structure_taxonomy_npclassifier_03class',
            'organism_name', 'organism_taxonomy_ottid',
            'organism_taxonomy_01domain', 'organism_taxonomy_02kingdom', 'organism_taxonomy_03phylum',
            'organism_taxonomy_04class', 'organism_taxonomy_05order', 'organism_taxonomy_06family', 'organism_taxonomy_07tribe', 'organism_taxonomy_08genus', 'organism_taxonomy_09species', 'organism_taxonomy_10varietas' ]

dt_isdb_results = pd.merge(
    left=dt_isdb_results, right=db_metadata[cols_to_use], left_on='short_inchikey', right_on='short_inchikey', how='outer')
dt_isdb_results.dropna(subset=['feature_id'], inplace=True)

print('Total number of annotations with unique Biosource/line: ' +
      str(len(dt_isdb_results)))

# Resolving the taxon information from the GNPS metadata file

# the metadata table path is generated from the base bath to the GNPS results folder
metadata_table_path = os.path.join(path_to_gnps_folder,'metadata_table','')

# the metadata table is loaded using the organism column specified before
samples_metadata = pd.read_csv(metadata_table_path + str(os.listdir(metadata_table_path)[0]), sep='\t',
                                usecols=['filename', organism_header])

# Now we want to get the taxonomic information for each of the samples
# so we want to extract the species information from the metadata file
samples_metadata[organism_header].dropna(inplace = True)
samples_metadata[organism_header] = samples_metadata[organism_header].str.lower()
species = samples_metadata[organism_header].unique()
len_species = len(species)

print("%s unique species have been selected from the metadata table." % len_species )

if do_taxo_resolving == True:

    species_tnrs_matched = OT.tnrs_match(species, context_name=None, do_approximate_matching=True, include_suppressed=False)

    with open(str(path_to_results_folders + project_name + '_' + 'species.json'), 'w') as out:
        sf = json.dumps(species_tnrs_matched.response_dict, indent=2, sort_keys=True)
        out.write('{}\n'.format(sf))

with open(str(path_to_results_folders + project_name + '_' + 'species.json')) as tmpfile:
        jsondic = json.loads(tmpfile.read())


json_normalize(jsondic)

df_species_tnrs_matched = json_normalize(jsondic,
            record_path=['results', 'matches']
            )
df_species_tnrs_unmatched = json_normalize(jsondic,
            record_path=['unmatched_names']
            )

df_species_tnrs_matched.info()

# We then want to match with the accepted name instead of the synonym in case both are present. 
# We thus order by matched_name and then by is_synonym status prior to returning the first row.

df_species_tnrs_matched.sort_values(['search_string', 'is_synonym'], axis = 0, inplace = True)
df_species_tnrs_matched_unique = df_species_tnrs_matched.drop_duplicates('search_string', keep = 'first')

# both df are finally merged
merged_df = pd.merge(samples_metadata, df_species_tnrs_matched_unique, how='left', left_on=organism_header, right_on='search_string', indicator=True)

# converting 'ott_ids' from float to int (check the astype('Int64') whic will work while the astype('int') won't see https://stackoverflow.com/a/54194908)
merged_df['taxon.ott_id'] = merged_df['taxon.ott_id'].astype('Int64')

# However, we then need to put them back to 
merged_df['taxon.ott_id']
ott_list = list(merged_df['taxon.ott_id'].dropna().astype('int'))

if do_taxo_resolving == True:

    taxon_info = []

    for i in ott_list:
        query = OT.taxon_info(i, include_lineage=True)
        taxon_info.append(query)

    tl = []

    for i in taxon_info:
        with open(str(path_to_results_folders + project_name + '_' + 'taxon_info.json'), 'w') as out:
            tl.append(i.response_dict)
            yo = json.dumps(tl)
            out.write('{}\n'.format(yo))

with open(str(path_to_results_folders + project_name + '_' + 'taxon_info.json')) as tmpfile:
    jsondic = json.loads(tmpfile.read())

df = json_normalize(jsondic)

df_tax_lineage = json_normalize(jsondic,
            record_path=['lineage'],
            meta = ['ott_id', 'unique_name'],
            record_prefix='sub_',
            errors='ignore'
            )

# This keeps the last occurence of each ott_id / sub_rank grouping https://stackoverflow.com/a/41886945
df_tax_lineage_filtered = df_tax_lineage.groupby(['ott_id', 'sub_rank'], as_index=False).last()

#Here we pivot long to wide to get the taxonomy
df_tax_lineage_filtered_flat = df_tax_lineage_filtered.pivot(index='ott_id', columns='sub_rank', values='sub_name')

# Here we actually also want the lowertaxon (species usually) name
df_tax_lineage_filtered_flat = pd.merge(df_tax_lineage_filtered_flat, df_tax_lineage_filtered[['ott_id', 'unique_name']], how='left', on='ott_id', )

#Despite the left join ott_id are duplicated 
df_tax_lineage_filtered_flat.drop_duplicates(subset = ['ott_id', 'unique_name'], inplace = True)

# here we want to have these columns whatevere happens
col_list = ['ott_id', 'domain', 'kingdom', 'phylum',
                        'class', 'order', 'family', 'tribe', 'genus', 'unique_name']

df_tax_lineage_filtered_flat = df_tax_lineage_filtered_flat.reindex(columns=col_list, fill_value = np.NaN)

# We now rename our columns of interest
renaming_dict = {'domain': 'query_otol_domain',
            'kingdom': 'query_otol_kingdom',
            'phylum': 'query_otol_phylum',
            'class': 'query_otol_class',
            'order': 'query_otol_order',
            'family': 'query_otol_family',
            'tribe': 'query_otol_tribe',
            'genus': 'query_otol_genus',
            'unique_name': 'query_otol_species'}

df_tax_lineage_filtered_flat.rename(columns=renaming_dict, inplace=True)

# We select columns of interest 
cols_to_keep = ['ott_id',
            'query_otol_domain',
            'query_otol_kingdom',
            'query_otol_phylum',
            'query_otol_class',
            'query_otol_order',
            'query_otol_family',
            'query_otol_tribe',
            'query_otol_genus',
            'query_otol_species']

df_tax_lineage_filtered_flat = df_tax_lineage_filtered_flat[cols_to_keep]

# We merge this back with the samplemetadata only if we have an ott.id in the merged df 
samples_metadata = pd.merge(merged_df[pd.notnull(merged_df['taxon.ott_id'])], df_tax_lineage_filtered_flat, how='left', left_on='taxon.ott_id', right_on='ott_id' )


# Extracting biosource / feature for line by line

print('''
Fetching the biosource contribution per feature ...
''')

quantification_table_reformatted_path = os.path.join(path_to_gnps_folder,'quantification_table_reformatted','')

metadata_table_path = os.path.join(path_to_gnps_folder,'metadata_table','')


feature_intensity = pd.read_csv(quantification_table_reformatted_path + str(
    os.listdir(quantification_table_reformatted_path)[0]), sep=',')

feature_intensity.rename(columns={'row ID': 'row_ID'}, inplace=True)
feature_intensity.set_index('row_ID', inplace=True)
feature_intensity = feature_intensity.filter(
    regex=file_extension + '|row_ID')
if Top_N_Sample == 0:
    feature_intensity = feature_intensity.where(feature_intensity.apply(
        lambda x: x.isin(x.nlargest(len(feature_intensity.columns))), axis=1), 0)  # top N here
else:
    feature_intensity = feature_intensity.where(feature_intensity.apply(
        lambda x: x.isin(x.nlargest(Top_N_Sample)), axis=1), 0)  # top N here
feature_intensity.columns = feature_intensity.columns.str.replace(msfile_suffix, '') # this is not safe, we should find an alternative. Maybe raising an issue if the suffix is not found 
feature_intensity = feature_intensity.transpose()
feature_intensity.index.name = 'MS_filename'
feature_intensity_table_t = feature_intensity
feature_intensity = feature_intensity.transpose()
res = feature_intensity[feature_intensity != 0].stack()
df_res = res.to_frame().reset_index()
df_merged = pd.merge(df_res, samples_metadata, left_on='MS_filename',
                        right_on='filename', how='left').drop([0, 'MS_filename', 'filename'], axis=1)
df_merged = df_merged.groupby('row_ID').agg(lambda x: list(x))
df_merged.reset_index(inplace=True)


# Here we will add three columns (even for the simple repond this way it will be close to the multiple species repond)
# these line will need to be defined as function arguments

dt_isdb_results = pd.merge(
    dt_isdb_results, df_merged, left_on='feature_id', right_on='row_ID', how='left')

       
# Taxonomical Reweighting

print('''
Proceeding to taxonomically informed reponderation ...
''')

cols_ref = ['organism_taxonomy_01domain', 'organism_taxonomy_02kingdom',  'organism_taxonomy_03phylum', 'organism_taxonomy_04class',
            'organism_taxonomy_05order', 'organism_taxonomy_06family', 'organism_taxonomy_07tribe', 'organism_taxonomy_08genus', 'organism_taxonomy_09species']

cols_att = ['query_otol_domain', 'query_otol_kingdom', 'query_otol_phylum', 'query_otol_class',
            'query_otol_order', 'query_otol_family', 'query_otol_tribe', 'query_otol_genus', 'query_otol_species']

cols_match = ['matched_domain', 'matched_kingdom', 'matched_phylum', 'matched_class',
              'matched_order', 'matched_family', 'matched_tribe', 'matched_genus', 'matched_species']

col_prev = None
for col_ref, col_att, col_match in zip(cols_ref, cols_att, cols_match):
        dt_isdb_results[col_ref].fillna('Unknown', inplace=True)
        dt_isdb_results[col_ref] = dt_isdb_results[col_ref].apply(lambda x: [x])
        dt_isdb_results[col_match] = [list(set(a).intersection(set(b))) for a, b in zip(dt_isdb_results[col_ref], dt_isdb_results[col_att])] # Allows to compare 2 lists
        dt_isdb_results[col_match] = dt_isdb_results[col_match].apply(lambda y: np.nan if len(y)==0 else y)
        if col_prev != None:
                dt_isdb_results[col_match].where(dt_isdb_results[col_prev].notnull(), np.nan)
        col_prev = col_match

# Note for future self. If you get a TypeError: unhashable type: 'list' error. before messing around with the previous line make sure that the taxonomy has been appended at the dt_isdb_results = pd.merge(
#  ' dt_isdb_results, df_merged, left_on='feature_id', right_on='row_ID', how='left')' step before. Usuall this comes from a bad definition of the regex (ex .mzXMl insted of .mzML) in the params file. Should find a safer way to deal with these extensions in the header.


dt_isdb_results['score_taxo'] = dt_isdb_results[cols_match].count(axis=1)

# Filter out MS1 annotations without a reweighting at a given taxo level prior to chemo repond

dt_isdb_results.info()



dt_isdb_results = dt_isdb_results[
    (dt_isdb_results['score_taxo'] >= min_score_taxo_ms1) | (
    dt_isdb_results['libname'] == 'ISDB')]



print('Total number of annotations after filtering MS1 annotations not reweighted at taxonomical level min: ' +
    str(len(dt_isdb_results)))

print('Number of annotations reweighted at the domain level: ' +
    str(dt_isdb_results['matched_domain'].count()))
print('Number of annotations reweighted at the kingom level: ' +
    str(dt_isdb_results['matched_kingdom'].count()))
print('Number of annotations reweighted at the phylum level: ' +
    str(dt_isdb_results['matched_phylum'].count()))
print('Number of annotations reweighted at the class level: ' +
    str(dt_isdb_results['matched_class'].count()))
print('Number of annotations reweighted at the order level: ' +
    str(dt_isdb_results['matched_order'].count()))
print('Number of annotations reweighted at the family level: ' +
    str(dt_isdb_results['matched_family'].count()))
print('Number of annotations reweighted at the tribe level: ' +
    str(dt_isdb_results['matched_tribe'].count()))
print('Number of annotations reweighted at the genus level: ' +
    str(dt_isdb_results['matched_genus'].count()))
print('Number of annotations reweighted at the species level: ' +
    str(dt_isdb_results['matched_species'].count()))


# we set the spectral score column as float
dt_isdb_results["score_input"] = pd.to_numeric(
    dt_isdb_results["score_input"], downcast="float")
# and we add it to the max txo score :
dt_isdb_results['score_input_taxo'] = dt_isdb_results['score_taxo'] + \
    dt_isdb_results['score_input']


dt_isdb_results['rank_spec_taxo'] = dt_isdb_results.groupby(
    'feature_id')['score_input_taxo'].rank(method='dense', ascending=False)

dt_isdb_results = dt_isdb_results.groupby(["feature_id"]).apply(
    lambda x: x.sort_values(["rank_spec_taxo"], ascending=True)).reset_index(drop=True)

# Get cluster Chemical class
for col in ['structure_taxonomy_npclassifier_01pathway', 'structure_taxonomy_npclassifier_02superclass', 'structure_taxonomy_npclassifier_03class']:

    df = dt_isdb_results.copy()
    df = df.drop_duplicates(subset=['feature_id', col])
    df = df[df["component_id"] != -1]
    df = df[df.rank_spec_taxo <= top_N_chemical_consistency]
    df = df.groupby(
        ["component_id", col]
    ).agg({'feature_id': 'count',
        'rank_spec_taxo': 'mean'}
        ).reset_index(
    ).rename(columns={'feature_id': (col + '_count'),
                    'rank_spec_taxo': ('rank_' + col + '_mean')}
            ).merge(cluster_count, on='component_id', how='left')

    df[('freq_' + col)] = df[(col + '_count')] / df['ci_count']
    df[(col + '_score')] = df[('freq_' + col)] / \
        (df[('rank_' + col + '_mean')]**(0.5))
    df = df.sort_values(
        (col + '_score'), ascending=False
    ).drop_duplicates(['component_id']
                    ).rename(columns={col: (col + '_consensus')})
    dt_isdb_results = dt_isdb_results.merge(
        df[[(col + '_consensus'), ('freq_' + col), 'component_id']], on='component_id', how='left')

# Chemical consistency reweighting

print('''
Proceeding to chemically informed reponderation ...
''')


dt_isdb_results['structure_taxonomy_npclassifier_01pathway_score'] = dt_isdb_results.apply(
    lambda x: 1 if x.structure_taxonomy_npclassifier_01pathway == x.structure_taxonomy_npclassifier_01pathway_consensus else 0, axis=1)
dt_isdb_results['structure_taxonomy_npclassifier_02superclass_score'] = dt_isdb_results.apply(
    lambda x: 2 if x.structure_taxonomy_npclassifier_02superclass == x.structure_taxonomy_npclassifier_02superclass_consensus else 0, axis=1)
dt_isdb_results['structure_taxonomy_npclassifier_03class_score'] = dt_isdb_results.apply(
    lambda x: 3 if x.structure_taxonomy_npclassifier_03class == x.structure_taxonomy_npclassifier_03class_consensus else 0, axis=1)

dt_isdb_results['score_max_consistency'] = dt_isdb_results[[
    "structure_taxonomy_npclassifier_01pathway_score",
    "structure_taxonomy_npclassifier_02superclass_score",
    "structure_taxonomy_npclassifier_03class_score"
]].max(axis=1)

dt_isdb_results['final_score'] = dt_isdb_results['score_input'] + dt_isdb_results['score_taxo'] + dt_isdb_results['score_max_consistency']

dt_isdb_results['rank_final'] = dt_isdb_results.groupby(
    'feature_id')['final_score'].rank(method='dense', ascending=False)



print('Number of annotations reweighted at the NPClassifier pathway level: ' +
    str(len(dt_isdb_results[(dt_isdb_results['structure_taxonomy_npclassifier_01pathway_score'] == 1)])))
print('Number of annotations reweighted at the NPClassifier superclass level: ' +
    str(len(dt_isdb_results[(dt_isdb_results['structure_taxonomy_npclassifier_02superclass_score'] == 2)])))
print('Number of annotations reweighted at the NPClassifier class level: ' +
    str(len(dt_isdb_results[(dt_isdb_results['structure_taxonomy_npclassifier_03class_score'] == 3)])))


dt_isdb_results_chem_rew = dt_isdb_results.loc[(
    dt_isdb_results.rank_final <= int(top_to_output))]
dt_isdb_results_chem_rew[["feature_id", "rank_final", "component_id"]] = dt_isdb_results_chem_rew[[
    "feature_id", "rank_final", "component_id"]].apply(pd.to_numeric, downcast='signed', axis=1)
dt_isdb_results_chem_rew = dt_isdb_results_chem_rew.sort_values(
    ["feature_id", "rank_final"], ascending=(False, True))
# dt_isdb_results_chem_rew = dt_isdb_results_chem_rew.astype(str) (Check if this one is necessary because it messes up quite a bit of things later on)


# Here we would like to filter results when short IK are repeated for the same feature_id at the same final rank
# see issue (https://gitlab.com/tima5/taxoscorer/-/issues/23)

dt_isdb_results_chem_rew = dt_isdb_results_chem_rew.drop_duplicates(subset=['feature_id', 'short_inchikey'], keep='first')

dt_isdb_results_chem_rew = dt_isdb_results_chem_rew.astype({'feature_id' : 'int64'})

if keep_lowest_taxon == True :
    
    dt_isdb_results_chem_rew['lowest_matched_taxon'] = dt_isdb_results_chem_rew['matched_species']
    dt_isdb_results_chem_rew['lowest_matched_taxon'] = dt_isdb_results_chem_rew['lowest_matched_taxon'].replace('nan', np.NaN)
    col_matched = ['matched_genus', 'matched_tribe', 'matched_family', 'matched_order', 'matched_order', 'matched_phylum', 'matched_kingdom', 'matched_domain']
    for col in col_matched:
        dt_isdb_results_chem_rew[col] = dt_isdb_results_chem_rew[col].replace('nan', np.NaN)  
        dt_isdb_results_chem_rew['lowest_matched_taxon'].fillna(dt_isdb_results_chem_rew[col], inplace=True)

    annot_attr = ['rank_spec', 'score_input', 'libname', 'structure_inchikey', 'structure_inchi', 'structure_smiles', 'structure_molecular_formula', 'adduct',
                'structure_exact_mass', 'structure_taxonomy_npclassifier_01pathway', 'structure_taxonomy_npclassifier_02superclass', 'structure_taxonomy_npclassifier_03class',
                'query_otol_species', 'lowest_matched_taxon', 'score_taxo', 'score_max_consistency', 'final_score', 'rank_final']

else :
    annot_attr = ['rank_spec', 'score_input', 'libname', 'structure_inchikey', 'structure_inchi',
                'structure_smiles', 'structure_molecular_formula', 'adduct',
                'structure_exact_mass', 'short_inchikey', 'structure_taxonomy_npclassifier_01pathway', 
                'structure_taxonomy_npclassifier_02superclass', 'structure_taxonomy_npclassifier_03class',
                'organism_name', 'organism_taxonomy_ottid',
                'organism_taxonomy_01domain', 'organism_taxonomy_02kingdom', 'organism_taxonomy_03phylum',
                'organism_taxonomy_04class', 'organism_taxonomy_05order', 'organism_taxonomy_06family', 'organism_taxonomy_07tribe', 'organism_taxonomy_08genus', 'organism_taxonomy_09species', 'organism_taxonomy_10varietas',  
                'matched_domain', 'matched_kingdom', 'matched_phylum', 'matched_class', 'matched_order',
                'matched_family', 'matched_tribe', 'matched_genus', 'matched_species', 'score_taxo', 'score_max_consistency', 'final_score', 'rank_final']


comp_attr = ['component_id', 'structure_taxonomy_npclassifier_01pathway_consensus', 'freq_structure_taxonomy_npclassifier_01pathway', 'structure_taxonomy_npclassifier_02superclass_consensus',
            'freq_structure_taxonomy_npclassifier_02superclass', 'structure_taxonomy_npclassifier_03class_consensus', 'freq_structure_taxonomy_npclassifier_03class']


col_to_keep = ['feature_id'] + comp_attr + annot_attr

# We add the min chemo score at this step 

dt_isdb_results_chem_rew.info()

print(type(dt_isdb_results_chem_rew['score_taxo']))
print(type(min_score_taxo_ms1))
print(type(dt_isdb_results_chem_rew['score_max_consistency']))
print(type(min_score_chemo_ms1))


dt_isdb_results_chem_rew = dt_isdb_results_chem_rew[
    ((dt_isdb_results_chem_rew['score_taxo'] >= min_score_taxo_ms1) & (dt_isdb_results_chem_rew['score_max_consistency'] >= min_score_chemo_ms1)) | (
    dt_isdb_results_chem_rew['libname'] == 'ISDB')]


df4cyto_flat = dt_isdb_results_chem_rew[col_to_keep]

#### fetching CHEMBL infos

from chembl_webresource_client.new_client import new_client
molecule = new_client.molecule

inchi_keys = df4cyto_flat['structure_inchikey'].unique()
chunks_query = [inchi_keys[x:x+35] for x in range(0, len(inchi_keys), 35)]

results = []
bad_keys = []


for chunk in tqdm(chunks_query):
    try:
        res = molecule.get(list(chunk))
        results.append(res)
    except:
        # Inchi key was not found in ChEMBL
        bad_keys.append(chunk)

flat_list = [item for sublist in results for item in sublist]

chembl_df = json_normalize(flat_list)

chembl_df = chembl_df[['molecule_chembl_id', 'molecule_structures.standard_inchi_key']]


df4cyto_flat = pd.merge(left=df4cyto_flat, right=chembl_df, left_on='structure_inchikey', right_on='molecule_structures.standard_inchi_key', how = 'left')

df4cyto_flat.rename(columns={'molecule_chembl_id': 'structure_chembl_id'}, inplace=True)
df4cyto_flat.drop(['molecule_structures.standard_inchi_key'], axis=1, inplace=True)


all_columns = list(df4cyto_flat) # Creates list of all column headers
df4cyto_flat[all_columns] = df4cyto_flat[all_columns].astype(str)

gb_spec = {c: '|'.join for c in annot_attr}
for c in comp_attr:
    gb_spec[c] = 'first'

df4cyto = df4cyto_flat.groupby('feature_id').agg(gb_spec)

df4cyto_flat.to_csv(isdb_results_repond_flat_path, sep='\t')

df4cyto.to_csv(isdb_results_repond_path, sep='\t')


print('Finished in %s seconds.' % (time.time() - start_time))
print('You can check your results here %s' % isdb_results_repond_path)

if output_plots == True:

    print('''
    Generating plots... check your web browser !
    ''')

    import plotly.express as px
    from plotly.subplots import make_subplots
    import plotly.graph_objects as go


    # if keep_lowest_taxon == False :


    #     # we have a problem because the organism_taxonomy_ are lists and not strings.
    #     # We subset specifically these columns

    #     dt_isdb_results_tax = dt_isdb_results.loc[:, dt_isdb_results.columns.str.startswith('organism_taxonomy_')]

    #     # and then use the explode function to yield the datframe with the values extractes from the lists

    #     dt_isdb_results_tax = dt_isdb_results_tax.set_index(['organism_taxonomy_ottid']).apply(pd.Series.explode).reset_index()

    #     # we now drop the previous columns with the list format 

    #     colsToDrop = [ 'organism_taxonomy_01domain', 'organism_taxonomy_02kingdom',
    #         'organism_taxonomy_03phylum', 'organism_taxonomy_04class', 'organism_taxonomy_05order',
    #         'organism_taxonomy_06family', 'organism_taxonomy_07tribe', 'organism_taxonomy_08genus',
    #         'organism_taxonomy_09species', 'organism_taxonomy_10varietas']

    #     dt_isdb_results = dt_isdb_results.drop(colsToDrop, axis=1)

    #     # and we merge back using the organism_taxonomy_ottid. Here we use concat and merge on indexes

    #     dt_isdb_results = pd.concat([dt_isdb_results, dt_isdb_results_tax], axis=1)



    #     dt_isdb_results['counter'] = 1

    #     dt_isdb_results = dt_isdb_results.replace({np.nan:'None'})

    #     fig = px.treemap(dt_isdb_results, path=[px.Constant("all"), 'organism_taxonomy_01domain', 'organism_taxonomy_02kingdom', 'organism_taxonomy_03phylum',
    #                 'organism_taxonomy_04class', 'organism_taxonomy_05order', 'organism_taxonomy_06family', 'organism_taxonomy_07tribe', 'organism_taxonomy_08genus', 'organism_taxonomy_09species'],  values='counter')


    #     fig.show()

    #     fig.update_layout(
    #         title_font_family="Courier New",
    #         title_font_color="black",
    #         title_font_size=14,
    #         legend_title_font_color="black",
    #         title_text="<b> Overview of the source organisms taxonomical repartition of the chemical annotations <br> before taxonomical reponderation <br>" + project_name + "</b>",
    #         title_x=0.5
    #     )

    #     fig.update_layout(
    #         title={
    #             'text': "<b> Overview of the source organisms taxonomical repartition of the chemical annotations <br> before taxonomical reponderation for <br>" + '<span style="font-size: 20px;">' + project_name + '</span>' + "</b>",
    #             'y':0.96,
    #             'x':0.5,
    #             'xanchor': 'center',
    #             'yanchor': 'top'})

    #     fig.update_layout(margin=dict(l=50, r=50, t=100, b=50)
    #     #,paper_bgcolor="Black"
    #     )

    #     fig.show()

        # fig.write_html(sunburst_organisms_results_path,
        #             full_html=False,
        #             include_plotlyjs='cdn')


    # here we want to have an puput per sample so we merge back the annotation frame with the feature table 
    #actually we might want to have the metadat joined to the feature table since the beginning

    feature_intensity_table_t

    samples_metadata_full = pd.read_csv(metadata_table_path + str(os.listdir(metadata_table_path)[0]), sep='\t')
    feature_intensity_meta = pd.merge(left=samples_metadata_full, right=feature_intensity_table_t, left_on='filename', right_on='MS_filename',how='inner')


    feature_intensity_meta_gp_species = feature_intensity_meta.groupby(organism_header).mean()
    feature_intensity_meta_gp_species = feature_intensity_meta_gp_species.transpose()
    feature_intensity_meta_gp_species.index.name = 'row_ID'



    feature_intensity_table = feature_intensity_table_t.transpose()

    feature_intensity_table.reset_index(inplace=True)
    feature_intensity_meta_gp_species.reset_index(inplace=True)

    

    ft_merged = pd.merge(feature_intensity_table, feature_intensity_meta_gp_species, on='row_ID', how='left')

    if multi_plot == True:
        feature_intensity_meta_gp_multi = feature_intensity_meta.groupby([organism_header,sampletype_header]).mean()
        feature_intensity_meta_gp_multi = feature_intensity_meta_gp_multi.transpose()
        feature_intensity_meta_gp_multi.columns = feature_intensity_meta_gp_multi.columns.map('_'.join)
        feature_intensity_meta_gp_multi.index.name = 'row_ID'
        feature_intensity_meta_gp_multi.reset_index(inplace=True)
        ft_merged = pd.merge(ft_merged, feature_intensity_meta_gp_multi, on='row_ID', how='left')

    df4cyto_flat['feature_id'] = df4cyto_flat['feature_id'].astype('int')

    dt_isdb_results_int = pd.merge(
        df4cyto_flat, ft_merged, left_on='feature_id', right_on='row_ID', how='left')

    dt_isdb_results_int['counter'] = 1




    # for n in samples_metadata_full['species_name'].unique():
    #     print(n)

    #     dt = dt_isdb_results_int[dt_isdb_results_int[n] > 0]

    #     fig = px.treemap(dt, path=[px.Constant("all"), 'structure_taxonomy_npclassifier_01pathway', 'structure_taxonomy_npclassifier_02superclass', 'structure_taxonomy_npclassifier_03class'], values=n)
    #     fig.update_traces(root_color="lightgrey")
    #     fig.update_layout(margin = dict(t=50, l=25, r=25, b=25))
    #     fig.show()


    # for n in samples_metadata_full['species_name'].unique():
    #     print(n)

    #     dt = dt_isdb_results_int[dt_isdb_results_int[n] > 0]

    #     fig = px.treemap(dt, path=[px.Constant("all"), 'structure_taxonomy_npclassifier_01pathway', 'structure_taxonomy_npclassifier_02superclass', 'structure_taxonomy_npclassifier_03class'], values='counter')
    #     fig.update_traces(root_color="lightgrey")
    #     fig.update_layout(margin = dict(t=50, l=25, r=25, b=25))
    #     fig.show()



    # here we also need to incresae the spec list of list of dic according to the lenght of unique_group_labels this can be done following https://stackoverflow.com/a/3459131 
    # in fact we do this with itertools
    if drop_blanks == True:
        samples_metadata_full = samples_metadata_full[~samples_metadata_full[sampletype_header].str.contains("none|BK|blanck|bk|mock")]

    import itertools
    unique_group_labels = samples_metadata_full[organism_header].unique()

    pattern=[{"type": "domain"}]


    rep_pattern = list(itertools.chain.from_iterable(itertools.repeat(x, len(unique_group_labels)) for x in pattern))


    fig = make_subplots(1, len(unique_group_labels),
    subplot_titles = (unique_group_labels),
    specs=[rep_pattern])

    i=1
    for n in unique_group_labels:
        print(n)

        dt = dt_isdb_results_int[dt_isdb_results_int[n] > 0]
        fig.add_trace(px.treemap(dt, path=[px.Constant("all"), 'structure_taxonomy_npclassifier_01pathway', 'structure_taxonomy_npclassifier_02superclass', 'structure_taxonomy_npclassifier_03class'], 
        values='counter').data[0], 
        row=1,col=i)
        i+=1

    fig.update_traces(root_color="lightgrey")
    fig.update_layout(margin = dict(t=50, l=25, r=25, b=25),
    title_text="Metabolite annotation overview (size proportional to individual count)")
    fig.update_annotations(font_size=12)
    fig.show()
    fig.write_html(treemap_chemo_counted_results_path,
                full_html=False,
                include_plotlyjs='cdn')

    fig = make_subplots(1, len(unique_group_labels),
    subplot_titles = (unique_group_labels),
    specs=[rep_pattern])

    i=1
    for n in unique_group_labels:
        print(n)

        dt = dt_isdb_results_int[dt_isdb_results_int[n] > 0]
        fig.add_trace(px.treemap(dt, path=[px.Constant("all"), 'structure_taxonomy_npclassifier_01pathway', 'structure_taxonomy_npclassifier_02superclass', 'structure_taxonomy_npclassifier_03class'], 
        values=n).data[0], 
        row=1,col=i)
        i+=1

    fig.update_traces(root_color="lightgrey")
    fig.update_layout(margin = dict(t=50, l=25, r=25, b=25),
    title_text="Metabolite annotation overview (size proportional to mean intensity)")
    fig.update_annotations(font_size=12)
    fig.show()
    fig.write_html(treemap_chemo_intensity_results_path,
                full_html=False,
                include_plotlyjs='cdn')

#### working on the multilabelled subset

    if multi_plot == True:
        
        samples_metadata_full['combined'] = samples_metadata_full[organism_header] + '_' + samples_metadata_full[sampletype_header]
        unique_group_labels = samples_metadata_full['combined'].unique()
        type(unique_group_labels)

        pattern=[{"type": "domain"}]


        rep_pattern = list(itertools.chain.from_iterable(itertools.repeat(x, len(unique_group_labels)) for x in pattern))

        fig = make_subplots(1, len(unique_group_labels),
        subplot_titles = (unique_group_labels),
        specs=[rep_pattern])

        i=1
        for n in unique_group_labels:
            print(n)

            dt = dt_isdb_results_int[dt_isdb_results_int[n] > 0]
            fig.add_trace(px.treemap(dt, path=[px.Constant("all"), 'structure_taxonomy_npclassifier_01pathway', 'structure_taxonomy_npclassifier_02superclass', 'structure_taxonomy_npclassifier_03class'], 
            values='counter').data[0], 
            row=1,col=i)
            i+=1

        fig.update_traces(root_color="lightgrey")
        fig.update_layout(margin = dict(t=50, l=25, r=25, b=25),
        title_text="Metabolite annotation overview (size proportional to individual count)")
        fig.update_annotations(font_size=12)
        fig.show()
        fig.write_html(treemap_chemo_multi_counted_results_path,
                    full_html=False,
                    include_plotlyjs='cdn')



        fig = make_subplots(1, len(unique_group_labels),
        subplot_titles = (unique_group_labels),
        specs=[rep_pattern])

        i=1
        for n in unique_group_labels:
            print(n)

            dt = dt_isdb_results_int[dt_isdb_results_int[n] > 0]
            fig.add_trace(px.treemap(dt, path=[px.Constant("all"), 'structure_taxonomy_npclassifier_01pathway', 'structure_taxonomy_npclassifier_02superclass', 'structure_taxonomy_npclassifier_03class'], 
            values=n).data[0], 
            row=1,col=i)
            i+=1

        fig.update_traces(root_color="lightgrey")
        fig.update_layout(margin = dict(t=50, l=25, r=25, b=25),
        title_text="Metabolite annotation overview (size proportional to mean intensity)")
        fig.update_annotations(font_size=12)
        fig.show()
        fig.write_html(treemap_chemo_multi_intensity_results_path,
                    full_html=False,
                    include_plotlyjs='cdn')


df4cyto_flat['final_score'] = df4cyto_flat['final_score'].astype('float')
df4cyto_flat[df4cyto_flat['final_score'] >= 8]

df4cyto_flat.columns


df4cyto_flat_sel = df4cyto_flat[['feature_id', 'component_id', 'structure_taxonomy_npclassifier_01pathway_consensus','structure_taxonomy_npclassifier_02superclass_consensus',
'structure_taxonomy_npclassifier_03class_consensus', 'score_input', 'libname',
'structure_inchikey', 'structure_inchi', 'structure_smiles', 'structure_molecular_formula',
'adduct', 'structure_exact_mass', 'short_inchikey',
'structure_taxonomy_npclassifier_01pathway', 'structure_taxonomy_npclassifier_02superclass',
'structure_taxonomy_npclassifier_03class', 'organism_name', 'organism_taxonomy_ottid',
'organism_taxonomy_01domain', 'organism_taxonomy_02kingdom', 'organism_taxonomy_03phylum',
'organism_taxonomy_04class', 'organism_taxonomy_05order', 'organism_taxonomy_06family',
'organism_taxonomy_07tribe', 'organism_taxonomy_08genus', 'organism_taxonomy_09species',
'score_taxo', 'score_max_consistency', 'final_score']]



df4cyto_flat_sel.to_csv(isdb_results_repond_flat_sel_path, sep='\t', index=None)


from pivottablejs import pivot_ui

pivot_ui(dt_isdb_results_int, outfile_path=pivot_table_results_path)

