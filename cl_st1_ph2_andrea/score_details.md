# Development Specification: `score_details.py`

## 1. Programme Purpose

`score_details.py` generates a plain-text score-details report showing, for each text and each LMDA factor dimension, which factor-loading words are present in that text.

For every text in the SAS scores file, the programme reports:

1. text ID;
2. source filename/path;
3. factor score for each dimension;
4. positive-pole loading words present in the text;
5. negative-pole loading words present in the text.

The programme is intended to support qualitative interpretation and checking of LMDA factor scores by linking each text’s numerical factor score to the factor-loading variables actually present in that text.

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
score_details.py
```

Example:

```text
cl_st1_ph2_andrea/score_details.py
cl_st1_ph3_andrea/score_details.py
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
sas/output_<project>/<project>_scores.tsv
```

Example for Phase 2:

```text
sas/output_cl_st1_ph2_andrea/cl_st1_ph2_andrea_scores.tsv
```

Example for Phase 3:

```text
sas/output_cl_st1_ph3_andrea/cl_st1_ph3_andrea_scores.tsv
```

This file is the full SAS scores export and must contain:

1. a `filename` column;
2. factor-score columns named `fac<n>`;
3. keyword variable columns named `v000001`, `v000002`, etc.

### 3.2 Required Scores Columns

The scores file must be tab-separated and contain:

| Column | Description |
|---|---|
| `filename` | Internal text identifier, such as `t000001` |
| `fac<n>` | Factor score for dimension `<n>` |
| `v######` | Binary or numeric keyword variable columns |

Example:

```text
filename	decade	v000001	v000002	fac1	fac2
t000001	1950	1	0	0.42	-0.13
t000002	1950	0	1	-0.22	0.54
```

The programme detects available factor dimensions from columns matching:

```regex
fac\d+
```

### 3.3 SAS Word Labels File

Default input path:

```text
sas/output_<project>/word_labels_format.sas
```

Example:

```text
sas/output_cl_st1_ph2_andrea/word_labels_format.sas
```

This file maps SAS variable IDs to readable word labels.

Expected line format:

```text
"v000001" = "word";
```

Example:

```text
"v000001" = "buy";
"v000002" = "save";
"v000003" = "new";
```

The programme must extract mappings of the form:

```text
v###### -> word
```

### 3.4 Factor Variable-ID Files

Default directory:

```text
factors/var_id
```

For each factor dimension, the programme reads:

```text
factors/var_id/f<n>_pos_var_id.txt
factors/var_id/f<n>_neg_var_id.txt
```

Examples:

```text
factors/var_id/f1_pos_var_id.txt
factors/var_id/f1_neg_var_id.txt
```

These files contain SAS variable IDs associated with the positive and negative poles of a factor.

Variable IDs inside parentheses are treated as secondary loadings and ignored.

### 3.5 File ID Map

Default input path:

```text
file_ids.txt
```

Expected format:

```text
<file_id> <relative_path>
```

The file must have no header.

Example:

```text
t000001 1950/tv_com_1950_1.txt
t000002 1950/tv_com_1950_2.txt
t000104 1960/tv_com_1960_4.txt
```

The first column must match the `filename` column in the scores file.

The second column is used as the readable source filename/path in the output report.

### 3.6 Command-Line Arguments

The programme must support:

```text
--project
```

Default:

```text
current working directory name
```

```text
--sas-output-dir
```

Default:

```text
sas/output_<project>
```

```text
--varid-dir
```

Default:

```text
factors/var_id
```

```text
--file-ids
```

Default:

```text
file_ids.txt
```

```text
--output
```

Default:

```text
examples/score_details.txt
```

---

## 4. Outputs

### 4.1 Output File

Default output path:

```text
examples/score_details.txt
```

The programme must create the parent output directory if it does not exist.

### 4.2 Output Encoding

The output file must be written using:

```text
UTF-8
```

### 4.3 Console Output

After successful generation, the programme should print:

1. completion message;
2. project name;
3. scores file path;
4. word labels file path;
5. factor variable-ID directory;
6. output file path.

Example:

```text
✓ Finished.
Project: cl_st1_ph2_andrea
Scores file: sas/output_cl_st1_ph2_andrea/cl_st1_ph2_andrea_scores.tsv
Word labels file: sas/output_cl_st1_ph2_andrea/word_labels_format.sas
Factor var-id directory: factors/var_id
Output written to: examples/score_details.txt
```

---

## 5. Functional Requirements

### 5.1 Project Inference

The programme must infer the default project name from:

```python
Path.cwd().name
```

This allows the programme to be run from the relevant project phase directory.

Example:

```shell
cd cl_st1_ph2_andrea
python score_details.py
```

infers:

```text
cl_st1_ph2_andrea
```

### 5.2 SAS Output Directory Resolution

If `--sas-output-dir` is omitted, resolve to:

```text
sas/output_<project>
```

If `--sas-output-dir` is supplied, use the supplied path.

Relative paths are resolved relative to the current working directory.

### 5.3 Load Scores Data

The programme must:

1. validate that the scores file exists;
2. read the file as tab-separated UTF-8 text;
3. validate that it contains a `filename` column;
4. detect factor columns.

The scores file path is:

```text
<sas-output-dir>/<project>_scores.tsv
```

### 5.4 Detect Factor Columns

The programme must detect factor-score columns matching:

```regex
fac\d+
```

The detected columns must be sorted numerically.

Example:

```text
fac1, fac2, fac10
```

must become:

```text
fac1, fac2, fac10
```

not:

```text
fac1, fac10, fac2
```

If no factor columns are found, raise:

```text
RuntimeError
```

### 5.5 Determine Number of Factors

The programme must determine the number of factors from the detected factor columns.

Example:

```text
fac1, fac2, fac3
```

means:

```text
3 factors
```

The programme then expects one positive and one negative variable-ID file for each factor number from `1` to the number of detected factors.

### 5.6 Load Word Labels

The programme must read:

```text
<sas-output-dir>/word_labels_format.sas
```

and extract mappings from SAS variable IDs to readable labels.

Expected format:

```text
"v000001" = "word";
```

Extraction pattern:

```regex
"(v\d{6})"\s*=\s*"([^"]+)"
```

The resulting lexicon maps:

```text
v000001 -> word
```

If the word-labels file is missing, raise:

```text
FileNotFoundError
```

If no labels can be extracted, raise:

```text
ValueError
```

### 5.7 Load Factor Variable IDs

The programme must read factor variable-ID files from:

```text
factors/var_id
```

or from the directory supplied with:

```text
--varid-dir
```

For each detected factor dimension, it must read:

```text
f<n>_pos_var_id.txt
f<n>_neg_var_id.txt
```

Variable IDs must match:

```regex
v\d{6}
```

### 5.8 Ignore Secondary Variable IDs

Variable IDs occurring inside parentheses are secondary loadings and must be ignored.

Example input:

```text
v000001, v000002, (v000003), v000004
```

Primary IDs:

```text
v000001
v000002
v000004
```

Secondary IDs ignored:

```text
v000003
```

### 5.9 Preserve Variable-ID Order

Within each factor variable-ID file, primary variable IDs must be kept in their original order.

Duplicate IDs must be removed while preserving the first occurrence.

Example input:

```text
v000001, v000002, v000001, v000003
```

Output list:

```text
v000001
v000002
v000003
```

### 5.10 Load File ID Map

The programme must read `file_ids.txt` as a headerless, whitespace-separated mapping.

Each non-empty line must contain:

```text
file_id relative_path
```

If a line does not contain these two fields, raise:

```text
ValueError
```

If the first line appears to be a header, raise:

```text
ValueError
```

If no file IDs are found, raise:

```text
ValueError
```

### 5.11 Generate Score Details Report

For each row in the scores file, the programme must write:

```text
text ID: <file_id>
filename: <mapped filename or UNKNOWN>
```

Then, for each factor dimension, it must write:

```text
f<n> score: <score>
f<n> pos words (N=<count>): <comma-separated words>
f<n> neg words (N=<count>): <comma-separated words>
```

A separator line must be written after each text:

```text
=============================================
```

### 5.12 Map File IDs to Source Paths

For each row, the programme must find the `filename` value in `file_ids.txt`.

If found, output the mapped path.

If not found, output:

```text
UNKNOWN
```

The programme must continue execution when a file ID is missing from the map.

### 5.13 Determine Present Positive-Pole Words

For each text and factor dimension:

1. read the factor’s positive variable-ID list;
2. check each variable ID against the corresponding column in the scores row;
3. treat the variable as present if its value is not equal to:

```text
0
```

4. convert present variable IDs to word labels using the lexicon;
5. if a variable ID has no label, use the variable ID itself.

### 5.14 Determine Present Negative-Pole Words

For each text and factor dimension:

1. read the factor’s negative variable-ID list;
2. check each variable ID against the corresponding column in the scores row;
3. treat the variable as present if its value is not equal to:

```text
0
```

4. convert present variable IDs to word labels using the lexicon;
5. if a variable ID has no label, use the variable ID itself.

### 5.15 Missing Variable Columns in Scores

If a variable ID from a factor variable-ID file is not present as a column in the scores file, it must be treated as absent.

The programme must not fail for a missing variable-ID column in the scores data.

### 5.16 Output Directory Creation

Before writing the report, the programme must create the parent directory of the output file if needed.

