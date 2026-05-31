# Development Specification: `columns.py`

## 1. Programme Purpose

`columns.py` converts a selected keyword list and a decade-organised tagged corpus into binary keyword-presence column files.

For each selected keyword lemma, the programme creates one binary column indicating whether that lemma is present in each tagged text.

The outputs are used by downstream matrix-building and SAS-processing scripts, especially:

- `merge_columns.py`
- `sas_formats.py`
- SAS factor-analysis scripts
- `factor_lists.py`
- example-extraction scripts

The programme also creates mapping files that preserve the relationship between:

- generated text IDs and source tagged files;
- generated keyword IDs and keyword lemmas.

---

## 2. Project Context

The project contains two parallel LMDA phases:

1. **Phase 2: commercial verbal subcorpus**
   - transcript texts representing spoken/audio-verbal commercial content;

2. **Phase 3: commercial visual subcorpus**
   - textual descriptions of visual commercial content.

In both phases, the tagged corpus is organised by decade:

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

Each decade folder contains tagged files:

```text
corpus/07_tagged/<Decade>/<Commercial ID>.txt
```

The programme operates identically in both phases.

---

## 3. Inputs

### 3.1 Keyword File

Default:

```text
corpus/09_kw_selected/keywords.txt
```

Format:

- UTF-8;
- no header;
- one keyword lemma per line.

Example:

```text
camera
product
screen
```

The programme must:

- strip whitespace;
- ignore blank lines;
- lowercase each keyword;
- deduplicate keywords;
- sort keywords using natural sort order.

### 3.2 Tagged Corpus Directory

Default:

```text
corpus/07_tagged
```

Expected structure:

```text
corpus/07_tagged/<Decade>/<Commercial ID>.txt
```

Only immediate subdirectories whose names match a four-digit decade pattern are considered:

```regex
^\d{4}$
```

Examples:

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

### 3.3 Tagged File Format

Each tagged file is expected to contain TreeTagger-style token rows with at least three fields:

```text
word<TAB>tag<TAB>lemma
```

If tab splitting produces fewer than three fields, the programme may fall back to whitespace splitting.

The lemma is taken from the third field.

---

## 4. Outputs

The programme writes four output groups:

1. `columns/`
2. `columns_clean/`
3. `file_ids.txt`
4. `index_keywords.txt`

---

## 5. Output Format Requirements

These output formats are strict because later stages depend on them.

### 5.1 `file_ids.txt`

Path:

```text
file_ids.txt
```

Format:

- no header;
- space-separated;
- two columns:

```text
file_id path
```

Example:

```text
t000001 1950/tv_com_1950_1.txt
t000002 1950/tv_com_1950_3.txt
```

Column definitions:

| Column | Description |
|---|---|
| `file_id` | Generated sequential text ID |
| `path` | Path relative to `corpus/07_tagged` |

The file ID format must be:

```text
t000001
t000002
...
```

with six numeric digits.

### 5.2 `index_keywords.txt`

Path:

```text
index_keywords.txt
```

Format:

- no header;
- space-separated;
- two columns:

```text
keyword_id lemma
```

Example:

```text
000001 camera
000002 product
```

Column definitions:

| Column | Description |
|---|---|
| `keyword_id` | Six-digit generated keyword ID |
| `lemma` | Keyword lemma |

The keyword ID format must be:

```text
000001
000002
...
```

with six numeric digits.

### 5.3 `columns/<Keyword ID>.txt`

Directory:

```text
columns/
```

One file per keyword:

```text
columns/000001.txt
columns/000002.txt
...
```

Format:

- no header;
- space-separated;
- three columns:

```text
file_id decade presence
```

Example:

```text
t000001 1950 0
t000002 1950 1
t000003 1950 0
```

Column definitions:

| Column | Description |
|---|---|
| `file_id` | Generated text ID |
| `decade` | Decade folder name |
| `presence` | `1` if keyword lemma is present in the text, else `0` |

Presence values must be binary:

```text
0
1
```

### 5.4 `columns_clean/<Keyword ID>.txt`

Directory:

```text
columns_clean/
```

One file per keyword:

```text
columns_clean/000001.txt
columns_clean/000002.txt
...
```

Format:

- first line: keyword ID;
- subsequent lines: one binary presence value per text;
- no header.

Example:

```text
000001
0
1
0
0
```

The number of binary rows after the first line must equal the number of texts in `file_ids.txt`.

---

## 6. Functional Requirements

### 6.1 Load Keywords

The programme must:

1. Read `corpus/09_kw_selected/keywords.txt`.
2. Strip each line.
3. Ignore empty lines.
4. Lowercase each lemma.
5. Deduplicate.
6. Sort using natural sort order.

If the keyword file does not exist, raise:

```text
FileNotFoundError
```

If no keywords remain after loading, raise:

```text
ValueError
```

### 6.2 Generate Keyword IDs

Each keyword receives a six-digit numeric ID based on sorted keyword order.

Example:

```text
camera → 000001
product → 000002
```

The mapping must be written to:

```text
index_keywords.txt
```

### 6.3 Collect Tagged Text Files

The programme must:

1. Validate that `corpus/07_tagged` exists.
2. Validate that it is a directory.
3. Find immediate decade folders matching:

```regex
^\d{4}$
```

4. Sort decade folders naturally.
5. Collect `.txt` files under each decade folder.
6. Sort files naturally.
7. Preserve this file order for all output files.

If no decade folders exist, raise:

```text
FileNotFoundError
```

If no tagged `.txt` files exist, raise:

```text
FileNotFoundError
```

### 6.4 Generate File IDs

Each tagged text file receives a sequential ID:

```text
t000001
t000002
...
```

File IDs must be assigned in deterministic order:

1. decade order;
2. filename natural sort order.

The mapping must be written to:

```text
file_ids.txt
```

### 6.5 Read Lemma Presence per Text

For each tagged text file:

1. Read all token lines.
2. Extract the lemma from the third column.
3. Normalize lemma:
   - strip whitespace;
   - lowercase.
4. Ignore:
   - empty lemmas;
   - `<unknown>`.
5. Store lemmas in a set.

Presence is text-level:

```text
keyword appears once or more in a text → presence = 1
keyword absent → presence = 0
```

Repeated occurrences do not increase the value beyond `1`.

### 6.6 Write Full Column Files

For each keyword:

1. Open:

```text
columns/<Keyword ID>.txt
```

2. For each text in the fixed text order:
   - write file ID;
   - write decade;
   - write binary presence.

Example:

```text
t000001 1950 0
```

The file must be space-separated and headerless.

### 6.7 Write Keyword Index

Write:

```text
index_keywords.txt
```

Each line:

```text
keyword_id lemma
```

No header.

### 6.8 Write Clean Column Files

For each keyword:

1. Read the corresponding full column file.
2. Create:

```text
columns_clean/<Keyword ID>.txt
```

3. First line must be keyword ID.
4. For every line in the full column file:
   - split on whitespace;
   - take the final field;
   - write it as the binary value.

Example:

```text
000001
0
1
0
```

This format is consumed by `merge_columns.py`.

---

## 7. Sorting and Determinism

The programme must be deterministic.

Sorting rules:

1. Keywords:
   - deduplicated and sorted using natural sort order.
2. Decade folders:
   - sorted naturally.
3. Text files:
   - sorted naturally within each decade.
4. Output rows:
   - same order in every column file.
5. Clean column rows:
   - same order as full column rows.

The same input corpus and keyword list must always produce the same:

- file IDs;
- keyword IDs;
- column order;
- row order.

---

## 8. Error Handling Requirements

### 8.1 Missing Keyword File

Raise:

```text
FileNotFoundError
```

with message:

```text
Keyword file does not exist: corpus/09_kw_selected/keywords.txt
```

### 8.2 Empty Keyword List

Raise:

```text
ValueError
```

with message indicating no keywords were found.

### 8.3 Missing Tagged Corpus Directory

Raise:

```text
FileNotFoundError
```

if `corpus/07_tagged` does not exist.

### 8.4 Tagged Corpus Path Is Not a Directory

Raise:

```text
NotADirectoryError
```

### 8.5 No Decade Folders

Raise:

```text
FileNotFoundError
```

with a message indicating expected folders such as:

```text
1950, 1960, 1970
```

### 8.6 No Tagged Files

Raise:

```text
FileNotFoundError
```

if no `.txt` files are found.

### 8.7 Malformed Tagged Lines

Lines with fewer than three fields must be ignored.

### 8.8 Unknown Lemmas

Lemmas equal to:

```text
<unknown>
```

must be ignored.

---

## 9. Non-Functional Requirements

### 9.1 Encoding

All input and output files must use:

```text
UTF-8
```

### 9.2 No Header Injection

The following outputs must not contain headers:

```text
file_ids.txt
index_keywords.txt
columns/*.txt
```

`columns_clean/*.txt` must contain only the keyword ID on the first line, followed by binary values.

### 9.3 Space-Separated Output

The following files must use spaces, not tabs:

```text
file_ids.txt
index_keywords.txt
columns/*.txt
```

### 9.4 Binary Values

Presence values must be exactly:

```text
0
1
```

No booleans, decimals, or textual labels are allowed.

### 9.5 No Randomness

The programme must not use random sampling.

### 9.6 No Corpus Mutation

The programme must not modify files under:

```text
corpus/07_tagged
corpus/09_kw_selected
```

It only reads from them.

---

## 10. Downstream Dependencies

### 10.1 `merge_columns.py`

Consumes:

```text
columns/000001.txt
columns_clean/*.txt
```

Assumes:

- `columns/000001.txt` has rows:

```text
file_id decade presence
```

- `columns_clean/*.txt` has:
  - keyword ID first line;
  - binary values afterwards.

### 10.2 `sas_formats.py`

Consumes:

```text
index_keywords.txt
```

Assumes:

```text
keyword_id lemma
```

with no header and space separation.

### 10.3 `examples.py`, `examples_txt.py`, `score_details.py`

Consume:

```text
file_ids.txt
```

Assume:

```text
file_id path
```

with no header and space separation.

### 10.4 SAS Factor Analysis

Indirectly consumes:

```text
sas/counts.txt
```

created from the outputs of this programme.

The order of rows and keyword columns must remain stable.

---

## 11. Acceptance Criteria

The programme is correct if:

1. It reads `corpus/09_kw_selected/keywords.txt`.
2. It reads tagged files from `corpus/07_tagged/<Decade>/`.
3. It writes `file_ids.txt` with no header.
4. `file_ids.txt` is space-separated.
5. `file_ids.txt` contains exactly:

```text
file_id path
```

6. It writes `index_keywords.txt` with no header.
7. `index_keywords.txt` is space-separated.
8. `index_keywords.txt` contains exactly:

```text
keyword_id lemma
```

9. It writes one file per keyword under `columns/`.
10. Each `columns/*.txt` file has no header.
11. Each `columns/*.txt` row contains exactly:

```text
file_id decade presence
```

12. It writes one file per keyword under `columns_clean/`.
13. Each `columns_clean/*.txt` file begins with the keyword ID.
14. Each subsequent line in `columns_clean/*.txt` is a binary value.
15. All column files contain the same number of text rows.
16. Downstream `merge_columns.py` runs successfully.

---

## 12. Example

### Input keyword file

```text
corpus/09_kw_selected/keywords.txt
```

```text
camera
product
screen
```

### Input tagged files

```text
corpus/07_tagged/1950/tv_com_1950_1.txt
corpus/07_tagged/1950/tv_com_1950_2.txt
```

### Output `index_keywords.txt`

```text
000001 camera
000002 product
000003 screen
```

### Output `file_ids.txt`

```text
t000001 1950/tv_com_1950_1.txt
t000002 1950/tv_com_1950_2.txt
```

### Output `columns/000001.txt`

If keyword `camera` appears in the first text but not the second:

```text
t000001 1950 1
t000002 1950 0
```

### Output `columns_clean/000001.txt`

```text
000001
1
0
```

---

## 13. Recommended Future Enhancements

These are optional and must not change current output formats unless explicitly requested.

### 13.1 CLI Arguments

Add:

```text
--keyword-file
--tagged-base
--columns-dir
--clean-dir
--file-ids
--index-file
```

### 13.2 Manifest

Write a manifest file, for example:

```text
columns_manifest.json
```

containing:

- number of keywords;
- number of texts;
- detected decades;
- output paths;
- generation timestamp.

### 13.3 Rebuild Safety

Optionally remove existing `columns/` and `columns_clean/` before writing, or add:

```text
--clean-output
```

### 13.4 Progress Bar

Add progress reporting for large keyword lists.

### 13.5 Strict TreeTagger Format Mode

Add a strict mode that raises an error if a tagged file contains no valid token lines.

### 13.6 Frequency Mode

Add optional frequency counting:

```text
--mode presence
--mode frequency
```

Current required mode remains:

```text
presence
```

---

## 14. Summary

`columns.py` creates the binary keyword-presence matrix components used for LMDA.

Its core responsibility is:

```text
For every selected keyword, create a binary vector indicating whether the keyword appears in each decade-organised tagged text.
```

It must preserve:

- decade metadata;
- stable file and keyword IDs;
- headerless mapping files;
- space-separated output for `file_ids.txt`, `index_keywords.txt`, and `columns/*.txt`;
- clean binary column format for `columns_clean/*.txt`;
- compatibility with `merge_columns.py` and SAS processing.