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

1950   → selected 71/250 from 71 available POSKW lemmas
1960   → selected 56/250 from 56 available POSKW lemmas
1970   → selected 34/250 from 34 available POSKW lemmas
1980   → selected 25/250 from 25 available POSKW lemmas
1990   → selected 72/250 from 72 available POSKW lemmas
2000   → selected 135/250 from 135 available POSKW lemmas
2010   → selected 196/250 from 196 available POSKW lemmas
2020   → selected 211/250 from 211 available POSKW lemmas

Total consolidated keywords before de-duplication: 800
Unique keywords after de-duplication: 688
Duplicates removed: 112

Final unique keywords written to: corpus/09_kw_selected/keywords.txt
Final unique keyword count: 688
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
