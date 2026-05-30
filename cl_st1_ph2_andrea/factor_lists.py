#!/usr/bin/env python3
"""
Create readable factor-loading lists from SAS rotated.csv output.

Expected inputs:
    sas/output_<Project Name>/rotated.csv
    index_keywords.txt

Expected index_keywords.txt format:
    No header
    Space-separated
    Columns:
        keyword_id lemma

Example:
    000001 act
    000002 air
    000003 camera

Outputs:
    factors/
        f1_pos.txt
        f1_neg.txt
        ...

    factors/var_id/
        f1_pos_var_id.txt
        f1_neg_var_id.txt
        ...

    factors/primary_loadings/
        f1_pos.txt
        f1_neg.txt
        ...

The output files intentionally include a first summary line:
    variables loading on this pole = <count>
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_PROJECT = "cl_st1_ph2_andrea"
DEFAULT_SAS_OUTPUT_DIR = Path("sas") / f"output_{DEFAULT_PROJECT}"
DEFAULT_INDEX_FILE = Path("index_keywords.txt")
DEFAULT_OUTPUT_DIR = Path("factors")
DEFAULT_CUTOFF = 0.3


def fmt_loading(value: float) -> str:
    """Format a loading value with no leading zero, e.g. .45, -.62."""
    text = f"{value:.2f}"

    if text.startswith("0"):
        return text[1:]

    if text.startswith("-0"):
        return "-" + text[2:]

    return text


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Create readable factor-loading lists from SAS rotated.csv output."
    )

    parser.add_argument(
        "--sas-output-dir",
        default=str(DEFAULT_SAS_OUTPUT_DIR),
        help=(
            "Directory containing rotated.csv, usually "
            "sas/output_<Project Name>."
        ),
    )
    parser.add_argument(
        "--index-file",
        default=str(DEFAULT_INDEX_FILE),
        help="Path to index_keywords.txt.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for factor lists.",
    )
    parser.add_argument(
        "--cutoff",
        type=float,
        default=DEFAULT_CUTOFF,
        help="Minimum absolute loading for secondary loadings.",
    )

    return parser.parse_args()


def load_keyword_index(index_file: Path) -> dict[str, str]:
    """
    Load keyword ID to lemma mapping.

    Expected format:
        000001 act
        000002 air

    Returns:
        v000001 -> act
        v000002 -> air
    """
    if not index_file.exists():
        raise FileNotFoundError(f"Keyword index file not found: {index_file}")

    id_to_word: dict[str, str] = {}

    with index_file.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()

            if not line:
                continue

            parts = line.split(maxsplit=1)

            if len(parts) != 2:
                raise ValueError(
                    f"Unexpected format in {index_file} at line {line_number}: "
                    "expected keyword_id and lemma."
                )

            keyword_id, word = parts

            if line_number == 1 and keyword_id.lower() in {"keyword_id", "id"}:
                raise ValueError(
                    f"{index_file} appears to contain a header. "
                    "Expected a headerless file."
                )

            if not keyword_id.isdigit():
                raise ValueError(
                    f"Invalid keyword ID in {index_file} at line {line_number}: "
                    f"{keyword_id}"
                )

            id_to_word[f"v{keyword_id}"] = word

    if not id_to_word:
        raise ValueError(f"No keyword entries found in {index_file}")

    return id_to_word


def load_rotated(rotated_path: Path) -> pd.DataFrame:
    """Load and validate SAS rotated.csv output."""
    if not rotated_path.exists():
        raise FileNotFoundError(f"Rotated CSV file not found: {rotated_path}")

    rotated = pd.read_csv(rotated_path)

    required_columns = {"_NAME_", "loaded", "factor", "pole"}
    missing_columns = required_columns - set(rotated.columns)

    if missing_columns:
        raise ValueError(
            f"{rotated_path} is missing required columns: "
            f"{', '.join(sorted(missing_columns))}"
        )

    factor_columns = [
        column for column in rotated.columns
        if column.startswith("Factor")
    ]

    if not factor_columns:
        raise ValueError(f"No Factor columns found in {rotated_path}")

    return rotated


def extract_loading(entry: str) -> float:
    """Extract absolute loading value from a formatted entry for sorting."""
    parts = entry.replace("(", "").replace(")", "").split()

    if len(parts) >= 2:
        try:
            return abs(float(parts[-1]))
        except ValueError:
            return 0.0

    return 0.0


def build_word_to_var_id(id_to_word: dict[str, str]) -> dict[str, str]:
    """Build reverse lookup from lemma to variable ID."""
    return {
        word: var_id
        for var_id, word in id_to_word.items()
    }


def write_factor_outputs(
        results: dict[Path, list[str]],
        output_dir: Path,
        id_to_word: dict[str, str],
) -> None:
    """Write word, variable-ID, and primary-only factor-list outputs."""
    var_id_dir = output_dir / "var_id"
    primary_dir = output_dir / "primary_loadings"

    output_dir.mkdir(parents=True, exist_ok=True)
    var_id_dir.mkdir(parents=True, exist_ok=True)
    primary_dir.mkdir(parents=True, exist_ok=True)

    word_to_var_id = build_word_to_var_id(id_to_word)

    for outfile, entries in results.items():
        sorted_entries = sorted(entries, key=extract_loading, reverse=True)
        count = len(sorted_entries)

        # Save full word version: primary plus secondary loadings.
        with outfile.open("w", encoding="utf-8") as f:
            f.write(f"variables loading on this pole = {count}\n")
            f.write(", ".join(sorted_entries) + "\n")

        # Save variable-ID version.
        var_id_entries = []

        for entry in sorted_entries:
            parts = entry.replace("(", "").replace(")", "").split()

            if not parts:
                continue

            word_part = parts[0]
            found_id = word_to_var_id.get(word_part, word_part)
            loading = parts[-1]

            if entry.startswith("("):
                new_entry = f"({found_id} ({loading}))"
            else:
                new_entry = f"{found_id} ({loading})"

            var_id_entries.append(new_entry)

        var_outfile = var_id_dir / outfile.name.replace(".txt", "_var_id.txt")

        with var_outfile.open("w", encoding="utf-8") as f:
            f.write(f"variables loading on this pole = {count}\n")
            f.write(", ".join(var_id_entries) + "\n")

        # Save primary-only word version.
        primary_only_entries = [
            entry for entry in sorted_entries
            if not entry.startswith("(")
        ]
        primary_only_count = len(primary_only_entries)

        primary_outfile = primary_dir / outfile.name

        with primary_outfile.open("w", encoding="utf-8") as f:
            f.write(f"variables loading on this pole = {primary_only_count}\n")
            f.write(", ".join(primary_only_entries) + "\n")


def main() -> None:
    """Run factor-list generation."""
    args = parse_args()

    sas_output_dir = Path(args.sas_output_dir)
    rotated_path = sas_output_dir / "rotated.csv"
    index_file = Path(args.index_file)
    output_dir = Path(args.output_dir)
    cutoff = args.cutoff

    if cutoff < 0:
        raise ValueError("--cutoff must be non-negative")

    rotated = load_rotated(rotated_path)
    id_to_word = load_keyword_index(index_file)

    output_dir.mkdir(parents=True, exist_ok=True)

    results: dict[Path, list[str]] = {}

    factor_columns = [
        column for column in rotated.columns
        if column.startswith("Factor")
    ]

    for _, row in rotated.iterrows():
        varname = row["_NAME_"]
        word = id_to_word.get(varname, varname)

        # Skip rows without primary loading.
        if (
                pd.isna(row["pole"])
                or pd.isna(row["factor"])
                or row["loaded"] != 1
        ):
            continue

        primary_factor = str(row["factor"])
        primary_pole = int(row["pole"])

        factor_id = primary_factor.replace("fac", "f")
        pole_label = "pos" if primary_pole == 1 else "neg"
        primary_outfile = output_dir / f"{factor_id}_{pole_label}.txt"

        results.setdefault(primary_outfile, [])

        # Mapping: fac1 -> Factor1
        factor_column = primary_factor.replace("fac", "Factor")
        primary_score = row.get(factor_column, None)

        if pd.isna(primary_score):
            continue

        formatted_score = fmt_loading(float(primary_score))
        entry = f"{word} ({formatted_score})"

        results[primary_outfile].append(entry)

        # Secondary loadings.
        for column in factor_columns:
            if column == factor_column:
                continue

            value = row[column]

            if pd.isna(value):
                continue

            if abs(value) >= cutoff:
                secondary_pole = 1 if value > 0 else -1
                secondary_factor_num = column.replace("Factor", "")
                secondary_pole_label = "pos" if secondary_pole == 1 else "neg"
                secondary_outfile = (
                        output_dir
                        / f"f{secondary_factor_num}_{secondary_pole_label}.txt"
                )

                results.setdefault(secondary_outfile, [])

                formatted_secondary = fmt_loading(float(value))
                secondary_entry = f"({word} ({formatted_secondary}))"

                results[secondary_outfile].append(secondary_entry)

    if not results:
        raise ValueError(
            "No factor-loading entries were generated. "
            "Check rotated.csv, loaded column, factor column, and cutoff."
        )

    write_factor_outputs(
        results=results,
        output_dir=output_dir,
        id_to_word=id_to_word,
    )

    print("Done.")
    print(f"Rotated input: {rotated_path}")
    print(f"Keyword index: {index_file}")
    print(f"Output directory: {output_dir}")
    print(f"Factor-list files written: {len(results)}")


if __name__ == "__main__":
    main()