# Development Specification: `examples_txt.py`

## 1. Programme Purpose

`examples_txt.py` generates plaintext example files for each LMDA factor pole.

The programme follows the same selection logic as the LaTeX example generator, but writes readable `.txt` files containing:

1. text ID;
2. decade;
3. source file path;
4. factor-pole score;
5. loading words present in the text;
6. the original full text.

The programme is intended to support qualitative review of factor examples without requiring LaTeX compilation.

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
examples_txt.py
```

Example:

```text
cl_st1_ph2_andrea/examples_txt.py
cl_st1_ph3_andrea/examples_txt.py
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

Example for Phase 2:

```text
sas/output_cl_st1_ph2_andrea/cl_st1_ph2_andrea_scores_only.tsv
```

Example for Phase 3:

```text
sas/output_cl_st1_ph3_andrea/cl_st1_ph3_andrea_scores_only.tsv
```

The file must be tab-separated.

### 3.2 Required Scores Columns

The scores file must contain:

| Column | Description |
|---|---|
| `filename` | Internal file identifier, such as `t000001` |
| `decade` | Decade stratum for the text |
| `fac<n>` | Factor score for dimension `<n>` |

Example:

```text
filename	decade	group	fac1	fac2
t000001	1950	1950	0.21	-0.13
t000002	1950	1950	0.44	0.05
t000104	1960	1960	-0.17	0.22
```

The programme detects available factor dimensions from columns matching:

```regex
fac\d+
```

### 3.3 SAS Means Files

For each factor dimension, the programme reads:

```text
means_decade_f<n>.tsv
```

from the SAS output directory.

Example:

```text
sas/output_cl_st1_ph2_andrea/means_decade_f1.tsv
```

Each means file must contain:

| Column | Description |
|---|---|
| `decade` | Decade group |
| `Mean fac<n>` | Mean score for factor `<n>` in that decade |

Example:

```text
decade	Mean fac1
1950	0.127
1960	-0.034
1970	0.088
```

These mean values determine the order in which decades are sampled for each factor pole.

### 3.4 File ID Map

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

The second column is resolved relative to both the tagged corpus root and the full-text corpus root.

### 3.5 Score Details File

Default input path:

```text
examples/score_details.txt
```

This file is produced by:

```shell
python score_details.py
```

It is used to retrieve the loading words present in each selected text for each factor pole.

Expected block structure:

```text
text ID: t000001
filename: 1950/tv_com_1950_1.txt

f1 score: 0.42
f1 pos words (N=2): buy, save
f1 neg words (N=0): 

=============================================
```

The programme parses lines of the form:

```text
f<n> pos words (N=<count>): <words>
f<n> neg words (N=<count>): <words>
```

### 3.6 Tagged Corpus Files

Default tagged corpus root:

```text
corpus/07_tagged
```

Expected tagged text path format:

```text
corpus/07_tagged/<Decade>/<Commercial ID>.txt
```

Example:

```text
corpus/07_tagged/1950/tv_com_1950_1.txt
```

The tagged corpus is used as an existence check so that plaintext example selection remains stable with the LaTeX example generation workflow.

### 3.7 Full-Text Corpus Files

The full-text corpus root may be supplied explicitly with:

```text
--fulltext-root
```

If omitted, the programme must infer the full-text root.

For Phase 2, preferred default:

```text
corpus/commercial_verbal
```

For Phase 3, preferred default:

```text
corpus/commercial_visual
```

If the project name contains:

```text
ph2
```

and `corpus/commercial_verbal` exists, use:

```text
corpus/commercial_verbal
```

If the project name contains:

```text
ph3
```

and `corpus/commercial_visual` exists, use:

```text
corpus/commercial_visual
```

If phase-specific inference fails, fall back to whichever of the following exists:

```text
corpus/commercial_visual
corpus/commercial_verbal
```

If neither exists, raise:

```text
FileNotFoundError
```

