# Development Specification: `latex_anova_table.py`

## 1. Programme Purpose

`latex_anova_table.py` generates a LaTeX table summarising ANOVA results for decade effects on LMDA factor scores.

For each factor dimension, the programme reads SAS ANOVA output files and creates one LaTeX `.tex` table containing:

1. factor dimension number;
2. F statistic;
3. p value;
4. R² value;
5. percent R² value.

The table is intended to support interpretation of diachronic variation in LMDA dimensions by showing how strongly each factor dimension varies by decade.

---

## 2. Project Context

The project analyses commercial subcorpora organised by decade:

```text
1950
1960
1970
1980
1990
2000
2010
2020
```

The programme is used in both:

1. **Phase 2: commercial verbal subcorpus**
    - transcript texts of spoken/audio-verbal commercial content;

2. **Phase 3: commercial visual subcorpus**
    - textual descriptions of commercial visual content.

The programme is expected to live in the project phase directory as:

```text
latex_anova_table.py
```

Example:

```text
cl_st1_ph2_andrea/latex_anova_table.py
cl_st1_ph3_andrea/latex_anova_table.py
```

By default, the project name is inferred from the current working directory.

Example:

```text
cl_st1_ph2_andrea
```

infers:

```text
cl_st1_ph2_andrea
```

---

## 3. Inputs

### 3.1 SAS Scores File

Default input path:

```text
sas/output_<project>/<project>_scores_only.tsv
```

resolved relative to the current working directory.

Example for Phase 2:

```text
sas/output_cl_st1_ph2_andrea/cl_st1_ph2_andrea_scores_only.tsv
```

Example for Phase 3:

```text
sas/output_cl_st1_ph3_andrea/cl_st1_ph3_andrea_scores_only.tsv
```

The scores file is used only to detect available factor dimensions.

### 3.2 Required Scores Columns

The scores file must be tab-separated and contain factor-score columns named:

```text
fac1
fac2
fac3
...
```

The programme detects available factor dimensions from columns matching:

```regex
fac\d+
```

Example:

```text
filename	decade	group	fac1	fac2	fac3
```

### 3.3 SAS ANOVA Files

For each factor dimension, the programme reads:

```text
anova_decade_f<n>.tsv
```

from the SAS output directory.

Example:

```text
sas/output_cl_st1_ph2_andrea/anova_decade_f1.tsv
```

Each ANOVA file must contain the relevant SAS `ModelANOVA` output for the factor dimension.

Required columns:

| Column | Description |
|---|---|
| `HypothesisType` | SAS hypothesis type; the programme uses `1` |
| `Source` | ANOVA source; expected to include `decade` |
| `FValue` | F statistic |
| `ProbF` | p value |

### 3.4 SAS Parameter Files

For each factor dimension, the programme reads:

```text
params_decade_f<n>.tsv
```

from the SAS output directory.

Example:

```text
sas/output_cl_st1_ph2_andrea/params_decade_f1.tsv
```

These files must contain an `RSquare` column.

The programme reads the first row and uses the value from:

```text
RSquare
```

### 3.5 Command-Line Arguments

The programme must support:

```text
--project
```

Default:

```text
current working directory name
```

Example:

```shell
python latex_anova_table.py --project cl_st1_ph2_andrea
```

```text
--input-dir
```

Default:

```text
sas/output_<project>
```

Example:

```shell
python latex_anova_table.py --input-dir sas/output_cl_st1_ph2_andrea
```

```text
--output-dir
```

Default:

```text
latex_tables
```

Example:

```shell
python latex_anova_table.py --output-dir latex_tables
```

---

## 4. Outputs

### 4.1 Output Directory

Default:

```text
latex_tables
```

The programme must create this directory if it does not exist.

### 4.2 ANOVA Table File

The programme writes:

```text
latex_tables/anova_decade.tex
```

The output is a LaTeX table fragment.

### 4.3 Output Encoding

The `.tex` file must be written using:

```text
UTF-8
```

---

## 5. Functional Requirements

### 5.1 Project Inference

The default project name must be inferred from:

```python
Path.cwd().name
```

This allows the programme to be run from the relevant project phase directory without manually specifying the project name.

Example:

