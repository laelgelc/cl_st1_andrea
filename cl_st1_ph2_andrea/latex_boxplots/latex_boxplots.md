# Development Specification: `latex_boxplots.py`

## 1. Programme Purpose

`latex_boxplots.py` generates LaTeX/TikZ boxplot figures for LMDA factor scores by decade.

For each factor dimension, the programme reads SAS factor-score outputs and creates:

1. one boxplot `.tex` file per factor dimension;
2. one mosaic `.tex` file combining the first few boxplots.

The figures show the distribution of factor scores across decades and include the ANOVA R² value in each caption.

The programme is intended to support interpretation of diachronic variation in LMDA dimensions.

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

The programme is expected to live in:

```text
latex_boxplots/latex_boxplots.py
```

inside each phase directory.

Example:

```text
cl_st1_ph2_andrea/latex_boxplots/latex_boxplots.py
cl_st1_ph3_andrea/latex_boxplots/latex_boxplots.py
```

Because of this location, the project name is inferred from the parent directory.

Example:

```text
cl_st1_ph2_andrea/latex_boxplots/latex_boxplots.py
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
../sas/output_<project>/<project>_scores_only.tsv
```

resolved relative to the project directory.

Example for Phase 2:

```text
sas/output_cl_st1_ph2_andrea/cl_st1_ph2_andrea_scores_only.tsv
```

Example for Phase 3:

```text
sas/output_cl_st1_ph3_andrea/cl_st1_ph3_andrea_scores_only.tsv
```

### 3.2 Required Scores Columns

The scores file must be tab-separated and contain:

```text
filename
decade
fac1
fac2
...
```

Required:

| Column | Description |
|---|---|
| `decade` | Decade stratum for each text |
| `fac<n>` | Factor score for dimension `<n>` |

The programme detects available factor dimensions from columns matching:

```regex
fac\d+
```

### 3.3 SAS Parameter Files

For each factor dimension, the programme reads:

```text
params_decade_f<n>.tsv
```

from the SAS output directory.

Example:

```text
sas/output_cl_st1_ph2_andrea/params_decade_f1.tsv
```

These files are expected to contain an `RSquare` column.

If a parameter file is missing, empty, or unreadable, the programme should use:

```text
0.0
```

for R².

### 3.4 Command-Line Arguments

The programme must support:

```text
--project
```

Default:

```text
parent directory name
```

```text
--sas-output-dir
```

Default:

```text
<project_dir>/sas/output_<project>
```

```text
--output-dir
```

Default:

```text
latex_boxplots/slides
```

---

## 4. Outputs

### 4.1 Output Directory

Default:

```text
latex_boxplots/slides
```

The programme must create it if it does not exist.

### 4.2 Per-Dimension Boxplot Files

For each factor dimension:

```text
slides/boxplot_f<n>_by_decade.tex
```

Examples:

```text
slides/boxplot_f1_by_decade.tex
slides/boxplot_f2_by_decade.tex
```

### 4.3 Mosaic File

The programme writes:

```text
slides/mosaic_by_decade.tex
```

The mosaic reuses the TikZ content from the generated boxplot files.

By default, it includes up to the first four factor dimensions.

### 4.4 Output Encoding

All `.tex` files must be written using:

```text
UTF-8
```

---

## 5. Functional Requirements

### 5.1 Project Inference

The programme must infer the project name from:

```python
Path(__file__).resolve().parent.parent.name
```

because the script is located in:

```text
latex_boxplots/
```

This prevents accidental inference of `latex_boxplots` as the project when run from inside that directory.

### 5.2 Path Resolution

If `--sas-output-dir` is omitted, resolve to:

```text
<project_dir>/sas/output_<project>
```

If a relative `--sas-output-dir` is supplied, resolve it relative to the current working directory.

If `--output-dir` is omitted, resolve to:

```text
<script_dir>/slides
```

If a relative `--output-dir` is supplied, resolve it relative to the current working directory.

### 5.3 Read Scores Data

The programme must:

1. validate the scores file exists;
2. read it with pandas using tab separation;
3. validate that the `decade` column exists;
4. normalize `decade` as a stripped string;
5. detect factor dimensions.

### 5.4 Detect Factor Dimensions

Factor dimensions are detected from columns matching:

```regex
fac\d+
```

The detected dimensions are sorted numerically.

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

### 5.5 Read R² Values

For each dimension:

1. look for:

```text
params_decade_f<n>.tsv
```

2. read the first row;
3. extract the `RSquare` column;
4. multiply by 100;
5. use the result in the caption.

If the parameter file cannot be read, return:

```text
0.0
```

### 5.6 Generate Boxplot Statistics

For each decade and factor dimension, compute:

- lower whisker;
- first quartile;
- median;
- third quartile;
- upper whisker.

The whisker rule is:

```text
lower whisker = max(min, Q1 - 1.5 × IQR)
upper whisker = min(max, Q3 + 1.5 × IQR)
```

where:

```text
IQR = Q3 - Q1
```

### 5.7 Outliers

Outliers are values:

```text
< Q1 - 1.5 × IQR
```

or:

```text
> Q3 + 1.5 × IQR
```

The programme must add them as black point markers in the TikZ output.

### 5.8 Mean Marker

For each decade, the programme must add a red point marker representing the mean factor score.

### 5.9 Decade Ordering

Decades must be sorted numerically:

```text
1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020
```

If a non-numeric group appears, it should be sorted after numeric decades.

### 5.10 LaTeX Escaping

Decade labels and caption text should be LaTeX-safe.

The programme must escape:

```text
\
_
%
&
#
{
}
^
~
```

### 5.11 Generate Boxplot `.tex`

For each factor dimension, write a LaTeX figure containing:

- `figure` environment;
- `tikzpicture`;
- `axis`;
- boxplot prepared data;
- red dashed zero line;
- outlier markers;
- red mean markers;
- caption;
- label.

The label format must be:

```text
fig:means_f<n>_by_decade
```

### 5.12 Generate Mosaic

The programme must create:

```text
mosaic_by_decade.tex
```

by reusing the TikZ block from the generated boxplot files.

Default maximum number of plots in mosaic:

```text
4
```

The mosaic figure label must be:

```text
fig:mosaic_by_decade
```

---

## 6. Output Content Requirements

### 6.1 Boxplot Caption

Each boxplot caption must follow:

```text
Mean Dim. <n> Scores by Decade (R² = <value>\%)
```

Example:

```text
Mean Dim. 1 Scores by Decade (R² = 12.34\%)
```

### 6.2 Y-axis Label

Each plot must use:

```text
Mean Dim. <n> Score
```

### 6.3 X-axis Labels

The x-axis labels must be decade labels.

Example:

```text
1950, 1960, 1970, ...
```

### 6.4 Zero Line

A horizontal red dashed line must be plotted at:

```text
y = 0
```

---

## 7. Error Handling Requirements

### 7.1 Missing Scores File

If the scores-only file does not exist, raise:

```text
FileNotFoundError
```

### 7.2 Missing Decade Column

If the scores file does not contain a `decade` column, raise:

```text
ValueError
```

### 7.3 No Factor Columns

If no `fac<n>` columns are found, raise:

```text
RuntimeError
```

### 7.4 Missing Boxplot File for Mosaic

If a boxplot file required for the mosaic does not exist, raise:

```text
FileNotFoundError
```

### 7.5 Empty Decade Values

If a decade has no values for a factor, skip that decade in the plot.

### 7.6 Missing Parameter File

Missing or unreadable parameter files must not stop execution. They should result in:

```text
R² = 0.00%
```

in the caption.

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
- decades sorted numerically;
- generated filenames stable.

### 8.3 No Input Mutation

The programme must not modify SAS output files.

### 8.4 Output Overwrite Behaviour

The programme may overwrite existing `.tex` files under:

```text
latex_boxplots/slides/
```

### 8.5 No External LaTeX Compilation

The programme only writes `.tex` fragments. It does not compile LaTeX.

### 8.6 Dependency Requirements

The programme depends on:

```text
pandas
tqdm
```

Both must be available in the active Python environment.

---

## 9. Downstream Usage

The generated `.tex` files are intended to be included in LaTeX documents or slides.

Typical inclusion:

```latex
\input{latex_boxplots/slides/boxplot_f1_by_decade.tex}
```

or:

```latex
\input{latex_boxplots/slides/mosaic_by_decade.tex}
```

The generated code assumes a LaTeX environment with TikZ/PGFPlots support.

---

## 10. Acceptance Criteria

The programme is correct if:

1. It can be run from inside `latex_boxplots/` using:

```shell
python latex_boxplots.py
```

2. It can be run from the project root using:

```shell
python latex_boxplots/latex_boxplots.py
```

3. It infers the correct project name.
4. It reads the correct `scores_only.tsv`.
5. It detects all `fac<n>` dimensions.
6. It generates one `boxplot_f<n>_by_decade.tex` per factor.
7. It generates `mosaic_by_decade.tex`.
8. It writes outputs under `latex_boxplots/slides` by default.
9. It orders decades chronologically.
10. It includes R² values in captions.
11. It includes outliers and mean markers.
12. It does not require manual path editing between Phase 2 and Phase 3.

---

## 11. Example

### Input

```text
sas/output_cl_st1_ph2_andrea/cl_st1_ph2_andrea_scores_only.tsv
```

Example columns:

```text
filename	decade	group	fac1	fac2
t000001	1950	1950	0.21	-0.13
t000002	1950	1950	0.44	0.05
t000104	1960	1960	-0.17	0.22
```

### Output

```text
latex_boxplots/slides/boxplot_f1_by_decade.tex
latex_boxplots/slides/boxplot_f2_by_decade.tex
latex_boxplots/slides/mosaic_by_decade.tex
```

### Caption Example

```latex
\caption{Mean Dim. 1 Scores by Decade (R² = 8.42\%)}
```

---

## 12. Recommended Future Enhancements

These are optional and must not alter current default behaviour unless explicitly requested.

### 12.1 Configurable Mosaic Size

Expose:

```text
--max-mosaic-plots
```

### 12.2 Plot Ordering Option

Allow ordering decades by mean instead of chronological order:

```text
--order chronological
--order mean
```

Current required behaviour is chronological.

### 12.3 Output Combined File

Generate a single combined LaTeX file:

```text
slides/all_boxplots_by_decade.tex
```

### 12.4 Width and Height Options

Expose:

```text
--plot-width
--plot-height
```

### 12.5 R² Strict Mode

Add:

```text
--require-rsquare
```

to fail if `params_decade_f<n>.tsv` is missing.

Current required behaviour is fallback to `0.0`.

### 12.6 Manifest

Write:

```text
slides/latex_boxplots_manifest.json
```

containing:

- project;
- input file;
- output directory;
- detected factors;
- generated files.

---

## 13. Summary

`latex_boxplots.py` creates LaTeX/TikZ visualisations of LMDA factor-score distributions by decade.

Its core responsibility is:

```text
For each factor dimension, show how text scores vary across decades using boxplots and mean markers.
```

It must preserve:

- project inference from script location;
- decade-based grouping;
- chronological decade ordering;
- TikZ/PGFPlots output;
- one file per factor plus a mosaic file;
- compatibility across Phase 2 and Phase 3.