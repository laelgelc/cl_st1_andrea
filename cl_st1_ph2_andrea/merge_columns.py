#!/usr/bin/env python3
import os
from pathlib import Path

# --- Configuration ---
CLEAN_DIR = Path("columns_clean")
COLUMNS_DIR = Path("columns")
OUTPUT_DIR = Path("sas")
OUTPUT_FILE = OUTPUT_DIR / "counts.txt"

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Step 1: Read the reference columns file (000001.txt) to get the first four fields
ref_file = COLUMNS_DIR / "000001.txt"
if not ref_file.exists():
    raise FileNotFoundError(f"Reference file not found: {ref_file}")

with ref_file.open("r", encoding="utf-8") as f:
    ref_lines = [line.strip().split() for line in f if line.strip()]

# Extract the first four columns from each line
initial_rows = [cols[:-1] for cols in ref_lines]

# Step 2: Get sorted list of all clean column files
clean_files = sorted(CLEAN_DIR.glob("*.txt"))

# Step 3: Read each clean file and append its flags to initial_rows
for clean_file in clean_files:
    with clean_file.open("r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    # Skip the header line (keyword ID), process only flag lines
    flags = lines[1:]
    if len(flags) != len(initial_rows):
        raise ValueError(
            f"Row count mismatch in {clean_file.name}: "
            f"{len(flags)} flags vs {len(initial_rows)} reference rows"
        )
    # Append each flag to the corresponding row
    for i, flag in enumerate(flags):
        initial_rows[i].append(flag)

# Step 4: Write merged data to sas/data.txt
with OUTPUT_FILE.open("w", encoding="utf-8") as out:
    for row in initial_rows:
        out.write(" ".join(row) + "\n")

print(f"Merged data written to {OUTPUT_FILE}")