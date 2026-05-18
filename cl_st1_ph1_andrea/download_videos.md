# `download_videos.py` — Programme Specification for Development

## 1. High-level Functionality Specification

### Programme Summary

`download_videos.py` is a batch-processing programme that downloads source YouTube videos for a television commercials corpus.

The programme reads the metadata file:

```text
corpus/00_sources/tv_commercials.ndjson
```

Each record in this NDJSON file contains metadata for one commercial. Because multiple commercials may come from the same YouTube source video, the programme must identify unique videos using the `Video ID` column and download each unique video only once.

For each unique video, the programme uses:

- the `Video ID` field to determine the output filename;
- the `URL` field as the YouTube source URL.

The base download command is:

```bash
yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" "https://youtu.be/G-zZFNf4PqQ" -o "video_0001.mp4"
```

The programme must generalise this command so that each video is downloaded as:

```bash
yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" "<URL>" -o "<output_dir>/<Video ID>.mp4"
```

For example:

```bash
yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" "https://youtu.be/G-zZFNf4PqQ" -o "corpus/01_videos/video_0001.mp4"
```

---

## 2. Key Behaviours

The programme must implement the following behaviours:

- Read video metadata from an NDJSON file.
- Extract the required fields:
  - `Video ID`
  - `URL`
- Download each unique `Video ID` only once.
- Save each video as an `.mp4` file named after its `Video ID`.
- Use `yt-dlp` as the external download engine.
- Use test mode by default, limiting processing to 5 unique videos.
- Skip already-downloaded videos by default, supporting safe re-runs.
- Allow reprocessing with an explicit command-line option.
- Continue processing remaining videos if one URL fails.
- Record progress and errors in an append-only log file.
- Produce a JSON manifest with run-level metadata and item-level results.
- Write both:
  - a timestamped per-run manifest;
  - a latest manifest that is overwritten on each run.
- Exit with status code `0` only when all attempted downloads succeed or are skipped.
- Exit with a non-zero status code if one or more attempted downloads fail, or if there is a configuration/validation error.

---

## 3. Input / Output Specification

## 3.1 Input

### Input metadata file

Default path:

```text
corpus/00_sources/tv_commercials.ndjson
```

The file is expected to be in **NDJSON** format, meaning one JSON object per line.

### Required fields

Each valid record must contain:

| Field | Type | Description |
|---|---:|---|
| `Video ID` | string | Unique identifier for a source video, e.g. `video_0001` |
| `URL` | string | YouTube URL to download |

Example record:

```json
{"Decade":"1950","Sequence":1,"Title":"Norwich Liquid Peptans","Category":"Health, Beauty & Personal Care","Commercial ID":"tv_com_1950_1","Video ID":"video_0001","URL":"https://youtu.be/G-zZFNf4PqQ","Start":"0:00:00","End":"0:00:59"}
```

### Discovery rules

The programme must:

1. Read all records from the NDJSON file.
2. Validate that each record has non-empty `Video ID` and `URL` values.
3. Build a list of unique videos based on `Video ID`.
4. If the same `Video ID` appears more than once:
   - keep the first occurrence;
   - ignore subsequent duplicates for download planning.
5. Sort or preserve the input order deterministically.  
   Preferred behaviour: preserve first-seen order from the NDJSON file.

### Invalid metadata rows

If a row is missing `Video ID` or `URL`:

- it must not be downloaded;
- it should be marked as `failed_metadata` or equivalent in the manifest;
- the error should be logged;
- processing should continue for other records.

---

## 3.2 Output

### Video output directory

Default path:

```text
corpus/01_videos/
```

The programme must create this directory if it does not already exist.

### Per-video output

Each downloaded video must be saved as:

```text
<output_dir>/<Video ID>.mp4
```

Examples:

```text
corpus/01_videos/video_0001.mp4
corpus/01_videos/video_0002.mp4
corpus/01_videos/video_0003.mp4
```

### Log file

Default path:

```text
corpus/01_videos/download_videos.log
```

The log file must be:

- plain text;
- UTF-8 encoded;
- append-only;
- line-oriented.

### Manifest files

The programme must write two manifest files:

#### Latest manifest

Default path:

```text
corpus/01_videos/download_videos_manifest.json
```

This file is overwritten at the end of each run.

#### Per-run manifest

A timestamped copy must also be written using the run ID.

