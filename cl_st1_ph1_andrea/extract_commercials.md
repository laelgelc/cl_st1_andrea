# `extract_commercials.py` — Programme Specification for Development

## 1. High-level Functionality Specification

### Programme Summary

`extract_commercials.py` is a batch-processing programme that clips individual television commercials from previously downloaded source video files.

The programme reads the metadata file:

```text
corpus/00_sources/tv_commercials.ndjson
```

Each record in this metadata file represents one commercial. The programme must process only rows where:

```text
Download Success = True
```

For each eligible row, the programme uses:

- `Video ID` to locate the downloaded source video;
- `Commercial ID` to name the extracted commercial clip;
- `Start` as the clip start timestamp;
- `End` as the clip end timestamp.

The source videos are stored in:

```text
corpus/01_videos/
```

The extracted commercial clips must be written to:

```text
corpus/02_commercials/
```

The base clipping command is:

```bash
ffmpeg -y -ss 0:00:00 -to 0:00:59 -i "video_0001.mp4" -c:v libx264 -c:a aac -avoid_negative_ts make_zero "tv_com_1950_1.mp4"
```

The programme must generalise this command so that each eligible commercial is clipped as:

```bash
ffmpeg -y -ss "<Start>" -to "<End>" -i "<input_dir>/<Video ID>.mp4" -c:v libx264 -c:a aac -avoid_negative_ts make_zero "<output_dir>/<Commercial ID>.mp4"
```

For example:

```bash
ffmpeg -y -ss "0:00:00" -to "0:00:59" -i "corpus/01_videos/video_0001.mp4" -c:v libx264 -c:a aac -avoid_negative_ts make_zero "corpus/02_commercials/tv_com_1950_1.mp4"
```

---

## 2. Key Behaviours

The programme must implement the following behaviours:

- Read commercial metadata from an NDJSON file.
- Process only records where `Download Success` is `True`.
- Extract the required fields:
  - `Commercial ID`
  - `Video ID`
  - `Start`
  - `End`
  - `Download Success`
- Build one `ffmpeg` clipping command per eligible commercial.
- Locate source videos as:

  ```text
  corpus/01_videos/<Video ID>.mp4
  ```

- Save commercial clips as:

  ```text
  corpus/02_commercials/<Commercial ID>.mp4
  ```

- Create the output directory if it does not already exist.
- Use `ffmpeg` as the external clipping engine.
- Use test mode by default, limiting processing to 5 eligible commercials.
- Skip already-extracted commercial clips by default, supporting safe re-runs.
- Allow reprocessing with an explicit command-line option.
- Continue processing remaining commercials if one clip fails.
- Record progress and errors in an append-only log file.
- Produce a JSON manifest with run-level metadata and item-level results.
- Write both:
  - a timestamped per-run manifest;
  - a latest manifest that is overwritten on each run.
- Exit with status code `0` only when all attempted clips succeed or are skipped.
- Exit with a non-zero status code if one or more attempted clips fail, or if there is a configuration/validation error.

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
| `Commercial ID` | string | Unique identifier for the commercial clip, e.g. `tv_com_1950_1` |
| `Video ID` | string | Identifier for the downloaded source video, e.g. `video_0001` |
| `Start` | string | Start timestamp for the commercial within the source video |
| `End` | string | End timestamp for the commercial within the source video |
| `Download Success` | boolean/string | Indicates whether the source video was successfully downloaded |

Example record:

```json
{"Decade":"1950","Sequence":1,"Title":"Norwich Liquid Peptans","Category":"Health, Beauty & Personal Care","Commercial ID":"tv_com_1950_1","Video ID":"video_0001","URL":"https://youtu.be/G-zZFNf4PqQ","Start":"0:00:00","End":"0:00:59","Download Success":true,"Reason":"Success"}
```

### Eligibility rules

The programme must:

1. Read all records from the NDJSON file.
2. Select only records where `Download Success` is `True`.
3. Ignore records where `Download Success` is `False`, missing, blank, or otherwise not truthy.
4. Validate that each selected record has non-empty:
   - `Commercial ID`
   - `Video ID`
   - `Start`
   - `End`
5. Build one planned clip per valid selected record.
6. Preserve metadata order from the NDJSON file.

### Handling `Download Success`

The value should be interpreted robustly.

The following values should be treated as true:

```text
True
true
"True"
"true"
"TRUE"
1
"1"
```

The following values should not be eligible:

```text
False
false
"False"
"false"
"FALSE"
0
"0"
null
""
missing value
```

### Invalid metadata rows

If a row has `Download Success = True` but is missing any required clipping field:

- it must not be clipped;
- it should be marked as `failed_metadata` in the manifest;
- the error should be logged;
- processing should continue for other records.

Rows where `Download Success` is not `True` are not errors. They are expected to be ignored because their source videos were not successfully downloaded.

---

## 3.2 Output

### Commercial output directory

Default path:

```text
corpus/02_commercials/
```

The programme must create this directory if it does not already exist.

### Per-commercial output

Each extracted commercial must be saved as:

```text
<output_dir>/<Commercial ID>.mp4
```

Examples:

```text
corpus/02_commercials/tv_com_1950_1.mp4
corpus/02_commercials/tv_com_1950_2.mp4
corpus/02_commercials/tv_com_1960_1.mp4
```

### Source video input directory

Default path:

```text
corpus/01_videos/
```

Each source video is expected to exist as:

```text
<input_dir>/<Video ID>.mp4
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
corpus/02_commercials/extract_commercials.log
```

The log file must be:

- plain text;
- UTF-8 encoded;
- append-only;
- line-oriented.

### Manifest files

The programme must write two manifest files.

#### Latest manifest

Default path:

```text
corpus/02_commercials/extract_commercials_manifest.json
```

This file is overwritten at the end of each run.

#### Per-run manifest

A timestamped copy must also be written using the run ID.

Filename pattern:

```text
extract_commercials_manifest_<run_id>.json
```

Example:

```text
corpus/02_commercials/extract_commercials_manifest_20260519T143012Z.json
```

---

# 4. Command-line Interface

## 4.1 Default usage

```bash
python extract_commercials.py
```

Default behaviour:

- metadata path: `corpus/00_sources/tv_commercials.ndjson`
- input directory: `corpus/01_videos/`
- output directory: `corpus/02_commercials/`
- test mode: enabled
- test limit: 5 commercials
- reprocess: disabled
- existing commercial `.mp4` files are skipped
- one worker / sequential processing

---

## 4.2 Required arguments

There are no required command-line arguments if all default paths are used.

However, all important paths and processing controls must be configurable.

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

### Input directory

```bash
--input-dir PATH
```

Default:

```text
corpus/01_videos/
```

Description:

Directory where downloaded source videos are stored.

The programme expects source videos to be named:

```text
<Video ID>.mp4
```

---

### Output directory

```bash
--output-dir PATH
```

Default:

```text
corpus/02_commercials/
```

Description:

Directory where extracted commercial `.mp4` clips will be saved.

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

When test mode is enabled, the programme processes only a limited number of planned commercials.

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

Maximum number of commercials to attempt when test mode is enabled.

Must be a positive integer.

Example:

```bash
python extract_commercials.py --test-limit 10
```

---

### Reprocess existing clips

```bash
--reprocess
```

Default:

```text
False
```

Description:

When omitted, the programme skips any commercial whose output `.mp4` file already exists.

When provided, the programme clips the commercial again and overwrites the existing output file.

Example:

```bash
python extract_commercials.py --reprocess
```

---

### Start commercial ID

```bash
--start-commercial-id COMMERCIAL_ID
```

Default:

```text
None
```

Description:

Optional `Commercial ID` from which to start planning commercial extraction.

When this option is provided, the programme must preserve metadata order but ignore all eligible commercials that occur before the specified `Commercial ID`. The specified commercial itself must be included in the planning step.

This is useful for resuming a long extraction run from a known point without relying only on existing-file detection.

Example:

```bash
python extract_commercials.py --start-commercial-id tv_com_1950_25
```

If the requested `Commercial ID` is not found among eligible metadata rows, the programme must fail fast with a configuration error.

---

### Log file

```bash
--log-file PATH
```

Default:

```text
corpus/02_commercials/extract_commercials.log
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
corpus/02_commercials/extract_commercials_manifest.json
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

For the current implementation, sequential execution with `--workers 1` is required. The architecture may allow parallel execution later.

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

Maximum allowed time for a single `ffmpeg` clipping process.

If the timeout is reached:

- terminate the process;
- mark the item as failed;
- log the timeout;
- continue with the next commercial.

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

Number of retry attempts after a failed clipping command.

For example, with `--max-retries 1`, each failed item may be attempted twice in total:

1. initial attempt;
2. one retry.

Must be zero or a positive integer.

---

## 4.4 Example commands

### Small default test run

```bash
python extract_commercials.py
```

### Test run with 10 commercials

```bash
python extract_commercials.py --test-limit 10
```

### Test run from a specific commercial ID

```bash
python extract_commercials.py \
  --test-limit 3 \
  --start-commercial-id tv_com_1950_25
```

### Full production run

```bash
python extract_commercials.py --no-test-mode
```

### Full production run from a specific commercial ID

```bash
python extract_commercials.py \
  --no-test-mode \
  --start-commercial-id tv_com_1950_25
```

### Full production run with explicit paths

```bash
python extract_commercials.py \
  --metadata corpus/00_sources/tv_commercials.ndjson \
  --input-dir corpus/01_videos \
  --output-dir corpus/02_commercials \
  --no-test-mode
```

### Re-extract commercials even if files already exist

```bash
python extract_commercials.py --no-test-mode --reprocess
```

### EC2 full run with `nohup`

```bash
nohup bash run_python_ec2.sh \
  extract_commercials.py \
    --no-test-mode \
> process_output.log 2>&1 &
```

### EC2 full run from a specific commercial ID

```bash
nohup bash run_python_ec2.sh \
  extract_commercials.py \
    --no-test-mode \
    --start-commercial-id tv_com_1950_25 \
> process_output.log 2>&1 &
```

---

# 5. Argument Validation

The programme must fail fast with a clear message if:

- the metadata file does not exist;
- the metadata file is unreadable;
- the metadata file contains invalid JSON lines;
- the input directory does not exist;
- the input directory is not a directory;
- the output directory cannot be created;
- `--test-limit` is less than or equal to zero;
- `--workers` is less than or equal to zero;
- `--workers` is not `1` in the current sequential implementation;
- `--timeout` is less than or equal to zero;
- `--max-retries` is negative;
- `--start-commercial-id` is provided but empty;
- `--start-commercial-id` is provided but the commercial ID is not found among eligible metadata rows;
- `ffmpeg` is not available on the system path.

The programme should check for `ffmpeg` availability before processing begins.

A validation error should:

- be printed clearly to the console;
- be written to the log if logging has already been configured;
- cause the programme to exit with a non-zero status code.

---

# 6. Environment and Configuration

This programme does not require API keys or secret environment variables.

The programme depends on the external command-line tool:

```text
ffmpeg
```

The implementation must verify that `ffmpeg` is available before starting extraction.

Suggested check:

```bash
ffmpeg -version
```

The programme should also be compatible with ordinary project-local paths and with EC2 execution through the existing shell runner.

No Python package beyond the standard library is required for the initial implementation.

Recommended standard-library modules:

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

---

# 7. Core Processing Architecture

## 7.1 High-level flow

The programme must follow this workflow:

1. **Startup**
   - Parse command-line arguments.
   - Validate simple argument values.
   - Generate a UTC `run_id`.
   - Ensure the output directory exists.
   - Set up logging.
   - Check that `ffmpeg` is available.

2. **Metadata loading**
   - Open the NDJSON metadata file.
   - Read records line by line.
   - Parse each JSON object.
   - Count total metadata records.
   - Select only records where `Download Success` is `True`.
   - Validate required fields for selected records:
     - `Commercial ID`
     - `Video ID`
     - `Start`
     - `End`

3. **Discovery**
   - Build an ordered list of eligible commercials.
   - Preserve metadata order.
   - Record invalid eligible rows in the manifest.
   - Ignore rows where `Download Success` is not `True`.

4. **Planning**
   - If `--start-commercial-id` is provided:
     - locate the specified `Commercial ID` in the eligible commercial list;
     - discard all eligible commercials before it;
     - include the specified commercial and all following eligible commercials;
     - fail fast if the specified `Commercial ID` is not found.
   - For each selected eligible commercial:
     - compute input path as `<input_dir>/<Video ID>.mp4`;
     - compute output path as `<output_dir>/<Commercial ID>.mp4`;
     - check whether the source video exists;
     - decide whether to skip or clip.
   - If the input source video is missing:
     - mark the item as `missing_input`;
     - log the missing input;
     - do not run `ffmpeg` for that item.
   - If the output file exists and `--reprocess` is not enabled:
     - mark the item as `skipped_existing`.
   - If the output file does not exist or `--reprocess` is enabled:
     - plan the item for extraction.
   - If test mode is enabled:
     - limit the planned extraction list to `--test-limit`.

5. **Execution**
   - For each planned item:
     - build the `ffmpeg` command;
     - run `ffmpeg`;
     - capture stdout, stderr, return code, timing, and any exception;
     - retry according to `--max-retries`;
     - mark the item as `success` or `failed`.

6. **End-of-run summary**
   - Count:
     - total metadata records;
     - eligible metadata records;
     - ignored records where `Download Success` is not `True`;
     - invalid metadata rows;
     - missing input videos;
     - skipped existing clips;
     - planned extractions;
     - attempted extractions;
     - successful extractions;
     - failed extractions.
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
    """Parse command-line arguments for the commercial extraction programme."""
```

