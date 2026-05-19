# Specification: `split4git.py`

## 1. Programme Summary

`split4git.py` is a command-line utility for safely preparing repositories that contain files larger than a chosen Git-safe threshold.

The programme takes a **working directory** as both input and output. It recursively scans the directory, detects regular files larger than a configurable threshold, splits them into ordered binary part files, and records enough metadata to later reassemble the original files exactly at binary level.

It also supports the reverse operation: reading the register, verifying the part files, and reassembling the original files.

The programme has two main commands:

- `disband`: split oversized files into ordered part files.
- `squad-up`: reassemble original files from previously created part files.

Both commands support `--dry-run`.

Default size threshold:

```text
45 MiB
```

The default threshold is intended to stay below GitHub’s common warning threshold for regular repository files.

---

## 2. Goals and Non-Goals

## 2.1 Goals

The programme must:

- Operate on a user-provided working directory.
- Recursively scan the working directory and its subdirectories.
- Detect regular files larger than a configurable threshold in MiB.
- Split oversized files into multiple binary-safe part files.
- Name part files after the original filename in deterministic ascending order.
- Create and maintain a register file in the working directory.
- Store enough information in the register to:
  - identify the original file
  - identify all part files
  - verify all part files
  - verify the reassembled original
  - reassemble the original file exactly at binary level
- Support `disband` for splitting.
- Support `squad-up` for reassembling.
- Support `--dry-run` for both commands.
- Generate a `.gitignore` section after splitting.
- Display the generated `.gitignore` section on screen.
- Save the generated `.gitignore` section in the register file.
- Preserve part files during `squad-up`.
- During `squad-up`, verify integrity before writing output.
- During `squad-up`, leave an already consistent original file unchanged.
- During `squad-up`, rename an inconsistent existing original before reassembling.
- Use safe, binary, streaming file operations.
- Avoid silent overwrites.

## 2.2 Non-Goals

The programme does **not** need to:

- Upload files to GitHub.
- Modify Git history.
- Automatically configure Git LFS.
- Automatically edit `.gitignore` by default.
- Compress files.
- Encrypt files.
- Transform file contents.
- Reconstruct originals without a register.
- Follow symlinks by default.
- Guarantee recovery from all possible system crashes.
- Delete part files after reassembly by default.

---

## 3. Terminology

| Term | Meaning |
|---|---|
| **Working directory** | The directory passed to the programme. It is scanned recursively and also receives programme metadata files. |
| **Repository root** | The root of the Git repository, if detectable. It may be the same as the working directory. |
| **Original file** | A file larger than the configured threshold and selected for splitting. |
| **Part file** | A binary fragment created from an original file. |
| **Register** | A JSON file containing metadata about originals, parts, hashes, sizes, runs, and generated `.gitignore` entries. |
| **Disband** | The command that splits large files into part files. |
| **Squad-up** | The command that reassembles original files from part files. |
| **Dry run** | A mode that reports planned actions without modifying the filesystem. |
| **Consistent original** | An existing original file whose size and SHA-256 match the register. |
| **Inconsistent original** | An existing original file whose size or SHA-256 does not match the register. |
| **Consistent part** | A part file whose path, size, index, and SHA-256 match the register. |

---

## 4. Input and Output

## 4.1 Input

The programme accepts:

- A command:
  - `disband`
  - `squad-up`
- A working directory path.
- Optional configuration flags, including:
  - threshold in MiB
  - part size in MiB
  - dry-run mode
  - register path
  - log path
  - force mode
  - verbosity options

The programme discovers files recursively under the working directory.

Only regular files are candidates for splitting.

The programme must ignore:

- directories
- symlinks by default
- sockets
- pipes
- device files
- files inside `.git` directories
- the register file
- the log file
- temporary files created by this programme
- part files already managed by this programme
- known backup files created by this programme

## 4.2 Output

The programme may produce:

- Part files next to each original file.
- A JSON register file.
- A log file.
- Console output.
- A generated `.gitignore` section.
- Reassembled original files during `squad-up`.
- Backup copies of inconsistent originals during `squad-up`.

Default generated files:

```text
<working-directory>/.split4git.register.json
<working-directory>/.split4git.log
```

---

## 5. Command-Line Interface

## 5.1 General Form

