# Development Specification: `cl_st1_ph2_andrea.sas`

## 1. Programme Purpose

`cl_st1_ph2_andrea.sas` performs the SAS-based Lexical Multi-Dimensional Analysis (LMDA) workflow for the Phase 2 commercial verbal subcorpus.

The programme reads a binary keyword matrix, computes polychoric correlations, performs factor analysis, extracts and rotates factors, generates factor loading tables, calculates factor scores for each text, runs ANOVAs by decade, exports all required downstream files, and packages the SAS output files into a zip archive.

The programme is intended to produce the core statistical outputs used by the project’s Python post-processing scripts, including factor lists, boxplots, ANOVA tables, examples, score details, and interpretation prompts.

---

## 2. Project Context

The project analyses selected television-commercial texts grouped by decade:

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

This programme is for:

```text
cl_st1_ph2_andrea
```

Phase 2 analyses the commercial verbal subcorpus: transcript texts representing spoken/audio-verbal content of the selected television commercials.

The SAS programme is expected to run in an online SAS environment under the configured SAS user account.

The programme assumes the project folder exists at:

```text
/home/<sasusername>/<project>
```

Example:

```text
/home/u63529080/cl_st1_ph2_andrea
```

---

## 3. Inputs

### 3.1 Main Counts File

The required input file is:

```text
counts.txt
```

Expected full path:

```text
/home/<sasusername>/<project>/counts.txt
```

Example:

```text
/home/u63529080/cl_st1_ph2_andrea/counts.txt
```

### 3.2 Counts File Format

The file must be:

```text
space-separated
headerless
```

Expected columns:

```text
filename decade v000001-v000265
```

Example row:

```text
t000001 1950 0 1 0 0 ...
```

### 3.3 Required Counts Columns

| Column | Description |
|---|---|
| `filename` | Text identifier, e.g. `t000001` |
| `decade` | Decade group, e.g. `1950` |
| `v000001` to `v000265` | Binary keyword variables |

The final keyword variable is controlled by:

```sas
%let lastkeywordvar = v000265 ;
```

### 3.4 SAS Format Files

The programme expects SAS format files to be available in the project folder:

```text
word_labels_format.sas
word_labels_full_format.sas
```

These files map variable IDs such as:

```text
v000001
```

to readable lexical labels.

They are included during loadings-table generation.

### 3.5 Configurable Macro Variables

The programme requires the following macro variables to be configured before execution:

| Macro variable | Default / Example | Description |
|---|---:|---|
| `project` | `cl_st1_ph2_andrea` | Project dataset and output prefix |
| `myfolder` | `&project` | Project folder name |
| `sasusername` | `u63529080` | SAS account username |
| `whereisit` | `/home/&sasusername` | Base directory |
| `lastkeywordvar` | `v000265` | Last keyword variable in `counts.txt` |
| `extractfactors` | `8` | Number of factors to extract |
| `factorvars` | `fac1-fac&extractfactors` | Factor-score variable range |
| `minloading` | `.3` | Minimum loading cutoff |
| `communalcutoff` | `.15` | Minimum communality cutoff |
| `extractclusters` | `2` | Cluster count parameter retained for project consistency |
| `primaryfixedvar` | `decade` | Primary grouping variable |

---

## 4. Outputs

### 4.1 Main Factor Analysis Outputs

The programme creates intermediate and final SAS datasets in the `WORK` library, including:

```text
polychor
fout
communal
rotatedfinal
rotated3
rotated4
score
scores
scores_only
```

### 4.2 Exported Files

The programme exports files to:

```text
/home/<sasusername>/<project>/
```

Expected exported files include:

```text
communalities.tsv
rotated.csv
<project>_scores.tsv
<project>_scores_only.tsv
overall_decade_f<n>.tsv
params_decade_f<n>.tsv
anova_decade_f<n>.tsv
means_decade_f<n>.tsv
loadtable.html
loadtable_full.html
scree_*.png
glm_meta.html
```

For this project:

```text
cl_st1_ph2_andrea_scores.tsv
cl_st1_ph2_andrea_scores_only.tsv
```

### 4.3 Zip Archive

The programme creates a zip archive:

```text
/home/u63529080/zip/output_<project>.zip
```

Example:

```text
/home/u63529080/zip/output_cl_st1_ph2_andrea.zip
```