### Validation

Responsible for:

- checking file paths;
- checking numeric arguments;
- checking start commercial ID syntax;
- checking `ffmpeg` availability.

Suggested function:

```python
def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments and external dependencies before processing."""
```

### Metadata loading

Responsible for:

- reading NDJSON;
- parsing records;
- filtering rows by `Download Success`;
- extracting required fields;
- detecting invalid eligible rows.

Suggested function:

```python
def load_commercial_metadata(metadata_path: Path) -> tuple[list[dict], list[dict], int, int]:
    """Load and validate eligible commercial metadata from an NDJSON file."""
```

Suggested return values:

```text
eligible_commercials, invalid_records, total_records, ignored_download_failures
```

### Planning

Responsible for:

- applying `--start-commercial-id`, if provided;
- creating input and output paths;
- checking missing input files;
- deciding whether items are skipped or attempted;
- applying test-mode limit.

Suggested function:

```python
def plan_extractions(
    commercials: list[dict],
    input_dir: Path,
    output_dir: Path,
    test_mode: bool,
    test_limit: int,
    reprocess: bool,
    start_commercial_id: str | None = None
) -> tuple[list[dict], list[dict], list[dict]]:
    """Create planned, skipped, and missing-input commercial extraction records."""
```

Suggested return values:

```text
planned, skipped_existing, missing_input
```

### Core extraction function

Responsible for extracting a single commercial.

It should:

- build the `ffmpeg` command;
- run the command using `subprocess`;
- capture return code, stdout, stderr;
- detect failure;
- return a structured result;
- not terminate the whole programme on failure.

Suggested function:

```python
def extract_one_commercial(
    commercial_id: str,
    video_id: str,
    start: str,
    end: str,
    input_path: Path,
    output_path: Path,
    timeout: int,
    max_retries: int,
    retry_delay: int
) -> dict:
    """Extract one commercial clip with ffmpeg and return a structured result."""
```

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

### Main orchestration

Responsible for:

- coordinating all steps;
- logging;
- error handling;
- exit code.

Suggested function:

```python
def main() -> int:
    """Run the batch commercial extraction workflow and return an exit code."""
```

---

# 8. Extraction Behaviour

## 8.1 Base command

For each eligible commercial, the programme must run:

```bash
ffmpeg -y -ss "<Start>" -to "<End>" -i "<input_path>" -c:v libx264 -c:a aac -avoid_negative_ts make_zero "<output_path>"
```

Example metadata row:

| Decade | Sequence | Title | Category | Commercial ID | Video ID | URL | Start | End | Download Success | Reason |
|---:|---:|---|---|---|---|---|---|---|---|---|
| 1950 | 1 | Norwich Liquid Peptans | Health, Beauty & Personal Care | `tv_com_1950_1` | `video_0001` | `https://youtu.be/G-zZFNf4PqQ` | `0:00:00` | `0:00:59` | `True` | `Success` |

Generated command:

```bash
ffmpeg -y -ss "0:00:00" -to "0:00:59" -i "corpus/01_videos/video_0001.mp4" -c:v libx264 -c:a aac -avoid_negative_ts make_zero "corpus/02_commercials/tv_com_1950_1.mp4"
```

The command must be built as a list of arguments for `subprocess`, not as a shell string.

Conceptually:

