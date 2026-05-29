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