```bash
python split4git.py COMMAND WORKING_DIRECTORY [OPTIONS]
```

`COMMAND` must be one of:

```text
disband
squad-up
```

---

## 5.2 `disband` Command

Splits files larger than the threshold.

Example:

```bash
python split4git.py disband . --threshold-mib 45
```

Dry run:

```bash
python split4git.py disband . --threshold-mib 45 --dry-run
```

---

## 5.3 `squad-up` Command

Reassembles files listed in the register.

Example:

```bash
python split4git.py squad-up .
```

Dry run:

```bash
python split4git.py squad-up . --dry-run
```

---

## 5.4 Required Arguments

### `COMMAND`

Required.

Allowed values:

- `disband`
- `squad-up`

### `WORKING_DIRECTORY`

Required.

Validation:

- Must exist.
- Must be a directory.
- Must be readable.
- Must be writable for non-dry-run operations.
- Must be resolved to an absolute path before processing.

---

## 5.5 Optional Arguments

### `--threshold-mib FLOAT`

Default:

```text
45
```

Meaning:

- Files strictly larger than this threshold are selected for splitting.
- Files equal to or below the threshold are not split.

Validation:

- Must be greater than `0`.

---

### `--part-size-mib FLOAT`

Default:

```text
same as --threshold-mib
```

Meaning:

- Maximum size of each generated part file.
- Normally each part file should be less than or equal to the Git-safe threshold.

Validation:

- Must be greater than `0`.
- Must be less than or equal to `--threshold-mib`.

---

### `--dry-run`

Default:

```text
false
```

Meaning:

- Report what would happen.
- Do not create, delete, rename, overwrite, or modify files.
- Do not write or update the register.
- Do not write or update the log.

Dry-run may still read files and compute hashes.

---

### `--register-file PATH`

Default:

```text
<working-directory>/.split4git.register.json
```

Meaning:

- Path to the JSON register file.

If relative, resolve relative to the working directory.

Validation:

- Must not escape the working directory.

---

### `--log-file PATH`

Default:

```text
<working-directory>/.split4git.log
```

Meaning:

- Path to the append-only log file.

If relative, resolve relative to the working directory.

Validation:

- Must not escape the working directory.

---

### `--force`

Default:

```text
false
```

For `disband`:

- Allows stale or inconsistent existing part files to be replaced.
- Without `--force`, conflicting existing files cause a safe failure for that item.

For `squad-up`:

- May allow conservative reassembly decisions to proceed.
- Must **not** bypass part hash verification.
- Must **not** bypass original hash verification after reassembly.

---

### `--keep-original`

Default:

```text
true
```

For `disband`:

- If true, keep the original large file after successful splitting.
- If false, remove the original only after:
  - all part files are written
  - all part hashes are verified
  - the register is safely written

Recommended default:

```text
true
```

Reason:

- Keeping originals is safer.
- The generated `.gitignore` section can prevent the originals from being committed.

---

### `--workers N`

Default:

```text
1
```

Meaning:

- Number of files to process concurrently.

Validation:

- Must be an integer greater than or equal to `1`.

Initial implementation may process sequentially only.

---

### `--verbose`

Show more detailed console output.

---

### `--quiet`

Reduce console output to warnings, errors, and final summary.

---

## 6. Size Definitions

The programme uses binary mebibytes:

```text
1 MiB = 1,048,576 bytes
```

Therefore, the default threshold is:

```text
45 MiB = 47,185,920 bytes
```

A file is eligible for splitting only if:

```text
file_size_bytes > threshold_bytes
```

A file whose size is exactly equal to the threshold is not split.

---

## 7. Part File Naming Scheme

Part files must be named deterministically after the original filename.

Recommended pattern:

```text
<original_filename>.split4git.partNNNN
```

Example original:

```text
video.mp4
```

Example parts:

```text
video.mp4.split4git.part0001
video.mp4.split4git.part0002
video.mp4.split4git.part0003
```

Rules:

- Numbering starts at `0001`.
- Numeric order must match lexicographic order.
- Width must be at least four digits.
- Width may expand if more than 9999 parts are required.
- Part files are written in the same directory as the original file.
- The register must store the explicit part file list.
- The programme must not rely on filename guessing alone during reassembly.

Temporary part files must use a distinct suffix:

```text
<original_filename>.split4git.partNNNN.tmp
```