```python
command = [
    "ffmpeg",
    "-y",
    "-ss",
    start,
    "-to",
    end,
    "-i",
    str(input_path),
    "-c:v",
    "libx264",
    "-c:a",
    "aac",
    "-avoid_negative_ts",
    "make_zero",
    str(output_path),
]
```

---

## 8.2 Input filename

The input filename must be derived from the `Video ID`.

Given:

```text
Video ID = video_0001
```

The input file must be:

```text
video_0001.mp4
```

The full default input path must be:

```text
corpus/01_videos/video_0001.mp4
```

---

## 8.3 Output filename

The output filename must be derived from the `Commercial ID`.

Given:

```text
Commercial ID = tv_com_1950_1
```

The output file must be:

```text
tv_com_1950_1.mp4
```

The full default output path must be:

```text
corpus/02_commercials/tv_com_1950_1.mp4
```

---

## 8.4 Existing files

If the output file already exists and `--reprocess` is not enabled:

- do not call `ffmpeg`;
- mark the item as `skipped_existing`;
- log the skip;
- include the item in the manifest.

If `--reprocess` is enabled:

- call `ffmpeg`;
- allow the output to be overwritten because the command includes `-y`.

---

## 8.5 Missing source videos

If the expected source video does not exist:

```text
corpus/01_videos/<Video ID>.mp4
```

The programme must:

- not call `ffmpeg`;
- mark the item as `missing_input`;
- include the expected input path in the manifest;
- log the missing input;
- continue processing other commercials.

Missing source videos should cause a non-zero exit code because the corresponding eligible commercial could not be extracted.

---

## 8.6 Start commercial ID behaviour

If `--start-commercial-id COMMERCIAL_ID` is provided:

- the programme must locate `COMMERCIAL_ID` in the eligible commercial list;
- all eligible commercials before `COMMERCIAL_ID` must be ignored for planning;
- `COMMERCIAL_ID` itself must be included;
- all following eligible commercials must be included;
- existing-file skipping must still apply after the start-commercial filter;
- missing-input checking must still apply after the start-commercial filter;
- test-mode limiting must apply after the start-commercial filter and after existing-file skipping;
- if `COMMERCIAL_ID` is not found, the programme must exit with a configuration error.

Example:

```bash
python extract_commercials.py \
  --no-test-mode \
  --start-commercial-id tv_com_1950_25
```

---

## 8.7 Invalid timestamps

If `Start` or `End` is missing, blank, malformed, or rejected by `ffmpeg`, the programme must:

- mark the item as `failed_metadata` if the problem is detected before planning;
- otherwise mark the item as `failed` if `ffmpeg` rejects the timestamps;
- save a short error summary in the manifest;
- log the failure;
- continue with the next commercial.

The initial implementation may rely on `ffmpeg` to reject malformed but non-empty timestamps, but it must validate that `Start` and `End` are present.

---

## 8.8 `ffmpeg` failures

If `ffmpeg` returns a non-zero exit code, the programme must:

- capture the failure;
- mark the commercial as `failed`;
- save a short error summary in the manifest;
- log the failure;
- continue with the next commercial.

The programme must not stop the entire batch because one commercial fails.

---

## 8.9 Retries

For failures that may be transient, the programme should retry up to `--max-retries`.

Retry behaviour:

- retry only failed `ffmpeg` commands;
- do not retry missing-input or failed-metadata records;
- log each retry attempt;
- record the number of retries used in the manifest;
- if all attempts fail, mark the item as `failed`.

A simple fixed delay between retries is acceptable for the initial implementation.

Suggested retry delay:

```text
5 seconds
```

---

# 9. JSON Manifest Design

## 9.1 Manifest structure

The manifest must use this general structure:

```json
{
  "run_metadata": {
    "run_id": "20260519T143012Z",
    "tool_name": "extract_commercials.py",
    "tool_version": "v1",
    "start_time": "2026-05-19T14:30:12Z",
    "end_time": "2026-05-19T14:35:42Z",
    "test_mode": true,
    "test_limit": 5,
    "reprocess": false,
    "workers": 1,
    "metadata_path": "corpus/00_sources/tv_commercials.ndjson",
    "input_dir": "corpus/01_videos",
    "output_dir": "corpus/02_commercials",
    "log_file": "corpus/02_commercials/extract_commercials.log",
    "manifest_file": "corpus/02_commercials/extract_commercials_manifest.json",
    "config": {
      "ffmpeg_codec_video": "libx264",
      "ffmpeg_codec_audio": "aac",
      "avoid_negative_ts": "make_zero",
      "timeout_seconds": 3600,
      "max_retries": 1,
      "retry_delay_seconds": 5,
      "start_commercial_id": "tv_com_1950_25"
    },
    "summary": {
      "metadata_records": 960,
      "eligible_download_success": 958,
      "ignored_download_not_success": 2,
      "invalid_metadata": 0,
      "planned": 5,
      "attempted": 5,
      "succeeded": 5,
      "failed": 0,
      "missing_input": 0,
      "skipped_existing": 0
    },
    "interrupted": false
  },
  "commercials": [
    {
      "commercial_id": "tv_com_1950_1",
      "video_id": "video_0001",
      "start": "0:00:00",
      "end": "0:00:59",
      "input_path": "corpus/01_videos/video_0001.mp4",
      "output_path": "corpus/02_commercials/tv_com_1950_1.mp4",
      "status": "success",
      "error": null,
      "return_code": 0,
      "retries": 0,
      "duration_seconds": 8.4,
      "start_time": "2026-05-19T14:30:15Z",
      "end_time": "2026-05-19T14:30:23Z",
      "metadata": {
        "title": "Norwich Liquid Peptans",
        "decade": "1950",
        "sequence": 1,
        "category": "Health, Beauty & Personal Care",
        "command": [
          "ffmpeg",
          "-y",
          "-ss",
          "0:00:00",
          "-to",
          "0:00:59",
          "-i",
          "corpus/01_videos/video_0001.mp4",
          "-c:v",
          "libx264",
          "-c:a",
          "aac",
          "-avoid_negative_ts",
          "make_zero",
          "corpus/02_commercials/tv_com_1950_1.mp4"
        ]
      }
    }
  ],
  "invalid_records": []
}
```

If no start commercial ID is provided, the manifest should record:

```json
"start_commercial_id": null
```

---

## 9.2 Required item statuses

The following statuses must be supported:

| Status | Meaning |
|---|---|
| `success` | Commercial was extracted successfully |
| `failed` | Extraction was attempted but `ffmpeg` failed |
| `skipped_existing` | Output clip already existed and `--reprocess` was not enabled |
| `missing_input` | Source video file was missing |
| `failed_metadata` | Metadata record was invalid and could not be planned |

---

## 9.3 Error field

The `error` field must be:

- `null` when there is no error;
- a short string when an error occurs.

For `ffmpeg` failures, the error should usually be derived from `stderr`.

Example:

```json
{
  "commercial_id": "tv_com_1950_1",
  "video_id": "video_0001",
  "start": "0:00:00",
  "end": "0:00:59",
  "input_path": "corpus/01_videos/video_0001.mp4",
  "output_path": "corpus/02_commercials/tv_com_1950_1.mp4",
  "status": "failed",
  "error": "Invalid duration specification for to: 0:00:bad",
  "return_code": 1,
  "retries": 1
}
```

---

# 10. Logging Specification

The programme must write an append-only log file.

Default:

```text
corpus/02_commercials/extract_commercials.log
```

## Log format

Each line should follow this format:

```text
[YYYY-MM-DD HH:MM:SS] LEVEL  message
```

Example:

```text
[2026-05-19 14:30:12] INFO  Starting extract_commercials.py run_id=20260519T143012Z
```

## Required log events

The programme must log:

- startup;
- parsed configuration summary;
- metadata file path;
- input directory;
- output directory;
- test mode status;
- test limit;
- reprocess setting;
- start commercial ID, if provided;
- `ffmpeg` availability and version if available;
- number of metadata records read;
- number of records eligible because `Download Success` is `True`;
- number of records ignored because `Download Success` is not `True`;
- number of invalid metadata records;
- number of planned extractions;
- each skipped existing commercial;
- each missing source video;
- each successful extraction;
- each failed extraction;
- each retry attempt;
- manifest write paths;
- end-of-run summary;
- keyboard interrupts;
- validation/configuration errors.

## Example log lines