The archive must contain the generated project files before cleanup.

### 4.4 Cleanup Outputs

After zipping, the programme deletes generated files in the project folder with extensions:

```text
png
html
tsv
csv
```

This keeps the SAS project folder clean after the archive has been created.

---

## 5. Functional Requirements

### 5.1 Read Counts Data

The programme must read:

```text
&whereisit/&myfolder/counts.txt
```

into a SAS dataset named after the project:

```sas
&project
```

It must define:

```text
filename
decade
v000001 - &lastkeywordvar
```

The variable lengths must support:

```text
filename: 7 characters
decade: 4 characters
keyword variables: numeric
```

### 5.2 Check Missing Values

After importing the counts data, the programme must run a missing-value check using:

```sas
proc means n nmiss
```

This provides a diagnostic summary for the imported matrix.

### 5.3 Remove Empty Text Rows

The programme must remove rows where all keyword variables sum to zero.

A row must be retained only if:

```text
total keyword count > 0
```

This prevents all-zero texts from affecting the factor analysis.

### 5.4 Build Keyword Variable List

The programme must build a macro variable containing all keyword variable names.

This list is used by later procedures including:

```text
proc corr
proc factor
proc stdize
```

### 5.5 Compute Polychoric Correlations

The programme must compute a polychoric correlation matrix for the binary keyword variables.

Output dataset:

```text
polychor
```

The correlation matrix must be suitable for factor analysis using:

```sas
type=corr
```

### 5.6 Replace Missing Correlations

Any missing values in the polychoric correlation matrix must be replaced with zero.

This produces a complete matrix for downstream factor analysis.

### 5.7 Determine Number of Observations

The programme must count the number of observations in the filtered project dataset and store it as:

```sas
&nobs
```

This value must be supplied to `proc factor`.

### 5.8 Initial Factor Analysis

The programme must run an initial unrotated factor analysis on the full keyword-variable set.

Required behaviour:

- use the polychoric correlation matrix;
- use principal factor method;
- request up to 100 factors;
- use eigenvalue threshold of 1;
- produce scree information;
- write output statistics to:

```text
fout
```

### 5.9 Identify Low-Communality Variables

The programme must extract communalities from the initial factor analysis and identify:

1. variables below the communality cutoff;
2. variables at or above the communality cutoff.

The communality cutoff is:

```sas
%let communalcutoff = .15 ;
```

Variables with:

```text
communality < .15
```

must be excluded from the final rotated factor analysis.

Variables with:

```text
communality >= .15
```

must be retained.

### 5.10 Export Communalities

The programme must export communalities to:

```text
communalities.tsv
```

The exported table must include:

```text
_NAME_
communal
```

and must be sorted by communality.

### 5.11 Generate Scree Plots

The programme must generate scree plot images using the eigenvalues from the initial factor analysis.

The programme must:

1. delete old scree files before generating new ones;
2. generate scree plot images in the project folder;
3. mark the selected number of factors using a vertical reference line.

The selected factor count is:

```sas
%let extractfactors = 8 ;
```

### 5.12 Rotated Factor Analysis

The programme must run a final rotated factor analysis using only variables that pass the communality cutoff.

Required behaviour:

- input data: polychoric correlation matrix;
- retained variables: `&highcomm`;
- method: principal;
- rotation: promax;
- number of factors: `&extractfactors`;
- output dataset:

```text
rotatedfinal
```

### 5.13 Extract Factor Pattern

The programme must extract the factor pattern from the rotated factor output.

The relevant rows are:

```text
_TYPE_ = "PATTERN"
```

These values represent the factor pattern used for loading assignment.

### 5.14 Assign Variables to Factors and Poles

Each keyword variable must be assigned to a factor only if:

1. its absolute loading on that factor is greater than its absolute loading on all other compared factors;
2. its absolute loading is at least:

```sas
&minloading
```

3. the sign determines the pole:
    - positive loading → `pole = 1`;
    - negative loading → `pole = -1`.

The default minimum loading is:

```sas
%let minloading = .3 ;
```

The assignment output must include:

```text
_NAME_
factor1-factor&extractfactors
loaded
factor
pole
```

### 5.15 Filter Loaded Variables

Only variables with:

```text
loaded = 1
```

must be retained for loading tables and score construction.

