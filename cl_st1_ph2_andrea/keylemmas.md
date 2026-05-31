# Development Specification: `keylemmas.py`

## 1. Programme Purpose

`keylemmas.py` computes **decade-specific key lemmas** from the tagged commercial corpus.

The programme compares each decade subcorpus against all other decades combined and produces a ranked key-lemma table for each decade.

It is part of the Lexical Multi-Dimensional Analysis (LMDA) pipeline and is run after `tag.py`.

The output is used by `select_kws_stratified.py` to choose a balanced list of positive keywords across decade strata.

---

## 2. Project Context

The project contains tagged commercial text files organised by decade:

```text
corpus/07_tagged/
    1950/
    1960/
    1970/
    1980/
    1990/
    2000/
    2010/
    2020/
```

Each decade folder contains TreeTagger output files:

```text
corpus/07_tagged/<Decade>/<Commercial ID>.txt
```

For example:

```text
corpus/07_tagged/1950/tv_com_1950_1.txt
corpus/07_tagged/1960/tv_com_1960_1.txt
```

The programme is applicable to both:

1. **Phase 2: Commercial verbal subcorpus**
   - tagged transcript texts of spoken/audio-verbal commercial content;

2. **Phase 3: Commercial visual subcorpus**
   - tagged textual descriptions of commercial visual content.

The same decade-based logic applies to both phases.

---

## 3. Inputs

### 3.1 Input Directory

Default:

```text
corpus/07_tagged
```

Can be overridden with:

```shell
--input <path>
```

Example:

```shell
python keylemmas.py --input corpus/07_tagged
```

### 3.2 Input Directory Structure

The input directory must contain decade-named subdirectories:

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

Only immediate subdirectories whose names match:

```regex
^\d{4}$
```

are treated as strata.

Non-decade directories must be ignored.

### 3.3 Input Files

Each decade directory should contain TreeTagger output files:

```text
*.txt
```

The programme reads files recursively within each decade directory using `os.walk`, although the expected project structure is one level deep.

### 3.4 Input File Format

Each tagged file is expected to contain TreeTagger-style token lines with at least three tab-separated fields:

```text
word<TAB>tag<TAB>lemma
```

Example:

```text
commercial	NN	commercial
shows	VBZ	show
bright	JJ	bright
```

Lines with fewer than three tab-separated fields must be skipped.

### 3.5 Command-Line Arguments

The programme must support:

```text
--input
```

Input directory containing tagged decade folders.

Default:

```text
corpus/07_tagged
```

```text
--output
```

Output directory for key-lemma files.

Default:

```text
corpus/08_keylemmas
```

```text
--cutoff
```

Minimum percentage presence in target decade texts.

Default:

```text
3.0
```

Example:

```shell
python keylemmas.py \
    --input corpus/07_tagged \
    --output corpus/08_keylemmas \
    --cutoff 3
```

---

## 4. Outputs

### 4.1 Output Directory

Default:

```text
corpus/08_keylemmas
```

The programme must create this directory if it does not exist.

### 4.2 Output Files

The programme writes one key-lemma table per decade:

```text
corpus/08_keylemmas/<Decade>.tsv
```

Examples:

```text
corpus/08_keylemmas/1950.tsv
corpus/08_keylemmas/1960.tsv
corpus/08_keylemmas/1970.tsv
...
corpus/08_keylemmas/2020.tsv
```

### 4.3 Output Format

Each output file must be:

- UTF-8 encoded;
- tab-separated;
- headered.

Header:

```text
lemma	target_count	comparison_count	target_per_1k	comparison_per_1k	expected	LL	%DIFF	status
```

Each row represents one lemma.

### 4.4 Output Columns

| Column | Description |
|---|---|
| `lemma` | Lowercased lemma retained after POS and lexical filtering |
| `target_count` | Number of texts in the target decade where the lemma occurs at least once |
| `comparison_count` | Number of texts in all other decades where the lemma occurs at least once |
| `target_per_1k` | Presence rate per 1,000 target-decade texts |
| `comparison_per_1k` | Presence rate per 1,000 comparison texts |
| `expected` | Expected target-decade count under the null distribution |
| `LL` | Log-likelihood statistic |
| `%DIFF` | Percentage difference between target and comparison rates |
| `status` | Keyword classification: `POSKW`, `NEGKW`, or `NOTKW` |

---

## 5. Core Concepts

### 5.1 Text-Level Presence

The programme measures **lemma presence per text**, not raw frequency.

For each lemma, each text contributes at most one count:

```text
lemma appears in text → count 1
lemma appears multiple times in same text → still count 1
```

This is done by maintaining a per-text `seen` set.

### 5.2 Target and Comparison Subcorpora

For each decade:

- **target subcorpus** = all texts in that decade;
- **comparison subcorpus** = all texts in all other decades combined.

Example for 1950:

```text
target = corpus/07_tagged/1950/
comparison = 1960 + 1970 + 1980 + 1990 + 2000 + 2010 + 2020
```

### 5.3 Decade as Stratum

The strata are decades, not human/AI source, model, prompt type, genre, or author category.