```text
[2026-05-19 14:30:12] INFO  Starting extract_commercials.py run_id=20260519T143012Z
[2026-05-19 14:30:12] INFO  Metadata path: corpus/00_sources/tv_commercials.ndjson
[2026-05-19 14:30:12] INFO  Input directory: corpus/01_videos
[2026-05-19 14:30:12] INFO  Output directory: corpus/02_commercials
[2026-05-19 14:30:12] INFO  Test mode: true; test_limit=5
[2026-05-19 14:30:12] INFO  Start commercial ID: tv_com_1950_25
[2026-05-19 14:30:13] INFO  Found 960 metadata records; 958 eligible for extraction
[2026-05-19 14:30:15] INFO  SUCCESS tv_com_1950_1 video_0001 0:00:00-0:00:59 -> corpus/02_commercials/tv_com_1950_1.mp4
[2026-05-19 14:35:42] INFO  Wrote latest manifest: corpus/02_commercials/extract_commercials_manifest.json
[2026-05-19 14:35:42] INFO  Finished run: succeeded=4 failed=1 skipped_existing=0 missing_input=0
```

---

# 11. Error Handling and Resiliency

## 11.1 Configuration errors

Configuration errors must stop the programme before extraction begins.

Examples:

- metadata file missing;
- metadata file unreadable;
- metadata file contains invalid JSON;
- input directory missing;
- output directory cannot be created;
- invalid command-line arguments;
- start commercial ID not found when `--start-commercial-id` is provided;
- `ffmpeg` is not installed or not found.

The programme must exit non-zero.

---

## 11.2 Per-commercial errors

Per-commercial errors must not stop the full run.

Examples:

- source video file missing;
- malformed timestamp;
- end timestamp before start timestamp;
- zero-length or negative-length clip;
- unreadable video file;
- unsupported video format;
- `ffmpeg` timeout;
- `ffmpeg` non-zero return code;
- output file cannot be written.

For each per-commercial error:

- mark the item as one of:
  - `missing_input`
  - `failed_metadata`
  - `failed`
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
| `0` | Completed with no failed attempted extractions, no missing inputs, and no invalid eligible metadata rows |
| `1` | Completed, but one or more commercial extractions failed, source videos were missing, or eligible metadata rows were invalid |
| `2` | Configuration or validation error |
| `130` | Interrupted by user |

Skipped existing files are not failures.

Rows where `Download Success` is not `True` are not failures.

---

# 12. Docstrings and In-code Documentation

The implementation must include clear docstrings.

## 12.1 Module-level docstring

At the top of `extract_commercials.py`, include a module-level docstring explaining:

- purpose of the programme;
- expected input metadata file;
- source video input directory;
- commercial output directory;
- use of `ffmpeg`;
- default test mode;
- resumability behaviour;
- example commands.

Suggested module docstring:

```python
"""
Extract television commercial clips from downloaded source videos.

This script reads commercial metadata from an NDJSON file, selects records where
"Download Success" is true, and extracts one commercial clip per eligible record
using ffmpeg.

Source videos are expected in the input directory as "<Video ID>.mp4".
Extracted clips are written to the output directory as "<Commercial ID>.mp4".

By default, the script runs in test mode and attempts only the first 5 planned
commercials. Existing output clips are skipped unless --reprocess is provided,
making the script safe to re-run.

Use --start-commercial-id to start planning extraction from a specific
Commercial ID onward.

Example:
    python extract_commercials.py

Full run:
    python extract_commercials.py --no-test-mode

Full run from a specific commercial:
    python extract_commercials.py --no-test-mode --start-commercial-id tv_com_1950_25

The script writes an append-only log file and JSON manifests describing
run-level metadata and per-commercial status.
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
- `load_commercial_metadata`
- `plan_extractions`
- `extract_one_commercial`
- `write_manifests`
- `main`

---

# 13. Suggested Constants

The implementation should define constants near the top of the file:

```python
TOOL_NAME = "extract_commercials.py"
TOOL_VERSION = "v1"

DEFAULT_METADATA_PATH = "corpus/00_sources/tv_commercials.ndjson"
DEFAULT_INPUT_DIR = "corpus/01_videos"
DEFAULT_OUTPUT_DIR = "corpus/02_commercials"
DEFAULT_LOG_FILE = "corpus/02_commercials/extract_commercials.log"
DEFAULT_MANIFEST_FILE = "corpus/02_commercials/extract_commercials_manifest.json"

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 5
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 5