### 5.16 Generate Full Loading Table

The programme must generate:

```text
loadtable_full.html
```

using:

```sas
word_labels_full_format.sas
```

For each factor, it must print:

1. positive-pole variables sorted by descending factor loading;
2. negative-pole variables sorted by ascending factor loading.

### 5.17 Generate Short Loading Table

The programme must generate:

```text
loadtable.html
```

using:

```sas
word_labels_format.sas
```

For each factor, it must print:

1. positive-pole variables sorted by descending factor loading;
2. negative-pole variables sorted by ascending factor loading.

### 5.18 Export Rotated Loading Data

The programme must export:

```text
rotated.csv
```

from the assigned loading dataset.

This file is used by downstream factor-list generation.

### 5.19 Build Factor Scoring Dataset

The programme must construct a scoring dataset from the loaded variables.

The scoring dataset must:

1. group variables by factor;
2. use the variable ID as the scoring column;
3. use `pole` as the scoring coefficient;
4. set `_TYPE_` to:

```text
SCORE
```

5. rename the factor identifier to:

```text
_NAME_
```

### 5.20 Calculate Factor Scores

The programme must run `proc score` to calculate factor scores for each text.

Output dataset:

```text
scores
```

Missing keyword values in the score output must be replaced with zero.

### 5.21 Create Grouped Scores

The programme must create a grouping column:

```text
group
```

with value equal to:

```text
decade
```

This supports downstream plotting and example-selection scripts.

### 5.22 Export Full Scores

The programme must export the full scores dataset to:

```text
<project>_scores.tsv
```

Example:

```text
cl_st1_ph2_andrea_scores.tsv
```

This file must include filename, decade, keyword variables, and factor-score variables.

### 5.23 Export Scores-Only File

The programme must export a reduced scores file to:

```text
<project>_scores_only.tsv
```

Example:

```text
cl_st1_ph2_andrea_scores_only.tsv
```

Required columns:

```text
filename
decade
group
fac1-fac&extractfactors
```

The column order must be retained as:

```text
filename decade group fac1 fac2 ...
```

### 5.24 Run ANOVAs by Decade

For each extracted factor, the programme must run a GLM model:

```text
fac<n> = decade
```

with:

```text
class decade
```

The programme must capture SAS ODS outputs:

```text
OverallANOVA
FitStatistics
ModelANOVA
Means
```

into datasets named:

```text
overall_decade_f<n>
params_decade_f<n>
anova_decade_f<n>
means_decade_f<n>
```

### 5.25 Export ANOVA Outputs

For each factor dimension, the programme must export:

```text
overall_decade_f<n>.tsv
params_decade_f<n>.tsv
anova_decade_f<n>.tsv
means_decade_f<n>.tsv
```

These files are required by downstream Python programmes for:

- ANOVA table generation;
- boxplot captions;
- example selection by decade;
- interpretation prompts.

### 5.26 Zip Project Outputs

The programme must create a zip archive containing the generated project files.

Before creating the zip, any existing archive at the target path must be deleted.

The zip archive path is:

```text
/home/u63529080/zip/output_&project..zip
```

### 5.27 Delete Temporary Export Files After Zipping

After the archive is created, the programme must delete generated files in the project folder with extensions:

```text
png
html
tsv
csv
```

The zip archive must remain available for download or transfer.

---

## 6. Output Content Requirements

### 6.1 Scores-Only File

The file:

```text
<project>_scores_only.tsv
```

must contain:

```text
filename
decade
group
fac1
fac2
...
fac8
```

For this project, the expected factor range is:

```text
fac1-fac8
```

### 6.2 Full Scores File

The file:

```text
<project>_scores.tsv
```

must include:

1. text identifier;
2. decade;
3. original keyword variables;
4. calculated factor scores.

### 6.3 Means Files

Each means file:

```text
means_decade_f<n>.tsv
```

must include decade-level mean factor scores.

These files are used to rank decades for positive and negative poles.

### 6.4 Parameter Files

Each parameter file:

```text
params_decade_f<n>.tsv
```

must include fit statistics, including:

```text
RSquare
```

This value is used by downstream visualisation and ANOVA-table generation.

### 6.5 ANOVA Files

Each ANOVA file:

```text
anova_decade_f<n>.tsv
```

must include model ANOVA results for the decade effect.