```shell
cd cl_st1_ph2_andrea
python latex_anova_table.py
```

infers:

```text
cl_st1_ph2_andrea
```

### 5.2 Path Resolution

If `--input-dir` is omitted, resolve to:

```text
sas/output_<project>
```

If `--input-dir` is supplied, use the supplied path.

If `--output-dir` is omitted, resolve to:

```text
latex_tables
```

If `--output-dir` is supplied, use the supplied path.

Relative paths are resolved relative to the current working directory.

### 5.3 Detect Factor Dimensions

The programme must detect factor dimensions from the scores-only file:

```text
<input-dir>/<project>_scores_only.tsv
```

It must read the header and find columns matching:

```regex
fac\d+
```

The detected dimensions must be sorted numerically.

Example:

```text
fac1, fac2, fac10
```

must become:

```text
1, 2, 10
```

If no factor columns are found, raise:

```text
RuntimeError
```

### 5.4 Read ANOVA Row

For each dimension, the programme must read:

```text
anova_decade_f<n>.tsv
```

It must select the row where:

```text
HypothesisType == 1
```

and:

```text
Source == decade
```

The source comparison should be case-insensitive.

If no matching `Source == decade` row exists, the programme may fall back to the first row where:

```text
HypothesisType == 1
```

If no `HypothesisType == 1` row exists, raise:

```text
ValueError
```

### 5.5 Read F Statistic

The F statistic must be read from:

```text
FValue
```

It must be formatted with two decimal places.

Example:

```text
12.3456
```

becomes:

```text
12.35
```

### 5.6 Read and Parse p Value

The p value must be read from:

```text
ProbF
```

The programme must handle normal numeric p values.

Example:

```text
0.02456
```

It must also handle SAS-style threshold p values.

Example:

```text
<.0001
```

SAS-style values must be parsed numerically for logic while preserving threshold-style display.

### 5.7 Format p Value

P values must be formatted for LaTeX table output as follows:

| Input | Output |
|---|---|
| `0.03456` | `0.035` |
| `0.0005` | `< .001` |
| `<.0001` | `< .0001` |

If the original SAS p value begins with:

```text
<
```

the output should preserve the threshold while inserting a space after `<`.

Example:

```text
<.0001
```

becomes:

```text
< .0001
```

### 5.8 Read R²

For each dimension, the programme must read:

```text
params_decade_f<n>.tsv
```

It must read the first row and extract:

```text
RSquare
```

The raw R² value must be stored as a float.

### 5.9 Format R²

The programme must output two R² columns:

1. raw R²;
2. percent R².

The raw R² value must be formatted to five decimal places and should omit the leading zero.

Example:

```text
0.12345
```

becomes:

```text
.12345
```

The percent R² value must be calculated as:

```text
RSquare * 100
```

and formatted to two decimal places.

Example:

```text
0.12345
```

becomes:

```text
12.35
```

### 5.10 Generate LaTeX Table

The output file must contain a LaTeX table with:

- `table` environment;
- `[H]` placement specifier;
- centred table;
- caption;
- label;
- tabular environment;
- header row;
- one row per detected factor dimension.

The table caption must be:

```text
ANOVA Results by Decade
```

The table label must be:

```text
tab:anova_decade
```

The tabular column specification must be:

```latex
{l r r r r}
```

The table header must be:

```latex
Dim. & F & p & R$^2$ & \% \\
```

### 5.11 Row Ordering

Rows must be ordered by factor dimension number in ascending numeric order.

Example:

```text
Dim. 1
Dim. 2
Dim. 3
...
Dim. 10
```

not:

```text
Dim. 1
Dim. 10
Dim. 2
```

### 5.12 Console Output

After successful generation, the programme should print:

1. project name;
2. input directory;
3. detected dimensions;
4. output file path.

Example:

```text
Project: cl_st1_ph2_andrea
Input directory: sas/output_cl_st1_ph2_andrea
Detected dimensions: 1, 2, 3, 4, 5, 6, 7, 8
LaTeX ANOVA table written to: latex_tables/anova_decade.tex
```

---

## 6. Output Content Requirements

### 6.1 Output File Name

The output file must be:

```text
anova_decade.tex
```

