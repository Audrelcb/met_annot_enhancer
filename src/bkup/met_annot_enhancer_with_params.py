# %% Load packages

import pandas as pd
import numpy as np
import zipfile
import glob
import os
import sys
import time
import shlex
import subprocess
from tqdm import tqdm
from tqdm import tqdm_notebook
from opentree import OT
import json
from pandas import json_normalize
import yaml
import spectral_lib_matcher


# %% defininbg display options

pd.set_option('display.max_rows', 50)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 100)

# We deactivate the iloc warning see https://stackoverflow.com/a/20627316
pd.options.mode.chained_assignment = None  # default='warn'

print(os.getcwd())

# Loading the parameters from yaml file

with open (r'./configs/default.yaml') as file:    
    # The FullLoader parameter handles the conversion from YAML
    # scalar values to Python the dictionary format
    params_list = yaml.load(file, Loader=yaml.FullLoader)


job_id = params_list['job'][0]['job_id']

gnps_job_path = params_list['paths'][0]['gnps_job_path']
project_name = params_list['paths'][1]['project_name']
metadata_path = params_list['paths'][2]['metadata_path']
db_file_path = params_list['paths'][3]['db_file_path']
adducts_pos_path = params_list['paths'][4]['adducts_pos_path']
adducts_neg_path = params_list['paths'][5]['adducts_neg_path']

parent_mz_tol = params_list['spectral_match_params'][0]['parent_mz_tol']
msms_mz_tol = params_list['spectral_match_params'][1]['msms_mz_tol']
min_cos = params_list['spectral_match_params'][2]['min_cos']
min_peaks = params_list['spectral_match_params'][3]['min_peaks']


Run_line_x_line = params_list['repond_params'][0]['Run_line_x_line']
Top_N_Sample = params_list['repond_params'][1]['Top_N_Sample']
top_to_output= params_list['repond_params'][2]['top_to_output']
ppm_tol = params_list['repond_params'][3]['ppm_tol']
polarity = params_list['repond_params'][4]['polarity']
organism_header = params_list['repond_params'][5]['organism_header']
sampletype_header = params_list['repond_params'][6]['sampletype_header']
use_post_taxo = params_list['repond_params'][7]['use_post_taxo']
top_N_chemical_consistency = params_list['repond_params'][8]['top_N_chemical_consistency']
file_extension = params_list['repond_params'][9]['file_extension']
msfile_suffix = params_list['repond_params'][10]['msfile_suffix']




base_filename = 'GNPS_output_' + project_name
filename_suffix = 'zip'

# Adding expanduser option to expand home path if encoded in the params file

path_to_folder = os.path.expanduser(os.path.join(gnps_job_path, base_filename))
path_to_file = os.path.expanduser(os.path.join(gnps_job_path, base_filename + "." + filename_suffix))




query_file_path = os.path.join(path_to_folder,'spectra/specs_ms.mgf')

spectral_match_results_filename = project_name + '_spectral_match_results.tsv'
isdb_results_path = os.path.join(path_to_folder,spectral_match_results_filename)

spectral_match_results_repond_filename = project_name + '_spectral_match_results_repond.tsv'
isdb_results_repond_path = os.path.join(path_to_folder,spectral_match_results_repond_filename)


spectral_match_results_repond_flat_filename = project_name + '_spectral_match_results_repond_flat.tsv'
isdb_results_repond_flat_path = os.path.join(path_to_folder,spectral_match_results_repond_flat_filename)



### to fill if not starting from GNPS Job

isdb_results_path = os.path.join(path_to_folder,spectral_match_results_filename)



sunburst_chem_filename = project_name + '_chemo_sunburst.html'
sunburst_organisms_filename = project_name + '_organisms_sunburst.html'
sunburst_chem_results_path = os.path.join(path_to_folder,sunburst_chem_filename)
sunburst_organisms_results_path = os.path.join(path_to_folder,sunburst_organisms_filename)




# timer is started
start_time = time.time()


# %% Import MS1 list

if polarity == 'Pos':
    adducts_df = pd.read_csv(
        adducts_pos_path, compression='gzip', sep='\t')
else:
    adducts_df = pd.read_csv(
        adducts_neg_path, compression='gzip', sep='\t')

