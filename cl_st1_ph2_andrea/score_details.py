#!/usr/bin/env python3
import re
import pandas as pd
from pathlib import Path

# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------
SAS_BASE = Path("sas/output_cl_st1_ph3_andressa")
SCORES_FILE = SAS_BASE / "cl_st1_ph3_andressa_scores.tsv"
WORD_LABELS_FILE = SAS_BASE / "word_labels_format.sas"
VARID_DIR = Path("factors/var_id")

FILE_IDS = Path("file_ids.txt")   # <-- updated for your current setup
OUTFILE = Path("examples/score_details.txt")

OUTFILE.parent.mkdir(exist_ok=True, parents=True)

# ------------------------------------------------------------
# Load SAS factor scores
# ------------------------------------------------------------
scores = pd.read_csv(SCORES_FILE, sep="\t")

# Detect number of factors dynamically (fac1, fac2, ...)
fac_cols = sorted(
    (c for c in scores.columns if re.fullmatch(r"fac\d+", str(c))),
    key=lambda x: int(x[3:])
)
num_factors = len(fac_cols)
if num_factors == 0:
    raise RuntimeError(f"No fac<n> columns found in {SCORES_FILE}")

# ------------------------------------------------------------
# Load SAS variable lexicon (varID → word)
# ------------------------------------------------------------
lex = {}
label_text = WORD_LABELS_FILE.read_text()

for vid, word in re.findall(r'"(v\d{6})"\s*=\s*"([^"]+)"', label_text):
    lex[vid] = word

# ------------------------------------------------------------
# Extract variable IDs that belong to positive/negative poles
# (IDs outside parentheses = main contributors)
# ------------------------------------------------------------
def load_var_ids(path: Path):
    text = path.read_text()

    all_ids = re.findall(r"v\d{6}", text)

    inside = set()
    for block in re.findall(r"\([^)]*\)", text):
        inside.update(re.findall(r"v\d{6}", block))

    outside = [vid for vid in all_ids if vid not in inside]

    # preserve order & remove duplicates
    seen = set()
    final = []
    for vid in outside:
        if vid not in seen:
            seen.add(vid)
            final.append(vid)
    return final

# ------------------------------------------------------------
# Load var IDs for factors
# ------------------------------------------------------------
varlist_pos = {}
varlist_neg = {}

for f in range(1, num_factors + 1):
    posfile = VARID_DIR / f"f{f}_pos_var_id.txt"
    negfile = VARID_DIR / f"f{f}_neg_var_id.txt"

    if not posfile.exists() or not negfile.exists():
        raise FileNotFoundError(f"Missing var-id files for f{f}: {posfile} / {negfile}")

    varlist_pos[f] = load_var_ids(posfile)
    varlist_neg[f] = load_var_ids(negfile)

# ------------------------------------------------------------
# Load file_ids.txt mapping
# ------------------------------------------------------------
id_map = {}
with open(FILE_IDS, encoding="utf-8") as f:
    for line in f:
        fid, fname = line.strip().split(maxsplit=1)
        id_map[fid] = fname

# ------------------------------------------------------------
# Main output
# ------------------------------------------------------------
with open(OUTFILE, "w", encoding="utf-8") as out:
    for _, row in scores.iterrows():

        fid = row["filename"]
        fname = id_map.get(fid, "UNKNOWN")

        out.write(f"text ID: {fid}\n")
        out.write(f"filename: {fname}\n\n")

        for f in range(1, num_factors + 1):

            score = row[f"fac{f}"]
            out.write(f"f{f} score: {score}\n")

            # POS
            pos_ids = varlist_pos[f]
            pos_used_ids = [vid for vid in pos_ids if row.get(vid, 0) != 0]
            pos_words = [lex.get(vid, vid) for vid in pos_used_ids]

            out.write(f"f{f} pos words (N={len(pos_used_ids)}): "
                      f"{', '.join(pos_words)}\n")

            # NEG
            neg_ids = varlist_neg[f]
            neg_used_ids = [vid for vid in neg_ids if row.get(vid, 0) != 0]
            neg_words = [lex.get(vid, vid) for vid in neg_used_ids]

            out.write(f"f{f} neg words (N={len(neg_used_ids)}): "
                      f"{', '.join(neg_words)}\n\n")

        out.write("=============================================\n\n")

print(f"\n✓ Finished. Output written to:\n  {OUTFILE}\n")