A temporary part file becomes final only after it has been fully written and verified.

---

## 8. Register File Specification

## 8.1 Register Location

Default:

```text
<working-directory>/.split4git.register.json
```

The register is the authoritative source for `squad-up`.

---

## 8.2 Register Requirements

The register must include enough information to:

- identify the working directory used when the split was created
- identify every original file
- identify every part file
- verify part sizes
- verify part hashes
- verify the original file size
- verify the original file hash
- determine the exact ordering of parts
- reconstruct the original file exactly
- reproduce the generated `.gitignore` section
- keep a history of programme runs

---

## 8.3 Register Encoding

The register must be:

- JSON
- UTF-8 encoded
- human-readable with indentation
- written atomically

---

## 8.4 Register Schema

Recommended top-level structure:

```json
{
  "schema_version": "1.0",
  "tool_name": "split4git.py",
  "tool_version": "1.0.0",
  "working_directory": "/absolute/path/to/working-directory",
  "created_at": "2026-05-19T12:00:00Z",
  "updated_at": "2026-05-19T12:05:00Z",
  "config": {
    "threshold_mib": 45.0,
    "threshold_bytes": 47185920,
    "part_size_mib": 45.0,
    "part_size_bytes": 47185920
  },
  "gitignore_section": {
    "begin_marker": "# BEGIN split4git managed originals",
    "end_marker": "# END split4git managed originals",
    "content": [
      "# BEGIN split4git managed originals",
      "/large-file.bin",
      "/data/archive.zip",
      "# END split4git managed originals"
    ],
    "generated_at": "2026-05-19T12:05:00Z"
  },
  "files": [
    {
      "original_relative_path": "large-file.bin",
      "original_size_bytes": 123456789,
      "original_sha256": "b1946ac92492d2347c6235b4d2611184...",
      "status": "split",
      "split_at": "2026-05-19T12:01:00Z",
      "part_size_bytes": 47185920,
      "parts": [
        {
          "index": 1,
          "relative_path": "large-file.bin.split4git.part0001",
          "size_bytes": 47185920,
          "sha256": "..."
        },
        {
          "index": 2,
          "relative_path": "large-file.bin.split4git.part0002",
          "size_bytes": 47185920,
          "sha256": "..."
        },
        {
          "index": 3,
          "relative_path": "large-file.bin.split4git.part0003",
          "size_bytes": 29484949,
          "sha256": "..."
        }
      ],
      "metadata": {
        "part_count": 3,
        "original_mtime_ns": 1779192000000000000,
        "original_mode": "0644"
      }
    }
  ],
  "runs": [
    {
      "run_id": "20260519T120500Z",
      "command": "disband",
      "dry_run": false,
      "start_time": "2026-05-19T12:00:00Z",
      "end_time": "2026-05-19T12:05:00Z",
      "status": "success",
      "summary": {
        "discovered": 120,
        "eligible": 2,
        "processed": 2,
        "skipped": 0,
        "failed": 0
      },
      "files": [
        {
          "relative_path": "large-file.bin",
          "status": "success",
          "error": null,
          "duration_seconds": 1.34,
          "metadata": {
            "parts_written": 3
          }
        }
      ]
    }
  ]
}
```

---

## 8.5 Path Rules in the Register

The register must store paths relative to the working directory.

Relative paths must:

- use `/` as separator in JSON
- not be absolute
- not contain `..`
- not escape the working directory when resolved
- refer to files inside the working directory

The absolute working directory path may be stored for diagnostics, but reassembly should primarily rely on safe relative paths.

---

## 8.6 Hashing

Required hash algorithm:

```text
SHA-256
```

The programme must compute and store:

- SHA-256 of each original file before or during splitting.
- SHA-256 of each part file after writing.
- SHA-256 of each existing part during `squad-up` verification.
- SHA-256 of each reassembled original.

Hashes must be represented as lowercase hexadecimal strings.

---

## 9. Logging Specification

Default log path:

```text
<working-directory>/.split4git.log
```

The log file must be append-only.

Recommended format:

```text
[YYYY-MM-DD HH:MM:SS] LEVEL  message
```

Minimum logged events:

- startup
- selected command
- working directory
- dry-run status
- threshold and part size
- register path
- log path
- discovery summary
- selected files
- skipped files and reasons
- conflicts
- part-writing events
- integrity-check events
- register read/write events
- generated `.gitignore` section
- backup rename events
- reassembly events
- per-file failures
- final summary
- interruptions

In `--dry-run` mode:

- The programme should not write a log file by default.
- It may print all relevant information to the console.

---

# 10. `disband` Behaviour

## 10.1 Purpose

`disband` splits oversized files into ordered part files and records the mapping in the register.

---

## 10.2 High-Level Flow

The `disband` command must:

1. Parse CLI arguments.
2. Validate configuration.
3. Resolve the working directory.
4. Set up logging unless in dry-run mode.
5. Load the existing register if present.
6. Recursively discover candidate files.
7. Exclude programme-managed files.
8. Select files larger than `threshold_bytes`.
9. Sort selected files by relative path.
10. Plan part filenames.
11. Check for existing-register consistency and part-file conflicts.
12. If `--dry-run`, display the plan and exit without changes.
13. For each eligible file:
    - compute original metadata
    - split file into temporary part files
    - verify each part
    - atomically rename temporary parts to final part names
    - update in-memory register
14. Generate `.gitignore` section for original files.
15. Display `.gitignore` section on screen.
16. Save `.gitignore` section in the register.
17. Atomically write the register.
18. Print final summary.
19. Exit with the appropriate status code.

---

## 10.3 File Selection

A file is eligible for splitting if:

- it is a regular file
- its size is strictly greater than `threshold_bytes`
- it is not inside `.git`
- it is not the register file
- it is not the log file
- it is not a part file
- it is not a temporary file
- it is not a programme-generated backup file

---

## 10.4 Splitting Rules

For each selected original:

- Open the original file in binary mode.
- Read using a bounded buffer.
- Never load the full file into memory.
- Write part files in binary mode.
- Each part except the final part must be exactly `part_size_bytes`.
- The final part may be smaller.
- Compute SHA-256 for the original.
- Compute SHA-256 for each part.
- Store all metadata in the register.
- Verify total part sizes equal the original size.
- Verify part hashes after writing.

The concatenation of all parts in ascending index order must exactly equal the original bytes.

---

## 10.5 Existing Register Entries

If a selected file is already listed in the register:

- If original path, size, hash, and part metadata are consistent, skip it as already split.
- If metadata differs, treat the entry as stale or conflicting.
- Without `--force`, fail safely for that file.
- With `--force`, replace stale metadata and parts safely.

---

## 10.6 Existing Part File Conflicts

If a planned part file already exists:

- If it matches the register metadata, it may be reused.
- If it does not match the register metadata, it is a conflict.
- Without `--force`, the file must fail safely.
- With `--force`, it may be replaced after logging the decision.

The programme must never silently overwrite unrelated files.

---

## 10.7 Original File Handling After Split

Default behaviour:

- Keep the original file.

If `--keep-original false` is selected:

- Delete the original only after:
  - all part files are written
  - all part files are verified
  - the register is safely written
- If any step fails, keep the original.

---

# 11. `.gitignore` Section Generation

After a successful `disband` run, the programme must generate a `.gitignore` section for original large files.

Purpose:

- Keep part files trackable by Git.
- Prevent original oversized files from being accidentally committed.

Recommended section:

```gitignore
# BEGIN split4git managed originals
/large-file.bin
/data/archive.zip
/models/model.pkl
# END split4git managed originals
```

Rules:

- The section must be displayed on screen.
- The section must be saved in the register.
- Entries must refer to original files, not part files.
- Entries must be deterministic and sorted.
- Entries should be relative to the repository root if it can be detected.
- If no repository root is detected, entries should be relative to the working directory.
- The programme must clearly say which base path was used.
- The programme should not automatically edit `.gitignore` by default.

Recommended console message:

```text
Add the following section to your repository root .gitignore:
```

If the working directory is not the repository root:

```text
Repository root detected at: /path/to/repo
The following .gitignore entries are relative to that repository root:
```

If no repository is detected:

```text
No Git repository root was detected.
The following entries are relative to the working directory:
```

---

# 12. `squad-up` Behaviour

## 12.1 Purpose

`squad-up` reassembles original files from registered part files.

It must verify all part files before reassembly and must preserve valid part files unchanged.

---

## 12.2 High-Level Flow

The `squad-up` command must:

1. Parse CLI arguments.
2. Validate configuration.
3. Resolve the working directory.
4. Load the register file.
5. Validate the register schema.
6. Sort registered files by original relative path.
7. For each registered file:
   - validate paths
   - verify all part files exist
   - verify all part file sizes
   - verify all part file SHA-256 hashes
   - verify part indexes and ordering
   - check whether the original file already exists
   - decide whether to skip, rename, or reassemble
8. If `--dry-run`, display the plan and exit without changes.
9. For each file requiring reassembly:
   - rename inconsistent existing original if present
   - write reassembled output to a temporary file
   - verify temporary output size and SHA-256
   - atomically rename temporary output to the original path
   - restore file metadata where practical
10. Preserve part files unchanged.
11. Update run history in the register.
12. Atomically write the register.
13. Print final summary.
14. Exit with the appropriate status code.

---

## 12.3 Part Integrity Checking

Before any reassembly decision is final, the programme must verify that all registered part files are consistent.

For each registered file, the programme must check:

- every part file exists
- every part file is a regular file
- every part path is safe
- every part size matches registered `size_bytes`
- every part SHA-256 matches registered `sha256`
- part indexes are complete
- part indexes start at `1`
- part indexes increase by `1`
- part ordering is unambiguous
- the sum of part sizes equals `original_size_bytes`

If any part fails integrity checking:

- do not reassemble that original
- do not rename an existing original
- do not modify any part file
- mark the file as failed
- report the reason clearly

---

## 12.4 Part File Preservation During `squad-up`

The `squad-up` command must preserve part files by default.

If the part files are consistent, they must be left unchanged.

The programme must not:

- delete part files
- rename part files
- overwrite part files
- truncate part files
- modify part file bytes
- relocate part files

This applies whether:

- the original already exists and is consistent
- the original is missing
- the original exists but is inconsistent
- reassembly succeeds
- reassembly fails

After successful reassembly, the part files must still remain in place so that:

- the operation is repeatable
- the repository remains self-contained
- the original can be reconstructed again later
- accidental data loss is avoided

Any future option to remove parts after reassembly must be:

- explicit
- opt-in
- disabled by default
- documented as potentially unsafe

Example future option name:

```text
--remove-parts-after-squad-up
```

This option is not required for the initial specification.

---

## 12.5 Original File Already Exists

During `squad-up`, after verifying part files, the programme must check whether the original file already exists.

---

### Case 1: Original exists and is consistent

If the original exists and:

- its size equals `original_size_bytes`
- its SHA-256 equals `original_sha256`

Then the programme must:

- leave the original unchanged
- leave all part files unchanged
- mark the file as `skipped_existing_consistent`
- report that no reassembly was needed

---

### Case 2: Original exists but is inconsistent

If the original exists but:

- its size does not match `original_size_bytes`, or
- its SHA-256 does not match `original_sha256`

Then the programme must:

1. Leave all part files unchanged.
2. Rename the inconsistent original to a backup path.
3. Reassemble the original from verified parts.
4. Verify the reassembled original.
5. Report both the backup rename and the reassembly.

Recommended backup pattern:

```text
<original_filename>.split4git.inconsistent.<YYYYMMDDTHHMMSSZ>.bak
```

Example:

```text
archive.zip.split4git.inconsistent.20260519T120500Z.bak
```

If that backup name already exists, append a counter:

```text
archive.zip.split4git.inconsistent.20260519T120500Z.001.bak
archive.zip.split4git.inconsistent.20260519T120500Z.002.bak
```

The backup rename must not overwrite an existing file.

If the rename fails:

- do not reassemble
- leave part files unchanged
- report failure

---

### Case 3: Original does not exist

If the original does not exist:

- leave all part files unchanged
- reassemble the original from verified parts
- verify the reassembled original
- report success or failure

---

## 12.6 Reassembly Rules

For each file requiring reassembly:

- Create parent directories if missing.
- Write to a temporary output file first.
- Use binary mode.
- Read part files in ascending index order.
- Use streaming I/O.
- Never load all parts into memory.
- Concatenate part bytes exactly.
- Compute SHA-256 of the reassembled output.
- Verify output size.
- Verify output hash.
- Atomically rename temporary output to the original path.
- Restore original mode and modification time where recorded and supported.

Recommended temporary output pattern:

