# Development Specification: `sas_formats.py`

## 1. Programme Purpose

`sas_formats.py` generates SAS format files that map keyword variable IDs to human-readable lemma labels.

The programme reads:

```text
index_keywords.txt
```

and writes SAS `PROC FORMAT` definitions to:

```text
sas/word_labels_format.sas
sas/word_labels_full_format.sas
```

These SAS format files are used by the SAS factor-analysis workflow to label variables in loading tables and related outputs.

---

## 2. Project Context

The LMDA pipeline assigns each selected keyword lemma a six-digit keyword ID.

Example:

```text
000001 camera
000002 product
000003 screen
```

SAS uses variable names with a leading `v`:

```text
v000001
v000002
v000003
```

The factor-analysis output refers to variables by these IDs. To make loading tables interpretable, SAS format files are generated to label variables with their lemma names.

The same programme is used for both:

1. **Phase 2: commercial verbal subcorpus**
2. **Phase 3: commercial visual subcorpus**

The input and output conventions are the same in both phases.

---

## 3. Inputs

### 3.1 Keyword Index File

Default input:

```text
index_keywords.txt
```

Expected format:

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
000003 screen
```

### 3.2 Input Column Definitions

| Column | Description |
|---|---|
| `keyword_id` | Six-digit keyword ID without the leading `v` |
| `lemma` | Keyword lemma label |

### 3.3 Keyword ID Format

The `keyword_id` must be numeric.

Expected:

```text
000001
000002
000003
```

The programme creates SAS variable names by prefixing each ID with:

```text
v
```

Example:

```text
000001 → v000001
```

### 3.4 Lemma Format

The lemma may contain characters requiring escaping in SAS quoted strings.

At minimum, double quotes must be escaped by doubling:

```text
" → ""
```

---

## 4. Outputs

### 4.1 Output Directory

Default:

```text
sas
```

The programme must create this directory if it does not exist.

### 4.2 Short Label Format File

Output:

```text
sas/word_labels_format.sas
```

Purpose:

Maps SAS variable IDs to keyword lemmas only.

Example conceptual mapping:

```sas
"v000001" = "camera"
"v000002" = "product"
```

Format name:

```sas
$lexlabels
```

### 4.3 Full Label Format File

Output:

```text
sas/word_labels_full_format.sas
```

Purpose:

Maps SAS variable IDs to keyword lemmas plus variable ID.

Example conceptual mapping:

```sas
"v000001" = "camera (v000001)"
"v000002" = "product (v000002)"
```

Format name:

```sas
$lexlabelsfull
```

### 4.4 Output Encoding

All output files must be written as:

```text
UTF-8
```

---

## 5. SAS Output Requirements

### 5.1 Short Format File Structure

`word_labels_format.sas` must define a SAS character format:

```sas
PROC FORMAT library=work ;
  VALUE  $lexlabels
"v000001" = "camera"
"v000002" = "product"
;
run;
quit;
```

### 5.2 Full Format File Structure

`word_labels_full_format.sas` must define a SAS character format:

```sas
PROC FORMAT library=work ;
  VALUE  $lexlabelsfull