adducts_df['min'] = adducts_df['adduct_mass'] - \
    int(ppm_tol) * (adducts_df['adduct_mass'] / 1000000)
adducts_df['max'] = adducts_df['adduct_mass'] + \
    int(ppm_tol) * (adducts_df['adduct_mass'] / 1000000)


# %% Downloading GNPS files
# Make this optionnal

# files = glob.glob(gnps_job_path)
# for f in files:
#    os.remove(f)

# print('''
# Fetching the GNPS job ...
# ''')


# job_url_zip = "https://gnps.ucsd.edu/ProteoSAFe/DownloadResult?task="+job_id+"&view=download_cytoscape_data"

# cmd = 'curl -d "" '+job_url_zip+' -o '+path_to_file
# subprocess.call(shlex.split(cmd))


# with zipfile.ZipFile(path_to_file, 'r') as zip_ref:
#     zip_ref.extractall(path_to_folder)

# # We finally remove the zip file
# cmd = 'rm '+ path_to_file
# subprocess.call(shlex.split(cmd))


# Once this folder is created we directly save the yaml params inside

params_suffix = '.yaml'

with open(os.path.join(path_to_folder, job_id + params_suffix), 'w') as file:  
    documents = yaml.dump(params_list, file)


# %% Spectral matching stage

# Yes we can !
# Make this optionnal


print('''
Proceeding to spectral matching ...
''')



# spectral_lib_matcher.main(query_file_path,
#                           db_file_path,
#                           parent_mz_tol,
#                           msms_mz_tol,
#                           min_cos,
#                           min_peaks,
#                           isdb_results_path
#                           )



# %% Loading the files

dt_isdb_results = pd.read_csv(isdb_results_path,
                              sep='\t',
                              usecols=['msms_score', 'feature_id', 'reference_id', 'inchikey'],
                              error_bad_lines=False, low_memory=True)


## we add a fixed libname (to be changed later on) 

dt_isdb_results['libname'] = 'ISDB'

dt_isdb_results.rename(columns={'componentindex': 'component_id',
                                'parent mass': 'mz', 'msms_score': 'score_input'}, inplace=True)


## In fact we can directly start here
## we get the networks info (cluster id, component index and parent mass form the downloaded folder)

clusterinfo_summary_path = os.path.join(path_to_folder,'clusterinfo_summary','')

clusterinfo_summary = pd.read_csv(clusterinfo_summary_path + str(os.listdir(clusterinfo_summary_path)[0]),
                                  sep='\t',
                                  usecols=['cluster index', 'componentindex', 'parent mass'],
                                  error_bad_lines=False, low_memory=True)

clusterinfo_summary.rename(columns={'cluster index': 'feature_id', 'componentindex': 'component_id',
                                'parent mass': 'mz', 'msms_score': 'score_input'}, inplace=True)


# ## we now merge this back with the isdb matched results 
dt_isdb_results = pd.merge(dt_isdb_results, clusterinfo_summary, on='feature_id')

# ## we drop the duplicated ['cluster index'] column
#dt_isdb_results.drop(columns=['cluster index'], inplace=True)

# ## we return a short_inchikey column

# dt_isdb_results['short_inchikey'] = dt_isdb_results['inchikey'].str.split("-", n=1, expand=True)[0]



dt_metadata = pd.read_csv(metadata_path,
                        sep=',', error_bad_lines=False, low_memory=True)

dt_metadata['short_inchikey'] = dt_metadata.structure_inchikey.str.split(
    "-", expand=True)[0]
dt_metadata.reset_index(inplace=True)


cluster_count = dt_isdb_results.drop_duplicates(
    subset=['feature_id', 'component_id']).groupby("component_id").count()
cluster_count = cluster_count[['feature_id']].rename(
    columns={'feature_id': 'ci_count'}).reset_index()

print('Number of features: ' + str(len(dt_isdb_results)))
print('Number of annotated features: ' +
    str(dt_isdb_results['inchikey'].count()))

# %%
# Now we directly do the MS1 matching stage on the cluster_summary. No need to have MS2 annotations

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

print('MS1 annotation done')


