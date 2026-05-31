# Development Specification: `corpus_size.py`

## 1. Programme Purpose

`corpus_size.py` calculates corpus-size statistics for the tagged commercial corpus.

It counts:

- the number of tagged text files per decade;
- the number of valid token lines per decade;
- the overall number of text files;
- the overall number of tokens.

The output is a tab-separated summary table:

```text
corpus_size/corpus_size.tsv
```

This table is used for documentation, reporting, and corpus-size sanity checks.

---

## 2. Project Context

The project contains two parallel LMDA phases:

1. **Phase 2: commercial verbal subcorpus**
   - transcript texts representing spoken/audio-verbal commercial content;

2. **Phase 3: commercial visual subcorpus**
   - textual descriptions of commercial visual content.

In both phases, after tagging, files are organised by decade:

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

The same programme applies to both phases.

---

## 3. Inputs

### 3.1 Tagged Corpus Root

Default:

```text
corpus/07_tagged
```

Expected structure:

```text
corpus/07_tagged/<Decade>/<Commercial ID>.txt
```

Example:

```text
corpus/07_tagged/1950/tv_com_1950_1.txt
```

### 3.2 Decade Folders

Only immediate subdirectories whose names match:

```regex
^\d{4}$
```

are counted.

Expected folders:

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

Non-decade folders must be ignored.

### 3.3 Tagged Files

The programme reads files matching:

```text
*.txt
```

directly inside each decade folder.

Current behaviour is non-recursive.

### 3.4 Tagged File Format

Each tagged file is expected to contain TreeTagger-style token lines:

```text
word<TAB>tag<TAB>lemma
```

The programme treats a line as a valid token if:

1. the stripped line is not empty;
2. the line begins with an alphabetic character;
3. after whitespace splitting, it has at least three fields.

Each valid token line counts as **one word/token**.

---

## 4. Outputs

### 4.1 Output Directory

Default:

```text
corpus_size
```

The programme must create the directory if it does not exist.

### 4.2 Output File

Default:

```text
corpus_size/corpus_size.tsv
```

### 4.3 Output Format

The output file must be:

- UTF-8 encoded;
- tab-separated;
- headered.

Header:

```text
Strata	Text Count	Word Count
```

### 4.4 Output Rows

The file must contain:

1. one row per decade;
2. a blank line;
3. one `overall` row.

Example:

```text
Strata	Text Count	Word Count
1950	103	12345
1960	103	12567
1970	103	11982

overall	824	98765
```

### 4.5 Column Definitions

| Column | Description |
|---|---|
| `Strata` | Decade label or `overall` |
| `Text Count` | Number of `.txt` files counted |
| `Word Count` | Number of valid TreeTagger token lines counted |

---

## 5. Counting Rules

### 5.1 File Count

Each `.txt` file in a valid decade folder counts as one text.

Example:

```text
corpus/07_tagged/1950/tv_com_1950_1.txt
```

adds:

```text
Text Count +1
```

for the `1950` stratum.

### 5.2 Word Count

Each valid token line counts as one word.

The programme must not count fields inside a tagged line as separate words.

For example:

```text
commercial	NN	commercial
```

counts as:

```text
1 word
```

not 3 words.

### 5.3 Valid Token Line

A line is counted if:

1. after stripping, it is not empty;
2. it begins with a character matching:

```regex
^[A-Za-z]
```

3. splitting the line on whitespace produces at least three fields.

### 5.4 Invalid Lines

The following must not be counted:

- empty lines;
- lines that do not begin with an ASCII alphabetic character;
- lines with fewer than three fields.

### 5.5 Overall Count

The overall text count is the sum of all decade file counts.

The overall word count is the sum of all decade word counts.

---

## 6. Functional Workflow

### Step 1: Validate Corpus Root

The programme must check:

```text
corpus/07_tagged
```

exists and is a directory.

If not, raise an appropriate error.

### Step 2: Discover Decade Folders

Find immediate child directories whose names match:

```regex
^\d{4}$
```

Sort naturally.

If none are found, raise:

```text
FileNotFoundError
```

### Step 3: Process Each Decade

For each decade folder:

1. list `.txt` files;
2. sort naturally;
3. for each file:
   - count valid token lines;
   - increment decade file count;
   - increment decade word count;
   - increment overall file count;
   - increment overall word count.

### Step 4: Write Output

Create:

```text
corpus_size/
```

Write:

```text
corpus_size/corpus_size.tsv
```