Example:

```text
examples/
```

---

## 6. Output Content Requirements

### 6.1 Report Structure

For each text, the report must follow this structure:

```text
text ID: t000001
filename: 1950/tv_com_1950_1.txt

f1 score: 0.42
f1 pos words (N=2): buy, save
f1 neg words (N=0): 

f2 score: -0.13
f2 pos words (N=1): new
f2 neg words (N=1): old

=============================================
```

### 6.2 Text ID Line

The text ID line must be:

```text
text ID: <file_id>
```

where `<file_id>` is the row value from the `filename` column.

### 6.3 Filename Line

The filename line must be:

```text
filename: <mapped path>
```

If the file ID is not found in the file ID map, the value must be:

```text
UNKNOWN
```

### 6.4 Factor Score Line

Each factor score line must be:

```text
f<n> score: <score>
```

The score may be written using its original pandas/string representation.

### 6.5 Positive Words Line

Each positive-pole words line must be:

```text
f<n> pos words (N=<count>): <comma-separated words>
```

The count must equal the number of present positive-pole variable IDs.

### 6.6 Negative Words Line

Each negative-pole words line must be:

```text
f<n> neg words (N=<count>): <comma-separated words>
```

The count must equal the number of present negative-pole variable IDs.

### 6.7 Separator

Each text block must end with:

```text
=============================================
```

followed by a blank line.

---

## 7. Error Handling Requirements

### 7.1 Missing Scores File

If the scores file does not exist, raise:

```text
FileNotFoundError
```

### 7.2 Missing Filename Column

If the scores file does not contain:

```text
filename
```

raise:

```text
ValueError
```

### 7.3 No Factor Columns

If no columns matching:

```regex
fac\d+
```

are found in the scores file, raise:

```text
RuntimeError
```

### 7.4 Missing Word Labels File

If:

```text
word_labels_format.sas
```

does not exist in the SAS output directory, raise:

```text
FileNotFoundError
```

### 7.5 Empty or Invalid Word Labels File

If no variable labels can be extracted from the word-labels file, raise:

```text
ValueError
```

### 7.6 Missing Variable-ID Directory

If the factor variable-ID directory does not exist, raise:

```text
FileNotFoundError
```

### 7.7 Missing Variable-ID File

If any expected file is missing:

```text
f<n>_pos_var_id.txt
f<n>_neg_var_id.txt
```

raise:

```text
FileNotFoundError
```

### 7.8 Missing File ID Map

If `file_ids.txt` does not exist, raise:

```text
FileNotFoundError
```

### 7.9 Invalid File ID Map Format

If a non-empty line in `file_ids.txt` does not contain:

```text
file_id path
```

raise:

```text
ValueError
```

### 7.10 Header in File ID Map

If the first line appears to be a header, raise:

```text
ValueError
```

### 7.11 Empty File ID Map

If no file IDs are found in `file_ids.txt`, raise:

```text
ValueError
```

### 7.12 Missing File ID in Map

If a row’s `filename` value is not present in `file_ids.txt`, output:

```text
UNKNOWN
```

and continue.

### 7.13 Missing Variable-ID Column in Scores

If a factor variable ID is not present as a column in the scores file, treat it as absent and continue.

---

## 8. Non-Functional Requirements

### 8.1 Encoding

All input and output text files must use:

```text
UTF-8
```

### 8.2 Determinism

The programme must produce deterministic output:

- scores rows processed in input order;
- factor columns sorted numerically;
- factors processed in ascending numeric order;
- positive-pole words listed in factor-file order;
- negative-pole words listed in factor-file order;
- duplicate variable IDs removed while preserving first occurrence.

### 8.3 No Input Mutation

The programme must not modify:

```text
sas/output_<project>/
factors/var_id/
file_ids.txt
```

### 8.4 Output Overwrite Behaviour

The programme may overwrite an existing output file at:

```text
examples/score_details.txt
```

or at the path supplied with:

```text
--output
```

### 8.5 No External Compilation or Analysis

The programme only writes a plain-text report.

It must not call SAS, LaTeX, or any external analysis tool.

### 8.6 Dependency Requirements

The programme depends on:

```text
pandas
```

It also uses Python standard-library modules including:

```text
argparse
re
pathlib
```

The programme must run under the project Python environment.

---

## 9. Downstream Usage

The generated report is intended for manual inspection during factor interpretation.

Typical output file:

```text
examples/score_details.txt
```

The report can be used to answer questions such as:

1. Which positive-pole words contributed to a text’s factor score?
2. Which negative-pole words appeared in a text?
3. Do the listed words support the interpretation of the factor dimension?
4. Are high-scoring or low-scoring examples driven by expected loading terms?

---

