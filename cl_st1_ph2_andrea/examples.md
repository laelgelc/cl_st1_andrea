# Development Specification: `examples.py`

## 1. Programme Purpose

`examples.py` generates LaTeX example extracts for LMDA factor dimensions.

For each factor dimension, the programme selects texts with the highest or lowest factor scores, grouped by decade, and writes LaTeX files containing annotated text examples.

The programme creates examples for both poles of each dimension:

1. **positive pole**;
2. **negative pole**.

In each example, wordforms whose lemmas belong to the relevant factor pole are highlighted in bold.

The programme is intended to support qualitative interpretation of LMDA factors by showing representative text extracts from the decades most strongly associated with each factor pole.

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
examples.py
```

Example:

```text
cl_st1_ph2_andrea/examples.py
cl_st1_ph3_andrea/examples.py
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

### 3.4 Factor Pole Files

For each factor dimension and pole, the programme reads:

```text
factors/f<n>_pos.txt
factors/f<n>_neg.txt
```

Examples:

```text
factors/f1_pos.txt
factors/f1_neg.txt
```

These files contain the primary lemmas associated with each factor pole.

The first line is treated as a heading and ignored.

Secondary loadings enclosed in parentheses are ignored.

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

The second column is resolved relative to the tagged corpus directory.

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

Each tagged corpus file must contain whitespace-separated token lines.

Expected minimum columns:

```text
wordform tag lemma
```

Example:

```text
Buy VB buy
now RB now
! . !
```

Only the first three columns are required.

### 3.7 Optional LaTeX Header

The programme may use:

```text
examples/top_header
```

as the preamble for the generated master LaTeX document.

If this file exists, the programme creates:

```text
examples/examples.tex
```