### Step 5: Print Summary

Print:

```text
Corpus sizes saved to corpus_size/corpus_size.tsv
Total texts: <total_files>
Total words: <total_words>
```

---

## 7. Error Handling Requirements

### 7.1 Missing Corpus Root

If `corpus/07_tagged` does not exist, raise:

```text
FileNotFoundError
```

### 7.2 Corpus Root Not Directory

If `corpus/07_tagged` exists but is not a directory, raise:

```text
NotADirectoryError
```

### 7.3 No Decade Folders

If no valid decade folders are found, raise:

```text
FileNotFoundError
```

with a message indicating expected folders such as:

```text
1950, 1960, 1970
```

### 7.4 Empty Decade Folders

If a decade folder has no `.txt` files, it contributes no row unless at least one file is counted.

Current implementation writes only decades present in the file-count dictionary.

### 7.5 Malformed Tagged Lines

Malformed token lines are skipped silently.

### 7.6 Encoding Assumption

The programme assumes input files are UTF-8 encoded.

If a file cannot be decoded as UTF-8, the exception may propagate.

---

## 8. Non-Functional Requirements

### 8.1 Encoding

All files must be read and written using:

```text
UTF-8
```

### 8.2 Determinism

The programme must use deterministic ordering:

- decade directories sorted naturally;
- files sorted naturally;
- output rows sorted naturally by decade.

### 8.3 No Randomness

The programme must not use random sampling.

### 8.4 No Input Mutation

The programme must not modify the tagged corpus.

It only reads:

```text
corpus/07_tagged/
```

and writes:

```text
corpus_size/corpus_size.tsv
```

### 8.5 Header Preservation

The output TSV must contain the header:

```text
Strata	Text Count	Word Count
```

### 8.6 Tab-Separated Output

The output file must remain tab-separated.

Do not replace tabs with spaces.

---

## 9. Downstream and Reporting Uses

The output is primarily used for:

- reporting corpus size;
- checking whether each decade has the expected number of texts;
- checking whether Phase 2 and Phase 3 have comparable text counts;
- documenting the final analysed corpus.

It is not part of the core SAS matrix construction, but it is an important validation artifact.

---

## 10. Acceptance Criteria

The programme is correct if:

1. It reads `corpus/07_tagged/<Decade>/*.txt`.
2. It counts only valid tagged token lines.
3. Each valid token line counts as one word.
4. It counts files per decade.
5. It writes `corpus_size/corpus_size.tsv`.
6. The output has a header.
7. The output is tab-separated.
8. The output includes one row per decade with files.
9. The output includes an `overall` row.
10. Printed totals match the contents of the output file.

---

## 11. Example

### Input

```text
corpus/07_tagged/1950/tv_com_1950_1.txt
```

Contents:

```text
The	DT	the
commercial	NN	commercial
shows	VBZ	show
.	SENT	.
```

### Counting

The first three lines begin with ASCII alphabetic characters and have at least three fields.

The punctuation line does not begin with an alphabetic character.

Word count:

```text
3
```

### Output Row

If this is the only file in 1950:

```text
1950	1	3
```

---

## 12. Recommended Future Enhancements

These are optional and must not change current output format unless explicitly requested.

### 12.1 CLI Arguments

Add:

```text
--corpus-root
--output-file
```

### 12.2 Recursive Mode

Add optional recursive search:

```text
--recursive
```

Current behaviour should remain non-recursive by default.

### 12.3 Unicode Letter Support

Replace ASCII token pattern:

```regex
^[A-Za-z]
```

with Unicode-aware alphabetic detection.

This would better support non-English tokens, but current corpus is English-oriented.

### 12.4 Detailed Report

Add optional file-level counts:

```text
corpus_size/file_counts.tsv
```

with:

```text
file_id	decade	word_count
```

### 12.5 Expected Count Validation

Warn if a decade does not contain the expected number of files, e.g.:

```text
103
```

### 12.6 Manifest

Write:

```text
corpus_size/corpus_size_manifest.json
```

containing:

- corpus root;
- output file;
- detected decades;
- total files;
- total tokens;
- generation timestamp.

---

## 13. Summary

`corpus_size.py` calculates corpus-size statistics for the tagged commercial corpus.

Its core responsibility is:

```text
Count tagged text files and valid TreeTagger token lines per decade and overall.
```

It must preserve:

- decade-based reporting;
- one-token-per-valid-line counting;
- tab-separated TSV output;
- headered output;
- no mutation of corpus files.