Filename pattern:

```text
download_videos_manifest_<run_id>.json
```

Example:

```text
corpus/01_videos/download_videos_manifest_20260518T143012Z.json
```

---

## 4. Command-line Interface

## 4.1 Default usage

```bash
python download_videos.py
```

Default behaviour:

- metadata path: `corpus/00_sources/tv_commercials.ndjson`
- output directory: `corpus/01_videos/`
- test mode: enabled
- test limit: 5 videos
- reprocess: disabled
- existing `.mp4` files are skipped
- one worker / sequential processing

---

## 4.2 Required arguments

There are no required command-line arguments if all default paths are used.

However, all important paths must be configurable.

---

## 4.3 Optional arguments

### Metadata path

```bash
--metadata PATH
```

Default:

```text
corpus/00_sources/tv_commercials.ndjson
```

Description:

Path to the NDJSON metadata file.

---

### Output directory

```bash
--output-dir PATH
```

Default:

```text
corpus/01_videos/
```

Description:

Directory where downloaded `.mp4` files will be saved.

---

### Test mode

```bash
--test-mode
--no-test-mode
```

Default:

```text
--test-mode
```

Description:

When test mode is enabled, the programme processes only a limited number of planned videos.

---

### Test limit

```bash
--test-limit N
```

Default:

```text
5
```

Description:

Maximum number of videos to attempt when test mode is enabled.

Must be a positive integer.

Example:

```bash
python download_videos.py --test-limit 10
```

---

### Reprocess existing videos

```bash
--reprocess
```

Default:

```text
False
```

Description:

When omitted, the programme skips any video whose output `.mp4` file already exists.

When provided, the programme downloads the video again and overwrites the existing output file.

Example:

```bash
python download_videos.py --reprocess
```

---

### Log file

```bash
--log-file PATH
```

Default:

```text
corpus/01_videos/download_videos.log
```

Description:

Path to the append-only log file.

---

### Manifest file

```bash
--manifest-file PATH
```

Default:

```text
corpus/01_videos/download_videos_manifest.json
```

Description:

Path to the latest manifest file. The per-run timestamped manifest should be written next to this file.

---

### Workers

```bash
--workers N
```

Default:

```text
1
```

Description:

Number of worker processes.

For initial implementation, sequential execution with `--workers 1` is sufficient and preferred for simplicity. The architecture should still allow parallel execution later.

Must be a positive integer.

---

### Timeout

```bash
--timeout SECONDS
```

Default suggestion:

```text
3600
```

Description:

Maximum allowed time for a single `yt-dlp` download process.

If the timeout is reached:

- terminate the process;
- mark the item as failed;
- log the timeout;
- continue with the next video.

---

### Maximum retries

```bash
--max-retries N
```

Default suggestion:

```text
1
```

Description:

Number of retry attempts after a failed download.

For example, with `--max-retries 1`, each failed item may be attempted twice in total:

1. initial attempt;
2. one retry.

Must be zero or a positive integer.

---

## 4.4 Example commands

### Small default test run

```bash
python download_videos.py
```

### Test run with 10 videos

```bash
python download_videos.py --test-limit 10
```

### Full production run

```bash
python download_videos.py --no-test-mode
```

### Full production run with explicit paths

```bash
python download_videos.py \
  --metadata corpus/00_sources/tv_commercials.ndjson \
  --output-dir corpus/01_videos \
  --no-test-mode
```

### Re-download videos even if files already exist

```bash
python download_videos.py --no-test-mode --reprocess
```

---

## 5. Argument Validation

The programme must fail fast with a clear message if:

- the metadata file does not exist;
- the metadata file is unreadable;
- the metadata file contains invalid JSON lines;
- the output directory cannot be created;
- `--test-limit` is less than or equal to zero;
- `--workers` is less than or equal to zero;
- `--timeout` is less than or equal to zero;
- `--max-retries` is negative;
- `yt-dlp` is not available on the system path.

The programme should check for `yt-dlp` availability before processing begins.

A validation error should:

- be printed clearly to the console;
- be written to the log if logging has already been configured;
- cause the programme to exit with a non-zero status code.

---

## 6. Environment and Configuration

This programme does not require API keys or secret environment variables.

The programme depends on the external command-line tool:

```text
yt-dlp
```

The implementation must verify that `yt-dlp` is available before starting downloads.

