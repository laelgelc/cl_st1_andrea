# ============================================================
# Project pipeline for CL-ST1 Phase 3
#
# Run this script from the project phase directory, e.g.:
#
#   cl_st1_ph3_andrea/
#
# The pipeline prepares the corpus, selects keywords, builds the
# SAS input files, generates post-SAS factor outputs, creates
# visualisations and examples, and finally prepares/interprets
# factor-pole prompts.
# ============================================================


# ------------------------------------------------------------
# 1. Tag the source corpus
#
# Reads the phase corpus and produces token/tag/lemma files
# grouped by decade.
# ------------------------------------------------------------

python tag.py
# Output: corpus/07_tagged/<Decade>/


# ------------------------------------------------------------
# 2. Extract key lemmas by decade
#
# Uses the tagged corpus to identify decade-level key lemmas.
# The cutoff controls the minimum threshold for retaining lemmas.
# ------------------------------------------------------------

python keylemmas.py \
    --input corpus/07_tagged \
    --output corpus/08_keylemmas \
    --cutoff 3
# Output: corpus/08_keylemmas/<Decade>.tsv


# ------------------------------------------------------------
# 3. Select a stratified keyword set
#
# Selects up to 250 keywords per decade, with a maximum of 1200
# keywords before final de-duplication. The final keyword list is
# used to construct binary keyword columns for SAS.
# ------------------------------------------------------------

# Run 1 - Prompt template 'visual_commercial_description_v1.txt'

python select_kws_stratified.py \
    --per-decade 250 \
    --max-total 1200
# Output: corpus/09_kw_selected/keywords.txt

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

# Run 2 - Prompt template 'visual_commercial_description_v5.md'

python select_kws_stratified.py \
    --per-decade 260 \
    --max-total 1200
# Output: corpus/09_kw_selected/keywords.txt

"
=== Decade Keyword Quotas ===
1950   → 260 keywords max
1960   → 260 keywords max
1970   → 260 keywords max
1980   → 260 keywords max
1990   → 260 keywords max
2000   → 260 keywords max
2010   → 260 keywords max
2020   → 260 keywords max
=============================

1950   → selected 245/260 from 245 available POSKW lemmas
1960   → selected 129/260 from 129 available POSKW lemmas
1970   → selected 41/260 from 41 available POSKW lemmas
1980   → selected 61/260 from 61 available POSKW lemmas
1990   → selected 107/260 from 107 available POSKW lemmas
2000   → selected 120/260 from 120 available POSKW lemmas
2010   → selected 136/260 from 136 available POSKW lemmas
2020   → selected 190/260 from 190 available POSKW lemmas

Total consolidated keywords before de-duplication: 1029
Unique keywords after de-duplication: 915
Duplicates removed: 114

Final unique keywords written to: corpus/09_kw_selected/keywords.txt
Final unique keyword count: 915
"

# Run 3 - Prompt template 'visual_commercial_description_v5.md'
# and considering lowercase alphabetic characters,
# optionally joined by internal hyphens

python select_kws_stratified.py \
    --per-decade 260 \
    --max-total 1200
# Output: corpus/09_kw_selected/keywords.txt

"
=== Decade Keyword Quotas ===
1950   → 260 keywords max
1960   → 260 keywords max
1970   → 260 keywords max
1980   → 260 keywords max
1990   → 260 keywords max
2000   → 260 keywords max
2010   → 260 keywords max
2020   → 260 keywords max
=============================

1950   → selected 260/260 from 260 available POSKW lemmas
1960   → selected 133/260 from 133 available POSKW lemmas
1970   → selected 44/260 from 44 available POSKW lemmas
1980   → selected 66/260 from 66 available POSKW lemmas
1990   → selected 116/260 from 116 available POSKW lemmas
2000   → selected 124/260 from 124 available POSKW lemmas
2010   → selected 148/260 from 148 available POSKW lemmas
2020   → selected 203/260 from 203 available POSKW lemmas