All decades are treated as strata of the same nature.

---

## 6. Lemma Filtering Requirements

### 6.1 POS Filtering

Only lemmas with TreeTagger POS tags beginning with one of the following prefixes must be retained:

```python
("NN", "NP", "VB", "JJ")
```

These correspond to:

- common nouns;
- proper nouns;
- verbs;
- adjectives.

Adverbs and function words are not intentionally retained unless they appear under one of the accepted POS prefixes.

### 6.2 Unknown Lemmas

If the lemma field is:

```text
<unknown>
```

or empty, the programme must use the surface wordform instead.

### 6.3 Lowercasing

All retained lemmas must be lowercased before counting.

### 6.4 Minimum Alphabetic Content

A lemma must contain at least two alphabetic characters.

Examples:

| Lemma | Keep? |
|---|---|
| `car` | yes |
| `tv` | yes |
| `a` | no |
| `1` | no |
| `.` | no |

### 6.5 Stopwords

The following lowercased lemmas must be excluded:

```text
be
have
do
```

The stopword list is intentionally small and project-specific.

---

## 7. Statistical Requirements

### 7.1 Log-Likelihood

The programme must calculate a log-likelihood value using the following inputs:

| Symbol | Meaning |
|---|---|
| `a` | target presence count |
| `b` | comparison presence count |
| `c` | number of target texts |
| `d` | number of comparison texts |

Expected values:

```text
E1 = c * (a + b) / (c + d)
E2 = d * (a + b) / (c + d)
```

Log-likelihood:

```text
LL = 2 * ((a * log(a / E1)) + (b * log(b / E2)))
```

If `a == 0` or `b == 0`, the programme returns:

```text
0.0
```

This behaviour is part of the current implementation and must be preserved unless explicitly revised.

### 7.2 Presence Cutoff

For a lemma to be included in a decade’s output file, it must occur in at least:

```text
size_target * cutoff_percent / 100
```

target texts.

Example:

If:

```text
size_target = 103
cutoff_percent = 3
```

then:

```text
cutoff_texts = 3.09
```

A lemma must appear in at least 4 target texts to pass the cutoff because the count is integer and must be greater than or equal to 3.09.

### 7.3 Rate Calculation

The programme calculates rates as presence per 1,000 texts:

```text
target_per_1k = (a / size_target) * 1000
comparison_per_1k = (b / size_comp) * 1000
```

### 7.4 Expected Count

Expected target count is:

```text
expected = (size_target * (a + b)) / total
```

where:

```text
total = size_target + size_comp
```

### 7.5 Percentage Difference

The programme calculates `%DIFF` as:

```text
100 * (target_per_1k - comparison_per_1k)
      / ((target_per_1k + comparison_per_1k) / 2)
```

If both rates are zero, `%DIFF` is:

```text
0.0
```

### 7.6 Keyword Status

Each lemma receives a status:

```text
POSKW
NEGKW
NOTKW
```

Classification rules:

```text
POSKW if LL >= 3.84 and %DIFF > 0
NEGKW if LL >= 3.84 and %DIFF <= 0
NOTKW otherwise
```

Interpretation:

- `POSKW`: over-represented in the target decade;
- `NEGKW`: under-represented in the target decade relative to other decades;
- `NOTKW`: does not meet keyness threshold.

---

## 8. Sorting Requirements

Rows in each output file must be sorted in the following order:

1. `POSKW`
2. `NEGKW`
3. `NOTKW`

Within each status group, rows must be sorted by descending `LL`.

If two rows have the same `LL`, they should be sorted alphabetically by lemma.

The current implementation sorts by:

```python
(status_priority, -LL, lemma)
```

where:

```python
status_priority = {
    "POSKW": 0,
    "NEGKW": 1,
    "NOTKW": 2,
}
```

---

## 9. Functional Workflow

### Step 1: Parse Arguments

Read:

```text
--input
--output
--cutoff
```

Validate that:

- `--cutoff` is non-negative.

### Step 2: Discover Decade Folders

Identify all valid decade folders under the input directory.

If no valid folders are found, raise an error.

### Step 3: Build Global Lemma Presence

For every decade folder:

1. Load lemma presence for that decade.
2. Add each lemma’s text labels to the global presence dictionary.
3. Add all text labels to the global text set.

The global text labels should be prefixed with the decade folder name to remain unique:

```text
1950/tv_com_1950_1.txt
```

### Step 4: Process Each Decade

For each decade folder:

1. Load target lemma presence.
2. Define target texts.
3. Define comparison texts as:

```python
global_texts - target_texts
```

4. For every lemma in global presence:
   - calculate target count;
   - calculate comparison count;
   - apply cutoff;
   - calculate rates, expected count, LL, %DIFF;
   - assign status;
   - append row.

### Step 5: Sort Rows

Sort rows by:

```text
status priority, descending LL, lemma
```

### Step 6: Write Output

Write one `.tsv` file per decade.

---

## 10. Error Handling Requirements

### 10.1 Missing Input Directory

If the input directory does not exist, raise:

```text
FileNotFoundError
```

with a clear message.

