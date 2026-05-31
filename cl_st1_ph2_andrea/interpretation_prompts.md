# Development Specification: `interpretation_prompts.py`

## 1. Programme Purpose

`interpretation_prompts.py` generates complete LLM prompt files for interpreting LMDA factor poles.

For each factor pole, the programme assembles a standalone prompt containing:

1. a system prompt;
2. a user prompt;
3. mean decade scores;
4. factor loadings;
5. plaintext example excerpts;
6. loading words present in each example.

The generated prompt files are intended to support qualitative interpretation of LMDA factor dimensions as discourse dimensions.

Each output file focuses on one pole only:

```text
f<n>_pos
f<n>_neg
```

The programme explicitly avoids generating “versus” interpretations of opposing poles.

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
interpretation_prompts.py
```

Example:

```text
cl_st1_ph2_andrea/interpretation_prompts.py
cl_st1_ph3_andrea/interpretation_prompts.py
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

### 3.1 Factor Loading Files

Default directory:

```text
factors
```

The programme reads factor pole files matching:

```text
f*_*.txt
```

Expected names:

```text
f<n>_pos.txt
f<n>_neg.txt
```

Examples:

```text
factors/f1_pos.txt
factors/f1_neg.txt
factors/f2_pos.txt
factors/f2_neg.txt
```

Each file contains the loadings for one factor pole.

The file stem determines the factor and polarity.

Example:

```text
f1_pos.txt
```

becomes:

```text
factor = f1
polarity = pos
```

### 3.2 Plaintext Example Files

Default directory:

```text
examples_txt
```

For each factor pole, examples are expected in:

```text
examples_txt/f<n>_<pole>/*.txt
```

Examples:

```text
examples_txt/f1_pos/f1_pos_001.txt
examples_txt/f1_pos/f1_pos_002.txt
examples_txt/f1_neg/f1_neg_001.txt
```

The programme includes up to a configurable number of examples per factor pole.

Default:

```text
10 examples
```

### 3.3 Score Details File

Default input path:

```text
examples/score_details.txt
```

This file is used to retrieve loading words present in each example.

Expected block structure:

```text
text ID: t000001
filename: 1950/tv_com_1950_1.txt

f1 score: 0.42
f1 pos words (N=2): buy, save
f1 neg words (N=0): 

=============================================
```

The programme parses the score-details file into:

```text
score_details[text_id][factor][polarity] -> list of words
```

Example:

```text
score_details["t000001"]["f1"]["pos"] -> ["buy", "save"]
```

### 3.4 SAS Means Files

Default SAS output directory:

```text
sas/output_<project>
```

For each factor, the programme reads:

```text
means_decade_f<n>.tsv
```

Example:

```text
sas/output_cl_st1_ph2_andrea/means_decade_f1.tsv
```

The raw contents of the means file are included in the generated prompt.

If a means file is missing, the programme inserts:

```text
(No means file found)
```

and continues.