### 3.8 Command-Line Arguments

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
--tagged-base
```

Default:

```text
corpus/07_tagged
```

```text
--fulltext-root
```

Default:

```text
inferred from project phase and available corpus directories
```

```text
--file-ids
```

Default:

```text
file_ids.txt
```

```text
--score-details
```

Default:

```text
examples/score_details.txt
```

```text
--output-dir
```

Default:

```text
examples_txt
```

```text
--top-decade-examples
```

Default:

```text
20
```

```text
--other-decade-examples
```

Default:

```text
10
```

---

## 4. Outputs

### 4.1 Output Directory

Default:

```text
examples_txt
```

The programme must create this directory if it does not exist.

### 4.2 Per-Factor Pole Directories

For each factor dimension and pole, the programme creates:

```text
examples_txt/f<n>_pos/
examples_txt/f<n>_neg/
```

Examples:

```text
examples_txt/f1_pos/
examples_txt/f1_neg/
examples_txt/f2_pos/
examples_txt/f2_neg/
```

### 4.3 Individual Plaintext Example Files

For each selected example, the programme writes one `.txt` file.

Filename format:

```text
examples_txt/f<n>_<pole>/f<n>_<pole>_<id>.txt
```

Example:

```text
examples_txt/f1_pos/f1_pos_001.txt
examples_txt/f1_pos/f1_pos_002.txt
examples_txt/f1_neg/f1_neg_001.txt
```

The example ID must be zero-padded to three digits.

### 4.4 Missing Files Report

If any selected tagged or full-text files cannot be located, the programme writes:

```text
missing_files.txt
```

This file contains one missing `filename` value per line.

### 4.5 Missing Loading Words Report

If loading-word information is missing from the score-details file for a selected text and label, the programme writes:

```text
missing_loading_words.txt
```

Each line must contain:

```text
<text_id>	<label>
```

Example:

```text
t000001	f1_pos
```

### 4.6 Output Encoding

All generated files must be written using:

```text
UTF-8
```

---

## 5. Functional Requirements

### 5.1 Project Inference

The programme must infer the default project name from:

```python
Path.cwd().name
```

This allows it to be run from the relevant project phase directory.

Example:

```shell
cd cl_st1_ph2_andrea
python examples_txt.py
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

### 5.3 Full-Text Root Resolution

If `--fulltext-root` is supplied, use the supplied path.

If it is omitted:

1. use `corpus/commercial_visual` for Phase 3 when available;
2. use `corpus/commercial_verbal` for Phase 2 when available;
3. otherwise use `corpus/commercial_visual` if it exists;
4. otherwise use `corpus/commercial_verbal` if it exists;
5. otherwise raise `FileNotFoundError`.

### 5.4 Input Path Validation

The programme must validate that the following exist:

```text
<sas-output-dir>/<project>_scores_only.tsv
<tagged-base>
<fulltext-root>
<file-ids>
<score-details>
```

If any required path is missing, the programme must raise:

```text
FileNotFoundError
```

### 5.5 Load File ID Map

The programme must read `file_ids.txt` as a headerless, whitespace-separated mapping.

Each non-empty line must contain:

```text
file_id relative_path
```

If a line does not contain exactly these two fields, raise:

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

### 5.6 Read Scores Data

The programme must:

1. read the scores file with pandas using tab separation;
2. validate required columns;
3. normalize `filename` as stripped strings;
4. normalize `decade` as stripped strings;
5. detect factor columns.

Required columns:

```text
filename
decade
```

### 5.7 Detect Factor Columns

The programme must detect factor-score columns named:

```regex
fac\d+
```

The detected factor columns must be sorted naturally.

Example:

```text
fac1, fac2, fac10
```

must be ordered as:

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

### 5.8 Parse Score Details

The programme must parse the score-details file into a lookup structure:

```text
loading_words[text_id][f<n>_pos] -> list of words
loading_words[text_id][f<n>_neg] -> list of words
```

It must:

1. split the report into text blocks using the separator line;
2. identify each block’s text ID;
3. parse positive-pole words for each factor;
4. parse negative-pole words for each factor;
5. split comma-separated words;
6. strip whitespace;
7. remove empty word values.

If the score-details file is missing, raise:

```text
FileNotFoundError
```

with guidance to run:

```shell
python score_details.py
```

### 5.9 Read Decade Means

For each factor dimension, the programme must read:

```text
means_decade_f<n>.tsv
```

from the SAS output directory.

The programme must validate that the file contains:

```text
decade
Mean fac<n>
```