```text
<original_filename>.split4git.reassemble.tmp
```

The temporary file must be removed after a failed reassembly if it is safe to do so.

The programme must never intentionally leave a corrupt file at the original path.

---

# 13. Dry-Run Mode

Dry-run mode must perform no filesystem modifications.

---

## 13.1 `disband --dry-run`

Must report:

- working directory
- threshold
- part size
- files discovered
- files eligible for splitting
- files skipped and reasons
- planned part filenames
- planned number of parts per file
- expected part sizes
- existing register entries that would be reused
- stale register entries
- conflicts
- generated `.gitignore` section
- final summary

Must not:

- create part files
- create temporary files
- write the register
- update the register
- write the log
- delete originals
- rename files
- modify `.gitignore`

---

## 13.2 `squad-up --dry-run`

Must report:

- register file path
- registered files found
- part files that would be verified
- detected missing or inconsistent parts
- originals that already exist and are consistent
- originals that would be renamed as inconsistent backups
- originals that would be reassembled
- temporary output paths that would be used
- final summary

Must not:

- create original files
- create temporary files
- rename inconsistent originals
- delete files
- modify part files
- update the register
- write the log
- modify `.gitignore`

Dry-run may:

- read files
- calculate file sizes
- compute SHA-256 hashes
- validate register entries

---

# 14. Safety and Atomicity

## 14.1 General Safety Rules

The programme must:

- use binary mode for file content
- use streaming reads and writes
- use deterministic ordering
- avoid silent overwrites
- validate paths before using them
- reject unsafe register paths
- avoid following symlinks by default
- write outputs through temporary files
- use atomic renames where practical
- keep enough metadata for manual recovery
- fail safely on ambiguity

---

## 14.2 Register Write Safety

When writing the register:

1. Write to a temporary file.
2. Flush the temporary file.
3. Close the temporary file.
4. Atomically replace the old register.

Recommended temporary path:

```text
.split4git.register.json.tmp
```

If register writing fails:

- report failure
- do not claim success
- do not delete originals
- do not delete parts

---

## 14.3 Part File Write Safety

During `disband`:

- Each part should first be written to a temporary file.
- The final part filename should appear only after successful writing and verification.
- Existing unrelated files must not be overwritten.
- If a part write fails, incomplete temporary files should be removed where safe.

---

## 14.4 Reassembly Write Safety

During `squad-up`:

- The original path must not be overwritten directly.
- Reassembly must write to a temporary file first.
- The temporary file must be verified before becoming the original.
- An inconsistent original must be renamed before the verified temporary file is moved into place.

---

## 14.5 Interrupt Handling

On `KeyboardInterrupt`, the programme must:

- stop scheduling new work
- safely finish or abort the current file operation
- remove incomplete temporary files where safe
- preserve existing originals
- preserve existing part files
- write a partial summary if safe
- exit non-zero

Recommended exit code:

```text
130
```

---

# 15. Error Handling

## 15.1 Configuration Errors

The programme must fail before processing if:

- command is unknown
- working directory is missing
- working directory is not a directory
- working directory is unreadable
- working directory is unwritable for non-dry-run execution
- threshold is invalid
- part size is invalid
- register path escapes the working directory
- log path escapes the working directory

Recommended exit code:

```text
2
```

---

## 15.2 Register Errors

For `squad-up`, if the register is missing:

- exit with a clear error
- do not attempt heuristic reconstruction from filenames alone

If the register is malformed:

- exit with a clear error
- do not modify files

If the schema version is unsupported:

- exit with a clear error
- do not modify files

Recommended exit code:

```text
3
```

---

## 15.3 Per-File Errors

A failure for one file should not necessarily abort the whole run.

Per-file failures include:

- unreadable original file
- unwritable destination directory
- conflicting part file
- failed part write
- failed part hash verification
- missing registered part
- invalid registered part metadata
- failed original backup rename
- failed reassembly
- failed final hash verification
- failed final rename

For each per-file error, the programme must:

- record the file as failed in the run summary
- report the error clearly
- continue with other files where safe
- exit non-zero if any file failed

Recommended exit code:

```text
1
```

---

# 16. Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Success; all planned actions completed or all relevant files were safely skipped |
| `1` | One or more per-file failures occurred |
| `2` | Command-line argument or configuration error |
| `3` | Register missing, malformed, or incompatible |
| `130` | Interrupted by user |

