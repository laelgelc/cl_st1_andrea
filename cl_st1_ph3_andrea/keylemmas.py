#!/usr/bin/env python3
"""
Compute decade-specific key lemmas for the tagged commercial verbal subcorpus.

Expected input structure:

    corpus/07_tagged/
        1950/
        1960/
        1970/
        1980/
        1990/
        2000/
        2010/
        2020/

Each decade folder should contain TreeTagger output files in .txt format.

Typical usage:

    python keylemmas.py \
        --input corpus/07_tagged \
        --output corpus/08_keylemmas \
        --cutoff 3

cutoff = minimum percent presence requirement in the target decade.
"""

import os
import re
import math
import argparse
from collections import defaultdict


# POS tags to keep: nouns, proper nouns, main verbs, adjectives
VALID_TAG_PREFIXES = ("NN", "NP", "VB", "JJ")

# Lemmas to exclude after lowercasing
STOPWORDS = {
    "be",
    "have",
    "do",
}

DECADE_FOLDER_RE = re.compile(r"^\d{4}$")


def natural_sort_key(text):
    """Return a natural-sort key that treats digit runs as integers."""
    parts = re.split(r"(\d+)", text)
    return [int(part) if part.isdigit() else part.lower() for part in parts]


def ll(a, b, c, d):
    """Calculate log-likelihood for presence/absence counts."""
    if a == 0 or b == 0:
        return 0.0

    E1 = c * (a + b) / (c + d)
    E2 = d * (a + b) / (c + d)

    if E1 == 0 or E2 == 0:
        return 0.0

    return 2 * ((a * math.log(a / E1)) + (b * math.log(b / E2)))


def discover_decade_folders(base_dir):
    """Return decade-named subdirectories under the tagged corpus directory."""
    if not os.path.isdir(base_dir):
        raise FileNotFoundError(f"Input directory does not exist: {base_dir}")

    folders = sorted(
        [
            d for d in os.listdir(base_dir)
            if (
                os.path.isdir(os.path.join(base_dir, d))
                and DECADE_FOLDER_RE.match(d)
        )
        ],
        key=natural_sort_key,
    )

    if not folders:
        raise FileNotFoundError(
            f"No decade folders found in {base_dir}. "
            "Expected folders such as 1950, 1960, 1970, etc."
        )

    return folders


def load_lemma_presence(base_dir, *, label_prefix=""):
    """
    Load lemma presence for one subcorpus folder.

    Returns:
        lemma -> set(text labels)
        set(text labels)
    """
    presence = defaultdict(set)
    all_texts = set()

    for root, dirs, files in os.walk(base_dir):
        dirs.sort(key=natural_sort_key)

        for filename in sorted(files, key=natural_sort_key):
            if not filename.endswith(".txt"):
                continue

            path = os.path.join(root, filename)
            rel = os.path.relpath(path, base_dir)
            text_label = os.path.join(label_prefix, rel) if label_prefix else rel

            all_texts.add(text_label)
            seen = set()

            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.rstrip("\n").split("\t")

                    if len(parts) < 3:
                        continue

                    word, tag, lemma = parts[:3]

                    # Keep only nouns, proper nouns, main verbs, and adjectives.
                    if not tag.startswith(VALID_TAG_PREFIXES):
                        continue

                    # If lemma is <unknown>, use the wordform.
                    lemma = lemma.strip()
                    if lemma == "<unknown>" or not lemma:
                        lemma = word.strip()

                    lemma_lc = lemma.lower()

                    # Lemma must contain at least two alphabetic characters.
                    if sum(1 for ch in lemma_lc if ch.isalpha()) < 2:
                        continue

                    if lemma_lc in STOPWORDS:
                        continue

                    # Record presence once per text.
                    if lemma_lc not in seen:
                        presence[lemma_lc].add(text_label)
                        seen.add(lemma_lc)

    return presence, all_texts


