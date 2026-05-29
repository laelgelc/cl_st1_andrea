#!/usr/bin/env python3
"""
select_kws_stratified.py

Selects a stratified (quota-based) subset of *positive* keywords (POSKW) from
key-lemma tables produced upstream (e.g., by `keylemmas.py`).

What it does
------------
1) Reads every `*.txt` key-lemma file in `corpus/08_keylemmas/` (one file per
   stratum/subcorpus, e.g., `human.txt`, `generic_gpt.txt`, `summary_guided_gpt.txt`).
2) Extracts lemmas whose final column is `POSKW`, applying additional filters:
   - drop lemmas containing Unicode punctuation
   - drop lemmas containing any digits
   - drop lemmas containing any uppercase letters (keep lowercase-only)
3) Applies per-stratum quotas:
   - each non-human stratum: at most `--ceiling` lemmas
   - `human`: at most `--ceiling * --human-weight` lemmas
   Selection preserves the original file order (i.e., top-ranked first).
4) Builds a consolidated list in a priority order tailored to this project:
   human → summary_guided_* → (other strata) → generic_*
   Truncates the consolidated list to `--max-total` (before de-duplication).
5) Writes outputs to `corpus/09_kw_selected/`:
   - one file per stratum: `<stratum>.txt`
   - one consolidated, de-duplicated list: `keywords.txt` (alphabetical)

Typical usage
-------------
python select_kws_stratified.py \
    --ceiling 250 \
    --human-weight 2 \
    --max-total 1200
"""

import os
import glob
import unicodedata
import argparse

INPUT_DIR = "corpus/08_keylemmas"
OUTPUT_DIR = "corpus/09_kw_selected"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -----------------------------------------------------------
# Helpers
# -----------------------------------------------------------

def contains_punctuation(s):
    return any(unicodedata.category(ch).startswith("P") for ch in s)

def load_poskw(filepath):
    """
    Load POSKW lemmas from a keylemma file.
    Skips header, punctuation, digits, uppercase.
    Returns lemmas in file order.
    """
    lemmas = []
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()[1:]  # skip header

    for line in lines:
        parts = line.strip().split()
        if len(parts) < 2:
            continue
        lemma, status = parts[0], parts[-1]

        # filtering criteria
        if status != "POSKW":
            continue
        if contains_punctuation(lemma):
            continue
        if any(ch.isdigit() for ch in lemma):
            continue
        if any(ch.isupper() for ch in lemma):
            continue

        lemmas.append(lemma)

    return lemmas

# -----------------------------------------------------------
# Main
# -----------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ceiling", type=int, required=True,
                        help="Max keywords per non-human stratum (e.g., 125)")
    parser.add_argument("--human-weight", type=int, required=True,
                        help="Multiplier applied to human quota (e.g., 2 → 250)")
    parser.add_argument("--max-total", type=int, required=True,
                        help="Max total keywords allowed (e.g., 1000)")
    args = parser.parse_args()

    ceiling = args.ceiling
    human_weight = args.human_weight
    max_total = args.max_total

    # Load all strata
    strata = {}
    for filepath in sorted(glob.glob(os.path.join(INPUT_DIR, "*.txt"))):
        name = os.path.basename(filepath).replace(".txt", "")
        strata[name] = load_poskw(filepath)

    # Determine quotas
    quotas = {}
    for name in strata:
        if name == "human":
            quotas[name] = ceiling * human_weight
        else:
            quotas[name] = ceiling

    # Display quotas
    print("=== Keyword Quotas ===")
    for name in sorted(quotas):
        print(f"{name:<15} → {quotas[name]} keywords (max)")
    print("=======================\n")

    # Per-stratum selection
    selected_by_stratum = {}
    consolidated = []

    for name, lemmas in strata.items():
        quota = quotas[name]
        chosen = lemmas[:quota]
        selected_by_stratum[name] = chosen

        print(f"{name:<15} → selected {len(chosen)}/{quota} keywords")

    # Build consolidated list in priority order
    # priority: human → summary_guided_* → (others) → generic_*

    human_key = ["human"] if "human" in strata else []
    summary_guided_keys = sorted([s for s in strata if s.startswith("summary_guided_")])
    generic_keys = sorted([s for s in strata if s.startswith("generic_")])

    # Any remaining files (e.g., model names) are treated as "other"
    other_keys = sorted([
        s for s in strata
        if s not in set(human_key + summary_guided_keys + generic_keys)
    ])

    ordered_strata = human_key + summary_guided_keys + other_keys + generic_keys

    for s in ordered_strata:
        consolidated.extend(selected_by_stratum[s])

    # Enforce max_total
    if len(consolidated) > max_total:
        consolidated = consolidated[:max_total]

    unique_count = len(set(consolidated))
    total_count = len(consolidated)

    print(f"\nTotal consolidated keywords (incl. duplicates): {total_count}")
    print(f"Unique keywords (used downstream): {unique_count}")
    print(f"Duplicates removed later: {total_count - unique_count}")

    # Write per-stratum outputs
    for name, words in selected_by_stratum.items():
        outpath = os.path.join(OUTPUT_DIR, f"{name}.txt")
        with open(outpath, "w", encoding="utf-8") as fout:
            for w in words:
                fout.write(w + "\n")

    # Write consolidated
    # Deduplicate and sort before saving
    unique_lemmas = sorted(set(consolidated))

    cons_path = os.path.join(OUTPUT_DIR, "keywords.txt")
    with open(cons_path, "w", encoding="utf-8") as fout:
        for w in unique_lemmas:
            fout.write(w + "\n")

    print(f"\nFinal unique keywords written: {len(unique_lemmas)}")


if __name__ == "__main__":
    main()