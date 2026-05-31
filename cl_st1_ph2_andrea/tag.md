# Development Specification: `tag.py`

## 1. Programme Purpose

`tag.py` performs automatic part-of-speech tagging and lemmatisation of the project’s decade-organised commercial text corpus using TreeTagger.

The programme reads plain-text input files from a commercial subcorpus directory, sends each file through the external `tree-tagger-english` command, and writes the tagged output to a parallel decade-based directory structure.

The programme is used as an early preprocessing step for Lexical Multi-Dimensional Analysis (LMDA). Its output is consumed by downstream scripts that extract key lemmas, select keywords, build binary keyword columns, and prepare SAS input matrices.

---

## 2. Project Context

The project contains two parallel commercial subcorpora:

1. **Phase 2: Commercial verbal subcorpus**
   - Input directory:
     ```text
     corpus/commercial_verbal/
     ```
   - Contains transcript texts representing the spoken/audio-verbal content of selected television commercials.

2. **Phase 3: Commercial visual subcorpus**
   - Input directory:
     ```text
     corpus/commercial_visual/
     ```
   - Contains textual descriptions of the visual content of the same selected television commercials.

Both subcorpora are organised into decade folders:

```text
corpus/<commercial_subcorpus>/
    1950/
    1960/
    1970/
    1980/
    1990/
    2000/
    2010/
    2020/
```

Each decade folder contains `.txt` files named by commercial ID, for example:

```text
corpus/commercial_verbal/1950/tv_com_1950_1.txt
corpus/commercial_visual/1950/tv_com_1950_1.txt
```

The tagged output is written to:

```text
corpus/07_tagged/
```

while preserving the same decade subdirectory structure:

```text
corpus/07_tagged/1950/tv_com_1950_1.txt
corpus/07_tagged/1960/tv_com_1960_1.txt
...
```

---

## 3. Required Inputs

### 3.1 Input Root Directory

The programme must read from one configured input root directory.

For Phase 2, default:

```text
corpus/commercial_verbal
```

For Phase 3, default:

```text
corpus/commercial_visual
```

The current phase-specific copy of `tag.py` may hard-code the relevant input directory, or a future version may expose it as a command-line argument.

### 3.2 Input Directory Structure

The input root must contain immediate subdirectories representing decades:

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

The programme should treat each immediate subdirectory as a corpus stratum.

### 3.3 Input Files

The programme must process files matching:

```text
*.txt
```

inside each decade directory.

The current programme only processes `.txt` files immediately inside each decade directory, not recursively nested files.

Expected example:

```text
corpus/commercial_verbal/1950/tv_com_1950_1.txt
```

### 3.4 External Dependency

The programme requires the external command:

```text
tree-tagger-english
```

This command must be available on the system `PATH`.

The programme does not install TreeTagger. It assumes TreeTagger has already been configured externally.

---

## 4. Outputs

### 4.1 Output Root Directory

Tagged files are written to:

```text
corpus/07_tagged
```

The programme must create this directory if it does not already exist.

### 4.2 Output Directory Structure

The output must preserve the decade structure from the input:

```text
corpus/07_tagged/<Decade>/
```

For example:

```text
corpus/07_tagged/1950/
corpus/07_tagged/1960/
...
```

### 4.3 Output Files

Each input file must produce one output file with the same filename:

```text
corpus/07_tagged/<Decade>/<Commercial ID>.txt
```

Example mapping:

```text
corpus/commercial_verbal/1950/tv_com_1950_1.txt
```

to:

```text
corpus/07_tagged/1950/tv_com_1950_1.txt
```

### 4.4 Tagged File Format

The output format is determined by `tree-tagger-english`.

Downstream scripts expect TreeTagger-style tabular output with at least three fields per token line:

```text
word<TAB>tag<TAB>lemma
```

Example conceptual format:

```text
product	NN	product
appears	VBZ	appear
bright	JJ	bright
```

The programme must not add headers or additional metadata to the tagged output files.

---

## 5. Functional Requirements

### 5.1 Directory Discovery

The programme must:

1. Set an input base directory.
2. List immediate child directories under the input base.
3. Sort those directories.
4. Treat each directory as a decade folder.
5. Ignore non-directory entries.

If no decade folders are found, the programme must print a clear message and exit without error.

Example message:

```text
No decade folders found under corpus/commercial_verbal. Exiting.
```

### 5.2 Task Collection

For each decade folder, the programme must:

1. Use the folder name as the output subfolder name.
2. Find all `.txt` files directly inside the folder.
3. Sort the files.
4. Create a task mapping:

```text
input file → output file
```

The output file path must be:

```text
OUTPUT_BASE / decade / input_filename
```

### 5.3 Output Directory Creation

For each output file, the programme must ensure the parent output directory exists before writing.

Example:

```text
corpus/07_tagged/1950/
```

### 5.4 Tagging

For each input file, the programme must:

1. Open the input file in UTF-8 text mode.
2. Open the output file in UTF-8 text mode.
3. Run:

```text
tree-tagger-english
```

4. Send the input file content to the command via standard input.
5. Capture the command’s standard output into the output file.
6. Use `check=True` so that failed tagging commands raise an error.

### 5.5 Parallel Processing

The programme must process files in parallel using Python’s `ProcessPoolExecutor`.

The number of workers should be:

```python
max(1, multiprocessing.cpu_count() - 1)
```

This leaves one CPU core free.

### 5.6 Progress Reporting

The programme must display:

- total number of files to tag;
- input root directory;
- output root directory;
- number of workers;
- progress bar over files;
- per-file completion message with elapsed time.

Example:

