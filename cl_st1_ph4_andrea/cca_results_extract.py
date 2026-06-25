#!/usr/bin/env python3
"""Extract canonical-structure CCA tables from a SAS HTML results file.

The programme extracts two tables from the "Canonical Structure" section:

1. "Correlations Between the VAR Variables and Their Canonical Variables"
   -> cca_var.json

2. "Correlations Between the WITH Variables and Their Canonical Variables"
   -> cca_with.json

Usage:
    python cca_results_extract.py HTML_FILE

    python cca_results_extract.py HTML_FILE --output-dir OUTPUT_DIR

Arguments:
    HTML_FILE
        Path to the SAS CANCORR HTML results export.

Options:
    --output-dir OUTPUT_DIR
        Directory where the JSON files will be written. If omitted, the files
        are written to the current working directory.

Examples:
    python cca_results_extract.py output_cl_st1_ph4_andrea_CCA/tv_commercials_cca-results.html

    python cca_results_extract.py \
        output_cl_st1_ph4_andrea_CCA/tv_commercials_cca-results.html \
        --output-dir output_cl_st1_ph4_andrea_CCA

Outputs:
    cca_var.json
        JSON array containing the VAR canonical-structure correlations.

    cca_with.json
        JSON array containing the WITH canonical-structure correlations.

Notes:
    The programme expects a SAS CANCORR HTML file containing a section titled
    "Canonical Structure". Within that section, it uses exact normalised table
    title matching, so it extracts only the two intended canonical-structure
    tables and ignores later cross-correlation tables with similar titles.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from bs4.element import Tag


CANONICAL_STRUCTURE_TITLE = "Canonical Structure"

VAR_TABLE_TITLE = (
    "Correlations Between the VAR Variables and Their Canonical Variables"
)

WITH_TABLE_TITLE = (
    "Correlations Between the WITH Variables and Their Canonical Variables"
)

VAR_OUTPUT_FILENAME = "cca_var.json"
WITH_OUTPUT_FILENAME = "cca_with.json"


def normalise_text(value: str | None) -> str:
    """Normalise whitespace and HTML-extracted text."""
    if value is None:
        return ""

    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def parse_number(value: str | None) -> float | None:
    """Convert SAS table cell text to float or None."""
    text = normalise_text(value)

    if text in {"", "."}:
        return None

    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"Could not parse numeric value: {text!r}") from exc


def make_soup(html_file: Path) -> BeautifulSoup:
    """Read an HTML file and create a BeautifulSoup document."""
    html = html_file.read_text(encoding="utf-8")

    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def find_canonical_structure_start(soup: BeautifulSoup) -> Tag:
    """Find the heading for the Canonical Structure section."""
    for node in soup.find_all(True):
        if normalise_text(node.get_text(" ")) == CANONICAL_STRUCTURE_TITLE:
            return node

    raise ValueError(
        f"Could not find section titled '{CANONICAL_STRUCTURE_TITLE}'."
    )


def get_table_title(table: Tag) -> str:
    """Extract the first header-row title from an HTML table."""
    first_header_row = table.find("thead")
    if first_header_row is None:
        return ""

    first_row = first_header_row.find("tr")
    if first_row is None:
        return ""

    first_cells = first_row.find_all(["th", "td"])
    if not first_cells:
        return ""

    return normalise_text(first_cells[0].get_text(" "))


def find_target_table(start_node: Tag, target_title: str) -> Tag:
    """Find a table after the selected section with an exact title match."""
    for node in start_node.find_all_next("table"):
        table_title = get_table_title(node)

        if table_title == target_title:
            return node

    raise ValueError(f"Could not find table: {target_title}")


def extract_headers(table: Tag, table_title: str) -> list[str]:
    """Extract column headers from the second header row."""
    thead = table.find("thead")
    if thead is None:
        raise ValueError(
            f"Malformed table '{table_title}': missing table header."
        )

    header_rows = thead.find_all("tr")
    if len(header_rows) < 2:
        raise ValueError(
            f"Malformed table '{table_title}': expected at least 2 header rows."
        )

    column_header_row = header_rows[1]
    header_cells = column_header_row.find_all(["th", "td"])

    if not header_cells:
        raise ValueError(
            f"Malformed table '{table_title}': no column headers found."
        )

    headers = [normalise_text(cell.get_text(" ")) for cell in header_cells]

    if not headers[0]:
        headers[0] = "Variable"

    if headers[0] != "Variable":
        headers.insert(0, "Variable")

    return headers


def extract_body_rows(table: Tag, table_title: str) -> list[list[str]]:
    """Extract body rows as raw text cells."""
    tbody = table.find("tbody")
    if tbody is None:
        raise ValueError(f"Malformed table '{table_title}': missing table body.")

    raw_rows: list[list[str]] = []

    for row in tbody.find_all("tr", recursive=False):
        cells = row.find_all(["th", "td"], recursive=False)

        if not cells:
            continue

        raw_rows.append(
            [normalise_text(cell.get_text(" ")) for cell in cells]
        )

    if not raw_rows:
        raise ValueError(f"Malformed table '{table_title}': no body rows found.")

    return raw_rows


def extract_table(table: Tag) -> list[dict[str, Any]]:
    """Convert an HTML table into a list of dictionaries."""
    table_title = get_table_title(table)

    if not table_title:
        raise ValueError("Malformed table: missing table title.")

    headers = extract_headers(table, table_title)
    raw_rows = extract_body_rows(table, table_title)

    extracted_rows: list[dict[str, Any]] = []

    for raw_row in raw_rows:
        row_name = raw_row[0] if raw_row else "UNKNOWN"

        if len(raw_row) != len(headers):
            raise ValueError(
                f"Malformed table '{table_title}': "
                f"expected {len(headers)} columns but found "
                f"{len(raw_row)} in row {row_name}."
            )

        row_data: dict[str, Any] = {"Variable": raw_row[0]}

        for header, value in zip(headers[1:], raw_row[1:]):
            row_data[header] = parse_number(value)

        extracted_rows.append(row_data)

    return extracted_rows


def write_json(data: list[dict[str, Any]], output_path: Path) -> None:
    """Write extracted rows to a pretty-printed UTF-8 JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as outfile:
        json.dump(data, outfile, ensure_ascii=False, indent=2)
        outfile.write("\n")


