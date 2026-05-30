#!/usr/bin/env python3
import re
from pathlib import Path
from collections import defaultdict

# --- CONFIGURATION ---
CORPUS_ROOT = Path('corpus/07_tagged')
VALID_LINE_PATTERN = re.compile(r'^[A-Za-z]')

# --- GLOBAL COUNTERS ---
total_files = 0
total_words = 0

# By source (human vs ai)
file_counts_source = defaultdict(int)
word_counts_source = defaultdict(int)

# By model (gemma, gpt, qwen, etc)
file_counts_model = defaultdict(int)
word_counts_model = defaultdict(int)

# By season (derived from filename)
file_counts_season = defaultdict(int)
word_counts_season = defaultdict(int)

# By source + model
file_counts_source_model = defaultdict(lambda: defaultdict(int))
word_counts_source_model = defaultdict(lambda: defaultdict(int))


# -------------------------------------------------
def extract_season(filename_stem: str) -> str:
    """
    Extracts season = 2nd and 3rd digits of filename stem.
    Example: a0712_xxx -> season = "07"
    """
    if len(filename_stem) >= 3 and filename_stem[1].isdigit() and filename_stem[2].isdigit():
        return filename_stem[1:3]
    return "unknown"


# -------------------------------------------------
def process_file(path: Path, source: str, model: str, season: str):
    global total_files, total_words

    # File counter
    file_counts_source[source] += 1
    file_counts_model[model] += 1
    file_counts_season[season] += 1
    file_counts_source_model[source][model] += 1
    total_files += 1

    # Word counting
    words = 0
    with path.open(encoding='utf-8') as f:
        for line in f:
            if VALID_LINE_PATTERN.match(line):
                words += len(line.split())

    # Word counters
    word_counts_source[source] += words
    word_counts_model[model] += words
    word_counts_season[season] += words
    word_counts_source_model[source][model] += words
    total_words += words


# -------------------------------------------------
# WALK THE CORPUS
for txt in CORPUS_ROOT.rglob("*.txt"):
    model_folder = txt.parent.name  # e.g., "gemma", "human", "gpt"

    # SOURCE
    source = "human" if model_folder == "human" else "ai"

    # MODEL
    model = model_folder

    # SEASON (from filename stem)
    season = extract_season(txt.stem)

    process_file(txt, source, model, season)


# -------------------------------------------------
# WRITE OUT TSV
out_dir = Path('corpus_size')
out_dir.mkdir(exist_ok=True)
out = out_dir / 'corpus_size.tsv'

with out.open('w', encoding='utf-8') as f:
    f.write("Strata\tText Count\tWord Count\n")

    # by source
    for src in sorted(file_counts_source):
        f.write(f"{src}\t{file_counts_source[src]}\t{word_counts_source[src]}\n")
    f.write("\n")

    # by model
    for mdl in sorted(file_counts_model):
        f.write(f"{mdl}\t{file_counts_model[mdl]}\t{word_counts_model[mdl]}\n")
    f.write("\n")

    # by source/model combined
    f.write("# Source/Model breakdown\n")
    for src in sorted(file_counts_source_model):
        for mdl in sorted(file_counts_source_model[src]):
            f.write(f"{src}/{mdl}\t"
                    f"{file_counts_source_model[src][mdl]}\t"
                    f"{word_counts_source_model[src][mdl]}\n")
    f.write("\n")

    # by season
    for ss in sorted(file_counts_season):
        f.write(f"{ss}\t{file_counts_season[ss]}\t{word_counts_season[ss]}\n")
    f.write("\n")

    # overall
    f.write(f"overall\t{total_files}\t{total_words}\n")

print(f"Corpus sizes saved to {out}")