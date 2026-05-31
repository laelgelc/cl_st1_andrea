python tag.py
# Output: corpus/07_tagged/<Decade>/

python keylemmas.py \
    --input corpus/07_tagged \
    --output corpus/08_keylemmas \
    --cutoff 3
# Output: corpus/08_keylemmas/<Decade>.tsv

python select_kws_stratified.py \
    --per-decade 250 \
    --max-total 1200
# Output: corpus/09_kw_selected

"
=== Decade Keyword Quotas ===
1950   → 250 keywords max
1960   → 250 keywords max
1970   → 250 keywords max
1980   → 250 keywords max
1990   → 250 keywords max
2000   → 250 keywords max
2010   → 250 keywords max
2020   → 250 keywords max
=============================

1950   → selected 187/250 from 187 available POSKW lemmas
1960   → selected 49/250 from 49 available POSKW lemmas
1970   → selected 8/250 from 8 available POSKW lemmas
1980   → selected 6/250 from 6 available POSKW lemmas
1990   → selected 6/250 from 6 available POSKW lemmas
2000   → selected 7/250 from 7 available POSKW lemmas
2010   → selected 10/250 from 10 available POSKW lemmas
2020   → selected 16/250 from 16 available POSKW lemmas

Total consolidated keywords before de-duplication: 289
Unique keywords after de-duplication: 265
Duplicates removed: 24

Final unique keywords written to: corpus/09_kw_selected/keywords.txt
Final unique keyword count: 265
"

rm -rf columns columns_clean
python columns.py
# Output: columns, columns_clean, file_ids.txt, index_keywords.txt

python merge_columns.py
# Output: sas/counts.txt

python sas_formats.py
# Output: sas/word_labels_format.sas, etc

## RUN SAS
## Rogerio Yamada's account

python factor_lists.py \
  --sas-output-dir sas/output_cl_st1_ph2_andrea \
  --index-file index_keywords.txt \
  --output-dir factors \
  --cutoff 0.3
# Output: factors

python corpus_size.py
# Output: corpus_size/corpus_size.tsv

cd latex_boxplots
# Builds boxplots for factor analysis:
python latex_boxplots.py
# Output: latex_boxplots/slides
cd ..

python latex_anova_table.py

python latex_anova_tables.py \
  --project cl_st1_ph3_andrea \
  --input-dir sas/output_cl_st1_ph3_andrea \
  --output-dir latex_tables
# Output: latex_tables