It must return a mapping:

```text
decade -> mean score
```

If the means file has no decades, raise:

```text
ValueError
```

### 5.10 Rank Decades by Pole

For each factor dimension:

- the positive pole ranks decades by descending mean factor score;
- the negative pole ranks decades by ascending mean factor score.

For the positive pole:

```text
highest mean = top decade
```

For the negative pole:

```text
lowest mean = top decade
```

The first ranked decade receives the larger example quota.

### 5.11 Example Quotas

For each factor pole:

1. select up to `--top-decade-examples` examples from the top-ranked decade;
2. select up to `--other-decade-examples` examples from every other ranked decade.

Default:

```text
top-ranked decade: 20 examples
other decades: 10 examples each
```

### 5.12 Sort Texts by Factor Score

Within each pole, texts must be sorted by the corresponding factor score:

- positive pole: descending score;
- negative pole: ascending score.

Texts with a factor score of exactly:

```text
0
```

must be skipped.

### 5.13 Tagged Corpus Existence Check

For each selected scores row, the programme must locate the corresponding tagged corpus file using:

```text
<tagged-base>/<relative_path_from_file_ids>
```

If the tagged file does not exist, the text must not be selected.

The `filename` must be recorded in:

```text
missing_files.txt
```

### 5.14 Locate Full Text

For each selected scores row, the programme must locate the corresponding full-text file using:

```text
<fulltext-root>/<relative_path_from_file_ids>
```

If the full-text file does not exist, the text must not be selected.

The `filename` must be recorded in:

```text
missing_files.txt
```

### 5.15 Retrieve Loading Words

For each selected text and pole label, retrieve loading words from the parsed score-details lookup.

The label format must be:

```text
f<n>_<pole>
```

Examples:

```text
f1_pos
f1_neg
```

If no loading-word entry exists for the selected text and label:

1. record the pair in `missing_loading_words.txt`;
2. continue with an empty loading-word list.

### 5.16 Write Plaintext Example

Each plaintext example must contain a header followed by the original full text.

Header format:

```text
Text ID: <text_id>
Decade: <decade>
File:   <fulltext_path>

Score (<label>): <score_value>
Loading words (<label>), N=<count>: <comma-separated loading words>

<full text>
```

The full text must be read from the full-text file using UTF-8, ignoring decoding errors if necessary.

### 5.17 Output Directory Creation

For each factor pole, create the corresponding output directory before writing examples.

Example:

```text
examples_txt/f1_pos
```

---

## 6. Output Content Requirements

### 6.1 Directory Layout

For two detected factor dimensions, the output structure should be:

```text
examples_txt/
  f1_pos/
    f1_pos_001.txt
    f1_pos_002.txt
  f1_neg/
    f1_neg_001.txt
    f1_neg_002.txt
  f2_pos/
    f2_pos_001.txt
  f2_neg/
    f2_neg_001.txt
```

### 6.2 Example File Naming

Individual plaintext example files must use:

```text
f<n>_<pole>_<three-digit-id>.txt
```

Examples:

```text
f1_pos_001.txt
f1_pos_020.txt
f1_neg_001.txt
```

### 6.3 Example Header

Each plaintext file must start with:

```text
Text ID: <text_id>
Decade: <decade>
File:   <fulltext_path>

Score (<label>): <score_value>
Loading words (<label>), N=<count>: <comma-separated loading words>
```

### 6.4 Full Text Body

The header must be followed by a blank line and then the original full text.

The full text should not be LaTeX-escaped or annotated.

### 6.5 Missing Files Report Format

If generated, `missing_files.txt` must contain sorted unique file IDs:

```text
t000001
t000044
t000207
```

### 6.6 Missing Loading Words Report Format

If generated, `missing_loading_words.txt` must contain sorted unique text ID / label pairs:

```text
t000001	f1_pos
t000003	f2_neg
```

---

## 7. Error Handling Requirements

### 7.1 Missing Scores File

If the scores file does not exist, raise:

```text
FileNotFoundError
```

### 7.2 Missing Tagged Corpus Directory

If the tagged corpus root does not exist, raise:

```text
FileNotFoundError
```

### 7.3 Missing Full-Text Corpus Directory