# %%
df_meta_2 = dt_metadata[['structure_inchikey', 'structure_exact_mass']]
df_meta_2.rename(columns={'structure_inchikey': 'inchikey'}, inplace=True)

df_meta_2 = df_meta_2.dropna(subset=['structure_exact_mass'])
df_meta_2 = df_meta_2.drop_duplicates(
    subset=['inchikey', 'structure_exact_mass'])

df_meta_2 = df_meta_2.round({'structure_exact_mass': 5})
df_MS1 = df_MS1.round({'exact_mass': 5})

df_MS1_merge = pd.merge(df_MS1, df_meta_2, left_on='exact_mass',
                        right_on='structure_exact_mass', how='left')
df_MS1_merge = df_MS1_merge.dropna(subset=['inchikey'])

df_MS1_merge['match_mzerror_MS1'] = df_MS1_merge['mz'] - \
    df_MS1_merge['adduct_mass']
df_MS1_merge = df_MS1_merge.round({'match_mzerror_MS1': 5}).astype({
    'match_mzerror_MS1': 'str'})

df_MS1_merge = df_MS1_merge.drop(
    ['structure_exact_mass', 'adduct_mass', 'exact_mass'], axis=1)
df_MS1_merge['score_input'] = 0

#df_MS1_merge = df_MS1_merge.astype({'score_input': 'str'})

# the line below trhrow an error on my side 
# TypeError: groupby() got an unexpected keyword argument 'dropna'
# It should normally be fixed in pandas 1.2.0 As Arnaud which version he is using (probably an older one)
# see https://github.com/pandas-dev/pandas/issues/37323 for a quick and dirty fix
# Actually I even think no dropna is needed
df_MS1_merge_gb = df_MS1_merge.groupby(['feature_id'], dropna=False).agg('|'.join)

df_MS1_merge_gb = df_MS1_merge.groupby(['feature_id']).agg('|'.join)
df_MS1_merge_gb.reset_index(inplace=True)

# %%

dt_isdb_results = pd.concat([dt_isdb_results, df_MS1_merge])

print('Number of annotated features after MS1: ' +
      str(len(df_MS1_merge['feature_id'].unique())))


len(clusterinfo_summary['feature_id'].unique())


# %%

print('Total number of MS1 and MSMS annotations: ' + str(len(dt_isdb_results)))

# %%
# Rank annotations based on the spectral score

dt_isdb_results["score_input"] = pd.to_numeric(
    dt_isdb_results["score_input"], downcast="float")
dt_isdb_results['rank_spec'] = dt_isdb_results[['feature_id', 'score_input']].groupby(
    'feature_id')['score_input'].rank(method='dense', ascending=False)


# %%
# Joining the Occurences DB metadata

# we start by outputing the SIK for the ISDB output

dt_isdb_results['short_inchikey'] = dt_isdb_results.inchikey.str.split(
    "-", expand=True)[0]
dt_isdb_results.reset_index(inplace=True)

# now we merge with the Occurences DB metadata after selection of our columns of interest

cols_to_use = ['structure_inchikey', 'structure_inchi',
            'structure_smiles', 'structure_molecular_formula',
            'structure_exact_mass', 'short_inchikey', 'structure_taxonomy_npclassifier_01pathway', 
            'structure_taxonomy_npclassifier_02superclass', 'structure_taxonomy_npclassifier_03class',
            'organism_name', 'organism_taxonomy_ottid',
            'organism_taxonomy_01domain', 'organism_taxonomy_02kingdom', 'organism_taxonomy_03phylum',
            'organism_taxonomy_04class', 'organism_taxonomy_05order', 'organism_taxonomy_06family', 'organism_taxonomy_07tribe', 'organism_taxonomy_08genus', 'organism_taxonomy_09species', 'organism_taxonomy_10varietas' ]

dt_isdb_results.dropna(subset=['short_inchikey'], inplace=True)
dt_isdb_results = pd.merge(
    left=dt_isdb_results, right=dt_metadata[cols_to_use], left_on='short_inchikey', right_on='short_inchikey', how='outer')
dt_isdb_results.dropna(subset=['feature_id'], inplace=True)


# dt_isdb_results = dt_isdb_results.astype({'feature_id' : 'int64'})