def save_keywords(path, rows):
    """Save key lemma rows as a tab-separated text file."""
    header = [
        "lemma",
        "target_count",
        "comparison_count",
        "target_per_1k",
        "comparison_per_1k",
        "expected",
        "LL",
        "%DIFF",
        "status",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\t".join(header) + "\n")

        for row in rows:
            f.write("\t".join(map(str, row)) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Compute decade-specific key lemmas for the commercial verbal subcorpus."
    )
    parser.add_argument(
        "--input",
        default="corpus/07_tagged",
        help="Directory containing tagged decade folders.",
    )
    parser.add_argument(
        "--output",
        default="corpus/08_keylemmas",
        help="Output directory for key lemma lists.",
    )
    parser.add_argument(
        "--cutoff",
        default=3.0,
        type=float,
        help="Minimum percentage presence in target decade texts.",
    )

    args = parser.parse_args()

    base_dir = args.input
    output_dir = args.output
    cutoff_percent = args.cutoff

    if cutoff_percent < 0:
        raise ValueError("--cutoff must be non-negative")

    os.makedirs(output_dir, exist_ok=True)

    folders = discover_decade_folders(base_dir)

    print("Found decade folders:")
    for folder in folders:
        print(f"  - {folder}")

    # Build global lemma presence across all decades.
    global_presence = defaultdict(set)
    global_texts = set()

    for folder in folders:
        subdir = os.path.join(base_dir, folder)
        presence, texts = load_lemma_presence(subdir, label_prefix=folder)

        for lemma, lemma_texts in presence.items():
            global_presence[lemma] |= lemma_texts

        global_texts |= texts

    status_priority = {
        "POSKW": 0,
        "NEGKW": 1,
        "NOTKW": 2,
    }

    for folder in folders:
        print(f"\nProcessing {folder}...")

        target_dir = os.path.join(base_dir, folder)

        target_presence, target_texts = load_lemma_presence(
            target_dir,
            label_prefix=folder,
        )
        comparison_texts = global_texts - target_texts

        comp_presence = defaultdict(set)
        for lemma, lemma_texts in global_presence.items():
            comp_presence[lemma] = lemma_texts & comparison_texts

        size_target = len(target_texts)
        size_comp = len(comparison_texts)
        total = size_target + size_comp
        cutoff_texts = size_target * cutoff_percent / 100

        if size_target == 0:
            print(f"Skipping {folder}: no tagged text files found.")
            continue

        rows = []

        for lemma in global_presence:
            a = len(target_presence.get(lemma, set()))
            b = len(comp_presence.get(lemma, set()))

            if a < cutoff_texts:
                continue

            target_per_1k = (a / size_target) * 1000
            comparison_per_1k = (b / size_comp) * 1000 if size_comp else 0.0
            expected = (size_target * (a + b)) / total if total else 0.0
            ll_value = ll(a, b, size_target, size_comp)

            if (target_per_1k + comparison_per_1k) == 0:
                percent_diff = 0.0
            else:
                percent_diff = (
                        100
                        * (target_per_1k - comparison_per_1k)
                        / ((target_per_1k + comparison_per_1k) / 2)
                )

            status = (
                "POSKW" if ll_value >= 3.84 and percent_diff > 0 else
                "NEGKW" if ll_value >= 3.84 else
                "NOTKW"
            )

            rows.append(
                (
                    lemma,
                    a,
                    b,
                    round(target_per_1k, 2),
                    round(comparison_per_1k, 2),
                    round(expected, 2),
                    round(ll_value, 2),
                    round(percent_diff, 2),
                    status,
                )
            )

        rows.sort(key=lambda row: (status_priority[row[8]], -row[6], row[0]))

        outpath = os.path.join(output_dir, f"{folder}.tsv")
        save_keywords(outpath, rows)

        print(
            f"Saved {outpath} "
            f"({size_target} target texts vs {size_comp} comparison texts; "
            f"{len(rows)} lemmas)"
        )


if __name__ == "__main__":
    main()