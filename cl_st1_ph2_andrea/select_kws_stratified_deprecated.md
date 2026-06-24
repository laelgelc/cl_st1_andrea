# Development Specification: `select_kws_stratified.py`

## 1. Programme Purpose

`select_kws_stratified.py` selects a balanced set of positive keywords from decade-specific key-lemma tables.

It reads the key-lemma tables produced by `keylemmas.py`, extracts lemmas classified as positive keywords (`POSKW`), applies filtering rules, enforces an equal maximum quota per decade, and writes:

1. one selected keyword list per decade;
2. one consolidated deduplicated keyword list for downstream LMDA processing.

This programme is used after `keylemmas.py` and before `columns.py`.

---

## 2. Project Context

The project analyses commercial subcorpora organised by decade.

The same logic applies to both:

1. **Phase 2: commercial verbal subcorpus**
   - transcript texts of spoken/audio-verbal commercial content;

2. **Phase 3: commercial visual subcorpus**
   - textual descriptions of visual commercial content.

In both phases, key-lemma tables are organised by decade:

```text
corpus/08_keylemmas/
    1950.tsv
    1960.tsv
    1970.tsv
    1980.tsv
    1990.tsv
    2000.tsv
    2010.tsv
    2020.tsv
```

Each decade is a stratum of the same nature. Therefore, all decades receive the same keyword quota.

There is no human/AI weighting, no model weighting, and no prompt-type weighting.

---

## 3. Inputs

### 3.1 Input Directory

Default:

```text
corpus/08_keylemmas
```

Can be overridden with:

```shell
--input <path>
```

Example:

```shell
python select_kws_stratified.py \
    --input corpus/08_keylemmas \
    --output corpus/09_kw_selected \
    --per-decade 250 \
    --max-total 1200
```

### 3.2 Input Files

The programme reads key-lemma files named after decades.

Supported extensions:

```text
.tsv
.txt
```

Expected default files:

```text
1950.tsv
1960.tsv
1970.tsv
1980.tsv
1990.tsv
2000.tsv
2010.tsv
2020.tsv
```

Only files whose stem matches the following pattern are considered:

```regex
^\d{4}$
```

Examples considered valid:

```text
1950.tsv
1960.txt
2020.tsv
```

Examples ignored:

```text
keywords.txt
summary.tsv
human.tsv
generic_gpt.tsv
```

### 3.3 Preferred File Extension

If both `.tsv` and `.txt` exist for the same decade, the `.tsv` file must be preferred.

Example:

```text
1950.tsv
1950.txt
```

The programme must use:

```text
1950.tsv
```

### 3.4 Input File Format

Each key-lemma file is expected to contain:

- one header row;
- one row per lemma;
- lemma in the first column;
- status in the final column.

Example:

```text
lemma	target_count	comparison_count	target_per_1k	comparison_per_1k	expected	LL	%DIFF	status
product	42	159	407.77	220.53	25.12	11.08	59.6	POSKW
```

The input may be:

- tab-separated; or
- whitespace-separated.

The programme must detect tabs and split accordingly:

- if the line contains `\t`, split on tab;
- otherwise split on whitespace.

### 3.5 Required Command-Line Arguments

The programme requires:

```text
--per-decade
```

This is the maximum number of POSKW lemmas selected from each decade.

Example:

```shell
--per-decade 250
```

### 3.6 Optional Command-Line Arguments

```text
--input
```

Default:

```text
corpus/08_keylemmas
```

```text
--output
```

Default:

```text
corpus/09_kw_selected
```

```text
--max-total
```

Default:

```text
0
```

Meaning:

```text
0 = no maximum
```

If greater than zero, it limits the consolidated list before deduplication.

---

## 4. Outputs

### 4.1 Output Directory

Default:

```text
corpus/09_kw_selected
```

The programme must create this directory if it does not exist.

### 4.2 Per-Decade Output Files

The programme writes one file per decade:

```text
corpus/09_kw_selected/<Decade>.txt
```

Examples:

```text
corpus/09_kw_selected/1950.txt
corpus/09_kw_selected/1960.txt
...
corpus/09_kw_selected/2020.txt
```

Each file must contain:

- no header;
- one selected lemma per line;
- UTF-8 encoding.

Example:

```text
product
camera
screen
```

### 4.3 Consolidated Output File

The programme writes one consolidated deduplicated keyword list:

```text
corpus/09_kw_selected/keywords.txt
```

Format:

- no header;
- one keyword per line;
- UTF-8 encoding;
- alphabetically sorted;
- duplicate-free.

Example:

```text
camera
product
screen
```

---

## 5. Selection Logic

### 5.1 Load POSKW Lemmas