print('Total number of annotations with unique Biosource/line: ' +
      str(len(dt_isdb_results)))

# %% Resolving the taxon information from the GNPS metadata file

# the metadata table path is generated from the base bath to the GNPS results folder
metadata_table_path = os.path.join(path_to_folder,'metadata_table','')

# the metadata table is loaded using the organism column specified before

samples_metadata = pd.read_csv(metadata_table_path + str(os.listdir(metadata_table_path)[0]), sep='\t',
                                   usecols=['filename', organism_header])

# Now we want to get the taxonomic information for each of the samples
# so we want to extract the species information from the metadata file
# %%
samples_metadata[organism_header].dropna(inplace = True)
samples_metadata[organism_header] = samples_metadata[organism_header].str.lower()
species = samples_metadata[organism_header].unique()
len_species = len(species)

print("%s unique species have been selected from the metadata table." % len_species )
# %%

species_tnrs_matched = OT.tnrs_match(species, context_name=None, do_approximate_matching=True, include_suppressed=False)



# %%

with open(str(path_to_folder +'/species.json'), 'w') as out:
    sf = json.dumps(species_tnrs_matched.response_dict, indent=2, sort_keys=True)
    out.write('{}\n'.format(sf))

# %%
with open(str(path_to_folder +'/species.json')) as tmpfile:
        jsondic = json.loads(tmpfile.read())

json_normalize(jsondic)
# %%

df_species_tnrs_matched = json_normalize(jsondic,
               record_path=['results', 'matches']
               )



df_species_tnrs_unmatched = json_normalize(jsondic,
               record_path=['unmatched_names']
               )
# %%

df_species_tnrs_matched.info()


# %%
len(df_species_tnrs_matched['taxon.ott_id'].unique())
# %%


# We then want to match with the accepted name instead of the synonym in case both are present. 
# We thus order by matched_name and then by is_synonym status prior to returning the first row.

df_species_tnrs_matched.sort_values(['search_string', 'is_synonym'], axis = 0, inplace = True)
df_species_tnrs_matched_unique = df_species_tnrs_matched.drop_duplicates('search_string', keep = 'first')

# both df are finally merged
merged_df = pd.merge(samples_metadata, df_species_tnrs_matched_unique, how='left', left_on=organism_header, right_on='search_string', indicator=True)


# %%
#Now we want to retrieve the upper taxa lineage for all the samples

# Firsst we retrieve a list of unique ott_ids

# Here when checking the columns datatype we observe that the ott_ids are as float.
# We need to keep them as int
# displaying the datatypes 
#display(merged_df.dtypes) 

# converting 'ott_ids' from float to int (check the astype('Int64') whic will work while the astype('int') won't see https://stackoverflow.com/a/54194908)
merged_df['taxon.ott_id'] = merged_df['taxon.ott_id'].astype('Int64')
  

# However, we then need to put them back to 
merged_df['taxon.ott_id']
ott_list = list(merged_df['taxon.ott_id'].dropna().astype('int'))

#ott_list = ott_list[0:10]

# %%

taxon_info = []

for i in ott_list:
    query = OT.taxon_info(i, include_lineage=True)
    taxon_info.append(query)

# %%


tl = []

for i in taxon_info:
    with open(str(path_to_folder +'/taxon_info.json'), 'w') as out:
        tl.append(i.response_dict)
        yo = json.dumps(tl)
        out.write('{}\n'.format(yo))

# %%

with open(str(path_to_folder +'/taxon_info.json')) as tmpfile:
        jsondic = json.loads(tmpfile.read())

df = json_normalize(jsondic)


# %%

df_tax_lineage = json_normalize(jsondic,
               record_path=['lineage'],
               meta = ['ott_id', 'unique_name'],
               record_prefix='sub_',
               errors='ignore'
               )
# %%
# This keeps the last occurence of each ott_id / sub_rank grouping https://stackoverflow.com/a/41886945

df_tax_lineage_filtered = df_tax_lineage.groupby(['ott_id', 'sub_rank'], as_index=False).last()
# %%
#Here we pivot long to wide to get the taxonomy

df_tax_lineage_filtered_flat = df_tax_lineage_filtered.pivot(index='ott_id', columns='sub_rank', values='sub_name')

