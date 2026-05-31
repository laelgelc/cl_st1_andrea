#!/usr/bin/env python3
"""
Generate plaintext example files for each factor pole.

Aligned with `examples.py` selection logic:
    - reads the same scores table (scores_only)
    - uses `group` as provided by SAS output (no re-inference)
    - ranks groups using means_group_f<n>.tsv
    - selects: top group → 20, others → 10 each, skipping score==0
    - uses tagged corpus existence checks to keep selection stable with `examples.py`

Additionally, this script makes the `examples/score_details.txt` dependency explicit:
    - fails fast if the file is missing
    - reports any missing (tid, pole) loading-word coverage to missing_loading_words.txt

Outputs:
    examples_txt/f<n>_<pole>/f<n>_<pole>_001.txt
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

# ============================================================
# PATHS
# ============================================================
SCORES_FILE = Path("sas/output_cl_st1_ph3_andressa/cl_st1_ph3_andressa_scores_only.tsv")
MEANS_PATTERN = "sas/output_cl_st1_ph3_andressa/means_group_f{dim}.tsv"

FILE_IDS_PATH = Path("file_ids.txt")           # tid -> relative path (often includes subfolder)
SCORE_DETAILS = Path("examples/score_details.txt")

TAGGED_BASE = Path("corpus/07_tagged")         # align selection behavior with examples.py
FULLTEXT_ROOT = Path("corpus")                 # full transcripts under corpus/05_*
OUT_ROOT = Path("examples_txt")
OUT_ROOT.mkdir(exist_ok=True, parents=True)


# ============================================================
# LOAD FILE-ID → RELATIVE PATH MAP (as in examples.py)
# ============================================================
def load_id_map(path: Path) -> dict[str, str]:
    if not path.exists():
        raise SystemExit(f"ERROR: required file missing: {path}")

    out: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            file_id, rel = line.strip().split(maxsplit=1)
            out[file_id] = rel
    return out


id_map = load_id_map(FILE_IDS_PATH)


# ============================================================
# LOAD SCORES (same source + semantics as examples.py)
# ============================================================
if not SCORES_FILE.exists():
    raise SystemExit(f"ERROR: required file missing: {SCORES_FILE}")

scores_df = pd.read_csv(SCORES_FILE, sep="\t")

# normalize core string fields (matches examples.py behavior)
for c in ("group", "source", "model"):
    if c in scores_df.columns:
        scores_df[c] = scores_df[c].astype(str).str.strip()
    else:
        raise SystemExit(f"ERROR: expected column '{c}' missing in {SCORES_FILE}")

# ============================================================
# FACTOR COUNT
# ============================================================
factor_cols = [c for c in scores_df.columns if c.startswith("fac")]
num_factors = len(factor_cols)
print(f"Detected {num_factors} factors.\n")
if num_factors == 0:
    raise SystemExit(f"ERROR: no factor columns 'fac*' found in {SCORES_FILE}")


# ============================================================
# LOAD loading words from examples/score_details.txt
#   Make dependency explicit + report missing coverage
# ============================================================
def parse_score_details(path: Path, *, num_factors: int) -> dict[str, dict[str, list[str]]]:
    """
    Returns:
        loading_words[tid]["f<n>_pos" or "f<n>_neg"] -> list[str]
    """
    out: dict[str, dict[str, list[str]]] = {}
    txt = path.read_text(encoding="utf-8")
    blocks = txt.split("=============================================")

    for b in blocks:
        m = re.search(r"text ID:\s*(t\d+)", b)
        if not m:
            continue

        tid = m.group(1)
        out[tid] = {}

        for f in range(1, num_factors + 1):
            mp = re.search(rf"f{f} pos words \(N=\d+\):\s*(.*)", b)
            mn = re.search(rf"f{f} neg words \(N=\d+\):\s*(.*)", b)

            pos = mp.group(1).split(",") if mp else []
            neg = mn.group(1).split(",") if mn else []

            out[tid][f"f{f}_pos"] = [w.strip() for w in pos if w.strip()]
            out[tid][f"f{f}_neg"] = [w.strip() for w in neg if w.strip()]

    return out


if not SCORE_DETAILS.exists():
    raise SystemExit(
        f"ERROR: required file missing: {SCORE_DETAILS}\n"
        "Run `python score_details.py` to generate it (expected output: examples/score_details.txt)."
    )

loading_words = parse_score_details(SCORE_DETAILS, num_factors=num_factors)

# Report when score_details exists but lacks coverage for selected (tid, label)
missing_loading_words: set[tuple[str, str]] = set()


# ============================================================
# PATH RESOLUTION
# ============================================================
def locate_tagged_text(row: pd.Series) -> Path | None:
    """
    Mirrors examples.py's locate_text behavior:
      - use file_ids mapping tid -> rel
      - check TAGGED_BASE / rel first
      - fallback: TAGGED_BASE / group / rel
    """
    tid = row["filename"]
    rel = id_map.get(tid)
    if not rel:
        return None

    p = TAGGED_BASE / rel
    if p.exists():
        return p

    return TAGGED_BASE / str(row["group"]).strip() / rel


def locate_fulltext(row: pd.Series) -> Path | None:
    """
    Locate the corresponding full transcript under corpus/05_*.

    Primary rule (recommended for this project):
      - if rel is "<subdir>/<fname>": use corpus/05_<subdir>/<fname>
        except subdir == "human" -> corpus/05_human/<fname>

    Fallback:
      - if rel is just "<fname>": use group to pick folder corpus/05_<group> (or 05_human)
    """
    tid = row["filename"]
    rel = id_map.get(tid)
    if not rel:
        return None

    rel_path = Path(rel)
    fname = rel_path.name

    if len(rel_path.parts) >= 2:
        subdir = rel_path.parts[0]
        folder = FULLTEXT_ROOT / ("05_human" if subdir == "human" else f"05_{subdir}")
        return folder / fname

    grp = str(row["group"]).strip()
    folder = FULLTEXT_ROOT / ("05_human" if grp == "human" else f"05_{grp}")
    return folder / fname


# ============================================================
# OUTPUT WRITER
# ============================================================
def write_plaintext_example(
        *,
        outfile: Path,
        tid: str,
        group: str,
        model: str,
        fulltext_path: Path,
        label: str,
        score_value,
        lw: list[str],
) -> None:
    header: list[str] = [
        f"Text ID: {tid}",
        f"Group: {group}",
        f"Model: {model}",
        f"File:   {fulltext_path}",
        "",
        f"Score ({label}): {score_value}",
        f"Loading words ({label}), N={len(lw)}: {', '.join(lw)}",
        "",
    ]

    body = fulltext_path.read_text(encoding="utf-8", errors="ignore")
    outfile.write_text("\n".join(header) + body, encoding="utf-8")


# ============================================================
# MAIN (selection logic mirrors examples.py)
# ============================================================
missing_files: set[str] = set()

for fac_num in range(1, num_factors + 1):
    col = f"fac{fac_num}"
    if col not in scores_df.columns:
        raise SystemExit(f"ERROR: expected factor score column '{col}' missing in {SCORES_FILE}")

    means_file = Path(MEANS_PATTERN.format(dim=fac_num))
    if not means_file.exists():
        raise SystemExit(f"ERROR: required means file missing: {means_file}")

    means_df = pd.read_csv(means_file, sep="\t")

    mean_col = f"Mean fac{fac_num}"
    if "group" not in means_df.columns or mean_col not in means_df.columns:
        raise SystemExit(f"ERROR: expected columns 'group' and '{mean_col}' missing in {means_file}")

    group_means = dict(zip(means_df["group"], means_df[mean_col]))

    for pole, ascending in (("pos", False), ("neg", True)):
        label = f"f{fac_num}_{pole}"
        print(f"→ {label}: selecting by group means (col={col}, ascending={ascending})")

        ranked_groups = sorted(
            group_means.keys(),
            key=lambda g: group_means[g],
            reverse=not ascending,
        )
        if not ranked_groups:
            raise SystemExit(f"ERROR: no groups found in {means_file}")

        top_group = ranked_groups[0]
        other_groups = ranked_groups[1:]

        sorted_df = scores_df.sort_values(by=col, ascending=ascending)

        out_dir = OUT_ROOT / label
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

            tagged_path = locate_tagged_text(row)
            if not tagged_path or not tagged_path.exists():
                missing_files.add(row["filename"])
                continue

            fulltext_path = locate_fulltext(row)
            if not fulltext_path or not fulltext_path.exists():
                missing_files.add(row["filename"])
                continue

            tid = row["filename"]
            lw = loading_words.get(tid, {}).get(label)
            if lw is None:
                missing_loading_words.add((tid, label))
                lw = []

            outfile = out_dir / f"{label}_{ex_id:03d}.txt"
            write_plaintext_example(
                outfile=outfile,
                tid=tid,
                group=str(row["group"]).strip(),
                model=str(row["model"]).strip(),
                fulltext_path=fulltext_path,
                label=label,
                score_value=row[col],
                lw=lw,
            )
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

                tagged_path = locate_tagged_text(row)
                if not tagged_path or not tagged_path.exists():
                    missing_files.add(row["filename"])
                    continue

                fulltext_path = locate_fulltext(row)
                if not fulltext_path or not fulltext_path.exists():
                    missing_files.add(row["filename"])
                    continue

                tid = row["filename"]
                lw = loading_words.get(tid, {}).get(label)
                if lw is None:
                    missing_loading_words.add((tid, label))
                    lw = []

                outfile = out_dir / f"{label}_{ex_id:03d}.txt"
                write_plaintext_example(
                    outfile=outfile,
                    tid=tid,
                    group=str(row["group"]).strip(),
                    model=str(row["model"]).strip(),
                    fulltext_path=fulltext_path,
                    label=label,
                    score_value=row[col],
                    lw=lw,
                )

                count += 1
                ex_id += 1

        print(f"  ✓ Wrote {ex_id - 1} examples for {label}\n")


# ============================================================
# REPORTS
# ============================================================
if missing_files:
    Path("missing_files.txt").write_text("\n".join(sorted(missing_files)), encoding="utf-8")
    print("⚠ Missing files written to missing_files.txt")

if missing_loading_words:
    report_path = Path("missing_loading_words.txt")
    report_path.write_text(
        "\n".join(f"{tid}\t{label}" for tid, label in sorted(missing_loading_words)),
        encoding="utf-8",
    )
    print(f"⚠ Missing loading words written to {report_path}")

print("\n✓ Done! All plaintext examples written to examples_txt/")