If the full-text corpus root does not exist or cannot be inferred, raise:

```text
FileNotFoundError
```

### 7.4 Missing File ID Map

If `file_ids.txt` does not exist, raise:

```text
FileNotFoundError
```

### 7.5 Invalid File ID Map Format

If a non-empty line in `file_ids.txt` does not contain exactly:

```text
file_id path
```

raise:

```text
ValueError
```

### 7.6 Header in File ID Map

If `file_ids.txt` appears to contain a header, raise:

```text
ValueError
```

### 7.7 Empty File ID Map

If no valid file IDs are found, raise:

```text
ValueError
```

### 7.8 Missing Score Details File

If the score-details file is missing, raise:

```text
FileNotFoundError
```

The error message should tell the user to generate it with:

```shell
python score_details.py
```

### 7.9 Missing Required Scores Columns

If the scores file does not contain:

```text
filename
decade
```

raise:

```text
ValueError
```

The error message should identify the missing columns.

### 7.10 No Factor Columns

If no columns matching:

```regex
fac\d+
```

are found, raise:

```text
RuntimeError
```

### 7.11 Missing Factor Score Column During Processing

If an expected factor score column is missing during factor processing, raise:

```text
ValueError
```

### 7.12 Missing Means File

If an expected means file is missing, raise:

```text
FileNotFoundError
```

### 7.13 Missing Means Columns

If a means file is missing either:

```text
decade
Mean fac<n>
```

raise:

```text
ValueError
```

### 7.14 Empty Means File

If no decades are available from a means file, raise:

```text
ValueError
```

### 7.15 Missing Tagged or Full-Text Files

If selected tagged or full-text files cannot be located, execution must continue.

The missing file IDs must be written to:

```text
missing_files.txt
```

### 7.16 Missing Loading Words

If loading-word data is absent for a selected text and label, execution must continue.

The missing text ID / label pairs must be written to:

```text
missing_loading_words.txt
```

---

## 8. Non-Functional Requirements

### 8.1 Encoding

All input and output text files must use:

```text
UTF-8
```

Full-text files should be read with decoding errors ignored.

### 8.2 Determinism

The programme must produce deterministic output:

- factor columns sorted naturally;
- factor dimensions processed in numeric order;
- positive pole processed before negative pole;
- decades ranked deterministically by mean score;
- selected examples ordered by factor score;
- output filenames stable;
- missing reports sorted.

### 8.3 No Input Mutation

The programme must not modify:

```text
sas/output_<project>/
corpus/07_tagged/
corpus/commercial_verbal/
corpus/commercial_visual/
file_ids.txt
examples/score_details.txt
```

### 8.4 Output Overwrite Behaviour

The programme may overwrite existing generated `.txt` files under:

```text
examples_txt/
```

It may also overwrite:

```text
missing_files.txt
missing_loading_words.txt
```

### 8.5 No External Compilation or Analysis

The programme only writes plaintext files.

It must not call SAS, LaTeX, or any external analysis process.

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

The generated plaintext files are intended for manual review and qualitative interpretation.

Typical output:

```text
examples_txt/f1_pos/f1_pos_001.txt
```

The files can be opened directly in a text editor and do not require LaTeX or other tooling.

They are useful for checking:

1. which texts were selected for each factor pole;
2. which loading words were present in those texts;
3. whether the full text supports the interpretation of the factor pole;
4. whether the selected examples align with the LaTeX examples.

---

## 10. Acceptance Criteria

The programme is correct if:

1. It can be run from the project root using:

```shell
python examples_txt.py
```

2. It accepts an explicit project name:

```shell
python examples_txt.py --project cl_st1_ph2_andrea
```

3. It accepts an explicit SAS output directory:

```shell
python examples_txt.py --sas-output-dir sas/output_cl_st1_ph2_andrea
```

4. It accepts an explicit tagged corpus directory:

```shell
python examples_txt.py --tagged-base corpus/07_tagged
```

5. It accepts an explicit full-text corpus root:

```shell
python examples_txt.py --fulltext-root corpus/commercial_verbal
```

6. It accepts an explicit file ID map:

```shell
python examples_txt.py --file-ids file_ids.txt
```

7. It accepts an explicit score-details file:

```shell
python examples_txt.py --score-details examples/score_details.txt
```

8. It accepts an explicit output directory:

```shell
python examples_txt.py --output-dir examples_txt
```

9. It reads the correct scores file.

10. It detects all `fac<n>` dimensions.

11. It reads the required `means_decade_f<n>.tsv` files.

12. It parses `examples/score_details.txt`.

13. It ranks decades correctly:
    - descending means for positive poles;
    - ascending means for negative poles.

14. It skips examples with factor score equal to zero.

15. It checks tagged corpus file existence before selecting a text.

16. It reads the corresponding full-text corpus file.

17. It writes individual plaintext files under:

```text
examples_txt/f<n>_pos/
examples_txt/f<n>_neg/
```

18. It includes score and loading-word metadata in each plaintext file.

19. It writes missing tagged or full-text file IDs to `missing_files.txt`.

20. It writes missing loading-word pairs to `missing_loading_words.txt`.

21. It does not require manual path editing between Phase 2 and Phase 3, provided it is run from the correct project directory or supplied with `--project`.

---

## 11. Example

### Input

Scores file:

```text
sas/output_cl_st1_ph2_andrea/cl_st1_ph2_andrea_scores_only.tsv
```

Example scores columns:

```text
filename	decade	group	fac1	fac2
t000001	1950	1950	1.24	-0.13
t000002	1950	1950	0.98	0.05
t000104	1960	1960	-0.77	0.22
```

Means file:

```text
sas/output_cl_st1_ph2_andrea/means_decade_f1.tsv
```

Example means columns:

```text
decade	Mean fac1
1950	0.42
1960	-0.18
1970	0.09
```

File ID map:

```text
file_ids.txt
```

Example content:

```text
t000001 1950/tv_com_1950_1.txt
```

Score details:

```text
examples/score_details.txt
```

Example content:

```text
text ID: t000001
filename: 1950/tv_com_1950_1.txt

f1 score: 1.24
f1 pos words (N=2): buy, save
f1 neg words (N=0): 

=============================================
```

Full-text file:

```text
corpus/commercial_verbal/1950/tv_com_1950_1.txt
```

Example content:

```text
Buy now and save with this special offer.
```

### Command

```shell
python examples_txt.py
```

### Output

```text
examples_txt/f1_pos/f1_pos_001.txt
```

### Example Output File

```text
Text ID: t000001
Decade: 1950
File:   corpus/commercial_verbal/1950/tv_com_1950_1.txt

Score (f1_pos): 1.24
Loading words (f1_pos), N=2: buy, save

Buy now and save with this special offer.
```

---

## 12. Recommended Future Enhancements

These are optional and must not alter current default behaviour unless explicitly requested.

### 12.1 Relative File Paths in Header

Add an option to write relative paths instead of full or resolved paths:

```text
--relative-paths
```

### 12.2 Configurable Source Variable

Expose:

```text
--group-var
```

Default:

```text
decade
```

This would allow plaintext examples to be selected by other grouping variables.

### 12.3 Minimum Loading Word Count

Expose:

```text
--min-loading-words
```

to require a selected example to contain at least a given number of loading words.

### 12.4 Include Ranked Decade Information

Add fields to the example header:

```text
Ranked decade position: 1
Decade mean score: 0.42
```

### 12.5 Manifest

Write:

```text
examples_txt/examples_txt_manifest.json
```

containing:

- project;
- scores file;
- tagged corpus root;
- full-text corpus root;
- score-details file;
- detected factors;
- generated files;
- missing files;
- missing loading-word pairs.

### 12.6 Clean Output Directory Option

Expose:

```text
--clean
```

to delete previously generated files before writing new output.

---

## 13. Summary

`examples_txt.py` creates plaintext examples for interpreting LMDA factor dimensions.

Its core responsibility is:

```text
For each factor pole, select high-scoring representative texts by decade and write the original full text with score and loading-word metadata.
```

It must preserve:

- project inference from the current working directory;
- automatic factor detection;
- decade ranking by SAS mean factor scores;
- selection alignment with the LaTeX examples workflow;
- separate positive and negative pole outputs;
- stable example numbering;
- compatibility across Phase 2 and Phase 3.