For each decade key-lemma file:

1. Skip the header row.
2. Read each remaining row.
3. Extract:
   - lemma from first column;
   - status from final column.
4. Keep only rows where status is exactly:

```text
POSKW
```

Rows with:

```text
NEGKW
NOTKW
```

must be ignored.

### 5.2 Preserve File Order

Within each decade, selected lemmas must preserve the order in the input key-lemma file.

Because `keylemmas.py` sorts `POSKW` rows by descending log-likelihood, this means the most key lemmas are selected first.

### 5.3 Lexical Filtering Rules

After selecting `POSKW` rows, the programme must apply additional lexical filters.

A lemma must be excluded if:

1. it contains Unicode punctuation;
2. it contains any digit;
3. it contains any uppercase letter.

### 5.4 Unicode Punctuation Filter

A lemma contains punctuation if any character has a Unicode category beginning with:

```text
P
```

Examples excluded:

```text
black-and-white
close-up
tvdays.com
display**
```

### 5.5 Digit Filter

A lemma must be excluded if it contains any digit.

Examples excluded:

```text
r2d2
mp3
covid19
```

### 5.6 Uppercase Filter

A lemma must be excluded if it contains any uppercase letter.

Examples excluded:

```text
Kodak
RCA
McDonald
```

Note: most lemmas are expected to be lowercased by upstream processing.

### 5.7 Per-Decade Quota

For each decade, choose at most:

```text
--per-decade
```

lemmas after filtering.

If fewer filtered `POSKW` lemmas are available than the quota, select all available lemmas.

Example:

```text
--per-decade 250
```

If 1950 has 187 available filtered POSKW lemmas, select 187.

### 5.8 Consolidated List Construction

The consolidated list must be built by concatenating selected decade lists in chronological decade order:

```text
1950 → 1960 → 1970 → 1980 → 1990 → 2000 → 2010 → 2020
```

### 5.9 Optional Max Total

If `--max-total` is greater than zero and the consolidated list exceeds that value, truncate the consolidated list before deduplication.

Example:

```text
--max-total 1200
```

If the concatenated list contains 1,400 items, keep only the first 1,200 before deduplicating.

### 5.10 Deduplication

After optional truncation, the consolidated list must be deduplicated.

The final `keywords.txt` file must contain:

```python
sorted(set(consolidated))
```

This produces an alphabetical, unique keyword list.

---

## 6. Functional Workflow

### Step 1: Parse Arguments

Read:

```text
--input
--output
--per-decade
--max-total
```

Validate:

- `--per-decade > 0`
- `--max-total >= 0`

### Step 2: Discover Key-Lemma Files

Scan the input directory for:

```text
*.tsv
*.txt
```

Keep only decade-named files.

If no decade files are found, raise a `FileNotFoundError`.

### Step 3: Load POSKW Lemmas

For each discovered decade file:

1. load POSKW lemmas;
2. apply lexical filters;
3. store the list under that decade.

### Step 4: Print Quotas

Print a quota summary.

Example:

```text
=== Decade Keyword Quotas ===
1950   → 250 keywords max
1960   → 250 keywords max
...
=============================
```

### Step 5: Select Per-Decade Keywords

For each decade:

```python
chosen = lemmas[:per_decade]
```

Print selection summary.

Example:

```text
1950   → selected 187/250 from 187 available POSKW lemmas
```

### Step 6: Build Consolidated List

Append selected lists in chronological order.

### Step 7: Apply Optional Total Cap

If `--max-total > 0`, truncate consolidated list before deduplication.

### Step 8: Deduplicate

Create:

```python
unique_lemmas = sorted(set(consolidated))
```

### Step 9: Write Outputs

Write:

```text
corpus/09_kw_selected/<Decade>.txt
corpus/09_kw_selected/keywords.txt
```

### Step 10: Print Final Summary

Print:

- total consolidated count before deduplication;
- unique keyword count after deduplication;
- duplicate count removed;
- output path;
- final unique keyword count.

---

## 7. Error Handling Requirements

### 7.1 Missing Input Directory

If the input directory does not exist, raise:

```text
FileNotFoundError
```

with message:

```text
Input directory does not exist: <input_dir>
```

### 7.2 No Decade Key-Lemma Files

If no valid decade files are found, raise:

```text
FileNotFoundError
```

with message explaining that files such as `1950.tsv`, `1960.tsv`, etc. were expected.

### 7.3 Invalid Per-Decade Quota

If `--per-decade <= 0`, raise:

```text
ValueError
```

### 7.4 Invalid Max Total

If `--max-total < 0`, raise:

```text
ValueError
```

### 7.5 Empty Input File

