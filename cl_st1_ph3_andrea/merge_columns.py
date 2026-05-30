#!/usr/bin/env python3
from pathlib import Path


# --- Configuration ---
CLEAN_DIR = Path("columns_clean")
COLUMNS_DIR = Path("columns")
OUTPUT_DIR = Path("sas")
OUTPUT_FILE = OUTPUT_DIR / "counts.txt"


def main():
    # Ensure output directory exists.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Read the reference columns file to get file_id and decade.
    ref_file = COLUMNS_DIR / "000001.txt"
    if not ref_file.exists():
        raise FileNotFoundError(f"Reference file not found: {ref_file}")

    with ref_file.open("r", encoding="utf-8") as f:
        ref_lines = [line.strip().split() for line in f if line.strip()]

    if not ref_lines:
        raise ValueError(f"Reference file is empty: {ref_file}")

    # Expected columns format:
    #   file_id decade presence
    for line_number, cols in enumerate(ref_lines, start=1):
        if len(cols) != 3:
            raise ValueError(
                f"Unexpected format in {ref_file} at line {line_number}: "
                f"expected 3 fields, found {len(cols)}"
            )

    # Keep file_id and decade; remove presence from the reference keyword column.
    initial_rows = [cols[:-1] for cols in ref_lines]

    # Step 2: Get sorted list of all clean column files.
    clean_files = sorted(CLEAN_DIR.glob("*.txt"))

    if not clean_files:
        raise FileNotFoundError(f"No clean column files found in {CLEAN_DIR}")

    # Step 3: Read each clean file and append its binary flags to initial_rows.
    for clean_file in clean_files:
        expected_keyword_id = clean_file.stem

        with clean_file.open("r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        if not lines:
            raise ValueError(f"Clean column file is empty: {clean_file}")

        keyword_id = lines[0]
        if keyword_id != expected_keyword_id:
            raise ValueError(
                f"Keyword ID mismatch in {clean_file.name}: "
                f"first line is {keyword_id}, expected {expected_keyword_id}"
            )

        # First line is the keyword ID; remaining lines are binary flags.
        flags = lines[1:]

        if len(flags) != len(initial_rows):
            raise ValueError(
                f"Row count mismatch in {clean_file.name}: "
                f"{len(flags)} flags vs {len(initial_rows)} reference rows"
            )

        for i, flag in enumerate(flags):
            if flag not in {"0", "1"}:
                raise ValueError(
                    f"Invalid binary flag in {clean_file.name} at data row {i + 1}: {flag}"
                )

            initial_rows[i].append(flag)

    # Step 4: Write merged data to sas/counts.txt.
    # Output format:
    #   file_id decade kw000001 kw000002 ...
    # No header; space-separated.
    with OUTPUT_FILE.open("w", encoding="utf-8") as out:
        for row in initial_rows:
            out.write(" ".join(row) + "\n")

    print(f"Merged data written to {OUTPUT_FILE}")
    print(f"Rows written: {len(initial_rows)}")
    print(f"Keyword columns merged: {len(clean_files)}")


if __name__ == "__main__":
    main()