# %%
# Here we actually also want the lowertaxon (species usually) name

df_tax_lineage_filtered_flat = pd.merge(df_tax_lineage_filtered_flat, df_tax_lineage_filtered[['ott_id', 'unique_name']], how='left', on='ott_id', )

#Despite the left join ott_id are duplicated 

df_tax_lineage_filtered_flat.drop_duplicates(subset = ['ott_id', 'unique_name'], inplace = True)

# %%
# we keep the fields of interest

# here we want to have these columns whatevere happens
col_list = ['ott_id', 'domain', 'kingdom', 'phylum',
                            'class', 'order', 'family', 'tribe', 'genus', 'unique_name']

df_tax_lineage_filtered_flat = df_tax_lineage_filtered_flat.reindex(columns=col_list, fill_value = np.NaN)

# df_tax_lineage_filtered_flat[['ott_id', 'domain', 'kingdom', 'phylum',
#                             'class', 'order', 'family', 'tribe', 'genus', 'unique_name']]


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


# %% Extracting biosource / feature for line by line

print('''
Fetching the biosource contribution per feature ...
''')

quantification_table_reformatted_path = os.path.join(path_to_folder,'quantification_table_reformatted','')

metadata_table_path = os.path.join(path_to_folder,'metadata_table','')


if Run_line_x_line == True:

    feature_intensity = pd.read_csv(quantification_table_reformatted_path + str(
        os.listdir(quantification_table_reformatted_path)[0]), sep=',')
    feature_intensity.rename(columns={'row ID': 'row_ID'}, inplace=True)
    feature_intensity.set_index('row_ID', inplace=True)
    feature_intensity = feature_intensity.filter(
        regex=file_extension + '|row_ID')
    feature_intensity = feature_intensity.where(feature_intensity.apply(
        lambda x: x.isin(x.nlargest(Top_N_Sample)), axis=1), 0)  # top N here
    feature_intensity.columns = feature_intensity.columns.str.replace(msfile_suffix, '')
    feature_intensity = feature_intensity.transpose()
    feature_intensity.index.name = 'MS_filename'
    feature_intensity = feature_intensity.transpose()
    # Samples_metadata = pd.read_csv(metadata_table_path + str(os.listdir(metadata_table_path)[0]), sep='\t',
    #                                # usecols=['filename','ATTRIBUTE_phylum_cof', 'ATTRIBUTE_kingdom_cof',  'ATTRIBUTE_class_cof', 'ATTRIBUTE_order_cof', 'ATTRIBUTE_family_cof', 'ATTRIBUTE_genus_cof', 'ATTRIBUTE_species_cof'])
    #                                #    usecols=['filename', 'ATTRIBUTE_Phylum', 'ATTRIBUTE_Kingdom',  'ATTRIBUTE_Class', 'ATTRIBUTE_Order', 'ATTRIBUTE_Family', 'ATTRIBUTE_Genus', 'ATTRIBUTE_Species'])
    #                                usecols=['filename',
    #                                         'query_otol_kingdom',
    #                                         'query_otol_phylum',
    #                                         'query_otol_class',
    #                                         'query_otol_order',
    #                                         'query_otol_family',
    #                                         'query_otol_genus',
    #                                         'query_otol_species'])
    res = feature_intensity[feature_intensity != 0].stack()
    df_res = res.to_frame().reset_index()
    df_merged = pd.merge(df_res, samples_metadata, left_on='MS_filename',
                         right_on='filename', how='left').drop([0, 'MS_filename', 'filename'], axis=1)
    df_merged = df_merged.groupby('row_ID').agg(lambda x: list(x))
    df_merged.reset_index(inplace=True)


# %%

# Here we will add three columns (even for the simple repond this way it will be close to the multiple species repond)
# these line will need to be defined as function arguments

if Run_line_x_line == True:
    dt_isdb_results = pd.merge(
        dt_isdb_results, df_merged, left_on='feature_id', right_on='row_ID', how='left')