## 10. Acceptance Criteria

The programme is correct if:

1. It can be run from the project root using:

```shell
python score_details.py
```

2. It accepts an explicit project name:

```shell
python score_details.py --project cl_st1_ph2_andrea
```

3. It accepts an explicit SAS output directory:

```shell
python score_details.py --sas-output-dir sas/output_cl_st1_ph2_andrea
```

4. It accepts an explicit variable-ID directory:

```shell
python score_details.py --varid-dir factors/var_id
```

5. It accepts an explicit file ID map:

```shell
python score_details.py --file-ids file_ids.txt
```

6. It accepts an explicit output path:

```shell
python score_details.py --output examples/score_details.txt
```

7. It reads:

```text
<project>_scores.tsv
```

from the SAS output directory.

8. It reads:

```text
word_labels_format.sas
```

from the SAS output directory.

9. It detects all `fac<n>` columns.

10. It reads all required positive and negative variable-ID files.

11. It ignores variable IDs inside parentheses.

12. It preserves the order of primary variable IDs.

13. It maps variable IDs to readable word labels.

14. It processes all rows in the scores file.

15. It writes one report block per text.

16. It lists present positive-pole and negative-pole words for each factor.

17. It treats missing variable-ID columns as absent.

18. It writes `UNKNOWN` for file IDs missing from `file_ids.txt`.

19. It creates the output parent directory if needed.

20. It writes UTF-8 output.

21. It does not require manual path editing between Phase 2 and Phase 3, provided it is run from the correct project directory or supplied with `--project`.

---

## 11. Example

### Input

Scores file:

```text
sas/output_cl_st1_ph2_andrea/cl_st1_ph2_andrea_scores.tsv
```

Example scores columns:

```text
filename	decade	v000001	v000002	v000003	fac1	fac2
t000001	1950	1	1	0	0.42	-0.13
t000002	1950	0	1	1	-0.22	0.54
```

Word labels file:

```text
sas/output_cl_st1_ph2_andrea/word_labels_format.sas
```

Example content:

```text
"value" $lexlabels
"v000001" = "buy";
"v000002" = "save";
"v000003" = "new";
```

Positive variable-ID file:

```text
factors/var_id/f1_pos_var_id.txt
```

Example content:

```text
v000001, v000002, (v000003)
```

Negative variable-ID file:

```text
factors/var_id/f1_neg_var_id.txt
```

Example content:

```text
v000003
```

File ID map:

```text
file_ids.txt
```

Example content:

```text
t000001 1950/tv_com_1950_1.txt
t000002 1950/tv_com_1950_2.txt
```

### Command

```shell
python score_details.py
```

### Output

```text
examples/score_details.txt
```

### Output Example

```text
text ID: t000001
filename: 1950/tv_com_1950_1.txt

f1 score: 0.42
f1 pos words (N=2): buy, save
f1 neg words (N=0): 

f2 score: -0.13
f2 pos words (N=0): 
f2 neg words (N=0): 

=============================================

text ID: t000002
filename: 1950/tv_com_1950_2.txt

f1 score: -0.22
f1 pos words (N=1): save
f1 neg words (N=1): new

f2 score: 0.54
f2 pos words (N=0): 
f2 neg words (N=0): 

=============================================
```

---

## 12. Recommended Future Enhancements

These are optional and must not alter current default behaviour unless explicitly requested.

### 12.1 Include Decade in Header

Add the text decade to each report block:

```text
decade: 1950
```

### 12.2 Sort by Factor Score

Expose:

```text
--sort-by fac<n>
```

to sort report blocks by a selected factor score.

### 12.3 Filter by Factor

Expose:

```text
--factor
```

to output details for only one factor dimension.

### 12.4 Filter by Text ID

Expose:

```text
--text-id
```

to output details for one selected text.

### 12.5 CSV or TSV Output

Add optional structured output formats:

```text
--format txt
--format csv
--format tsv
```

### 12.6 Missing Label Report

Write a separate report listing variable IDs that appeared in factor files but were not found in:

```text
word_labels_format.sas
```

### 12.7 Manifest

Write:

```text
examples/score_details_manifest.json
```

containing:

- project;
- scores file;
- word labels file;
- factor variable-ID directory;
- file ID map;
- output file;
- detected factors.

---

## 13. Summary

`score_details.py` creates a plain-text report linking LMDA factor scores to the factor-loading words present in each text.

Its core responsibility is:

```text
For each text and factor dimension, list the positive-pole and negative-pole loading words that occur in the text.
```

It must preserve:

- project inference from the current working directory;
- automatic factor detection;
- use of SAS variable labels;
- primary loading selection from factor variable-ID files;
- stable input-order text processing;
- compatibility across Phase 2 and Phase 3.