### 10.2 No Decade Folders

If no decade folders are found, raise:

```text
FileNotFoundError
```

with a clear message indicating that folders such as `1950`, `1960`, etc. were expected.

### 10.3 Invalid Cutoff

If `--cutoff` is negative, raise:

```text
ValueError
```

### 10.4 Empty Decade

If a decade folder contains no usable tagged text files, print:

```text
Skipping <Decade>: no tagged text files found.
```

and continue processing the remaining decades.

### 10.5 Malformed Tagged Lines

Lines with fewer than three tab-separated fields must be skipped silently.

### 10.6 Unknown Lemmas

`<unknown>` lemmas must be replaced with the wordform.

---

## 11. Non-Functional Requirements

### 11.1 Encoding

All input and output files must be read and written as:

```text
UTF-8
```

### 11.2 Determinism

The programme must use deterministic ordering:

- decade folders sorted naturally;
- files sorted naturally;
- output rows sorted deterministically.

### 11.3 No Randomness

The programme must not use random sampling.

### 11.4 No Output Format Drift

The output format must remain:

- tab-separated;
- headered;
- `.tsv`;
- one file per decade.

### 11.5 No Downstream Header Changes

This programme’s output files are expected to have a header. Do not remove the header unless explicitly requested.

### 11.6 No Delimiter Changes

Do not replace tabs with spaces in `corpus/08_keylemmas/*.tsv`.

Downstream `select_kws_stratified.py` supports tab-separated keylemma files and expects the final column to contain the status.

---

## 12. Downstream Dependencies

The output is consumed by:

```text
select_kws_stratified.py
```

That programme expects:

- one file per decade;
- filename stem is the decade, e.g. `1950`;
- supported extension `.tsv`;
- first row is a header;
- first column is lemma;
- final column is status;
- rows with `POSKW` are eligible for keyword selection.

Therefore, the following output convention is mandatory:

```text
corpus/08_keylemmas/<Decade>.tsv
```

---

## 13. Acceptance Criteria

The programme is correct if:

1. It discovers all decade folders under `corpus/07_tagged`.
2. It reads all `.txt` TreeTagger files in each decade.
3. It extracts lemmas from the third column.
4. It retains only accepted POS classes.
5. It counts lemma presence once per text.
6. It compares each decade against all other decades combined.
7. It applies the configured cutoff.
8. It writes one `.tsv` file per decade to `corpus/08_keylemmas`.
9. Each `.tsv` file has the required header.
10. Each `.tsv` file is tab-separated.
11. Output rows contain valid `POSKW`, `NEGKW`, or `NOTKW` statuses.
12. `select_kws_stratified.py` can read the output without modification.

---

## 14. Example

Given input:

```text
corpus/07_tagged/1950/tv_com_1950_1.txt
corpus/07_tagged/1950/tv_com_1950_2.txt
corpus/07_tagged/1960/tv_com_1960_1.txt
...
```

The programme should write:

```text
corpus/08_keylemmas/1950.tsv
corpus/08_keylemmas/1960.tsv
...
```

Example output row:

```text
product	42	159	407.77	220.53	25.12	11.08	59.6	POSKW
```

This means:

- `product` appears in 42 target-decade texts;
- appears in 159 comparison texts;
- is over-represented in the target decade;
- is classified as a positive keyword for that decade.

---

## 15. Recommended Future Enhancements

These are optional and should not change the current output format unless explicitly requested.

### 15.1 CLI POS Configuration

Allow accepted POS prefixes to be passed via CLI:

```shell
--pos-prefixes NN NP VB JJ
```

### 15.2 Stopword File

Allow an external stopword file:

```shell
--stopwords stopwords.txt
```

### 15.3 Minimum Alphabetic Count

Make minimum alphabetic count configurable:

```shell
--min-alpha 2
```

### 15.4 Manifest Output

Write a processing manifest:

```text
corpus/08_keylemmas/keylemmas_manifest.json
```

containing:

- input directory;
- output directory;
- discovered decades;
- text counts per decade;
- cutoff;
- POS prefixes;
- stopwords;
- number of lemmas written per decade.

### 15.5 Raw Frequency Mode

Add optional raw frequency counting while preserving presence mode as default:

```shell
--count-mode presence
--count-mode frequency
```

### 15.6 Strict Decade Validation

Warn if expected decades are missing:

```text
1950 1960 1970 1980 1990 2000 2010 2020
```

### 15.7 Improved Log-Likelihood Handling for Zero Counts

Current behaviour returns `0.0` if either `a` or `b` is zero. A future statistical revision may support zero cells more formally, but this would change analytical behaviour and should be documented carefully.

---

## 16. Summary

`keylemmas.py` is responsible for converting decade-organised tagged corpus files into decade-specific key-lemma tables.

Its core analytical principle is:

```text
For each decade, identify lemmas that are over- or under-represented relative to all other decades combined, using text-level lemma presence and log-likelihood.
```

It must preserve:

- decade-based comparison;
- TreeTagger input assumptions;
- tab-separated `.tsv` output;
- headered output files;
- keyword status labels used downstream.