Suggested check:

```bash
yt-dlp --version
```

The programme must not log sensitive system information.

No credentials, cookies, or authentication files are required in the initial specification.

Future extensions may optionally support cookies or browser authentication, but this should not be part of the first implementation unless explicitly added later.

---

## 7. Core Processing Architecture

## 7.1 High-level flow

The programme must follow this workflow:

1. **Startup**
   - Parse command-line arguments.
   - Validate arguments.
   - Generate a UTC `run_id`.
   - Ensure the output directory exists.
   - Set up logging.
   - Check that `yt-dlp` is available.

2. **Metadata loading**
   - Open the NDJSON metadata file.
   - Read records line by line.
   - Parse each JSON object.
   - Validate required fields.
   - Extract `Video ID` and `URL`.

3. **Discovery**
   - Identify unique videos by `Video ID`.
   - Preserve first-seen order.
   - Record duplicates as metadata in the manifest if useful.

4. **Planning**
   - For each unique video:
     - compute output path as `<output_dir>/<Video ID>.mp4`;
     - decide whether to skip or download.
   - If the file exists and `--reprocess` is not enabled:
     - mark the item as `skipped_existing`.
   - If the file does not exist or `--reprocess` is enabled:
     - plan the item for download.
   - If test mode is enabled:
     - limit the planned list to `--test-limit`.

5. **Execution**
   - For each planned item:
     - run `yt-dlp`;
     - capture stdout, stderr, return code, timing, and any exception;
     - retry according to `--max-retries`;
     - mark the item as `success` or `failed`.

6. **End-of-run summary**
   - Count:
     - total metadata records;
     - total unique videos;
     - skipped existing files;
     - attempted downloads;
     - successful downloads;
     - failed downloads;
     - invalid metadata rows, if any.
   - Write the latest manifest.
   - Write the per-run manifest.
   - Log the final summary.
   - Exit with an appropriate status code.

7. **Interrupt handling**
   - Catch `KeyboardInterrupt`.
   - Stop cleanly.
   - Write a partial manifest.
   - Log the interruption.
   - Exit non-zero.

---

## 7.2 Separation of concerns

The implementation should be organised around the following responsibilities.

### CLI parsing

Responsible for:

- defining command-line arguments;
- applying defaults;
- returning a configuration object or namespace.

Suggested function:

```python
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the video download programme."""
```

---

### Validation

Responsible for:

- checking file paths;
- checking numeric arguments;
- checking `yt-dlp` availability.

Suggested function:

```python
def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments and external dependencies before processing."""
```

---

### Metadata loading

Responsible for:

- reading NDJSON;
- parsing records;
- extracting `Video ID` and `URL`;
- detecting invalid rows;
- deduplicating by `Video ID`.

Suggested function:

```python
def load_video_metadata(metadata_path: Path) -> tuple[list[dict], list[dict]]:
    """Load and validate video metadata from an NDJSON file."""
```

Expected return:

- list of valid unique video items;
- list of invalid metadata records or validation errors.

Each valid item should contain at least:

```json
{
  "video_id": "video_0001",
  "url": "https://youtu.be/G-zZFNf4PqQ"
}
```

---

### Planning

Responsible for:

- creating output paths;
- deciding whether items are skipped or attempted;
- applying test-mode limit.

Suggested function:

```python
def plan_downloads(
    videos: list[dict],
    output_dir: Path,
    test_mode: bool,
    test_limit: int,
    reprocess: bool
) -> tuple[list[dict], list[dict]]:
    """Create skipped and planned download records."""
```

---

### Core download function

Responsible for downloading a single video.

It should:

- build the `yt-dlp` command;
- run the command using `subprocess`;
- capture return code, stdout, stderr;
- detect failure;
- return a structured result;
- not terminate the whole programme on failure.

Suggested function:

```python
def download_one_video(
    video_id: str,
    url: str,
    output_path: Path,
    timeout: int,
    max_retries: int
) -> dict:
    """Download one video with yt-dlp and return a structured result."""
```

The command must be equivalent to:

```bash
yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" "<URL>" -o "<output_path>"
```

The function should use argument lists rather than shell strings for safer execution.

Equivalent Python command structure:

```python
[
    "yt-dlp",
    "-f",
    "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
    url,
    "-o",
    str(output_path),
]
```

---

### Manifest writing