else:
       dt_isdb_results['query_otol_species'] = species_bio
       dt_isdb_results['query_otol_genus'] = genus_bio
       dt_isdb_results['query_otol_family'] = family_bio
       dt_isdb_results['query_otol_order'] = order_bio
       dt_isdb_results['query_otol_class'] = class_bio
       dt_isdb_results['query_otol_phylum'] = phylum_bio
       dt_isdb_results['query_otol_kingdom'] = kingdom_bio
       
#%% Taxonomical Reweighting

print('''
Proceeding to taxonomically informed reponderation ...
''')

cols_ref = ['organism_taxonomy_01domain', 'organism_taxonomy_02kingdom',  'organism_taxonomy_03phylum', 'organism_taxonomy_04class',
            'organism_taxonomy_05order', 'organism_taxonomy_06family', 'organism_taxonomy_07tribe', 'organism_taxonomy_08genus', 'organism_taxonomy_09species']
cols_att = ['query_otol_domain',
            'query_otol_kingdom',
            'query_otol_phylum',
            'query_otol_class',
            'query_otol_order',
            'query_otol_family',
            'query_otol_tribe',
            'query_otol_genus',
            'query_otol_species']
cols_match = ['matched_domain', 'matched_kingdom', 'matched_phylum', 'matched_class',
              'matched_order', 'matched_family', 'matched_tribe', 'matched_genus', 'matched_species']

col_prev = None
if Run_line_x_line == True:
       for col_ref, col_att, col_match in zip(cols_ref, cols_att, cols_match):
              dt_isdb_results[col_ref].fillna('Unknown', inplace=True)
              dt_isdb_results[col_ref] = dt_isdb_results[col_ref].apply(lambda x: [x])
              dt_isdb_results[col_match] = [list(set(a).intersection(set(b))) for a, b in zip(dt_isdb_results[col_ref], dt_isdb_results[col_att])] # Allows to compare 2 lists
              dt_isdb_results[col_match] = dt_isdb_results[col_match].apply(lambda y: np.nan if len(y)==0 else y)
              if col_prev != None:
                     dt_isdb_results[col_match].where(dt_isdb_results[col_prev].notnull(), np.nan)
              col_prev = col_match

else:
       for col_ref, col_att, col_match in zip(cols_ref, cols_att, cols_match):
              dt_isdb_results[col_ref].fillna('Unknown', inplace=True)
              dt_isdb_results[col_match] = np.where((dt_isdb_results[col_ref] == dt_isdb_results[col_att]), dt_isdb_results[col_att], np.nan)
              if col_prev != None:
                     dt_isdb_results[col_match].where(dt_isdb_results[col_prev].notnull(), np.nan)
              col_prev = col_match


dt_isdb_results['score_taxo'] = dt_isdb_results[cols_match].count(axis=1)


# %%
# Filter out MS1 annotations without a reweighting at the family level at least

if polarity == 'Pos':
    dt_isdb_results = dt_isdb_results[(dt_isdb_results['score_taxo'] >= 6) | (
        dt_isdb_results['libname'] == 'ISDB')]
else:
    dt_isdb_results = dt_isdb_results[(dt_isdb_results['score_taxo'] >= 4) | (
        dt_isdb_results['libname'] == 'ISDB')]


