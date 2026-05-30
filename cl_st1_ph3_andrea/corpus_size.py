#!/usr/bin/env python3
"""
Calculate corpus size for the tagged commercial corpus.

Expected input structure:
    corpus/07_tagged/<Decade>/<Commercial ID>.txt

Example:
    corpus/07_tagged/1950/tv_com_1950_1.txt
    corpus/07_tagged/1960/tv_com_1960_1.txt

Expected tagged-file format:
    word<TAB>tag<TAB>lemma

Output:
    corpus_size/corpus_size.tsv

Output format:
    Header included
    Tab-separated
    Columns:
        Strata
        Text Count
        Word Count
"""

import re
from pathlib import Path
from collections import defaultdict


# --- Configuration ---
CORPUS_ROOT = Path("corpus/07_tagged")
OUTPUT_DIR = Path("corpus_size")
OUTPUT_FILE = OUTPUT_DIR / "corpus_size.tsv"

DECADE_PATTERN = re.compile(r"^\d{4}$")
VALID_TOKEN_PATTERN = re.compile(r"^[A-Za-z]")


# --- Counters ---
total_files = 0
total_words = 0

file_counts_decade = defaultdict(int)
word_counts_decade = defaultdict(int)


def natural_sort_key(text):
    """Return a natural-sort key that treats digit runs as integers."""
    parts = re.split(r"(\d+)", str(text))
    return [int(part) if part.isdigit() else part.lower() for part in parts]


def count_tokens_in_tagged_file(path: Path) -> int:
    """
    Count token lines in a TreeTagger output file.

    Each valid tagged token line counts as one word/token.
    """
    words = 0

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            if not VALID_TOKEN_PATTERN.match(line):
                continue

            parts = line.split()

            if len(parts) >= 3:
                words += 1

    return words


def main():
    global total_files, total_words

    if not CORPUS_ROOT.exists():
        raise FileNotFoundError(f"Corpus directory does not exist: {CORPUS_ROOT}")

    if not CORPUS_ROOT.is_dir():
        raise NotADirectoryError(f"Corpus path is not a directory: {CORPUS_ROOT}")

    decade_dirs = sorted(
        [
            path for path in CORPUS_ROOT.iterdir()
            if path.is_dir() and DECADE_PATTERN.match(path.name)
        ],
        key=lambda path: natural_sort_key(path.name),
    )

    if not decade_dirs:
        raise FileNotFoundError(
            f"No decade folders found under {CORPUS_ROOT}. "
            "Expected folders such as 1950, 1960, 1970, etc."
        )

    for decade_dir in decade_dirs:
        decade = decade_dir.name

        text_files = sorted(
            decade_dir.glob("*.txt"),
            key=lambda path: natural_sort_key(path.name),
        )

        for text_file in text_files:
            words = count_tokens_in_tagged_file(text_file)

            file_counts_decade[decade] += 1
            word_counts_decade[decade] += words

            total_files += 1
            total_words += words

    OUTPUT_DIR.mkdir(exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        f.write("Strata\tText Count\tWord Count\n")

        for decade in sorted(file_counts_decade, key=natural_sort_key):
            f.write(
                f"{decade}\t"
                f"{file_counts_decade[decade]}\t"
                f"{word_counts_decade[decade]}\n"
            )

        f.write("\n")
        f.write(f"overall\t{total_files}\t{total_words}\n")

    print(f"Corpus sizes saved to {OUTPUT_FILE}")
    print(f"Total texts: {total_files}")
    print(f"Total words: {total_words}")


if __name__ == "__main__":
    main()