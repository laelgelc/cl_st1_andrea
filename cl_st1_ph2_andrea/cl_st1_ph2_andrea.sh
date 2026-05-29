python tag.py
# Output: corpus/07_tagged/<Decade>/

python keylemmas.py \
    --input corpus/07_tagged \
    --output corpus/08_keylemmas \
    --cutoff 3
# Output: corpus/08_keylemmas/<Decade>.tsv