If this file is missing, individual example files are still generated, but the master file is not created.

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
--factor-folder
```

Default:

```text
factors
```

```text
--examples-dir
```

Default:

```text
examples
```

```text
--file-ids
```

Default:

```text
file_ids.txt
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
examples
```

The programme must create this directory if it does not exist.

### 4.2 Per-Factor Pole Directories

For each factor dimension and pole, the programme creates:

```text
examples/f<n>_pos/
examples/f<n>_neg/
```

Examples:

```text
examples/f1_pos/
examples/f1_neg/
examples/f2_pos/
examples/f2_neg/
```

### 4.3 Individual Example Files

For each selected example, the programme writes one `.tex` file.

Filename format:

```text
examples/f<n>_<pole>/f<n>_<pole>_<id>.tex
```

Example:

```text
examples/f1_pos/f1_pos_001.tex
examples/f1_pos/f1_pos_002.tex
examples/f1_neg/f1_neg_001.tex
```

The example ID must be zero-padded to three digits.

### 4.4 Master LaTeX File

If:

```text
examples/top_header
```

exists, the programme writes:

```text
examples/examples.tex
```

This master file includes:

1. the contents of `examples/top_header`;
2. `\begin{document}`;
3. `\maketitle`;
4. `\tableofcontents`;
5. one section per factor pole;
6. `\input{...}` statements for all generated example files;
7. `\end{document}`.

### 4.5 Missing Files Report

If any tagged text files listed in the scores data cannot be located through `file_ids.txt`, the programme writes:

```text
missing_files.txt
```

This file contains one missing `filename` value per line.

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
python examples.py
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

### 5.3 Input Directory Validation

The programme must validate that the following exist:

```text
<sas-output-dir>/<project>_scores_only.tsv
<tagged-base>
<factor-folder>
<file-ids>
```

If any required path is missing, the programme must raise:

```text
FileNotFoundError
```

### 5.4 Load File ID Map

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

### 5.5 Read Scores Data

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

### 5.6 Detect Factor Columns

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

### 5.7 Read Decade Means

For each factor dimension, the programme must read:

```text
means_decade_f<n>.tsv
```

The programme must validate that the file contains:

```text
decade
Mean fac<n>
```

It must return a mapping:

```text
decade -> mean score
```

### 5.8 Rank Decades by Pole

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

### 5.9 Example Quotas

For each factor pole:

1. select up to `--top-decade-examples` examples from the top-ranked decade;
2. select up to `--other-decade-examples` examples from every other ranked decade.

Default:

```text
top-ranked decade: 20 examples
other decades: 10 examples each
```

### 5.10 Sort Texts by Factor Score

Within each pole, texts must be sorted by the corresponding factor score:

- positive pole: descending score;
- negative pole: ascending score.

Texts with a factor score of exactly:

```text
0
```

must be skipped.

### 5.11 Load Primary Lemmas

For each factor pole file:

```text
factors/f<n>_pos.txt
factors/f<n>_neg.txt
```

the programme must extract primary lemmas.

Rules:

1. ignore the first line;
2. split remaining content on commas;
3. ignore empty items;
4. ignore items starting with `(`;
5. extract the lemma before the first opening parenthesis.

Example item:

```text
buy (0.45)
```

extracts:

```text
buy
```

Example secondary item:

```text
(sell 0.32)
```

is ignored.

### 5.12 Locate Tagged Text

For each selected row in the scores file:

1. find the row’s `filename` in the file ID map;
2. retrieve the mapped relative path;
3. resolve it against the tagged corpus root.

Example:

```text
filename: t000001
file_ids.txt: t000001 1950/tv_com_1950_1.txt
tagged base: corpus/07_tagged
resolved path: corpus/07_tagged/1950/tv_com_1950_1.txt
```

If the file cannot be found, record the `filename` for the missing-files report and continue.

### 5.13 Annotate Text

The programme must read tagged text files and reconstruct readable text.

For each token line:

1. split the line into whitespace-separated fields;
2. skip lines with fewer than three fields;
3. read:
    - `wordform`;
    - `tag`;
    - `lemma`;
4. if the lemma is a primary lemma for the current factor pole, bold the wordform;
5. otherwise, output the wordform normally.

Bolded wordforms must use:

```latex
\textbf{...}
```

### 5.14 Stoplist

The programme must support a stoplist of lemmas that should not be bolded even if they occur in the primary lemma set.

Default stoplist:

```text
empty
```

If a lemma is in the stoplist, it must not be bolded.

### 5.15 LaTeX Escaping

The programme must escape common LaTeX special characters in wordforms, paths, and labels where appropriate.

At minimum, it must escape:

```text
\
_
%
&
#
{
}
$
```

Before token annotation, raw text must remove characters that can break LaTeX command structure:

```text
{
}
\
```

### 5.16 Text Cleanup

After reconstructing token text, the programme must clean spacing.

Required cleanup:

1. merge English negation spacing:

```text
do n 't
```

or equivalent token spacing must become:

```text
don't
```

2. remove spaces before punctuation:

```text
word .
```

becomes:

```text
word.
```

3. remove unwanted spacing around quotation marks where possible.

### 5.17 Paragraph Splitting

The reconstructed text must be split into paragraph-like units at sentence boundaries.

Sentence boundaries are punctuation marks:

```text
.
!
?
```

followed by whitespace and an uppercase letter.

Empty paragraphs must be removed.

### 5.18 Emoji Handling

Characters whose Unicode category is:

```text
So
```

must be wrapped so that a LaTeX emoji font command can render them.

Format:

```latex
{\EmojiFont <character>}
```

This assumes that `\EmojiFont` may be defined in `examples/top_header`.

### 5.19 Write Individual Example Files

Each selected example file must contain a `textsample` environment.

Format:

```latex
\begin{textsample}{<title>}  \label{<label>}
<paragraph text>

% matched lemmas: <comma-separated matched lemmas>
\end{textsample}
```

The title must contain:

1. pole name;
2. dimension number;
3. decade;
4. factor score rounded to two decimal places;
5. source filename/path.

Example title:

```text
POS Dim 1 – 1950 – Score 1.24 – 1950/tv_com_1950_1.txt
```

The label format must be:

```text
ex:f<n>_<pole>_<id>
```

Example:

```text
ex:f1_pos_001
```

### 5.20 Matched Lemma Comment

Each example file must include a comment listing the primary lemmas that were matched in that text.

Format:

```latex
% matched lemmas: buy, new, save
```

If no lemmas are matched, the comment may be empty after the colon.

### 5.21 Generate Master File

If:

```text
examples/top_header
```

exists, the programme must generate:

```text
examples/examples.tex
```

The master file must:

1. insert the header content;
2. begin the document;
3. write title and table of contents commands;
4. create one section per factor pole;
5. include each generated example file using `\input`;
6. end the document.

Section headings must follow:

```latex
\section{POS Dim <n>}
\section{NEG Dim <n>}
```

Example file inclusions must be sorted naturally.

---

## 6. Output Content Requirements

### 6.1 Directory Layout

For two detected factor dimensions, the output structure should be:

```text
examples/
  f1_pos/
    f1_pos_001.tex
    f1_pos_002.tex
  f1_neg/
    f1_neg_001.tex
    f1_neg_002.tex
  f2_pos/
    f2_pos_001.tex
  f2_neg/
    f2_neg_001.tex
  examples.tex
```

### 6.2 Example File Naming

Individual example files must use:

```text
f<n>_<pole>_<three-digit-id>.tex
```

Examples:

```text
f1_pos_001.tex
f1_pos_020.tex
f1_neg_001.tex
```

### 6.3 Example Environment

Each individual example file must use:

```latex
\begin{textsample}{...}
...
\end{textsample}
```

### 6.4 Bolded Factor Lemmas

Matched factor-pole wordforms must be bolded.

Example:

```latex
This offer will \textbf{save} you money.
```

### 6.5 Source Metadata in Title

Each example title must identify:

- pole;
- dimension;
- decade;
- score;
- source file.

Example:

```latex
\begin{textsample}{POS Dim 1 – 1950 – Score 1.24 – 1950/tv\_com\_1950\_1.txt}  \label{ex:f1_pos_001}
```

### 6.6 Master File Inclusion

The master file must include generated examples with:

```latex
\input{<absolute-or-resolved-path-to-example>}
```

The examples must be grouped by factor and pole.

---

## 7. Error Handling Requirements

### 7.1 Missing Scores File

If the scores file does not exist, raise:

```text
FileNotFoundError
```

### 7.2 Missing Tagged Corpus Directory

If the tagged corpus directory does not exist, raise:

```text
FileNotFoundError
```

### 7.3 Missing Factor Folder

If the factor folder does not exist, raise:

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

### 7.8 Missing Required Scores Columns

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

### 7.9 No Factor Columns

If no columns matching:

```regex
fac\d+
```

are found, raise:

```text
RuntimeError
```

### 7.10 Missing Means File

If an expected means file is missing, raise:

```text
FileNotFoundError
```

### 7.11 Missing Means Columns

If a means file is missing either:

```text
decade
Mean fac<n>
```

raise:

```text
ValueError
```

### 7.12 Missing Factor Pole File

If an expected factor pole file is missing, raise:

```text
FileNotFoundError
```

### 7.13 Missing Tagged Text Files

If selected tagged text files cannot be located, execution must continue.

The missing file IDs must be written to:

```text
missing_files.txt
```

### 7.14 Missing `top_header`

If:

```text
examples/top_header
```

does not exist, the programme must print a warning and skip generation of:

```text
examples/examples.tex
```

Individual example files must remain valid outputs.

---

## 8. Non-Functional Requirements

### 8.1 Encoding

All input and output text files must use:

```text
UTF-8
```

### 8.2 Determinism

The programme must produce deterministic output:

- factor columns sorted naturally;
- factor dimensions processed in numeric order;
- positive pole processed before negative pole;
- decades ranked deterministically by mean score;
- selected examples ordered by factor score;
- output filenames stable.

### 8.3 No Input Mutation

The programme must not modify:

```text
sas/output_<project>/
factors/
corpus/07_tagged/
file_ids.txt
```

### 8.4 Output Overwrite Behaviour

The programme may overwrite existing generated `.tex` files under:

```text
examples/
```

It may also overwrite:

```text
examples/examples.tex
missing_files.txt
```

### 8.5 No External LaTeX Compilation

The programme only writes `.tex` fragments and a master `.tex` file.

It must not run LaTeX, LuaLaTeX, XeLaTeX, or any external compilation command.

### 8.6 Dependency Requirements

The programme depends on:

```text
pandas
```

It also uses Python standard-library modules including:

```text
argparse
re
unicodedata
pathlib
```

The programme must run under the project Python environment.

---

## 9. Downstream Usage

The generated files are intended for LaTeX compilation or inclusion in a larger LaTeX document.

Typical direct compilation target:

```text
examples/examples.tex
```

Typical inclusion of an individual example:

```latex
\input{examples/f1_pos/f1_pos_001.tex}
```

The generated example files assume that the LaTeX environment defines a `textsample` environment.

Emoji rendering assumes that the LaTeX header may define:

```latex
\EmojiFont
```

---

## 10. Acceptance Criteria

The programme is correct if:

1. It can be run from the project root using:

```shell
python examples.py
```

2. It accepts an explicit project name:

```shell
python examples.py --project cl_st1_ph2_andrea
```

3. It accepts an explicit SAS output directory:

```shell
python examples.py --sas-output-dir sas/output_cl_st1_ph2_andrea
```

4. It accepts an explicit tagged corpus directory:

```shell
python examples.py --tagged-base corpus/07_tagged
```

5. It accepts an explicit factor folder:

```shell
python examples.py --factor-folder factors
```

6. It accepts an explicit examples output directory:

```shell
python examples.py --examples-dir examples
```

7. It accepts an explicit file ID map:

```shell
python examples.py --file-ids file_ids.txt
```

8. It reads the correct scores file.

9. It detects all `fac<n>` dimensions.

10. It reads the required `means_decade_f<n>.tsv` files.

11. It reads the required `f<n>_pos.txt` and `f<n>_neg.txt` files.

12. It ranks decades correctly:
    - descending means for positive poles;
    - ascending means for negative poles.

13. It skips examples with factor score equal to zero.

14. It writes individual example `.tex` files under:

```text
examples/f<n>_pos/
examples/f<n>_neg/
```

15. It bolds wordforms whose lemmas are primary lemmas for the relevant pole.

16. It records matched lemmas in a LaTeX comment.

17. It creates `examples/examples.tex` when `examples/top_header` exists.

18. It warns but does not fail when `examples/top_header` is missing.

19. It writes missing tagged files to `missing_files.txt`.

20. It does not require manual path editing between Phase 2 and Phase 3, provided it is run from the correct project directory or supplied with `--project`.

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

Factor pole file:

```text
factors/f1_pos.txt
```

Example content:

```text
Factor 1 positive pole
buy (0.41), save (0.38), new (0.36), (secondary 0.22)
```

File ID map:

```text
file_ids.txt
```

Example content:

```text
t000001 1950/tv_com_1950_1.txt
```

Tagged text:

```text
corpus/07_tagged/1950/tv_com_1950_1.txt
```

Example content:

```text
Buy VB buy
now RB now
and CC and
save VB save
! . !
```

### Command

```shell
python examples.py
```

### Output

```text
examples/f1_pos/f1_pos_001.tex
examples/f1_neg/f1_neg_001.tex
examples/examples.tex
```

### Example Output File

```latex
\begin{textsample}{POS Dim 1 – 1950 – Score 1.24 – 1950/tv\_com\_1950\_1.txt}  \label{ex:f1_pos_001}
\textbf{Buy} now and \textbf{save}!

% matched lemmas: buy, save
\end{textsample}
```

---

## 12. Recommended Future Enhancements

These are optional and must not alter current default behaviour unless explicitly requested.

### 12.1 Configurable Source Variable

Expose:

```text
--group-var
```

Default:

```text
decade
```

This would allow examples to be selected by other grouping variables.

### 12.2 Configurable Score Exclusion

Expose:

```text
--include-zero-scores
```

Current required behaviour skips score `0`.

### 12.3 Minimum Matched Lemmas

Expose:

```text
--min-matched-lemmas
```

to require at least a certain number of highlighted lemmas before writing an example.

### 12.4 Relative Paths in Master File

Expose:

```text
--relative-input-paths
```

to write relative `\input{...}` paths in `examples/examples.tex`.

### 12.5 Manifest

Write:

```text
examples/examples_manifest.json
```

containing:

- project;
- scores file;
- tagged corpus directory;
- factor folder;
- detected factors;
- generated example files;
- missing files.

### 12.6 Configurable Stoplist

Expose:

```text
--stoplist
```

to load stoplisted lemmas from an external text file.

### 12.7 Maximum Text Length

Expose:

```text
--max-paragraphs
```

or:

```text
--max-tokens
```

to limit very long examples.

---

## 13. Summary

`examples.py` creates LaTeX example extracts for interpreting LMDA factor dimensions.

Its core responsibility is:

```text
For each factor pole, select high-scoring representative texts by decade and bold the pole’s primary factor lemmas.
```

It must preserve:

- project inference from the current working directory;
- automatic factor detection;
- decade ranking by SAS mean factor scores;
- separate positive and negative pole outputs;
- stable example numbering;
- LaTeX-safe text output;
- compatibility across Phase 2 and Phase 3.