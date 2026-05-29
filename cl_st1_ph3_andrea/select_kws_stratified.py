#!/usr/bin/env python3
"""
select_kws_stratified.py

Selects a balanced, decade-stratified subset of positive keywords (POSKW)
from key-lemma tables produced by keylemmas.py.

In this project, the strata are decades:

    1950
    1960
    1970
    1980
    1990
    2000
    2010
    2020

The strata are of the same nature, so each decade receives the same maximum
keyword quota. There is no human/non-human weighting.

What it does
------------
1) Reads every decade key-lemma file in corpus/08_keylemmas/.
   Supported extensions: .tsv and .txt.

2) Extracts lemmas whose final column is POSKW, applying additional filters:
   - drop lemmas containing Unicode punctuation;
   - drop lemmas containing digits;
   - drop lemmas containing uppercase letters.

3) Applies the same quota to every decade:
   - each decade: at most --per-decade lemmas.

4) Builds a consolidated list in chronological decade order.

5) Optionally truncates the consolidated list to --max-total before
   de-duplication.

6) Writes outputs to corpus/09_kw_selected/:
   - one file per decade: <decade>.txt
   - one consolidated, de-duplicated list: keywords.txt

Typical usage
-------------
python select_kws_stratified.py \
    --per-decade 250 \
    --max-total 1200
"""

import os
import re
import glob
import argparse
import unicodedata


INPUT_DIR = "corpus/08_keylemmas"
OUTPUT_DIR = "corpus/09_kw_selected"

DECADE_RE = re.compile(r"^\d{4}$")
SUPPORTED_EXTENSIONS = (".tsv", ".txt")


# -----------------------------------------------------------
# Helpers
# -----------------------------------------------------------

def natural_sort_key(text):
    """Return a natural-sort key that treats digit runs as integers."""
    parts = re.split(r"(\d+)", text)
    return [int(part) if part.isdigit() else part.lower() for part in parts]


def contains_punctuation(text):
    """Return True if text contains any Unicode punctuation character."""
    return any(unicodedata.category(ch).startswith("P") for ch in text)


def is_clean_lemma(lemma):
    """Return True if lemma passes lexical filtering rules."""
    if contains_punctuation(lemma):
        return False
    if any(ch.isdigit() for ch in lemma):
        return False
    if any(ch.isupper() for ch in lemma):
        return False

    return True


def discover_keylemma_files(input_dir):
    """Return decade-named key-lemma files from the input directory."""
    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    files = []

    for extension in SUPPORTED_EXTENSIONS:
        files.extend(glob.glob(os.path.join(input_dir, f"*{extension}")))

    decade_files = {}

    for filepath in files:
        stem = os.path.splitext(os.path.basename(filepath))[0]

        if not DECADE_RE.match(stem):
            continue

        # Prefer .tsv if both .tsv and .txt exist for the same decade.
        existing = decade_files.get(stem)
        if existing is None:
            decade_files[stem] = filepath
        elif filepath.endswith(".tsv") and existing.endswith(".txt"):
            decade_files[stem] = filepath

    if not decade_files:
        raise FileNotFoundError(
            f"No decade key-lemma files found in {input_dir}. "
            "Expected files such as 1950.tsv, 1960.tsv, etc."
        )

    return [
        (decade, decade_files[decade])
        for decade in sorted(decade_files, key=natural_sort_key)
    ]


def load_poskw(filepath):
    """
    Load POSKW lemmas from a key-lemma file.

    The file may be tab-separated or whitespace-separated.
    The first column is assumed to be the lemma.
    The final column is assumed to be the status.
    """
    lemmas = []

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if not lines:
        return lemmas

    for line in lines[1:]:  # skip header
        line = line.strip()

        if not line:
            continue

        if "\t" in line:
            parts = line.split("\t")
        else:
            parts = line.split()

        if len(parts) < 2:
            continue

        lemma = parts[0].strip()
        status = parts[-1].strip()

        if status != "POSKW":
            continue

        if not is_clean_lemma(lemma):
            continue

        lemmas.append(lemma)

    return lemmas


def write_word_list(path, words):
    """Write one word per line."""
    with open(path, "w", encoding="utf-8") as fout:
        for word in words:
            fout.write(word + "\n")


# -----------------------------------------------------------
# Main
# -----------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Select balanced POSKW keyword lists across decade strata."
    )
    parser.add_argument(
        "--input",
        default=INPUT_DIR,
        help="Input directory containing decade key-lemma files.",
    )
    parser.add_argument(
        "--output",
        default=OUTPUT_DIR,
        help="Output directory for selected keyword lists.",
    )
    parser.add_argument(
        "--per-decade",
        type=int,
        required=True,
        help="Maximum number of POSKW lemmas to select from each decade.",
    )
    parser.add_argument(
        "--max-total",
        type=int,
        default=0,
        help=(
            "Optional maximum consolidated keyword count before de-duplication. "
            "Use 0 for no maximum."
        ),
    )

    args = parser.parse_args()

    if args.per_decade <= 0:
        raise ValueError("--per-decade must be greater than 0")

    if args.max_total < 0:
        raise ValueError("--max-total must be non-negative")

    os.makedirs(args.output, exist_ok=True)

    keylemma_files = discover_keylemma_files(args.input)

    # Load all decade strata.
    strata = {}

    for decade, filepath in keylemma_files:
        strata[decade] = load_poskw(filepath)

    print("=== Decade Keyword Quotas ===")
    for decade in sorted(strata, key=natural_sort_key):
        print(f"{decade:<6} → {args.per_decade} keywords max")
    print("=============================\n")

    # Per-decade selection.
    selected_by_decade = {}

    for decade in sorted(strata, key=natural_sort_key):
        lemmas = strata[decade]
        chosen = lemmas[:args.per_decade]
        selected_by_decade[decade] = chosen

        print(
            f"{decade:<6} → selected {len(chosen)}/{args.per_decade} "
            f"from {len(lemmas)} available POSKW lemmas"
        )

    # Build consolidated list in chronological decade order.
    consolidated = []

    for decade in sorted(selected_by_decade, key=natural_sort_key):
        consolidated.extend(selected_by_decade[decade])

    # Enforce optional max_total before de-duplication.
    if args.max_total and len(consolidated) > args.max_total:
        consolidated = consolidated[:args.max_total]

    unique_lemmas = sorted(set(consolidated))

    total_count = len(consolidated)
    unique_count = len(unique_lemmas)

    print(f"\nTotal consolidated keywords before de-duplication: {total_count}")
    print(f"Unique keywords after de-duplication: {unique_count}")
    print(f"Duplicates removed: {total_count - unique_count}")

    # Write per-decade outputs.
    for decade, words in selected_by_decade.items():
        outpath = os.path.join(args.output, f"{decade}.txt")
        write_word_list(outpath, words)

    # Write consolidated deduplicated output.
    cons_path = os.path.join(args.output, "keywords.txt")
    write_word_list(cons_path, unique_lemmas)

    print(f"\nFinal unique keywords written to: {cons_path}")
    print(f"Final unique keyword count: {len(unique_lemmas)}")


if __name__ == "__main__":
    main()