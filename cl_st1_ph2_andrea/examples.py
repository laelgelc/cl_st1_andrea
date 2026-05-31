#!/usr/bin/env python3
"""
Generate example text extracts based on highest factor scores by group.
For each factor:
    - positive pole: groups ranked by descending mean
    - negative pole: groups ranked by ascending mean
    - take top group → 20 examples
    - all other groups → 10 examples each
    - skip any file where the factor score == 0

Requires SAS output:
    sas/output_cl_st1_ph3_andressa/means_group_f<n>.tsv
    sas/output_cl_st1_ph3_andressa/cl_st1_ph3_andressa_scores_only.tsv

Requires:
    factors/f<n>_pos.txt
    factors/f<n>_neg.txt

Requires:
    file_ids.txt mapping t000001 → t001_human.txt
    or
    file_ids.txt mapping t00001 → human/t001_human.txt
"""

import pandas as pd
import re
from pathlib import Path
from tqdm import tqdm
import unicodedata

# =============================================================================
# PATHS
# =============================================================================
BASE             = Path("corpus/07_tagged")
FACTOR_FOLDER    = Path("factors")
EXAMPLES_DIR     = Path("examples")
EXAMPLES_DIR.mkdir(exist_ok=True)

SCORES_FILE      = Path("sas/output_cl_st1_ph3_andressa/cl_st1_ph3_andressa_scores_only.tsv")
MEANS_PATTERN    = "sas/output_cl_st1_ph3_andressa/means_group_f{dim}.tsv"

FILE_IDS_PATH    = Path("file_ids.txt")

# =============================================================================
# LOAD FILE-ID → FILENAME MAP
# =============================================================================
id_map = {}
with open(FILE_IDS_PATH, encoding="utf-8") as f:
    for line in f:
        file_id, fname = line.strip().split(maxsplit=1)
        id_map[file_id] = fname

# =============================================================================
# STOP WORDS THAT MUST NOT BE BOLD
# =============================================================================
STOPLIST = {"edith", "doorbell", "michael", "recorded", "attempt", "request"}

# =============================================================================
# LOAD SCORES
# =============================================================================
scores_df = pd.read_csv(SCORES_FILE, sep="\t")

# Ensure columns exist
scores_df["group"]  = scores_df["group"].str.strip()
scores_df["source"] = scores_df["source"].str.strip()
scores_df["model"]  = scores_df["model"].str.strip()

# =============================================================================
# FIND FACTOR COUNT
# =============================================================================
factor_cols = [c for c in scores_df.columns if c.startswith("fac")]
num_factors = len(factor_cols)
print(f"Detected {num_factors} factors.\n")

# =============================================================================
# PARSE PRIMARY LEMMAS
# =============================================================================
def load_primary_lemmas(pole_file: Path):
    lines = pole_file.read_text(encoding='utf-8').splitlines()[1:]
    items = ' '.join(lines).split(',')
    lemmas = set()

    for item in items:
        item = item.strip()
        m = re.match(r'\(?(?P<lem>[A-Za-z0-9_-]+)\s*\(', item)
        if m:
            lemmas.add(m.group('lem'))
    return lemmas

# =============================================================================
# ANNOTATE TEXT
# =============================================================================
def _wrap_emoji_for_latex(s: str) -> str:
    """
    Wrap emoji/symbol-other characters so LuaLaTeX renders them with \\EmojiFont
    (defined in examples/top_header).
    """
    out = []
    for ch in s:
        if unicodedata.category(ch) == "So":
            out.append(r"{\EmojiFont " + ch + "}")
        else:
            out.append(ch)
    return "".join(out)

def annotate_text(text_path: Path, primary_lemmas: set):

    raw = text_path.read_text(encoding="utf-8")

    # ============================================================
    # NEW STEP: REMOVE ALL { and } BEFORE ANY OTHER PROCESSING
    # ============================================================
    raw = raw.replace("{", "").replace("}", "").replace("\\", "")

    tokens = []
    matched = set()

    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue

        wordform, tag, lemma = parts[0], parts[1], parts[2]

        if lemma in primary_lemmas and lemma not in STOPLIST:
            wordform = r"\textbf{" + wordform + "}"
            matched.add(lemma)

        tokens.append(wordform)

    # Join into a single string
    text = " ".join(tokens)

    # Fix spacing issues
    text = re.sub(r"\b([A-Za-z]+)\s+n['’]t\b", r"\1n't", text)
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    text = re.sub(r'\s+"', '"', text)
    text = re.sub(r'"\s+', '"', text)

    # Escape LaTeX specials
    for ch, rep in {"$": r"\$", "#": r"\#", "&": r"\&", "_": r"\_"}.items():
        text = text.replace(ch, rep)

    # Break sentences into paragraphs
    paras = re.split(r"([.!?])\s+(?=[A-Z])", text)
    paras = ["".join(paras[i:i+2]).strip() for i in range(0, len(paras), 2)]
    paras = [p for p in paras if p]

    # Ensure emoji survive LaTeX
    paras = [_wrap_emoji_for_latex(p) for p in paras]

    return paras, matched

# =============================================================================
# LOCATE TEXT FILE BASED ON GROUP
# =============================================================================
def locate_text(row):
    rel = id_map.get(row["filename"])
    if not rel:
        return None

    p = BASE / rel
    if p.exists():
        # file_ids.txt already includes the subfolder, e.g. "generic_gpt/t001_gpt.txt"
        return p

    # fallback: old behavior if mapping is only a filename
    return BASE / row["group"] / rel

# =============================================================================
# SELECT EXAMPLES
# =============================================================================
missing_files = set()