"v000001" = "camera (v000001)"
"v000002" = "product (v000002)"
;
run;
quit;
```

### 5.3 Format Names

The format names must remain:

```text
$lexlabels
$lexlabelsfull
```

because SAS scripts refer to these names.

### 5.4 Variable Naming

Each keyword ID must be converted to:

```text
v<keyword_id>
```

Example:

```text
000265 → v000265
```

The leading zeros must be preserved.

---

## 6. Functional Requirements

### 6.1 Load Keyword Index

The programme must:

1. Open `index_keywords.txt`.
2. Read all non-empty lines.
3. Split each line using:

```python
split(maxsplit=1)
```

4. Interpret the two parts as:
   - keyword ID;
   - lemma.
5. Validate the file has no header.
6. Validate the keyword ID is numeric.
7. Convert keyword ID to SAS variable name:

```python
varname = f"v{keyword_id}"
```

8. Escape lemma text for SAS.

### 6.2 Header Detection

If the first non-empty line appears to contain a header, such as:

```text
keyword_id lemma
```

or:

```text
id lemma
```

the programme must raise an error.

### 6.3 Lemma Escaping

The programme must escape double quotes inside lemmas by replacing:

```text
"
```

with:

```text
""
```

Example:

```text
children"s
```

becomes:

```text
children""s
```

### 6.4 Generate Short Format

For each item, write a mapping:

```sas
"v000001" = "lemma"
```

to:

```text
sas/word_labels_format.sas
```

### 6.5 Generate Full Format

For each item, write a mapping:

```sas
"v000001" = "lemma (v000001)"
```

to:

```text
sas/word_labels_full_format.sas
```

### 6.6 Print Summary

After successful execution, print:

```text
SAS format files written to sas
Keyword labels written: <count>
```

---

## 7. Error Handling Requirements

### 7.1 Missing Index File

If `index_keywords.txt` does not exist, raise:

```text
FileNotFoundError
```

Message:

```text
Keyword index file not found: index_keywords.txt
```

### 7.2 Malformed Row

If a non-empty line does not contain exactly two fields under `split(maxsplit=1)`, raise:

```text
ValueError
```

Message should include:

- file path;
- line number;
- expected format.

### 7.3 Header Present

If the first line appears to be a header, raise:

```text
ValueError
```

Expected headerless file.

### 7.4 Invalid Keyword ID

If the keyword ID is not numeric, raise:

```text
ValueError
```

### 7.5 Empty Index File

If no keyword entries are loaded, raise:

```text
ValueError
```

---

## 8. Non-Functional Requirements

### 8.1 Encoding

All files must be read and written using:

```text
UTF-8
```

### 8.2 Determinism

The programme must preserve the order of entries in `index_keywords.txt`.

The output SAS format mappings must appear in the same order as the input keyword index.

### 8.3 No Input Mutation

The programme must not modify:

```text
index_keywords.txt
```

### 8.4 Output Overwrite Behaviour

The programme may overwrite:

```text
sas/word_labels_format.sas
sas/word_labels_full_format.sas
```

on each run.

### 8.5 No Additional Dependencies

The programme should only rely on the Python standard library.

---

## 9. Downstream Dependencies

The generated files are used by SAS scripts.

### 9.1 SAS Loading Table Labels

The SAS scripts include:

```sas
%include "/home/&sasusername/&myfolder/word_labels_full_format.sas";
```

and use:

```sas
FORMAT _NAME_ $lexlabelsfull.;
```

for full labels.

### 9.2 Short Loading Labels

The SAS scripts include:

```sas
%include "/home/&sasusername/&myfolder/word_labels_format.sas";
```

and use:

```sas
FORMAT _NAME_ $lexlabels.;
```

for short labels.

### 9.3 Expected Variable Names

The SAS factor outputs refer to variables such as:

```text
v000001
v000002
```

Therefore, the generated SAS format file must use those exact names.

---

## 10. Acceptance Criteria

The programme is correct if:

1. It reads `index_keywords.txt`.
2. It rejects headered `index_keywords.txt`.
3. It preserves six-digit keyword IDs.
4. It creates variable names such as `v000001`.
5. It escapes double quotes in lemmas.
6. It writes `sas/word_labels_format.sas`.
7. It writes `sas/word_labels_full_format.sas`.
8. The short format file defines `$lexlabels`.
9. The full format file defines `$lexlabelsfull`.
10. SAS can successfully include both files.
11. SAS loading tables display readable lemma labels.

---

## 11. Example

### Input

`index_keywords.txt`:

```text
000001 camera
000002 product
000003 screen
```

### Output

`word_labels_format.sas`:

```sas
PROC FORMAT library=work ;
  VALUE  $lexlabels
"v000001" = "camera"
"v000002" = "product"
"v000003" = "screen"
;
run;
quit;
```

### Output

`word_labels_full_format.sas`:

```sas
PROC FORMAT library=work ;
  VALUE  $lexlabelsfull
"v000001" = "camera (v000001)"
"v000002" = "product (v000002)"
"v000003" = "screen (v000003)"
;
run;
quit;
```

---

## 12. Known Operational Note

In SAS, formats created in `WORK.FORMATS` can persist during a SAS session.

If a format is regenerated and SAS reports that `$lexlabels` or `$lexlabelsfull` already exists, stale session state may affect results.

Recommended SAS-side precaution before including regenerated formats:

```sas
proc catalog catalog=work.formats;
  delete lexlabels.formatc lexlabelsfull.formatc;
quit;
```

This is not part of `sas_formats.py`, but it is relevant to operational use.

---

## 13. Recommended Future Enhancements

These are optional and must not alter current format names unless explicitly requested.

### 13.1 CLI Arguments

Add optional arguments:

```text
--index-file
--output-dir
```

### 13.2 Semicolon Per Mapping

Optionally write each mapping with an explicit semicolon:

```sas
"v000001" = "camera";
```

This may improve SAS log readability and debugging.

### 13.3 Additional SAS Escaping

Add support for escaping or normalising other problematic characters if encountered.

### 13.4 Format Validation

After writing the SAS files, optionally validate that:

- number of mappings equals number of index entries;
- all variable names match `v\d{6}`.

### 13.5 Manifest

Write a manifest:

```text
sas/sas_formats_manifest.json
```

containing:

- input file path;
- output file paths;
- number of labels;
- timestamp.

---

## 14. Summary

`sas_formats.py` translates the project’s keyword index into SAS character formats.

Its core responsibility is:

```text
Map v-prefixed keyword IDs to readable lemma labels for SAS output tables.
```

It must preserve:

- headerless `index_keywords.txt` input;
- six-digit keyword IDs;
- `v000001` variable naming;
- `$lexlabels` and `$lexlabelsfull` format names;
- SAS compatibility.