Required downstream fields include:

```text
HypothesisType
Source
FValue
ProbF
```

### 6.6 Rotated Loading File

The file:

```text
rotated.csv
```

must include the assigned factor and pole for loaded variables.

Required downstream fields include:

```text
_NAME_
factor1-factor8
loaded
factor
pole
```

### 6.7 Loading Tables

The files:

```text
loadtable.html
loadtable_full.html
```

must present positive and negative pole loading lists by factor.

---

## 7. Error Handling Requirements

### 7.1 Missing Counts File

If:

```text
counts.txt
```

is missing, SAS must report an input-file error and the programme cannot proceed correctly.

### 7.2 Incorrect Counts Width

If `lastkeywordvar` does not match the actual last keyword column in `counts.txt`, the imported matrix will be malformed.

The user must update:

```sas
%let lastkeywordvar = ...
```

before running the programme.

### 7.3 Missing Format Files

If either of the following is missing:

```text
word_labels_format.sas
word_labels_full_format.sas
```

loading-table generation will fail.

The format files must be generated and uploaded before running the SAS programme.

### 7.4 No Non-Zero Rows

If all rows are removed because their keyword totals are zero, factor analysis cannot proceed.

The input matrix must contain at least one non-empty text.

### 7.5 No Variables Passing Communality Cutoff

If no variables meet:

```text
communality >= &communalcutoff
```

the final rotated factor analysis cannot proceed.

The communality cutoff may need to be reviewed.

### 7.6 Factor Count Mismatch

If `extractfactors` is greater than the number of usable factors supported by the data, factor analysis or downstream factor references may fail.

The selected factor count should be checked against the scree plot.

### 7.7 Loading Assignment Limit

The loading-assignment logic compares factors through `factor9`.

If more than 9 factors are extracted, the assignment logic must be extended before use.

### 7.8 Zip Path Missing

If:

```text
/home/u63529080/zip/
```

does not exist or is not writable, zip creation will fail.

### 7.9 Cleanup Risk

The cleanup step deletes project-folder files with extensions:

```text
png
html
tsv
csv
```

The programme must be used only after confirming that these files have been successfully added to the zip archive.

---

## 8. Non-Functional Requirements

### 8.1 Determinism

Given the same input files and macro settings, the programme should produce stable outputs:

- same retained variables;
- same factor extraction settings;
- same rotated loading assignments;
- same factor scores;
- same exported file names.

### 8.2 No Manual Edits After Run Starts

All configurable values must be set in the macro-variable section before running the programme.

### 8.3 SAS Environment

The programme requires SAS procedures including:

```text
PROC CORR
PROC STDIZE
PROC FACTOR
PROC TRANSPOSE
PROC SQL
PROC SORT
PROC EXPORT
PROC GLM
PROC SGPLOT
```

### 8.4 Output Overwrite Behaviour

The programme uses `REPLACE` for exported files.

Existing files with the same names may be overwritten.

### 8.5 Intermediate Dataset Scope

Intermediate datasets are created in the SAS `WORK` library and do not need to persist after the SAS session ends.

### 8.6 External Post-Processing Compatibility

The exported files must remain compatible with downstream Python scripts that expect SAS output filenames and columns to follow the established naming conventions.

---

## 9. Downstream Usage

The zip archive produced by the SAS programme is intended to be downloaded or transferred back into the project as:

```text
sas/output_cl_st1_ph2_andrea/
```

Downstream scripts depend on these outputs, including:

```text
factor_lists.py
latex_boxplots.py
latex_anova_table.py
examples.py
score_details.py
examples_txt.py
interpretation_prompts.py
```

Typical required downstream files:

```text
rotated.csv
cl_st1_ph2_andrea_scores.tsv
cl_st1_ph2_andrea_scores_only.tsv
means_decade_f1.tsv
params_decade_f1.tsv
anova_decade_f1.tsv
word_labels_format.sas
```

and equivalent files for each factor dimension.

---

## 10. Acceptance Criteria

The programme is correct if:

1. It reads:

```text
/home/u63529080/cl_st1_ph2_andrea/counts.txt
```

2. It imports all expected keyword variables:

```text
v000001-v000265
```

3. It removes all-zero rows.

4. It computes a polychoric correlation matrix.

5. It replaces missing correlation values with zero.