---

# 17. Core Processing Architecture

## 17.1 Main Components

The implementation should separate the following concerns:

- CLI parsing
- argument validation
- configuration construction
- logging setup
- file discovery
- split planning
- part writing
- hash calculation
- register loading
- register validation
- register writing
- `.gitignore` section generation
- reassembly planning
- reassembly execution
- summary reporting

---

## 17.2 Recommended Functions

### `discover_files`

Purpose:

- Recursively discover regular candidate files.

Responsibilities:

- walk the working directory
- exclude `.git`
- exclude programme-managed files
- avoid symlinks by default
- return deterministic sorted relative paths

Filesystem writes:

- none

---

### `hash_file`

Purpose:

- Compute SHA-256 for a file in streaming mode.

Responsibilities:

- read file in binary mode
- use bounded buffer size
- return lowercase SHA-256 hex digest

Filesystem writes:

- none

---

### `plan_disband`

Purpose:

- Create a non-mutating split plan.

Responsibilities:

- select oversized files
- calculate part count
- generate part filenames
- detect conflicts
- inspect existing register entries
- prepare dry-run details

Filesystem writes:

- none

---

### `split_file`

Purpose:

- Split one file into verified part files.

Responsibilities:

- read original in binary mode
- write temporary part files
- hash original and parts
- verify sizes
- atomically rename temporary parts
- return structured metadata

Filesystem writes:

- yes

---

### `load_register`

Purpose:

- Load and validate the register.

Responsibilities:

- read JSON
- validate schema
- validate safe paths
- return structured register data

Filesystem writes:

- none

---

### `write_register_atomic`

Purpose:

- Safely persist register data.

Responsibilities:

- write temporary JSON
- flush and close
- atomically replace existing register

Filesystem writes:

- yes

---

### `generate_gitignore_section`

Purpose:

- Generate deterministic `.gitignore` guidance.

Responsibilities:

- collect original paths from register
- convert to repository-root-relative paths where possible
- create marker-delimited section
- return lines for console output and register storage

Filesystem writes:

- none by default

---

### `plan_squad_up`

Purpose:

- Create a non-mutating reassembly plan.

Responsibilities:

- inspect register
- validate part files
- check original existence
- decide skip, backup, or reassemble
- prepare dry-run output

Filesystem writes:

- none

---

### `reassemble_file`

Purpose:

- Reassemble one original from verified parts.

Responsibilities:

- preserve part files
- rename inconsistent original if needed
- concatenate parts in binary order
- write temporary output
- verify size and hash
- atomically move verified output to original path
- restore metadata where practical

Filesystem writes:

- yes, but only to original/backup/temp paths; never to part files

---

# 18. Run History

The register should include run history.

Each non-dry-run execution should append a run record.

Recommended run record:

```json
{
  "run_id": "20260519T120500Z",
  "command": "squad-up",
  "dry_run": false,
  "start_time": "2026-05-19T12:00:00Z",
  "end_time": "2026-05-19T12:05:00Z",
  "status": "success",
  "summary": {
    "registered": 2,
    "processed": 1,
    "skipped": 1,
    "failed": 0
  },
  "files": [
    {
      "relative_path": "large-file.bin",
      "status": "skipped_existing_consistent",
      "error": null,
      "duration_seconds": 0.52,
      "metadata": {
        "parts_verified": 3,
        "part_files_preserved": true
      }
    }
  ]
}
```

Dry-run executions should not be persisted by default.

---

# 19. Status Values

Recommended file-level status values:

For `disband`:

- `success`
- `skipped_below_threshold`
- `skipped_already_split`
- `failed_conflict`
- `failed_io`
- `failed_integrity`
- `failed_register`

For `squad-up`:

- `success_reassembled`
- `skipped_existing_consistent`
- `failed_missing_part`
- `failed_part_integrity`
- `failed_original_backup`
- `failed_reassembly`
- `failed_integrity`
- `failed_register`

Recommended run-level status values:

- `success`
- `partial_success`
- `failed`
- `interrupted`

---

# 20. Documentation and Docstrings

The implementation must include a module-level docstring explaining:

