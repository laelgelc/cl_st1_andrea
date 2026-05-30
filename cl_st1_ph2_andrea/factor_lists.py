#!/usr/bin/env python3
# Updated factor_lists.py
from pathlib import Path
import os
import pandas as pd

def fmt_loading(x):
    """Format a loading value with no leading zero (e.g., .45, -.62)."""
    s = f"{x:.2f}"
    if s.startswith("0"):
        return s[1:]       # 0.45  → .45
    if s.startswith("-0"):
        return "-" + s[2:] # -0.45 → -.45
    return s              # fallback

# Step 1: Load rotated matrix
rotated = pd.read_csv("sas/output_cl_st1_ph3_andressa/rotated.csv")

# Step 2: Load index_keywords.txt
id_to_word = {}
with open("index_keywords.txt", encoding="utf-8") as f:
    for line in f:
        parts = line.strip().split()
        if parts:
            id_num, word = parts
            id_to_word[f"v{id_num}"] = word

# Step 3: Prepare output folders
os.makedirs("factors", exist_ok=True)
os.makedirs("factors/var_id", exist_ok=True)
os.makedirs("factors/primary_loadings", exist_ok=True)

# Step 4: Main loop
cutoff = 0.3
results = {}

for idx, row in rotated.iterrows():
    varname = row["_NAME_"]
    word = id_to_word.get(varname, varname)

    # Skip rows without primary loading
    if pd.isna(row["pole"]) or pd.isna(row["factor"]) or row["loaded"] != 1:
        continue

    primary_factor = row["factor"]
    primary_pole = int(row["pole"])

    # Build primary output filename
    factor_id = primary_factor.replace("fac", "f")
    primary_outfile = f"factors/{factor_id}_{'pos' if primary_pole == 1 else 'neg'}.txt"

    if primary_outfile not in results:
        results[primary_outfile] = []

    # Correct mapping: fac1 -> Factor1
    factor_column = primary_factor.replace("fac", "Factor")

    primary_score = row.get(factor_column, None)

    if pd.isna(primary_score):
        continue

    # Format primary loading
    formatted_score = fmt_loading(primary_score)    
    entry = f"{word} ({formatted_score})"

    results[primary_outfile].append(entry)

    # Step 5: Handle secondary loadings
    for col in rotated.columns:
        if col.startswith("Factor") and col != factor_column:
            value = row[col]
            if abs(value) >= cutoff:
                sec_pole = 1 if value > 0 else -1
                sec_factor_num = col.replace("Factor", "")
                sec_outfile = f"factors/f{sec_factor_num}_{'pos' if sec_pole == 1 else 'neg'}.txt"

                if sec_outfile not in results:
                    results[sec_outfile] = []

                formatted_sec = fmt_loading(value)
                sec_entry = f"({word} ({formatted_sec}))"
                results[sec_outfile].append(sec_entry)

# Step 6: Sort and save all outputs
for outfile, entries in results.items():
    # Extract loading values for sorting
    def extract_loading(entry):
        parts = entry.replace("(", "").replace(")", "").split()
        if len(parts) >= 2:
            try:
                return abs(float(parts[-1]))
            except ValueError:
                return 0.0
        return 0.0

    sorted_entries = sorted(entries, key=extract_loading, reverse=True)
    count = len(sorted_entries)

    # Save the full word version (primary + secondary) into factors/
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(f"variables loading on this pole = {count}\n")
        f.write(", ".join(sorted_entries) + "\n")

    # Save the var_id version into factors/var_id/
    var_id_entries = []

    for entry in sorted_entries:
        parts = entry.replace("(", "").replace(")", "").split()
        if not parts:
            continue
        word_part = parts[0]

        found_id = None
        for var_id, word in id_to_word.items():
            if word == word_part:
                found_id = var_id
                break
        if found_id is None:
            found_id = word_part

        loading = parts[-1]
        if entry.startswith("("):  # secondary loading
            new_entry = f"({found_id} ({loading}))"
        else:  # primary loading
            new_entry = f"{found_id} ({loading})"

        var_id_entries.append(new_entry)

    var_outfile = Path("factors/var_id") / Path(outfile).name.replace(".txt", "_var_id.txt")
    with open(var_outfile, "w", encoding="utf-8") as f:
        f.write(f"variables loading on this pole = {count}\n")
        f.write(", ".join(var_id_entries) + "\n")

    # Save the **primary-only** word version into factors/primary_loadings/
    primary_only_entries = [e for e in sorted_entries if not e.startswith("(")]
    primary_only_count = len(primary_only_entries)

    primary_outfile_clean = Path("factors/primary_loadings") / Path(outfile).name
    with open(primary_outfile_clean, "w", encoding="utf-8") as f:
        f.write(f"variables loading on this pole = {primary_only_count}\n")
        f.write(", ".join(primary_only_entries) + "\n")

print("Done.")