#!/usr/bin/env python3
"""
Generate example text extracts based on highest factor scores by decade.

For each factor:
    - positive pole: decades ranked by descending mean factor score
    - negative pole: decades ranked by ascending mean factor score
    - top decade: 20 examples
    - all other decades: 10 examples each
    - skip any file where the factor score == 0

The project name is inferred from the current working directory.

Expected inputs:
    sas/output_<project>/means_decade_f<n>.tsv
    sas/output_<project>/<project>_scores_only.tsv
    factors/f<n>_pos.txt
    factors/f<n>_neg.txt
    file_ids.txt
    corpus/07_tagged/<Decade>/<Commercial ID>.txt

Expected file_ids.txt format:
    No header
    Space-separated
    Columns:
        file_id path

Example:
    t000001 1950/tv_com_1950_1.txt

Outputs:
    examples/f<n>_pos/*.tex
    examples/f<n>_neg/*.tex
    examples/examples.tex
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

import pandas as pd


# =============================================================================
# DEFAULTS
# =============================================================================

DEFAULT_PROJECT = Path.cwd().name
DEFAULT_BASE = Path("corpus/07_tagged")
DEFAULT_FACTOR_FOLDER = Path("factors")
DEFAULT_EXAMPLES_DIR = Path("examples")
DEFAULT_FILE_IDS_PATH = Path("file_ids.txt")


# =============================================================================
# CONFIGURATION
# =============================================================================

#STOPLIST = {
#    "edith",
#    "doorbell",
#    "michael",
#    "recorded",
#    "attempt",
#    "request",
#}

STOPLIST = {
}

# =============================================================================
# ARGUMENTS
# =============================================================================

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate LaTeX example extracts for factor poles by decade."
    )

    parser.add_argument(
        "--project",
        default=DEFAULT_PROJECT,
        help=(
            "Project name, e.g. cl_st1_ph2_andrea or cl_st1_ph3_andrea. "
            "Default: current directory name."
        ),
    )
    parser.add_argument(
        "--sas-output-dir",
        default=None,
        help=(
            "Directory containing SAS outputs. "
            "Default: sas/output_<project>."
        ),
    )
    parser.add_argument(
        "--tagged-base",
        default=str(DEFAULT_BASE),
        help="Tagged corpus root. Default: corpus/07_tagged.",
    )
    parser.add_argument(
        "--factor-folder",
        default=str(DEFAULT_FACTOR_FOLDER),
        help="Directory containing factor pole files. Default: factors.",
    )
    parser.add_argument(
        "--examples-dir",
        default=str(DEFAULT_EXAMPLES_DIR),
        help="Directory where example files will be written. Default: examples.",
    )
    parser.add_argument(
        "--file-ids",
        default=str(DEFAULT_FILE_IDS_PATH),
        help="Path to file_ids.txt. Default: file_ids.txt.",
    )
    parser.add_argument(
        "--top-decade-examples",
        type=int,
        default=20,
        help="Number of examples for the top-ranked decade.",
    )
    parser.add_argument(
        "--other-decade-examples",
        type=int,
        default=10,
        help="Number of examples for each other decade.",
    )

    return parser.parse_args()


def resolve_sas_output_dir(project: str, sas_output_dir_arg: str | None) -> Path:
    """Resolve the SAS output directory."""
    if sas_output_dir_arg is None:
        return Path("sas") / f"output_{project}"

    return Path(sas_output_dir_arg)


# =============================================================================
# HELPERS
# =============================================================================

def natural_sort_key(text: str) -> list[int | str]:
    """Return a natural-sort key that treats digit runs as integers."""
    parts = re.split(r"(\d+)", str(text))
    return [int(part) if part.isdigit() else part.lower() for part in parts]


def latex_escape(text: str) -> str:
    """Escape common LaTeX special characters."""
    replacements = {
        "\\": r"\textbackslash{}",
        "_": r"\_",
        "%": r"\%",
        "&": r"\&",
        "#": r"\#",
        "{": r"\{",
        "}": r"\}",
        "$": r"\$",
    }

    for original, escaped in replacements.items():
        text = text.replace(original, escaped)

    return text


def load_file_id_map(file_ids_path: Path) -> dict[str, str]:
    """
    Load file_id -> relative path mapping.

    Expected format:
        t000001 1950/tv_com_1950_1.txt
    """
    if not file_ids_path.exists():
        raise FileNotFoundError(f"File ID map not found: {file_ids_path}")

    id_map: dict[str, str] = {}

    with file_ids_path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()

            if not line:
                continue

            parts = line.split(maxsplit=1)

            if len(parts) != 2:
                raise ValueError(
                    f"Unexpected format in {file_ids_path} at line {line_number}: "
                    "expected file_id and path."
                )

            file_id, relative_path = parts

            if line_number == 1 and file_id.lower() in {"file_id", "filename"}:
                raise ValueError(
                    f"{file_ids_path} appears to contain a header. "
                    "Expected a headerless file."
                )

            id_map[file_id] = relative_path

    if not id_map:
        raise ValueError(f"No file IDs found in {file_ids_path}")

    return id_map


def detect_factor_columns(scores_df: pd.DataFrame) -> list[str]:
    """Detect factor-score columns named fac1, fac2, etc."""
    factor_columns = [
        column for column in scores_df.columns
        if re.fullmatch(r"fac\d+", str(column))
    ]

    if not factor_columns:
        raise RuntimeError("No fac<n> columns found in scores file.")

    return sorted(factor_columns, key=natural_sort_key)


def load_primary_lemmas(pole_file: Path) -> set[str]:
    """
    Load primary lemmas from a factor pole file.

    Secondary loadings are enclosed in parentheses and are ignored.
    """
    if not pole_file.exists():
        raise FileNotFoundError(f"Factor pole file not found: {pole_file}")

    lines = pole_file.read_text(encoding="utf-8").splitlines()[1:]
    items = " ".join(lines).split(",")

    lemmas = set()

    for item in items:
        item = item.strip()

        if not item:
            continue

        # Ignore secondary loadings, which begin with "(".
        if item.startswith("("):
            continue

        match = re.match(r"(?P<lemma>[^\s(]+)\s*\(", item)

        if match:
            lemmas.add(match.group("lemma"))

    return lemmas


def wrap_emoji_for_latex(text: str) -> str:
    """
    Wrap emoji/symbol-other characters so LuaLaTeX can render them with \\EmojiFont,
    if \\EmojiFont is defined in examples/top_header.
    """
    output = []

    for char in text:
        if unicodedata.category(char) == "So":
            output.append(r"{\EmojiFont " + char + "}")
        else:
            output.append(char)

    return "".join(output)


def annotate_text(text_path: Path, primary_lemmas: set[str]) -> tuple[list[str], set[str]]:
    """
    Read a tagged text file and bold wordforms whose lemmas are primary factor lemmas.
    """
    raw = text_path.read_text(encoding="utf-8")

    # Remove characters that can break LaTeX command structure.
    raw = raw.replace("{", "").replace("}", "").replace("\\", "")

    tokens = []
    matched = set()

    for line in raw.splitlines():
        parts = line.split()

        if len(parts) < 3:
            continue

        wordform, tag, lemma = parts[0], parts[1], parts[2]

        if lemma in primary_lemmas and lemma not in STOPLIST:
            wordform = r"\textbf{" + latex_escape(wordform) + "}"
            matched.add(lemma)
        else:
            wordform = latex_escape(wordform)

        tokens.append(wordform)

    text = " ".join(tokens)

    # Fix spacing issues.
    text = re.sub(r"\b([A-Za-z]+)\s+n['’]t\b", r"\1n't", text)
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    text = re.sub(r'\s+"', '"', text)
    text = re.sub(r'"\s+', '"', text)

    # Break sentences into paragraphs.
    paragraphs = re.split(r"([.!?])\s+(?=[A-Z])", text)
    paragraphs = [
        "".join(paragraphs[i:i + 2]).strip()
        for i in range(0, len(paragraphs), 2)
    ]
    paragraphs = [paragraph for paragraph in paragraphs if paragraph]

    paragraphs = [wrap_emoji_for_latex(paragraph) for paragraph in paragraphs]

    return paragraphs, matched


def locate_text(row: pd.Series, id_map: dict[str, str], tagged_base: Path) -> Path | None:
    """Locate the tagged text file for a row in the scores table."""
    relative_path = id_map.get(row["filename"])

    if not relative_path:
        return None

    path = tagged_base / relative_path

    if path.exists():
        return path

    return None


def read_means_file(means_file: Path, factor_number: int) -> dict[str, float]:
    """Read decade means for one factor."""
    if not means_file.exists():
        raise FileNotFoundError(f"Means file not found: {means_file}")

    means_df = pd.read_csv(means_file, sep="\t")

    mean_column = f"Mean fac{factor_number}"

    if "decade" not in means_df.columns:
        raise ValueError(f"Column 'decade' not found in {means_file}")

    if mean_column not in means_df.columns:
        raise ValueError(f"Column '{mean_column}' not found in {means_file}")

    return dict(zip(
        means_df["decade"].astype(str).str.strip(),
        means_df[mean_column],
    ))


def write_example_file(
        out_file: Path,
        env_title: str,
        env_label: str,
        paragraphs: list[str],
        matched: set[str],
) -> None:
    """Write one LaTeX textsample file."""
    with out_file.open("w", encoding="utf-8") as f:
        f.write(r"\begin{textsample}{" + env_title + r"}  \label{" + env_label + "}\n")
        f.write("\n".join(paragraphs))
        f.write("\n\n")
        f.write("% matched lemmas: " + ", ".join(sorted(matched)) + "\n")
        f.write(r"\end{textsample}" + "\n")


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    """Generate example extracts for all factors and poles."""
    args = parse_args()

    project = args.project
    sas_output_dir = resolve_sas_output_dir(project, args.sas_output_dir)
    tagged_base = Path(args.tagged_base)
    factor_folder = Path(args.factor_folder)
    examples_dir = Path(args.examples_dir)
    file_ids_path = Path(args.file_ids)

    examples_dir.mkdir(exist_ok=True, parents=True)

    scores_file = sas_output_dir / f"{project}_scores_only.tsv"

    if not scores_file.exists():
        raise FileNotFoundError(f"Scores file not found: {scores_file}")

    if not tagged_base.exists():
        raise FileNotFoundError(f"Tagged corpus directory not found: {tagged_base}")

    if not factor_folder.exists():
        raise FileNotFoundError(f"Factor folder not found: {factor_folder}")

    id_map = load_file_id_map(file_ids_path)

    scores_df = pd.read_csv(scores_file, sep="\t")

    required_columns = {"filename", "decade"}

    missing_columns = required_columns - set(scores_df.columns)

    if missing_columns:
        raise ValueError(
            f"{scores_file} is missing required columns: "
            f"{', '.join(sorted(missing_columns))}"
        )

    scores_df["filename"] = scores_df["filename"].astype(str).str.strip()
    scores_df["decade"] = scores_df["decade"].astype(str).str.strip()

    factor_columns = detect_factor_columns(scores_df)
    num_factors = len(factor_columns)

    print(f"Project: {project}")
    print(f"Scores file: {scores_file}")
    print(f"Detected {num_factors} factors.\n")

    missing_files = set()

    for factor_number in range(1, num_factors + 1):
        factor_column = f"fac{factor_number}"

        means_file = sas_output_dir / f"means_decade_f{factor_number}.tsv"
        decade_means = read_means_file(means_file, factor_number)

        for pole, ascending in (("pos", False), ("neg", True)):
            label = f"f{factor_number}_{pole}"

            print(
                f"→ {label}: selecting by decade means "
                f"(column={factor_column}, ascending={ascending})"
            )

            ranked_decades = sorted(
                decade_means.keys(),
                key=lambda decade: decade_means[decade],
                reverse=not ascending,
            )

            if not ranked_decades:
                print(f"  No decades found for {label}; skipping.")
                continue

            top_decade = ranked_decades[0]
            other_decades = ranked_decades[1:]

            primary_lemmas = load_primary_lemmas(factor_folder / f"{label}.txt")

            sorted_df = scores_df.sort_values(by=factor_column, ascending=ascending)

            out_dir = examples_dir / label
            out_dir.mkdir(parents=True, exist_ok=True)

            example_id = 1

            # Top decade: more examples.
            top_decade_df = sorted_df[sorted_df["decade"] == top_decade]

            for _, row in top_decade_df.iterrows():
                if row[factor_column] == 0:
                    continue

                if example_id > args.top_decade_examples:
                    break

                text_path = locate_text(row, id_map, tagged_base)

                if not text_path or not text_path.exists():
                    missing_files.add(row["filename"])
                    continue

                paragraphs, matched = annotate_text(text_path, primary_lemmas)

                raw_filename = id_map.get(row["filename"], row["filename"])
                latex_filename = latex_escape(raw_filename)
                decade_latex = latex_escape(top_decade)

                env_title = (
                    f"{pole.upper()} Dim {factor_number} – {decade_latex} – "
                    f"Score {row[factor_column]:.2f} – {latex_filename}"
                )
                env_label = f"ex:{label}_{example_id:03d}"

                out_file = out_dir / f"{label}_{example_id:03d}.tex"

                write_example_file(
                    out_file=out_file,
                    env_title=env_title,
                    env_label=env_label,
                    paragraphs=paragraphs,
                    matched=matched,
                )

                example_id += 1

            # Other decades: fewer examples each.
            for decade in other_decades:
                decade_df = sorted_df[sorted_df["decade"] == decade]

                count = 0

                for _, row in decade_df.iterrows():
                    if row[factor_column] == 0:
                        continue

                    if count >= args.other_decade_examples:
                        break

                    text_path = locate_text(row, id_map, tagged_base)

                    if not text_path or not text_path.exists():
                        missing_files.add(row["filename"])
                        continue

                    paragraphs, matched = annotate_text(text_path, primary_lemmas)

                    raw_filename = id_map.get(row["filename"], row["filename"])
                    latex_filename = latex_escape(raw_filename)
                    decade_latex = latex_escape(decade)

                    env_title = (
                        f"{pole.upper()} Dim {factor_number} – {decade_latex} – "
                        f"Score {row[factor_column]:.2f} – {latex_filename}"
                    )
                    env_label = f"ex:{label}_{example_id:03d}"

                    out_file = out_dir / f"{label}_{example_id:03d}.tex"

                    write_example_file(
                        out_file=out_file,
                        env_title=env_title,
                        env_label=env_label,
                        paragraphs=paragraphs,
                        matched=matched,
                    )

                    count += 1
                    example_id += 1

            print(f"  ✓ Wrote {example_id - 1} examples for {label}\n")

    if missing_files:
        missing_path = Path("missing_files.txt")
        missing_path.write_text("\n".join(sorted(missing_files)), encoding="utf-8")
        print(f"⚠ Missing files written to {missing_path}")

    top_header_path = examples_dir / "top_header"

    if not top_header_path.exists():
        print(
            "\n⚠ top_header missing. "
            "Create examples/top_header before compiling LaTeX.\n"
        )
        return

    master = examples_dir / "examples.tex"

    preamble = top_header_path.read_text(encoding="utf-8")

    with master.open("w", encoding="utf-8") as out:
        out.write(preamble + "\n\n")
        out.write(r"\begin{document}" + "\n\n")
        out.write(r"\maketitle" + "\n\n")
        out.write(r"\tableofcontents" + "\n\n")

        for factor_number in range(1, num_factors + 1):
            for pole in ("pos", "neg"):
                label = f"f{factor_number}_{pole}"
                out.write(r"\section{" + f"{pole.upper()} Dim {factor_number}" + "}\n\n")

                label_dir = examples_dir / label

                if not label_dir.exists():
                    continue

                for tex_file in sorted(label_dir.glob("*.tex"), key=lambda p: natural_sort_key(p.name)):
                    out.write(r"\input{" + str(tex_file.resolve()) + "}\n")

        out.write("\n" + r"\end{document}" + "\n")

    print(f"✓ Created {master}")


if __name__ == "__main__":
    main()