FFMPEG_VIDEO_CODEC = "libx264"
FFMPEG_AUDIO_CODEC = "aac"
FFMPEG_AVOID_NEGATIVE_TS = "make_zero"
```

---

# 14. Development Notes

## Initial implementation scope

The first implementation should prioritise:

- correct sequential execution;
- reliable metadata filtering by `Download Success`;
- robust input-file checking;
- reliable logging;
- robust manifest output;
- safe resumability;
- optional start-commercial-ID support;
- clear error handling.

Parallel extraction can be prepared architecturally but does not need to be implemented in the first version.

## Recommended implementation approach

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

# 15. Acceptance Criteria

The programme is considered complete when the following conditions are met:

1. Running:

   ```bash
   python extract_commercials.py
   ```

   performs a test run of up to 5 commercials.

2. The programme reads:

   ```text
   corpus/00_sources/tv_commercials.ndjson
   ```

3. The programme processes only rows where:

   ```text
   Download Success = True
   ```

4. The programme uses source videos from:

   ```text
   corpus/01_videos/
   ```

5. The programme creates the output directory if needed:

   ```text
   corpus/02_commercials/
   ```

6. Each extracted commercial is saved as:

   ```text
   corpus/02_commercials/<Commercial ID>.mp4
   ```

7. The `ffmpeg` command is equivalent to:

   ```bash
   ffmpeg -y -ss "<Start>" -to "<End>" -i "corpus/01_videos/<Video ID>.mp4" -c:v libx264 -c:a aac -avoid_negative_ts make_zero "corpus/02_commercials/<Commercial ID>.mp4"
   ```

8. Existing commercial `.mp4` files are skipped unless `--reprocess` is used.

9. Failed extractions do not stop the full batch.

10. Missing input videos are marked as `missing_input`.

11. Invalid eligible metadata rows are marked as `failed_metadata`.

12. The programme supports starting from a specific commercial ID with:

    ```bash
    --start-commercial-id COMMERCIAL_ID
    ```

13. When `--start-commercial-id COMMERCIAL_ID` is provided, the programme plans extraction from that commercial ID onward, preserving metadata order.

14. If `--start-commercial-id COMMERCIAL_ID` is not found among eligible rows, the programme exits with a configuration error.

15. A log file is written at:

    ```text
    corpus/02_commercials/extract_commercials.log
    ```

16. A latest manifest is written at:

    ```text
    corpus/02_commercials/extract_commercials_manifest.json
    ```

17. A timestamped per-run manifest is also written.

18. The manifest records:
    - run metadata;
    - configuration;
    - start commercial ID, if any;
    - per-commercial status;
    - errors;
    - timings;
    - summary counts.

19. The programme exits with:
    - `0` if all attempted extractions succeed or are skipped and there are no missing inputs or invalid eligible metadata rows;
    - `1` if any attempted extraction fails, any eligible input video is missing, or any eligible metadata row is invalid;
    - `2` for configuration errors;
    - `130` for keyboard interruption.

---

# 16. Short README Section

The following section can be added to project documentation.

## Extract commercial clips

The `extract_commercials.py` programme extracts individual commercial clips from the downloaded source videos listed in:

```text
corpus/00_sources/tv_commercials.ndjson
```

Only rows where `Download Success` is `True` are processed.

Source videos are read from:

```text
corpus/01_videos/
```

Each source video is identified by the `Video ID` field and expected to exist as:

```text
corpus/01_videos/<Video ID>.mp4
```

Commercial clips are written to:

```text
corpus/02_commercials/
```

Each clip is named after its `Commercial ID`:

```text
corpus/02_commercials/<Commercial ID>.mp4
```

Default test run:

```bash
python extract_commercials.py
```

This processes up to 5 eligible commercials.

Full run:

```bash
python extract_commercials.py --no-test-mode
```

To resume planning from a specific commercial ID onward, use:

```bash
python extract_commercials.py \
  --no-test-mode \
  --start-commercial-id tv_com_1950_25
```

The programme is safe to re-run: existing commercial clips are skipped by default. To force re-extraction, use:

```bash
python extract_commercials.py --no-test-mode --reprocess
```

The programme writes:

```text
corpus/02_commercials/extract_commercials.log
corpus/02_commercials/extract_commercials_manifest.json
```

A timestamped per-run manifest is also created for each execution.