If a key-lemma file is empty, return an empty lemma list for that decade and continue.

### 7.6 Malformed Rows

If a row has fewer than two fields, skip it.

### 7.7 Missing POSKW Rows

If a decade has no valid POSKW lemmas after filtering, write an empty decade file and continue.

---

## 8. Non-Functional Requirements

### 8.1 Encoding

All files must be read and written using:

```text
UTF-8
```

### 8.2 Determinism

The programme must be deterministic:

- decade files sorted naturally;
- selected lemmas preserve file order;
- consolidated list follows chronological decade order;
- final `keywords.txt` is alphabetically sorted.

### 8.3 No Randomness

The programme must not use random sampling.

### 8.4 No Header Injection

Output files must not contain headers.

This applies to:

```text
corpus/09_kw_selected/<Decade>.txt
corpus/09_kw_selected/keywords.txt
```

### 8.5 No Delimiter Changes

The output files are one-token-per-line word lists.

No delimiter should be introduced.

### 8.6 Equal Decade Treatment

All decades must use the same quota.

The programme must not include:

- human weighting;
- model weighting;
- prompt weighting;
- source weighting.

---

## 9. Downstream Dependencies

The output of this programme is consumed by:

```text
columns.py
```

`columns.py` expects:

```text
corpus/09_kw_selected/keywords.txt
```

with:

- no header;
- one keyword per line;
- lowercased lemmas;
- duplicate-free list.

If the output format changes, downstream binary column generation may fail or produce inconsistent variable IDs.

The per-decade files are useful for inspection and documentation but are not the primary downstream input.

---

## 10. Acceptance Criteria

The programme is correct if:

1. It discovers decade files under `corpus/08_keylemmas`.
2. It reads `.tsv` files preferentially over `.txt` files.
3. It extracts only `POSKW` lemmas.
4. It filters punctuation, digits, and uppercase letters.
5. It applies the same quota to every decade.
6. It writes one file per decade to `corpus/09_kw_selected`.
7. It writes `corpus/09_kw_selected/keywords.txt`.
8. `keywords.txt` has no header.
9. `keywords.txt` contains one keyword per line.
10. `keywords.txt` is duplicate-free.
11. `keywords.txt` is alphabetically sorted.
12. `columns.py` can read `keywords.txt` without modification.

---

## 11. Example

### Input

```text
corpus/08_keylemmas/1950.tsv
```

Example rows:

```text
lemma	target_count	comparison_count	target_per_1k	comparison_per_1k	expected	LL	%DIFF	status
product	42	159	407.77	220.53	25.12	11.08	59.6	POSKW
black-and-white	25	48	242.72	66.57	9.12	22.96	113.9	POSKW
screen	23	308	223.3	427.18	41.38	10.88	-62.69	NEGKW
```

### Processing

- `product` is retained if it passes filters.
- `black-and-white` is excluded because it contains punctuation.
- `screen` is excluded because it is not `POSKW`.

### Per-Decade Output

```text
corpus/09_kw_selected/1950.txt
```

Example:

```text
product
```

### Consolidated Output

```text
corpus/09_kw_selected/keywords.txt
```

Example:

```text
camera
product
screen
```

---

## 12. Recommended Future Enhancements

These are optional and must not change current output formats unless explicitly requested.

### 12.1 Configurable Filters

Allow users to turn filters on/off:

```text
--allow-punctuation
--allow-digits
--allow-uppercase
```

### 12.2 Minimum Lemma Length

Add:

```text
--min-length
```

to exclude very short lemmas.

### 12.3 Selection Report

Write a report such as:

```text
corpus/09_kw_selected/selection_report.tsv
```

with:

```text
decade	available_poskw	selected
```

### 12.4 Preserve Consolidated Order Option

Add an option:

```text
--preserve-consolidated-order
```

to write `keywords.txt` in decade-priority order instead of alphabetically.

Current required behaviour remains alphabetical sorting.

### 12.5 Manifest

Write a JSON manifest:

```text
corpus/09_kw_selected/select_kws_manifest.json
```

containing:

- input directory;
- output directory;
- per-decade quota;
- max-total;
- filters applied;
- selected counts by decade;
- final keyword count.

---

## 13. Summary

`select_kws_stratified.py` creates the keyword list used to build the LMDA binary matrix.

Its core analytical principle is:

```text
Select positive key lemmas from each decade using equal per-decade quotas, then consolidate them into one duplicate-free keyword list.
```

The programme must preserve:

- decade-based stratification;
- equal treatment of all decades;
- POSKW-only selection;
- lexical filters;
- headerless one-word-per-line outputs;
- `keywords.txt` compatibility with `columns.py`.