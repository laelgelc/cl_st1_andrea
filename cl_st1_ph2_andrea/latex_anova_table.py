#!/usr/bin/env python3
"""
Generate LaTeX ANOVA tables for:
    source
    model
    prompt
    group

Each table lists F, p, R², and percent R² for each available factor dimension.

Reads (per dim):
    anova_<cond>_f<n>.tsv
    params_<cond>_f<n>.tsv

Writes:
    latex_tables/anova_<cond>.tex
"""

import csv
import re
import pandas as pd
from pathlib import Path

INPUT_DIR  = Path('sas/output_cl_st1_ph3_andressa')
OUTPUT_DIR = Path('latex_tables')
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

SCORES_ONLY = INPUT_DIR / "cl_st1_ph3_andressa_scores_only.tsv"

CONDITIONS = [
    ('Source', 'anova_source_f{dim}.tsv', 'params_source_f{dim}.tsv', 'anova_source.tex'),
    ('Model',  'anova_model_f{dim}.tsv',  'params_model_f{dim}.tsv',  'anova_model.tex'),
    ('Prompt', 'anova_prompt_f{dim}.tsv', 'params_prompt_f{dim}.tsv', 'anova_prompt.tex'),
    ('Group',  'anova_group_f{dim}.tsv',  'params_group_f{dim}.tsv',  'anova_group.tex'),
]


def read_rsquare(path: Path) -> float:
    """Read RSquare from first row of a TSV file."""
    with path.open(newline='') as f:
        reader = csv.DictReader(f, delimiter='\t')
        rows = list(reader)
    return float(rows[0]['RSquare']) if rows else 0.0


def format_rsquare(rs: float):
    """Return R² without leading zero + percent."""
    actual = f"{rs:.5f}"
    if actual.startswith("0"):
        actual = actual[1:]
    return actual, f"{rs*100:.2f}"


def detect_dims() -> list[int]:
    df = pd.read_csv(SCORES_ONLY, sep="\t", nrows=1)
    fac_cols = [c for c in df.columns if re.fullmatch(r"fac\d+", str(c))]
    dims = sorted({int(str(c)[3:]) for c in fac_cols})
    if not dims:
        raise RuntimeError(f"No fac<n> columns found in {SCORES_ONLY}")
    return dims


def make_table(cond_name, anova_pat, params_pat, out_filename, dims: list[int]):
    rows = []

    for dim in dims:
        anova_file = INPUT_DIR / anova_pat.format(dim=dim)
        df = pd.read_csv(anova_file, sep='\t')

        target = cond_name.lower()
        sel = df[(df["HypothesisType"] == 1) &
                 (df["Source"].str.lower() == target)]

        if sel.empty:
            sel = df[df["HypothesisType"] == 1]

        row = sel.iloc[0]
        F_val = row["FValue"]
        p_val = row["ProbF"]

        rs = read_rsquare(INPUT_DIR / params_pat.format(dim=dim))
        r2_act, r2_pct = format_rsquare(rs)

        rows.append((dim, F_val, p_val, r2_act, r2_pct))

    out_path = OUTPUT_DIR / out_filename
    with out_path.open('w', encoding='utf-8') as f:
        f.write("\\begin{table}[H]\n")
        f.write("  \\centering\n")
        f.write(f"  \\caption{{ANOVA Results for {cond_name}}}\n")
        f.write(f"  \\label{{tab:{out_filename.replace('.tex','')}}}\n")
        f.write("  \\begin{tabular}{l r r r r}\n")
        f.write("    Dim. & F & p & R$^2$ & \\% \\\\\n")
        f.write("    \\hline\n")

        for dim, F_val, p_val, r2_act, r2_pct in rows:
            f.write(f"    {dim} & {F_val:.2f} & {p_val} & {r2_act} & {r2_pct} \\\\\n")

        f.write("  \\end{tabular}\n")
        f.write("\\end{table}\n")


def main():
    dims = detect_dims()
    for cond_name, anova_pat, params_pat, out_fn in CONDITIONS:
        make_table(cond_name, anova_pat, params_pat, out_fn, dims)


if __name__ == "__main__":
    main()