### 3.5 Command-Line Arguments

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
--factors-dir
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
examples_txt
```

```text
--details-file
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
interpretation/input
```

```text
--excerpt-count
```

Default:

```text
10
```

```text
--excerpt-lines
```

Default:

```text
30
```

---

## 4. Outputs

### 4.1 Output Directory

Default:

```text
interpretation/input
```

The programme must create this directory if it does not exist.

### 4.2 Per-Pole Prompt Files

For each valid factor pole file, the programme writes:

```text
interpretation/input/f<n>_<pole>.txt
```

Examples:

```text
interpretation/input/f1_pos.txt
interpretation/input/f1_neg.txt
interpretation/input/f2_pos.txt
```

### 4.3 Output Encoding

All generated prompt files must be written using:

```text
UTF-8
```

### 4.4 Console Output

For each prompt file written, the programme should print:

```text
Wrote: <output_path>
```

At the end, it should print:

```text
Project: <project>
SAS output directory: <sas-output-dir>
Interpretation prompts written to: <output-dir>
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
python interpretation_prompts.py
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
<factors-dir>
<examples-dir>
<sas-output-dir>
<details-file>
```

If `factors-dir`, `examples-dir`, `sas-output-dir`, or `details-file` is missing, raise:

```text
FileNotFoundError
```

### 5.4 Detect Factor Pole Files

The programme must list files in the factors directory matching:

```text
f*_*.txt
```

Files must be sorted naturally.

Example order:

```text
f1_pos.txt
f1_neg.txt
f2_pos.txt
f2_neg.txt
f10_pos.txt
```

not:

```text
f10_pos.txt
f1_pos.txt
f2_pos.txt
```

If no factor pole files are found, raise:

```text
FileNotFoundError
```

### 5.5 Validate Factor Pole Filename

Each factor file stem must split into exactly two parts:

```text
f<n>_<pole>
```

where `<pole>` is either:

```text
pos
neg
```

If a factor file has an unexpected name, print a warning and skip it.

Examples to skip:

```text
f1.txt
f1_positive.txt
notes.txt
```

### 5.6 Phase-Specific System Prompt

The generated system prompt must include a phase-specific corpus description based on the project name.

If the project name contains:

```text
ph2
```

the description must state that the phase analyses the commercial verbal subcorpus.

If the project name contains:

```text
ph3
```

the description must state that the phase analyses the commercial visual subcorpus.

If neither is present, use a generic commercial subcorpus description.

### 5.7 System Prompt Content

The system prompt must instruct the model that:

1. it is acting as a corpus linguist specialising in Lexical Multi-Dimensional Analysis;
2. it is interpreting a single factor pole as a discourse dimension;
3. the corpus consists of selected television-commercial texts organised by decade;
4. the dataset is balanced across decades;
5. the decades range from the 1950s through the 2020s;
6. the interpretation must consider:
    - lexical loadings;
    - example excerpts;
    - the decades that score most strongly at the pole.

### 5.8 User Prompt Content

The user prompt must instruct the model to:

1. interpret the selected factor and polarity as a discourse dimension;
2. propose possible labels for the pole;
3. justify the labels;
4. use mean decade scores;
5. use factor loadings;
6. use example excerpts;
7. use loading words appearing in the examples;
8. identify which decades appear to drive the pole;
9. discuss diachronic tendencies;
10. avoid a “versus” interpretation of the opposite pole;
11. focus on the single pole only;
12. give equal weight to loadings and examples.

### 5.9 Load Score Details

The programme must parse the score-details file into:

```text
score_details[text_id][factor][polarity] -> list of words
```

Parsing requirements:

1. detect text IDs from lines matching:

```regex
text ID:\s*(t\d+)
```

2. detect factor sections from lines matching:

```regex
(f\d+)\s+score:
```

3. detect word lists from lines matching:

```regex
f\d+\s+(pos|neg)\s+words.*:\s*(.*)
```

4. split word lists on commas;
5. strip whitespace;
6. remove empty strings.

### 5.10 Read Factor Loadings

For each valid factor pole file, the programme must read its full text as UTF-8.

The stripped contents must be included under a section named:

```text
=== FACTOR LOADINGS (<factor_name>) ===
```

Example:

```text
=== FACTOR LOADINGS (f1_pos) ===
```

### 5.11 Read Mean Decade Scores

For each factor pole, the programme must infer the factor number from the factor name.

Example:

```text
f1_pos
```

uses:

```text
means_decade_f1.tsv
```

The programme must read the full contents of the means file as UTF-8 and include them under:

```text
=== MEAN DECADE SCORES ===
```

If the means file is missing, it must:

1. print a warning;
2. insert:

```text
(No means file found)
```

3. continue generating the prompt.

### 5.12 Select Example Files

For each factor pole, the programme must find examples in:

```text
<examples-dir>/<factor_name>/*.txt
```

Example:

```text
examples_txt/f1_pos/*.txt
```

The example files must be sorted naturally.

The programme must include at most:

```text
--excerpt-count
```

examples per factor pole.

Default:

```text
10
```

If the example folder is missing or contains no `.txt` files, the programme should continue and produce a prompt with an empty examples section.

### 5.13 Extract Example Excerpts

For each selected example file, the programme must include only the first:

```text
--excerpt-lines
```

lines.

Default:

```text
30
```

The excerpt must preserve line order and remove only trailing newline characters.

### 5.14 Detect Text ID in Example

For each selected example file, the programme must detect a text ID matching:

```regex
t\d{6}
```

If no text ID is found:

1. print a warning;
2. skip that example.

### 5.15 Attach Loading Words to Each Excerpt

For each selected example, the programme must retrieve loading words from the parsed score-details data using:

```text
score_details[text_id][factor][polarity]
```

If no loading words are found, use:

```text
(none)
```

The excerpt block must end with:

```text
--- Loading words for this example (<polarity>): <words>
```

Example:

```text
--- Loading words for this example (pos): buy, save, new
```

### 5.16 Prompt Assembly

Each final prompt must be assembled in this order:

1. system prompt;
2. user prompt;
3. mean decade scores section;
4. factor loadings section;
5. example excerpts section.

The example excerpts section must begin with:

```text
=== EXAMPLE EXCERPTS ===
```

Each excerpt block must begin with:

```text
===== EXCERPT: <filename> (text ID <text_id>) =====
```

### 5.17 Output File Writing

Each prompt must be written to:

```text
<output-dir>/<factor_name>.txt
```

using UTF-8 encoding.

Existing prompt files may be overwritten.

---

## 6. Output Content Requirements

### 6.1 Prompt File Naming

Prompt files must use the factor pole name:

```text
f<n>_<pole>.txt
```

Examples:

```text
f1_pos.txt
f1_neg.txt
f10_pos.txt
```

### 6.2 Required Prompt Sections

Each output file must contain the following section labels:

```text
=== MEAN DECADE SCORES ===
=== FACTOR LOADINGS (<factor_name>) ===
=== EXAMPLE EXCERPTS ===
```

### 6.3 Excerpt Block Format

Each included excerpt must follow:

```text
===== EXCERPT: <example_filename> (text ID <text_id>) =====
<excerpt text>

--- Loading words for this example (<polarity>): <comma-separated words>
```

If no loading words are found:

```text
--- Loading words for this example (<polarity>): (none)
```

### 6.4 Missing Means Placeholder

If the means file is missing, the mean decade scores section must contain:

```text
(No means file found)
```

### 6.5 Single-Pole Focus

The prompt content must instruct the interpreting model to focus on the selected pole only and not to construct a “positive versus negative” factor interpretation.

---

## 7. Error Handling Requirements

### 7.1 Missing Factors Directory

If the factors directory does not exist, raise:

```text
FileNotFoundError
```

### 7.2 Missing Examples Directory

If the examples directory does not exist, raise:

```text
FileNotFoundError
```

### 7.3 Missing SAS Output Directory

If the SAS output directory does not exist, raise:

```text
FileNotFoundError
```

### 7.4 Missing Score Details File

If the score-details file does not exist, raise:

```text
FileNotFoundError
```

### 7.5 No Factor Pole Files

If no files matching:

```text
f*_*.txt
```

are found in the factors directory, raise:

```text
FileNotFoundError
```

### 7.6 Unexpected Factor Filename

If a factor file does not follow:

```text
f<n>_<pole>.txt
```

print a warning and skip it.

### 7.7 Unexpected Polarity

If the parsed polarity is not one of:

```text
pos
neg
```

print a warning and skip the file.

### 7.8 Missing Means File

If the means file for a factor is missing, print a warning and continue.

The generated prompt must include:

```text
(No means file found)
```

### 7.9 Missing Example Folder or No Examples

If a factor’s example folder is missing or contains no `.txt` files, continue and generate the prompt with an empty example excerpts section.

### 7.10 Missing Text ID in Example

If no text ID can be detected in an example file, print a warning and skip that example.

### 7.11 Missing Loading Words

If no loading words are available in the score-details lookup for an example, continue and insert:

```text
(none)
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

- factor files sorted naturally;
- example files sorted naturally;
- excerpt count bounded by a fixed argument;
- excerpt length bounded by a fixed argument;
- stable output filenames.

### 8.3 No Input Mutation

The programme must not modify:

```text
factors/
examples_txt/
examples/score_details.txt
sas/output_<project>/
```

### 8.4 Output Overwrite Behaviour

The programme may overwrite existing files under:

```text
interpretation/input/
```

or under the configured output directory.

### 8.5 No External LLM Calls

The programme only creates prompt files.

It must not call an LLM API, submit prompts, or generate interpretations.

### 8.6 No External Compilation or Analysis

The programme must not call SAS, LaTeX, or any external analysis process.

### 8.7 Dependency Requirements

The programme uses only Python standard-library modules, including:

```text
argparse
re
pathlib
```

The programme must run under the project Python environment.

---

## 9. Downstream Usage

The generated files are intended to be used as input prompts for a separate interpretation-generation process.

Typical output:

```text
interpretation/input/f1_pos.txt
interpretation/input/f1_neg.txt
```

These prompt files may then be reviewed manually or passed to an LLM workflow.

The programme does not create final interpretations itself.

---

## 10. Acceptance Criteria

The programme is correct if:

1. It can be run from the project root using:

```shell
python interpretation_prompts.py
```

2. It accepts an explicit project name:

```shell
python interpretation_prompts.py --project cl_st1_ph2_andrea
```

3. It accepts an explicit SAS output directory:

```shell
python interpretation_prompts.py --sas-output-dir sas/output_cl_st1_ph2_andrea
```

4. It accepts an explicit factors directory:

```shell
python interpretation_prompts.py --factors-dir factors
```

5. It accepts an explicit examples directory:

```shell
python interpretation_prompts.py --examples-dir examples_txt
```

6. It accepts an explicit score-details path:

```shell
python interpretation_prompts.py --details-file examples/score_details.txt
```

7. It accepts an explicit output directory:

```shell
python interpretation_prompts.py --output-dir interpretation/input
```

8. It accepts excerpt limits:

```shell
python interpretation_prompts.py --excerpt-count 10 --excerpt-lines 30
```

9. It detects factor pole files in the factors directory.

10. It skips unexpected factor filenames with warnings.

11. It reads the corresponding mean decade score file for each factor.

12. It includes a missing-means placeholder when a means file is absent.

13. It reads plaintext examples from the matching examples directory.

14. It includes no more than the configured number of examples per pole.

15. It includes no more than the configured number of lines per example.

16. It detects text IDs in example files.

17. It attaches loading words from `examples/score_details.txt`.

18. It writes one prompt file per valid factor pole.

19. It writes prompt files under `interpretation/input` by default.

20. It creates the output directory if needed.

21. It writes UTF-8 output.

22. It does not call an LLM or produce final interpretations.

23. It does not require manual path editing between Phase 2 and Phase 3, provided it is run from the correct project directory or supplied with `--project`.

---

## 11. Example

### Input

Factor loading file:

```text
factors/f1_pos.txt
```

Example content:

```text
Factor 1 positive pole
buy (0.41), save (0.38), new (0.36)
```

Means file:

```text
sas/output_cl_st1_ph2_andrea/means_decade_f1.tsv
```

Example content:

```text
decade	Mean fac1
1950	0.42
1960	-0.18
1970	0.09
```

Plaintext example:

```text
examples_txt/f1_pos/f1_pos_001.txt
```

Example content:

```text
Text ID: t000001
Decade: 1950
File:   corpus/commercial_verbal/1950/tv_com_1950_1.txt

Score (f1_pos): 1.24
Loading words (f1_pos), N=2: buy, save

Buy now and save with this special offer.
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

### Command

```shell
python interpretation_prompts.py
```

### Output

```text
interpretation/input/f1_pos.txt
```

### Output Excerpt

```text
You are a corpus linguist specialising in Lexical Multi-Dimensional Analysis (LMDA).
Your task is to interpret a single factor pole as a discourse dimension.

...

Interpret Factor f1 (pos) as a discourse dimension.
Propose possible labels for this pole only and justify them.

...

=== MEAN DECADE SCORES ===
decade	Mean fac1
1950	0.42
1960	-0.18
1970	0.09

=== FACTOR LOADINGS (f1_pos) ===
Factor 1 positive pole
buy (0.41), save (0.38), new (0.36)

=== EXAMPLE EXCERPTS ===

===== EXCERPT: f1_pos_001.txt (text ID t000001) =====
Text ID: t000001
Decade: 1950
File:   corpus/commercial_verbal/1950/tv_com_1950_1.txt

Score (f1_pos): 1.24
Loading words (f1_pos), N=2: buy, save

Buy now and save with this special offer.

--- Loading words for this example (pos): buy, save
```

---

## 12. Recommended Future Enhancements

These are optional and must not alter current default behaviour unless explicitly requested.

### 12.1 Configurable Prompt Template

Expose:

```text
--system-template
--user-template
```

to load prompt templates from external files.

### 12.2 Include Metadata Manifest

Write:

```text
interpretation/input/manifest.json
```

containing:

- project;
- SAS output directory;
- factors directory;
- examples directory;
- score-details file;
- output directory;
- generated prompt files.

### 12.3 Prompt Length Limit

Expose:

```text
--max-chars
```

to cap prompt length for model context limits.

### 12.4 Example Selection Modes

Allow selecting examples by:

```text
--example-selection first
--example-selection balanced
--example-selection random
```

Current required behaviour uses the first naturally sorted examples.

### 12.5 Include Opposite Pole Summary

Add an optional argument:

```text
--include-opposite-pole-summary
```

Current required behaviour explicitly avoids “versus” interpretation.

### 12.6 Markdown Output

Expose:

```text
--format txt
--format md
```

Current required output is plaintext `.txt`.

---

## 13. Summary

`interpretation_prompts.py` creates standalone prompt files for interpreting LMDA factor poles.

Its core responsibility is:

```text
For each factor pole, combine project context, mean decade scores, factor loadings, example excerpts, and example-level loading words into one LLM-ready prompt file.
```

It must preserve:

- project inference from the current working directory;
- phase-specific corpus descriptions;
- single-pole interpretation focus;
- natural ordering of factors and examples;
- bounded excerpt count and length;
- compatibility across Phase 2 and Phase 3.