Responsible for writing:

- latest manifest;
- timestamped per-run manifest.

Suggested function:

```python
def write_manifests(
    manifest: dict,
    manifest_file: Path,
    run_id: str
) -> tuple[Path, Path]:
    """Write latest and per-run manifest files."""
```

---

### Main orchestration

Responsible for:

- coordinating all steps;
- logging;
- error handling;
- exit code.

Suggested function:

```python
def main() -> int:
    """Run the batch video download workflow and return an exit code."""
```

---

## 8. Download Behaviour

## 8.1 Base command

For each video, the programme must run:

```bash
yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" "<URL>" -o "<output_path>"
```

Example:

```bash
yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" "https://youtu.be/G-zZFNf4PqQ" -o "corpus/01_videos/video_0001.mp4"
```

---

## 8.2 Output filename

The output filename must be derived from the `Video ID`.

Given:

```text
Video ID = video_0001
```

The output file must be:

```text
video_0001.mp4
```

The full default output path must be:

```text
corpus/01_videos/video_0001.mp4
```

---

## 8.3 Existing files

If the output file already exists and `--reprocess` is not enabled:

- do not call `yt-dlp`;
- mark the item as `skipped_existing`;
- log the skip;
- include the item in the manifest.

If `--reprocess` is enabled:

- call `yt-dlp`;
- allow the output to be overwritten.

---

## 8.4 Invalid or unavailable URLs

If a video URL is no longer valid, private, deleted, unavailable, region-blocked, malformed, or otherwise not downloadable, `yt-dlp` is expected to return a non-zero exit code.

The programme must:

- capture the failure;
- mark the video as `failed`;
- save a short error summary in the manifest;
- log the failure;
- continue with the next video.

The programme must not stop the entire batch because one video fails.

---

## 8.5 Retries

For failures that may be transient, the programme should retry up to `--max-retries`.

Retry behaviour:

- retry only failed `yt-dlp` commands;
- log each retry attempt;
- record the number of retries used in the manifest;
- if all attempts fail, mark the item as `failed`.

A simple fixed delay between retries is acceptable for the initial implementation.

Suggested retry delay:

```text
5 seconds
```

Future extension may add exponential backoff.

---

## 9. JSON Manifest Design

## 9.1 Manifest structure

The manifest must use this general structure:

```json
{
  "run_metadata": {
    "run_id": "20260518T143012Z",
    "tool_name": "download_videos.py",
    "tool_version": "v1",
    "start_time": "2026-05-18T14:30:12Z",
    "end_time": "2026-05-18T14:35:42Z",
    "test_mode": true,
    "test_limit": 5,
    "reprocess": false,
    "workers": 1,
    "metadata_path": "corpus/00_sources/tv_commercials.ndjson",
    "output_dir": "corpus/01_videos",
    "log_file": "corpus/01_videos/download_videos.log",
    "manifest_file": "corpus/01_videos/download_videos_manifest.json",
    "config": {
      "yt_dlp_format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
      "timeout_seconds": 3600,
      "max_retries": 1
    },
    "summary": {
      "metadata_records": 960,
      "unique_videos": 739,
      "planned": 5,
      "attempted": 5,
      "succeeded": 5,
      "failed": 0,
      "skipped_existing": 0,
      "invalid_metadata": 0
    }
  },
  "videos": [
    {
      "video_id": "video_0001",
      "url": "https://youtu.be/G-zZFNf4PqQ",
      "output_path": "corpus/01_videos/video_0001.mp4",
      "status": "success",
      "error": null,
      "return_code": 0,
      "retries": 0,
      "duration_seconds": 42.8,
      "start_time": "2026-05-18T14:30:15Z",
      "end_time": "2026-05-18T14:30:58Z",
      "metadata": {
        "command": [
          "yt-dlp",
          "-f",
          "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
          "https://youtu.be/G-zZFNf4PqQ",
          "-o",
          "corpus/01_videos/video_0001.mp4"
        ]
      }
    }
  ],
  "invalid_records": []
}
```

---

## 9.2 Required item statuses

The following statuses must be supported:

| Status | Meaning |
|---|---|
| `success` | Video was downloaded successfully |
| `failed` | Download was attempted but failed |
| `skipped_existing` | Output file already existed and `--reprocess` was not enabled |
| `failed_metadata` | Metadata record was invalid and could not be planned |