for fac_num in range(1, num_factors + 1):
    col = f"fac{fac_num}"

    means_file = Path(MEANS_PATTERN.format(dim=fac_num))
    means_df = pd.read_csv(means_file, sep="\t")

    group_means = dict(zip(means_df["group"], means_df[f"Mean fac{fac_num}"]))

    # =========================================================================
    # TWO POLES: POSITIVE (descending) AND NEGATIVE (ascending)
    # =========================================================================
    for pole, ascending in (("pos", False), ("neg", True)):

        label = f"f{fac_num}_{pole}"
        print(f"→ {label}: selecting by group means (col={col}, ascending={ascending})")

        # Rank groups
        ranked_groups = sorted(group_means.keys(),
                               key=lambda g: group_means[g],
                               reverse=not ascending)

        top_group = ranked_groups[0]
        other_groups = ranked_groups[1:]

        # Load primary lemmas for this pole
        primary_lemmas = load_primary_lemmas(FACTOR_FOLDER / f"{label}.txt")

        # Sort entire DF by factor polarity
        sorted_df = scores_df.sort_values(by=col, ascending=ascending)

        out_dir = EXAMPLES_DIR / label
        out_dir.mkdir(parents=True, exist_ok=True)

        ex_id = 1

        # ---------------------------------------
        # TOP GROUP — 20 EXAMPLES
        # ---------------------------------------
        tg_df = sorted_df[sorted_df["group"] == top_group]
        for _, row in tg_df.iterrows():
            if row[col] == 0:
                continue
            if ex_id > 20:
                break

            tpath = locate_text(row)
            if not tpath or not tpath.exists():
                missing_files.add(row["filename"])
                continue

            paras, matched = annotate_text(tpath, primary_lemmas)

            raw_fname = id_map.get(row["filename"], row["filename"])
            latex_fname = raw_fname.replace("_", r"\_")

            # LaTeX-escaped group name
            group_latex = top_group.replace("_", r"\_")

            env_title = (
                f"{pole.upper()} Dim {fac_num} – {group_latex} – "
                f"Score {row[col]:.2f} – {latex_fname}"
            )
            env_label = f"ex:{label}_{ex_id:03d}"

            out_file = out_dir / f"{label}_{ex_id:03d}.tex"

            with open(out_file, "w", encoding="utf-8") as f:
                f.write(r"\begin{textsample}{" + env_title + r"}  \label{" + env_label + "}\n")
                f.write("\n".join(paras))
                f.write("\n" * 2)
                f.write("% matched lemmas: " + ", ".join(sorted(matched)) + "\n")
                f.write(r"\end{textsample}" + "\n")

            ex_id += 1

        # ---------------------------------------
        # OTHER GROUPS — 10 EACH
        # ---------------------------------------
        for grp in other_groups:
            grp_df = sorted_df[sorted_df["group"] == grp]

            count = 0
            for _, row in grp_df.iterrows():
                if row[col] == 0:
                    continue
                if count >= 10:
                    break

                tpath = locate_text(row)
                if not tpath or not tpath.exists():
                    missing_files.add(row["filename"])
                    continue

                paras, matched = annotate_text(tpath, primary_lemmas)

                raw_fname = id_map.get(row["filename"], row["filename"])
                latex_fname = raw_fname.replace("_", r"\_")

                # LaTeX-escaped group name
                group_latex = grp.replace("_", r"\_")

                env_title = (
                    f"{pole.upper()} Dim {fac_num} – {group_latex} – "
                    f"Score {row[col]:.2f} – {latex_fname}"
                )
                env_label = f"ex:{label}_{ex_id:03d}"

                out_file = out_dir / f"{label}_{ex_id:03d}.tex"

                with open(out_file, "w", encoding="utf-8") as f:
                    f.write(r"\begin{textsample}{" + env_title + r"}  \label{" + env_label + "}\n")
                    f.write("\n".join(paras))
                    f.write("\n" * 2)
                    f.write("% matched lemmas: " + ", ".join(sorted(matched)) + "\n")
                    f.write(r"\end{textsample}" + "\n")

                count += 1
                ex_id += 1

        print(f"  ✓ Wrote {ex_id-1} examples for {label}\n")

# =============================================================================
# MISSING FILE REPORT
# =============================================================================
if missing_files:
    Path("missing_files.txt").write_text("\n".join(sorted(missing_files)))
    print(f"⚠ Missing files written to missing_files.txt")

# =============================================================================
# BUILD MASTER LATEX FILE
# =============================================================================
top_header_path = EXAMPLES_DIR / "top_header"
if not top_header_path.exists():
    print("\n⚠ top_header missing. Create examples/top_header before compiling LaTeX.\n")

master = EXAMPLES_DIR / "examples.tex"

with open(top_header_path, "r", encoding="utf-8") as f:
    preamble = f.read()

with open(master, "w", encoding="utf-8") as out:
    out.write(preamble + "\n\n")
    out.write(r"\begin{document}" + "\n\n")
    out.write(r"\maketitle" + "\n\n")
    out.write(r"\tableofcontents" + "\n\n")

    for fac_num in range(1, num_factors + 1):
        for pole in ("pos", "neg"):
            label = f"f{fac_num}_{pole}"
            out.write(r"\section{" + f"{pole.upper()} Dim {fac_num}" + "}\n\n")

            for tex in sorted((EXAMPLES_DIR / label).glob("*.tex")):
                out.write(r"\input{" + str(tex.resolve()) + "}\n")

    out.write("\n" + r"\end{document}" + "\n")

print("✓ Created examples/examples.tex")