- purpose of `split4git.py`
- why large files may need splitting for Git workflows
- expected input
- generated output
- register purpose
- examples for `disband`
- examples for `squad-up`
- dry-run usage
- safety assumptions
- limitations

Example commands to include:

```bash
python split4git.py disband . --threshold-mib 45 --dry-run
python split4git.py disband . --threshold-mib 45
python split4git.py squad-up . --dry-run
python split4git.py squad-up .
```

Core public functions should include docstrings describing:

- role in the architecture
- parameters
- return values
- whether they perform filesystem writes
- whether they raise exceptions or return structured errors

---

# 21. README Section Requirements

A README section for `split4git.py` should include:

- short description
- warning to review generated output before committing
- explanation of `disband`
- explanation of `squad-up`
- default threshold
- generated files
- part naming pattern
- register file purpose
- `.gitignore` guidance
- dry-run examples
- recovery notes
- exit codes

Suggested README section:

````markdown
## split4git.py

`split4git.py` splits files larger than a configurable threshold into ordered binary parts so the parts can be committed safely, then reassembles them later using a JSON register.

Default threshold: `45 MiB`.

Typical usage:

```bash
python split4git.py disband . --threshold-mib 45 --dry-run
python split4git.py disband . --threshold-mib 45
python split4git.py squad-up . --dry-run
python split4git.py squad-up .
```

Generated files:

```text
.split4git.register.json
.split4git.log
```

After `disband`, copy the generated `split4git` section into your repository root `.gitignore` to avoid committing the original large files.

The part files are preserved during `squad-up`; they are verified and left unchanged.
````

---

# 22. Security Considerations

The programme must guard against unsafe paths, especially when reading from the register.

During `squad-up`, every registered path must be validated:

- must be relative
- must not contain `..`
- must not escape the working directory
- must not point through unsafe symlinks by default
- must not overwrite unrelated files

The programme should not follow symlinks by default.

If a registered path points to or through a symlink, the programme should fail safely unless a future explicit option allows that behaviour.

---

# 23. Performance Considerations

The programme must support large files efficiently.

Requirements:

- Use streaming I/O.
- Use a fixed-size buffer.
- Avoid loading full files into memory.
- Sort files deterministically.
- Hash while streaming where practical.

Recommended buffer size:

```text
1 MiB to 8 MiB
```

For `disband`, the original SHA-256 may be computed:

- during splitting, or
- in a separate pre-splitting pass

For `squad-up`, part hashes may be verified:

- before reassembly, or
- during a preflight verification pass

The final reassembled original must always be verified against the registered original size and SHA-256.

---

# 24. Compatibility Requirements

The programme should target:

```text
Python 3.13+
```

It should use only the Python standard library for the initial implementation.

Recommended modules:

- `argparse`
- `datetime`
- `hashlib`
- `json`
- `logging`
- `os`
- `pathlib`
- `shutil`
- `stat`
- `sys`
- `tempfile`
- `time`

---

# 25. Acceptance Criteria

The implementation is acceptable if all of the following are true:

1. `disband` recursively scans the working directory.
2. `disband` detects files strictly larger than the threshold.
3. `disband` ignores `.git`, programme metadata files, temporary files, and existing part files.
4. `disband` creates ordered part files named after the original filename.
5. Each part file is no larger than the configured part size.
6. The concatenation of part files exactly equals the original bytes.
7. The register records original path, original size, original SHA-256, part paths, part sizes, part indexes, and part SHA-256 values.
8. The register is sufficient to reassemble the original without guessing.
9. The register is written atomically.
10. The generated `.gitignore` section is displayed after `disband`.
11. The generated `.gitignore` section is saved in the register.
12. `squad-up` refuses to operate without a valid register.
13. `squad-up` validates all part files before reassembling.
14. `squad-up` preserves all valid part files unchanged.
15. `squad-up` leaves an existing consistent original unchanged.
16. `squad-up` renames an existing inconsistent original before reassembling.
17. `squad-up` writes reassembled output through a temporary file first.
18. `squad-up` verifies reassembled size and SHA-256 before finalising.
19. `--dry-run` performs no writes, deletes, or renames.
20. Large files are processed in streaming mode.
21. The programme fails safely on conflicts.
22. The programme exits non-zero if any file fails.
23. Paths from the register cannot escape the working directory.
24. The implementation includes clear module and function docstrings.
25. Part files remain available after successful reassembly.