```text
Total files to tag: 824

Input root directory: corpus/commercial_verbal
Output root directory: corpus/07_tagged

Using 7 workers...

✓ tv_com_1950_1.txt tagged in 0.4s
```

### 5.7 Empty Corpus Handling

If no `.txt` files are found in the discovered decade folders, the programme must print:

```text
No text files to tag. Exiting.
```

and exit without error.

---

## 6. Non-Functional Requirements

### 6.1 Encoding

All input and output text files must be read and written using:

```text
UTF-8
```

### 6.2 Deterministic Ordering

The programme must sort:

- decade folders;
- input text files within each decade.

This ensures reproducible processing order and predictable progress output.

### 6.3 No Header Injection

The programme must not insert any header lines or metadata lines into tagged output files.

The output must be exactly the output generated by `tree-tagger-english`.

### 6.4 No Delimiter Modification

The programme must not alter TreeTagger delimiters.

Downstream scripts expect tab-separated TreeTagger output.

### 6.5 Re-runnability

The programme may overwrite existing tagged files by default.

Current behaviour:

- if an output file already exists, it is overwritten.

A future version may add `--skip-existing` or `--reprocess`, but the current expected behaviour is overwrite-safe regeneration.

### 6.6 External Command Failure

If `tree-tagger-english` fails for a file, the subprocess call raises an exception.

Current implementation does not include per-file failure recovery. A single worker failure may interrupt the executor process.

Future improvement may include structured failure reporting, but this is not required for the current programme.

---

## 7. Phase-Specific Configuration

### 7.1 Phase 2 Configuration

For Phase 2, `INPUT_BASE` should be:

```python
Path("corpus/commercial_verbal")
```

Output:

```python
Path("corpus/07_tagged")
```

### 7.2 Phase 3 Configuration

For Phase 3, `INPUT_BASE` should be:

```python
Path("corpus/commercial_visual")
```

Output:

```python
Path("corpus/07_tagged")
```

### 7.3 Shared Behaviour

All other behaviour should remain identical between phases.

Both phases use:

```text
corpus/07_tagged/<Decade>/<Commercial ID>.txt
```

as downstream input for key-lemma extraction.

---

## 8. Expected Downstream Compatibility

The output of `tag.py` must be compatible with:

1. `keylemmas.py`
   - expects decade folders under `corpus/07_tagged`;
   - reads TreeTagger tabular output;
   - uses the third column as lemma.

2. `select_kws_stratified.py`
   - indirectly depends on `keylemmas.py` outputs.

3. `columns.py`
   - reads tagged files under decade folders;
   - uses lemmas from the third column.

4. SAS matrix generation pipeline
   - indirectly depends on stable decade-based folder structure.

Therefore, the following output convention is mandatory:

```text
corpus/07_tagged/<Decade>/<Commercial ID>.txt
```

---

## 9. Error Conditions

### 9.1 Missing Input Directory

If the input directory does not exist, the programme will currently raise an error when attempting to iterate over it.

Recommended future behaviour:

```text
Input directory does not exist: corpus/commercial_verbal
```

### 9.2 Missing TreeTagger Command

If `tree-tagger-english` is not available on `PATH`, subprocess execution will fail.

Recommended user-facing error:

```text
tree-tagger-english command not found. Ensure TreeTagger is installed and available on PATH.
```

Current programme does not explicitly catch this.

### 9.3 Invalid Encoding

If an input file is not UTF-8 encoded, reading may fail.

Current programme assumes all input files are UTF-8.

### 9.4 Empty Input

If no `.txt` files are found, the programme exits cleanly with an explanatory message.

---

## 10. Recommended Future Enhancements

These are optional and should not alter current output format.

### 10.1 Command-Line Arguments

Add optional CLI arguments:

```text
--input-base
--output-base
--workers
--skip-existing
```

Example:

```shell
python tag.py \
  --input-base corpus/commercial_visual \
  --output-base corpus/07_tagged \
  --workers 4
```

### 10.2 Skip Existing Outputs

Add an option to skip files already tagged:

```text
--skip-existing
```

This would support resuming interrupted runs.

### 10.3 Failure Manifest

Write a manifest recording:

- input file;
- output file;
- status;
- elapsed time;
- error message if any.

Possible output:

```text
corpus/07_tagged/tag_manifest.tsv
```

### 10.4 Decade Folder Validation

Warn if unexpected folders are found or if expected decades are missing.

Expected decades:

```text
1950 1960 1970 1980 1990 2000 2010 2020
```

### 10.5 Recursive Option

Add an optional recursive mode if the project later introduces nested text directories.

Current behaviour should remain non-recursive by default.

---

## 11. Acceptance Criteria

The programme is considered correct if:

1. It reads `.txt` files from:

```text
corpus/commercial_verbal/<Decade>/
```

or:

```text
corpus/commercial_visual/<Decade>/
```

depending on phase.

2. It writes tagged outputs to:

```text
corpus/07_tagged/<Decade>/<Same Filename>.txt
```

3. It preserves the decade folder structure.

4. It does not add headers.

5. It does not modify TreeTagger output format.

6. It creates `corpus/07_tagged` and decade subfolders if needed.

7. It processes all available input `.txt` files.

8. It reports progress and final completion.

9. Downstream `keylemmas.py` can read the output successfully.

---

## 12. Minimal Example

Given:

```text
corpus/commercial_verbal/1950/tv_com_1950_1.txt
```

The programme should produce:

```text
corpus/07_tagged/1950/tv_com_1950_1.txt
```

with TreeTagger output similar to:

```text
The	DT	the
commercial	NN	commercial
begins	VBZ	begin
...
```

No additional lines should be added.