print('Total number of annotations after filtering MS1 annotations not reweighted at order level: ' +
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



# %%

# we set the spectral score column as float
dt_isdb_results["score_input"] = pd.to_numeric(
    dt_isdb_results["score_input"], downcast="float")
# and we add it to the max txo score :
dt_isdb_results['score_input_taxo'] = dt_isdb_results['score_taxo'] + \
    dt_isdb_results['score_input']

# %%

dt_isdb_results['rank_spec_taxo'] = dt_isdb_results.groupby(
    'feature_id')['score_input_taxo'].rank(method='dense', ascending=False)

dt_isdb_results = dt_isdb_results.groupby(["feature_id"]).apply(
    lambda x: x.sort_values(["rank_spec_taxo"], ascending=True)).reset_index(drop=True)

# %%
# Get cluster Chemical class
for col in ['structure_taxonomy_npclassifier_01pathway', 'structure_taxonomy_npclassifier_02superclass', 'structure_taxonomy_npclassifier_03class']:

    df = dt_isdb_results.copy()
    df = df.drop_duplicates(subset=['feature_id', col])
    if use_post_taxo == True:
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
    else:
        df = df[df.component_id != -1]
        df = df[df.rank_spec <= top_N_chemical_consistency]
        df = df.groupby(
            ["component_id", col]
        ).agg({'feature_id': 'count',
            'rank_spec': 'mean'}
            ).reset_index(
        ).rename(columns={'feature_id': (col + '_count'),
                        'rank_spec': ('rank_' + col + '_mean')}
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

# %% 
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

dt_isdb_results['Final_score'] = dt_isdb_results['score_input'] + \
    dt_isdb_results['score_taxo'] + dt_isdb_results['score_max_consistency']

dt_isdb_results['rank_final'] = dt_isdb_results.groupby(
    'feature_id')['Final_score'].rank(method='dense', ascending=False)




# %%

print('Number of annotations reweighted at the NPClassifier pathway level: ' +
    str(len(dt_isdb_results[(dt_isdb_results['structure_taxonomy_npclassifier_01pathway_score'] == 1)])))
print('Number of annotations reweighted at the NPClassifier superclass level: ' +
    str(len(dt_isdb_results[(dt_isdb_results['structure_taxonomy_npclassifier_02superclass_score'] == 2)])))
print('Number of annotations reweighted at the NPClassifier class level: ' +
    str(len(dt_isdb_results[(dt_isdb_results['structure_taxonomy_npclassifier_03class_score'] == 3)])))


# %%


dt_isdb_results_chem_rew = dt_isdb_results.loc[(
    dt_isdb_results.rank_final <= int(top_to_output))]
dt_isdb_results_chem_rew[["feature_id", "rank_final", "component_id"]] = dt_isdb_results_chem_rew[[
    "feature_id", "rank_final", "component_id"]].apply(pd.to_numeric, downcast='signed', axis=1)
dt_isdb_results_chem_rew = dt_isdb_results_chem_rew.sort_values(
    ["feature_id", "rank_final"], ascending=(False, True))
dt_isdb_results_chem_rew = dt_isdb_results_chem_rew.astype(str)

# %%
# Here we would like to filter results when short IK are repeated for the same feature_id at the same final rank
# see issue (https://gitlab.com/tima5/taxoscorer/-/issues/23)
# used 
# dt_isdb_results_chem_rew = dt_isdb_results_chem_rew.drop_duplicates(subset=['feature_id', 'short_inchikey', 'rank_final'], keep='first')

dt_isdb_results_chem_rew = dt_isdb_results_chem_rew.drop_duplicates(subset=['feature_id', 'short_inchikey'], keep='first')

dt_isdb_results_chem_rew = dt_isdb_results_chem_rew.astype({'feature_id' : 'float'})
dt_isdb_results_chem_rew = dt_isdb_results_chem_rew.astype({'feature_id' : 'int64'})


# %%

annot_attr = ['rank_spec', 'score_input', 'inchikey', 'libname', 'structure_inchikey', 'structure_inchi',
            'structure_smiles', 'structure_molecular_formula', 'adduct',
            'structure_exact_mass', 'short_inchikey', 'structure_taxonomy_npclassifier_01pathway', 
            'structure_taxonomy_npclassifier_02superclass', 'structure_taxonomy_npclassifier_03class',
            'organism_name', 'organism_taxonomy_ottid',
            'organism_taxonomy_01domain', 'organism_taxonomy_02kingdom', 'organism_taxonomy_03phylum',
            'organism_taxonomy_04class', 'organism_taxonomy_05order', 'organism_taxonomy_06family', 'organism_taxonomy_07tribe', 'organism_taxonomy_08genus', 'organism_taxonomy_09species', 'organism_taxonomy_10varietas',  
            'matched_domain', 'matched_kingdom', 'matched_phylum', 'matched_class', 'matched_order',
            'matched_family', 'matched_tribe', 'matched_genus', 'matched_species', 'score_taxo', 'score_max_consistency', 'Final_score', 'rank_final']

comp_attr = ['component_id', 'structure_taxonomy_npclassifier_01pathway_consensus', 'freq_structure_taxonomy_npclassifier_01pathway', 'structure_taxonomy_npclassifier_02superclass_consensus',
            'freq_structure_taxonomy_npclassifier_02superclass', 'structure_taxonomy_npclassifier_03class_consensus', 'freq_structure_taxonomy_npclassifier_03class']

col_to_keep = ['feature_id'] + comp_attr + annot_attr

df4cyto_flat = dt_isdb_results_chem_rew[col_to_keep]

# %%

gb_spec = {c: '|'.join for c in annot_attr}
for c in comp_attr:
    gb_spec[c] = 'first'

# %%

df4cyto = df4cyto_flat.groupby('feature_id').agg(gb_spec)

# %%

df4cyto_flat.to_csv(isdb_results_repond_flat_path, sep='\t')

df4cyto.to_csv(isdb_results_repond_path, sep='\t')


# %%

print('Finished in %s seconds.' % (time.time() - start_time))
print('You can check your results here %s' % isdb_results_repond_path)


# %%

# dt_isdb_results = dt_isdb_results.astype(str)
# df4cyto = dt_isdb_results.groupby(['feature_id']).agg('|'.join)
# df4cyto.reset_index(drop=True, inplace=True)


# %%

# Testing cytoscape ready formatting



# df4cyto['rank_spec'] = df4cyto['rank_spec'].apply(lambda x: [x])


# %%
# using px express to plot some quick and dirty sunbursts (https://plotly.com/python/sunburst-charts/)
# customize fonts in titles following https://stackoverflow.com/a/57926862
# customize margins following https://stackoverflow.com/a/63162535

print('''
Generating plots ... check your web browser !
''')

import plotly.express as px


fig = px.sunburst(df4cyto_flat, path=['structure_taxonomy_npclassifier_01pathway_consensus', 'structure_taxonomy_npclassifier_02superclass_consensus', 'structure_taxonomy_npclassifier_03class_consensus'],
                  )
fig.update_layout(
    #font_family="Courier New",
    title_font_family="Courier New",
    title_font_color="black",
    title_font_size=14,
    legend_title_font_color="black",
    title_text="<b> Overview of the consensus chemical annotions <br> at the NP Classifier pathway, superclass and class level for <br>" + project_name + "</b>",
    title_x=0.5
)

fig.update_layout(
    title={
        'text': "<b> Overview of the consensus chemical annotions <br> at the NP Classifier pathway, superclass and class level for <br>" + '<span style="font-size: 20px;">' + project_name + '</span>' + "</b>",
        'y':0.96,
        'x':0.5,
        'xanchor': 'center',
        'yanchor': 'top'})

fig.update_layout(margin=dict(l=50, r=50, t=100, b=50)
#,paper_bgcolor="Black"
)

fig.show()

fig.write_html(sunburst_chem_results_path,
               full_html=False,
               include_plotlyjs='cdn')

# %%

fig = px.sunburst(df4cyto_flat, path=['organism_taxonomy_01domain', 'organism_taxonomy_02kingdom', 'organism_taxonomy_03phylum',
            'organism_taxonomy_04class', 'organism_taxonomy_05order', 'organism_taxonomy_06family', 'organism_taxonomy_07tribe', 'organism_taxonomy_08genus', 'organism_taxonomy_09species', 'organism_taxonomy_10varietas'],
                  )
fig.update_layout(
    #font_family="Courier New",
    title_font_family="Courier New",
    title_font_color="black",
    title_font_size=14,
    legend_title_font_color="black",
    title_text="<b> Overview of the source organisms of the chemical annotation <br> at the domain, kingdom, phylum, class, order, family, tribe, genus, species and varietas level for <br>" + project_name + "</b>",
    title_x=0.5
)

fig.update_layout(
    title={
        'text': "<b> Overview of the source organisms of the chemical annotation <br> at the domain, kingdom, phylum, class, order, family, tribe, genus, species and varietas level for <br>" + '<span style="font-size: 20px;">' + project_name + '</span>' + "</b>",
        'y':0.96,
        'x':0.5,
        'xanchor': 'center',
        'yanchor': 'top'})

fig.update_layout(margin=dict(l=50, r=50, t=100, b=50)
#,paper_bgcolor="Black"
)

fig.show()

fig.write_html(sunburst_organisms_results_path,
               full_html=False,
               include_plotlyjs='cdn')