inside the configured output directory.

Default full path:

```text
latex_tables/anova_decade.tex
```

### 6.2 Table Structure

The generated table must follow this structure:

```latex
\begin{table}[H]
  \centering
  \caption{ANOVA Results by Decade}
  \label{tab:anova_decade}
  \begin{tabular}{l r r r r}
    Dim. & F & p & R$^2$ & \% \\
    \hline
    1 & 12.35 & < .001 & .12345 & 12.35 \\
  \end{tabular}
\end{table}
```

### 6.3 Dimension Column

The dimension column must contain only the numeric factor dimension.

Example:

```text
1
2
3
```

not:

```text
fac1
fac2
fac3
```

### 6.4 F Column

The F column must contain the F statistic formatted to two decimal places.

Example:

```text
7.41
```

### 6.5 p Column

The p column must contain the formatted p value.

Examples:

```text
0.042
< .001
< .0001
```

### 6.6 R² Column

The R² column must contain the raw R² value formatted to five decimal places, without a leading zero for values between 0 and 1.

Example:

```text
.08764
```

### 6.7 Percent Column

The percent column must contain R² multiplied by 100 and formatted to two decimal places.

Example:

```text
8.76
```

The column header must be:

```latex
\%
```

---

## 7. Error Handling Requirements

### 7.1 Missing Scores File

If the scores-only file does not exist, raise:

```text
FileNotFoundError
```

Example missing path:

```text
sas/output_cl_st1_ph2_andrea/cl_st1_ph2_andrea_scores_only.tsv
```

### 7.2 No Factor Columns

If the scores-only file contains no columns matching:

```regex
fac\d+
```

raise:

```text
RuntimeError
```

### 7.3 Missing ANOVA File

If an expected ANOVA file does not exist, raise:

```text
FileNotFoundError
```

Example:

```text
anova_decade_f1.tsv
```

### 7.4 Missing Required ANOVA Columns

If an ANOVA file is missing any of the required columns:

```text
HypothesisType
Source
FValue
ProbF
```

raise:

```text
ValueError
```

The error message should identify the missing columns.

### 7.5 Missing Hypothesis Row

If no row with:

```text
HypothesisType == 1
```

exists in an ANOVA file, raise:

```text
ValueError
```

### 7.6 Missing Parameter File

If an expected R² parameter file does not exist, raise:

```text
FileNotFoundError
```

Example:

```text
params_decade_f1.tsv
```

### 7.7 Missing RSquare Column

If a parameter file does not contain:

```text
RSquare
```

raise:

```text
ValueError
```

### 7.8 Empty Parameter File

If a parameter file contains a header but no data rows, use:

```text
0.0
```

as the R² value.

### 7.9 Invalid p Value

If a p value cannot be parsed as either a numeric value or a SAS-style threshold value, raise:

```text
ValueError
```

### 7.10 Invalid Numeric Fields

If `FValue` or `RSquare` cannot be converted to a float, raise:

```text
ValueError
```

---

## 8. Non-Functional Requirements

### 8.1 Encoding

All input and output text files must use:

```text
UTF-8
```

### 8.2 Determinism

The programme must produce deterministic output:

- factor dimensions sorted numerically;
- stable row order;
- stable output filename;
- stable numeric formatting.

### 8.3 No Input Mutation

The programme must not modify SAS output files.

Input files are read-only.

### 8.4 Output Overwrite Behaviour

The programme may overwrite an existing file at:

```text
latex_tables/anova_decade.tex
```

or at the configured output path.

### 8.5 No External LaTeX Compilation

The programme only writes a `.tex` table fragment.

It must not call LaTeX, `pdflatex`, `xelatex`, or any external compilation process.

### 8.6 Dependency Requirements

The programme depends on:

```text
pandas
```

It also uses Python standard-library modules including:

```text
argparse
csv
re
pathlib
```

The programme must run under the project Python environment.

---

## 9. Downstream Usage

The generated `.tex` file is intended to be included in LaTeX documents or slides.

Typical inclusion:

```latex
\input{latex_tables/anova_decade.tex}
```

The generated table assumes a LaTeX environment where the `[H]` float placement specifier is available.

This normally requires:

```latex
\usepackage{float}
```