def extract_cca_results(html_file: Path, output_dir: Path) -> tuple[Path, Path]:
    """Extract the required CCA tables and write JSON outputs."""
    if not html_file.exists():
        raise FileNotFoundError(f"Input HTML file not found: {html_file}")

    soup = make_soup(html_file)
    canonical_structure_start = find_canonical_structure_start(soup)

    var_table = find_target_table(canonical_structure_start, VAR_TABLE_TITLE)
    with_table = find_target_table(canonical_structure_start, WITH_TABLE_TITLE)

    var_data = extract_table(var_table)
    with_data = extract_table(with_table)

    var_output_path = output_dir / VAR_OUTPUT_FILENAME
    with_output_path = output_dir / WITH_OUTPUT_FILENAME

    write_json(var_data, var_output_path)
    write_json(with_data, with_output_path)

    return var_output_path, with_output_path


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Extract the first two canonical-structure tables from a SAS "
            "CANCORR HTML results file into JSON."
        )
    )

    parser.add_argument(
        "html_file",
        type=Path,
        help="Path to the SAS HTML results file.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help=(
            "Directory where cca_var.json and cca_with.json will be written. "
            "Defaults to the current working directory."
        ),
    )

    return parser


def main() -> None:
    """Run the command-line interface."""
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        var_output_path, with_output_path = extract_cca_results(
            html_file=args.html_file,
            output_dir=args.output_dir,
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"Wrote {var_output_path}")
    print(f"Wrote {with_output_path}")


if __name__ == "__main__":
    main()