6. It performs an initial factor analysis.

7. It exports:

```text
communalities.tsv
```

8. It generates scree plot images.

9. It performs a final promax-rotated factor analysis using variables that pass the communality cutoff.

10. It assigns loaded variables to factor poles using the minimum loading cutoff.

11. It creates loading tables:

```text
loadtable.html
loadtable_full.html
```

12. It exports:

```text
rotated.csv
```

13. It calculates factor scores for all retained texts.

14. It exports:

```text
cl_st1_ph2_andrea_scores.tsv
cl_st1_ph2_andrea_scores_only.tsv
```

15. It runs decade ANOVAs for all extracted factors.

16. It exports, for every factor:

```text
overall_decade_f<n>.tsv
params_decade_f<n>.tsv
anova_decade_f<n>.tsv
means_decade_f<n>.tsv
```

17. It creates:

```text
/home/u63529080/zip/output_cl_st1_ph2_andrea.zip
```

18. The zip archive contains the exported SAS outputs needed by downstream scripts.

19. The programme cleans temporary `.png`, `.html`, `.tsv`, and `.csv` files from the SAS project folder after zipping.

20. The downloaded output archive can be unpacked into the local project’s SAS output directory and used by the Python post-processing pipeline.

---

## 11. Example

### Input

```text
/home/u63529080/cl_st1_ph2_andrea/counts.txt
```

Example row:

```text
t000001 1950 0 1 0 0 1 0
```

### Main Configuration

```sas
%let project = cl_st1_ph2_andrea ;
%let lastkeywordvar = v000265 ;
%let extractfactors = 8 ;
%let minloading = .3 ;
%let communalcutoff = .15 ;
%let primaryfixedvar = decade ;
```

### Key Outputs

```text
communalities.tsv
rotated.csv
cl_st1_ph2_andrea_scores.tsv
cl_st1_ph2_andrea_scores_only.tsv
means_decade_f1.tsv
params_decade_f1.tsv
anova_decade_f1.tsv
overall_decade_f1.tsv
loadtable.html
loadtable_full.html
```

### Zip Output

```text
/home/u63529080/zip/output_cl_st1_ph2_andrea.zip
```

---

## 12. Recommended Future Enhancements

These are optional and must not alter current behaviour unless explicitly requested.

### 12.1 Parameterise Zip Path

Replace the hard-coded zip path with a macro variable:

```sas
%let zipdir = /home/&sasusername/zip ;
```

### 12.2 Remove Hard-Coded Project Path in Zip Filelist

Use macro variables in the filelist `cards4` block instead of hard-coding:

```text
/home/u63529080/cl_st1_ph2_andrea
```

### 12.3 Generalise Loading Assignment

Replace the repeated `if/else` factor comparison logic with macro-generated code so any number of factors can be supported.

Current logic is effectively limited to factors compared through:

```text
factor9
```

### 12.4 Add Preflight Checks

Add explicit checks for:

```text
counts.txt
word_labels_format.sas
word_labels_full_format.sas
zip directory
```

before running the full analysis.

### 12.5 Export Run Metadata

Create a metadata file such as:

```text
sas_run_metadata.tsv
```

containing:

- project;
- number of observations;
- last keyword variable;
- number of extracted factors;
- minimum loading cutoff;
- communality cutoff;
- run date/time.

### 12.6 Make Cleanup Optional

Add a macro variable:

```sas
%let cleanup_after_zip = 1 ;
```

so temporary files can be retained for debugging when needed.

### 12.7 Export Low-Communality Variable List

In addition to `communalities.tsv`, export:

```text
low_communality_vars.tsv
high_communality_vars.tsv
```

for easier review.

---

## 13. Summary

`cl_st1_ph2_andrea.sas` performs the central SAS LMDA analysis for the Phase 2 commercial verbal subcorpus.

Its core responsibility is:

```text
Transform a binary keyword matrix into rotated LMDA factors, factor scores, decade ANOVAs, and downloadable SAS output files.
```

It must preserve:

- project-specific SAS configuration;
- binary keyword matrix import;
- polychoric-correlation factor analysis;
- communality-based variable filtering;
- promax rotated factor extraction;
- positive/negative factor-pole assignment;
- factor-score generation;
- decade-level ANOVA outputs;
- zip packaging for downstream Python processing.