---

## 10. Acceptance Criteria

The programme is correct if:

1. It can be run from the project root using:

```shell
python latex_anova_table.py
```

2. It accepts an explicit project name:

```shell
python latex_anova_table.py --project cl_st1_ph2_andrea
```

3. It accepts an explicit input directory:

```shell
python latex_anova_table.py --input-dir sas/output_cl_st1_ph2_andrea
```

4. It accepts an explicit output directory:

```shell
python latex_anova_table.py --output-dir latex_tables
```

5. It reads:

```text
<project>_scores_only.tsv
```

from the SAS output directory.

6. It detects all available `fac<n>` columns.

7. It sorts factor dimensions numerically.

8. It reads one ANOVA file per factor dimension.

9. It reads one parameter file per factor dimension.

10. It extracts F, p, R², and percent R² values.

11. It handles SAS-style p values such as:

```text
<.0001
```

12. It writes:

```text
latex_tables/anova_decade.tex
```

by default.

13. It creates the output directory if needed.

14. It writes UTF-8 output.

15. It does not require manual changes when moving between Phase 2 and Phase 3, provided it is run from the correct project directory or supplied with `--project`.

---

## 11. Example

### Input

```text
sas/output_cl_st1_ph2_andrea/cl_st1_ph2_andrea_scores_only.tsv
sas/output_cl_st1_ph2_andrea/anova_decade_f1.tsv
sas/output_cl_st1_ph2_andrea/params_decade_f1.tsv
```

Example scores columns:

```text
filename	decade	group	fac1	fac2
t000001	1950	1950	0.21	-0.13
t000002	1950	1950	0.44	0.05
t000104	1960	1960	-0.17	0.22
```

Example ANOVA columns:

```text
HypothesisType	Source	FValue	ProbF
1	decade	12.3456	<.0001
```

Example parameter columns:

```text
RSquare
0.0842
```

### Command

```shell
python latex_anova_table.py
```

### Output

```text
latex_tables/anova_decade.tex
```

### Output Example

```latex
\begin{table}[H]
  \centering
  \caption{ANOVA Results by Decade}
  \label{tab:anova_decade}
  \begin{tabular}{l r r r r}
    Dim. & F & p & R$^2$ & \% \\
    \hline
    1 & 12.35 & < .0001 & .08420 & 8.42 \\
    2 & 4.71 & 0.003 & .03125 & 3.12 \\
  \end{tabular}
\end{table}
```

---

## 12. Recommended Future Enhancements

These are optional and must not alter current default behaviour unless explicitly requested.

### 12.1 Configurable Source Variable

Expose:

```text
--source
```

Default:

```text
decade
```

This would allow the same programme to generate ANOVA tables for other grouping variables.

### 12.2 Configurable Output Filename

Expose:

```text
--output-file
```

Default:

```text
anova_decade.tex
```

### 12.3 Optional Caption Argument

Expose:

```text
--caption
```

Default:

```text
ANOVA Results by Decade
```

### 12.4 Optional Label Argument

Expose:

```text
--label
```

Default:

```text
tab:anova_decade
```

### 12.5 Strict Source Matching

Expose:

```text
--strict-source
```

When enabled, the programme should fail if no row has:

```text
Source == decade
```

Current required behaviour allows fallback to the first `HypothesisType == 1` row.

### 12.6 Manifest

Write:

```text
latex_tables/latex_anova_table_manifest.json
```

containing:

- project;
- input directory;
- output file;
- detected dimensions;
- ANOVA files used;
- parameter files used.

### 12.7 Additional Table Formats

Optionally generate:

```text
latex_tables/anova_decade.csv
latex_tables/anova_decade.tsv
```

for checking and downstream reuse.

---

## 13. Summary

`latex_anova_table.py` creates a LaTeX summary table of ANOVA results for LMDA factor scores by decade.

Its core responsibility is:

```text
For each factor dimension, report the decade effect using F, p, R², and percent R².
```

It must preserve:

- project-based SAS output discovery;
- automatic factor-dimension detection;
- numeric factor ordering;
- SAS-compatible p-value handling;
- stable LaTeX table formatting;
- compatibility across Phase 2 and Phase 3.