---

## 9.3 Error field

The `error` field must be:

- `null` when there is no error;
- a short string when an error occurs.

For `yt-dlp` failures, the error should usually be derived from `stderr`.

Example:

```json
{
  "video_id": "video_0001",
  "url": "https://youtu.be/G-zZFNf4PqQ",
  "output_path": "corpus/01_videos/video_0001.mp4",
  "status": "failed",
  "error": "ERROR: [youtube] G-zZFNf4PqQ: Video unavailable",
  "return_code": 1,
  "retries": 1
}
```

---

## 10. Logging Specification

The programme must write an append-only log file.

Default:

```text
corpus/01_videos/download_videos.log
```

### Log format

Each line should follow this format:

```text
[YYYY-MM-DD HH:MM:SS] LEVEL  message
```

Example:

```text
[2026-05-18 14:30:12] INFO  Starting download_videos.py run_id=20260518T143012Z
```

### Required log events

The programme must log:

- startup;
- parsed configuration summary;
- metadata file path;
- output directory;
- test mode status;
- test limit;
- reprocess setting;
- `yt-dlp` availability and version if available;
- number of metadata records read;
- number of unique videos found;
- number of invalid metadata records;
- number of planned downloads;
- each skipped existing video;
- each successful download;
- each failed download;
- each retry attempt;
- manifest write paths;
- end-of-run summary;
- keyboard interrupts;
- validation/configuration errors.

### Example log lines

```text
[2026-05-18 14:30:12] INFO  Starting download_videos.py run_id=20260518T143012Z
[2026-05-18 14:30:12] INFO  Metadata path: corpus/00_sources/tv_commercials.ndjson
[2026-05-18 14:30:12] INFO  Output directory: corpus/01_videos
[2026-05-18 14:30:12] INFO  Test mode: true; test_limit=5
[2026-05-18 14:30:13] INFO  Found 960 metadata records and 739 unique videos
[2026-05-18 14:30:15] INFO  SUCCESS video_0001 https://youtu.be/G-zZFNf4PqQ -> corpus/01_videos/video_0001.mp4
[2026-05-18 14:31:02] ERROR FAILED video_0002 https://youtu.be/example error='Video unavailable'
[2026-05-18 14:35:42] INFO  Wrote latest manifest: corpus/01_videos/download_videos_manifest.json
[2026-05-18 14:35:42] INFO  Finished run: succeeded=4 failed=1 skipped_existing=0
```

---

## 11. Error Handling and Resiliency

## 11.1 Configuration errors

Configuration errors must stop the programme before downloads begin.

Examples:

- metadata file missing;
- output directory cannot be created;
- invalid command-line arguments;
- `yt-dlp` is not installed or not found.

The programme must exit non-zero.

---

## 11.2 Per-video errors

Per-video errors must not stop the full run.

Examples:

- video unavailable;
- video private;
- video deleted;
- region restriction;
- malformed URL;
- network error;
- timeout;
- `yt-dlp` non-zero return code.

For each per-video error:

- mark the item as `failed`;
- capture a short error message;
- log the error;
- continue to the next item.

---

## 11.3 Keyboard interruption

If the user interrupts the programme with `Ctrl+C`, the programme must:

- stop processing;
- mark the run as interrupted in the manifest;
- write a partial manifest with completed results so far;
- log the interruption;
- exit non-zero.

The manifest should include:

```json
"interrupted": true
```

inside `run_metadata`.

---

## 11.4 Exit codes

The programme must use the following exit-code conventions:

| Exit code | Meaning |
|---:|---|
| `0` | Completed with no failed attempted downloads |
| `1` | Completed, but one or more downloads failed |
| `2` | Configuration or validation error |
| `130` | Interrupted by user |

Skipped existing files are not failures.

Invalid metadata records should result in a non-zero exit unless the implementation explicitly treats them as warnings. Preferred behaviour: invalid metadata records count as failures and cause exit code `1`.

---

## 12. Docstrings and In-code Documentation

The implementation must include clear docstrings.

## 12.1 Module-level docstring

At the top of `download_videos.py`, include a module-level docstring explaining:

- purpose of the programme;
- expected input metadata file;
- output video directory;
- use of `yt-dlp`;
- default test mode;
- resumability behaviour;
- example commands.

Suggested module docstring:

```python
"""
Download source YouTube videos for the television commercials corpus.

This script reads video metadata from an NDJSON file, extracts unique videos
using the "Video ID" and "URL" fields, and downloads each source video with
yt-dlp. Downloaded files are saved as "<Video ID>.mp4" in the output directory.

By default, the script runs in test mode and attempts only the first 5 planned
videos. Existing output files are skipped unless --reprocess is provided,
making the script safe to re-run.

Example:
    python download_videos.py

Full run:
    python download_videos.py --no-test-mode

The script writes an append-only log file and JSON manifests describing
run-level metadata and per-video status.
"""
```

---

## 12.2 Function docstrings

All major functions must include docstrings describing:

- purpose;
- parameters;
- return values;
- whether the function performs I/O;
- error behaviour.

At minimum, docstrings are required for:

- `parse_args`
- `validate_args`
- `setup_logging`
- `load_video_metadata`
- `plan_downloads`
- `download_one_video`
- `write_manifests`
- `main`

---

## 13. Suggested Constants

The implementation should define constants near the top of the file:

```python
TOOL_NAME = "download_videos.py"
TOOL_VERSION = "v1"

DEFAULT_METADATA_PATH = "corpus/00_sources/tv_commercials.ndjson"
DEFAULT_OUTPUT_DIR = "corpus/01_videos"
DEFAULT_LOG_FILE = "corpus/01_videos/download_videos.log"
DEFAULT_MANIFEST_FILE = "corpus/01_videos/download_videos_manifest.json"

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 5
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_MAX_RETRIES = 1

YT_DLP_FORMAT = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"
```

---

## 14. Development Notes

### Initial implementation scope

The first implementation should prioritise:

- correct sequential execution;
- reliable logging;
- robust manifest output;
- safe resumability;
- clear error handling.

Parallel downloads can be prepared architecturally but do not need to be implemented in the first version.

### Recommended implementation approach

Use only the Python standard library for this programme where possible:

- `argparse`
- `json`
- `logging`
- `subprocess`
- `pathlib`
- `datetime`
- `time`
- `shutil`
- `sys`
- `traceback`, if needed for debugging summaries

No additional Python package is required for the first implementation.

---

## 15. Acceptance Criteria

The programme is considered complete when the following conditions are met:

1. Running:

   ```bash
   python download_videos.py
   ```

   performs a test run of up to 5 videos.

2. The programme reads:

   ```text
   corpus/00_sources/tv_commercials.ndjson
   ```

3. The programme creates the output directory if needed:

   ```text
   corpus/01_videos/
   ```

4. Each downloaded video is saved as:

   ```text
   corpus/01_videos/<Video ID>.mp4
   ```

5. Existing `.mp4` files are skipped unless `--reprocess` is used.

6. Duplicate `Video ID` values are downloaded only once.

7. Failed downloads do not stop the full batch.

8. Invalid or unavailable YouTube URLs are marked as `failed`.

9. A log file is written at:

   ```text
   corpus/01_videos/download_videos.log
   ```

10. A latest manifest is written at:

   ```text
   corpus/01_videos/download_videos_manifest.json
   ```

11. A timestamped per-run manifest is also written.

12. The manifest records:
   - run metadata;
   - configuration;
   - per-video status;
   - errors;
   - timings;
   - summary counts.

13. The programme exits with:
   - `0` if all attempted downloads succeed or are skipped;
   - non-zero if any attempted download fails;
   - non-zero for configuration errors;
   - `130` for keyboard interruption.

---

## 16. Short README Section

The following section can be added to project documentation.

## Download source videos

The `download_videos.py` programme downloads the source YouTube videos listed in
`corpus/00_sources/tv_commercials.ndjson`.

Each unique video is identified by the `Video ID` field and downloaded from the
corresponding `URL`. Videos are saved as `.mp4` files named after their video ID.

Default test run:

```bash
python download_videos.py
```

This processes up to 5 videos.

Full run:

```bash
python download_videos.py --no-test-mode
```

Outputs are written to:

```text
corpus/01_videos/
```

The programme is safe to re-run: existing videos are skipped by default. To
force re-downloading, use:

```bash
python download_videos.py --no-test-mode --reprocess
```

The programme writes:

```text
corpus/01_videos/download_videos.log
corpus/01_videos/download_videos_manifest.json
```

A timestamped per-run manifest is also created for each execution.