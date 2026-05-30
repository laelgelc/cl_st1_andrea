#!/usr/bin/env python3
import os
from pathlib import Path

# === Configuration ===
KEYWORD_FILE = Path("corpus/09_kw_selected/keywords.txt")
TAGGED_BASE  = Path("corpus/07_tagged")
OUTPUT_DIR   = Path("columns")
CLEAN_DIR    = Path("columns_clean")
INDEX_FILE   = Path("index_keywords.txt")
FILE_IDS     = Path("file_ids.txt")   # <-- renamed

# === Step 1: Load consolidated keywords ===
lemmas = [
    kw.strip()
    for kw in KEYWORD_FILE.read_text(encoding="utf-8").splitlines()
    if kw.strip()
]

# Ensure stable, duplicate-free keyword list (keywords.txt is usually already unique)
lemmas = sorted(set(lemmas))

# === Step 2: Create index map for unique lemmas (proper numbering) ===
lemma_index = {lemma: f"{i+1:06d}" for i, lemma in enumerate(lemmas)}

# === Step 3: Collect all tagged text files ===
text_paths = []
for folder in sorted(TAGGED_BASE.iterdir()):
    if not folder.is_dir():
        continue
    for text_file in sorted(folder.rglob("*.txt")):
        text_paths.append(text_file)

# === Step 4: Assign file IDs ===
file_id_map = {}
with FILE_IDS.open("w", encoding="utf-8") as fidx:
    for i, text_file in enumerate(text_paths, 1):
        fid = f"t{i:06d}"
        file_id_map[text_file] = fid
        rel = text_file.relative_to(TAGGED_BASE).as_posix()
        fidx.write(f"{fid} {rel}\n")

# === Step 5: Read each text and record lemma presence ===
text_infos = []
for text_file in text_paths:
    fid = file_id_map[text_file]

    # Top-level folder under corpus/07_tagged/
    folder = text_file.relative_to(TAGGED_BASE).parts[0]

    # ----- SOURCE -----
    source = "human" if folder == "human" else "ai"

    # ----- PROMPT -----
    if folder == "human":
        prompt = "human"
    elif folder.startswith("generic_"):
        prompt = "generic"
    elif folder.startswith("summary_guided_"):
        prompt = "summary_guided"
    else:
        prompt = "unknown"

    # ----- MODEL -----
    # Expected folder formats:
    #   human
    #   generic_gpt
    #   summary_guided_gpt
    if folder == "human":
        model = "human"
    else:
        # model is whatever comes after the last underscore
        # generic_gpt -> gpt
        # summary_guided_gpt -> gpt
        model = folder.split("_")[-1].lower()

    # Extract lemmas from 3rd column (word, tag, lemma) in tagged files
    present = set()
    with text_file.open(encoding="utf-8") as tf:
        for line in tf:
            parts = line.strip().split()
            if len(parts) >= 3:
                present.add(parts[2])

    text_infos.append({
        "id": fid,
        "name": text_file.name,
        "source": source,
        "prompt": prompt,
        "model": model,
        "lemmas": present
    })

# === Step 6: Write one column file per lemma ===
OUTPUT_DIR.mkdir(exist_ok=True)

for lemma in lemmas:
    lemma_id = lemma_index[lemma]
    outpath = OUTPUT_DIR / f"{lemma_id}.txt"

    with outpath.open("w", encoding="utf-8") as outf:
        for info in text_infos:
            has_kw = 1 if lemma in info["lemmas"] else 0
            outf.write(
                f"{info['id']} {info['prompt']} {info['model']} "
                f"{info['source']} {has_kw}\n"
            )

# === Step 7: Save lemma index (consistent with column filenames) ===
with INDEX_FILE.open("w", encoding="utf-8") as idxf:
    for lemma in lemmas:
        idxf.write(f"{lemma_index[lemma]} {lemma}\n")

# === Step 8: Produce clean column files ===
CLEAN_DIR.mkdir(exist_ok=True)

for lemma in lemmas:
    lemma_id = lemma_index[lemma]
    src = OUTPUT_DIR / f"{lemma_id}.txt"
    dst = CLEAN_DIR / f"{lemma_id}.txt"

    lines = src.read_text(encoding="utf-8").splitlines()

    with dst.open("w", encoding="utf-8") as fout:
        fout.write(f"{lemma_id}\n")
        for line in lines:
            parts = line.split()
            if parts:
                fout.write(f"{parts[-1]}\n")

print("Processing complete.")
print("→ Columns in 'columns/'")
print("→ Clean binary columns in 'columns_clean/'")
print("→ File IDs saved to 'file_ids.txt'")