Total consolidated keywords before de-duplication: 1094
Unique keywords after de-duplication: 973
Duplicates removed: 121

Final unique keywords written to: corpus/09_kw_selected/keywords.txt
Final unique keyword count: 973
"

# ------------------------------------------------------------
# 4. Build binary keyword columns
#
# Remove previous generated column folders before rebuilding them.
# This keeps the keyword matrix consistent with the latest selected
# keyword list.
# ------------------------------------------------------------

rm -rf columns columns_clean

python columns.py
# Outputs:
#   columns/
#   columns_clean/
#   file_ids.txt
#   index_keywords.txt


# ------------------------------------------------------------
# 5. Merge columns into the SAS counts matrix
#
# Combines the per-text keyword columns into the space-separated
# counts file expected by the SAS LMDA workflow.
# ------------------------------------------------------------

python merge_columns.py
# Output: sas/counts.txt


# ------------------------------------------------------------
# 6. Generate SAS format files
#
# Creates SAS label/format files that map keyword variable IDs
# such as v000001 to readable word labels.
# ------------------------------------------------------------

python sas_formats.py
# Outputs:
#   sas/word_labels_format.sas
#   sas/word_labels_full_format.sas
#   other SAS helper format files


# ------------------------------------------------------------
# Run SAS
# ------------------------------------------------------------


# ------------------------------------------------------------
# 8. Build factor loading lists
#
# Reads SAS factor outputs and produces readable positive/negative
# loading lists for each factor.
# ------------------------------------------------------------

python factor_lists.py
# Output: factors/


# ------------------------------------------------------------
# 9. Calculate corpus size summaries
#
# Produces corpus-size metadata for reporting and checking balance
# across decades.
# ------------------------------------------------------------

python corpus_size.py
# Output: corpus_size/corpus_size.tsv


# ------------------------------------------------------------
# 10. Generate LaTeX/TikZ boxplots
#
# Creates one boxplot per factor dimension and a combined mosaic
# for use in slides or reports.
# ------------------------------------------------------------

cd latex_boxplots

python latex_boxplots.py
# Output: latex_boxplots/slides/

cd ..


# ------------------------------------------------------------
# 11. Generate LaTeX ANOVA table
#
# Summarises decade effects for each factor using F, p, R², and
# percent R².
# ------------------------------------------------------------

python latex_anova_table.py
# Output: latex_tables/anova_decade.tex


# ------------------------------------------------------------
# 12. Generate LaTeX example extracts
#
# Selects representative high-scoring texts by factor pole and
# decade, then writes LaTeX examples with factor-loading lemmas
# highlighted.
# ------------------------------------------------------------

python examples.py
# Output: examples/


# ------------------------------------------------------------
# 13. Generate score-details report
#
# Sanity-check report showing, for each text and factor, which
# positive- and negative-pole loading words are present.
# ------------------------------------------------------------

python score_details.py
# Output: examples/score_details.txt


# ------------------------------------------------------------
# 14. Generate plaintext example extracts
#
# Produces plain `.txt` versions of the selected examples, including
# score metadata and loading words. These are useful for manual review
# and for building interpretation prompts.
# ------------------------------------------------------------

python examples_txt.py
# Output: examples_txt/


# ------------------------------------------------------------
# 15. Build interpretation prompts
#
# Combines factor loadings, mean decade scores, plaintext examples,
# and score-details information into one prompt per factor pole.
# ------------------------------------------------------------

python interpretation_prompts.py
# Output: interpretation/input/


# ------------------------------------------------------------
# 16. Submit interpretation prompts to GPT
#
# Sends each prompt file to the configured GPT model and writes one
# response file per factor pole. Requires OPENAI_API_KEY in the
# environment or in env/.env.
# ------------------------------------------------------------

python generate_interpretation_gpt.py \
    --input interpretation/input \
    --output interpretation/output \
    --model gpt-5.5 \
    --workers 4
# Output: interpretation/output/