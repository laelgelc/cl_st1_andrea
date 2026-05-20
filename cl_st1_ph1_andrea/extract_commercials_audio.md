# `extract_commercials_audio.py` — Programme Specification for Development

## 1. High-level Functionality Specification

### Programme Summary

`extract_commercials_audio.py` is a batch-processing programme that extracts transcription-ready audio from previously extracted television commercial video files.

The programme reads the metadata file:

```text
corpus/00_sources/tv_commercials.ndjson
```

Each record in this metadata file represents one commercial. The programme must process only rows where:

```text
Download Success = True
```

For each eligible row, the programme uses:

- `Commercial ID` to locate the source commercial video file;
- `Commercial ID` again to name the extracted audio file.

The source commercial video files are stored in:

```text
corpus/02_commercials/
```

The extracted audio files must be written to:

```text
corpus/03_audio/
```

The base audio extraction command is:

```bash
ffmpeg -y -i "tv_com_1950_1.mp4" -vn -ac 1 -ar 16000 -sample_fmt s16 "tv_com_1950_1.wav"
```

The programme must generalise this command so that each eligible commercial audio file is extracted as:

```bash
ffmpeg -y -i "<input_dir>/<Commercial ID>.mp4" -vn -ac 1 -ar 16000 -sample_fmt s16 "<output_dir>/<Commercial ID>.wav"
```

For example:

```bash
ffmpeg -y -i "corpus/02_commercials/tv_com_1950_1.mp4" -vn -ac 1 -ar 16000 -sample_fmt s16 "corpus/03_audio/tv_com_1950_1.wav"
```

The output audio format is designed to be convenient for transcription with Whisper:

- WAV container;
- mono audio;
- 16 kHz sample rate;
- signed 16-bit PCM sample format.

---

## 2. Key Behaviours

The programme must implement the following behaviours:

- Read commercial metadata from an NDJSON file.
- Process only records where `Download Success` is `True`.
- Extract the required field:
  - `Commercial ID`
- Build one `ffmpeg` audio extraction command per eligible commercial.
- Locate source commercial videos as:

  ```text
  corpus/02_commercials/<Commercial ID>.mp4
  ```

- Save extracted audio as:

  ```text
  corpus/03_audio/<Commercial ID>.wav
  ```

- Create the output directory if it does not already exist.
- Use `ffmpeg` as the external audio extraction engine.
- Produce audio suitable for Whisper transcription:
  - no video stream;
  - mono channel;
  - 16 kHz sampling rate;
  - 16-bit signed PCM WAV.
- Use test mode by default, limiting processing to 5 eligible commercials.
- Skip already-extracted audio files by default, supporting safe re-runs.
- Allow reprocessing with an explicit command-line option.
- Continue processing remaining commercials if one audio extraction fails.
- Record progress and errors in an append-only log file.
- Produce a JSON manifest with run-level metadata and item-level results.
- Write both:
  - a timestamped per-run manifest;
  - a latest manifest that is overwritten on each run.
- Exit with status code `0` only when all attempted audio extractions succeed or are skipped.
- Exit with a non-zero status code if one or more attempted extractions fail, or if there is a configuration/validation error.

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

Each valid eligible record must contain:

| Field | Type | Description |
|---|---:|---|
| `Commercial ID` | string | Unique identifier for the commercial, e.g. `tv_com_1950_1` |
| `Download Success` | boolean/string | Indicates whether the original source video was successfully downloaded |

Other metadata fields may be preserved in the manifest for traceability:

| Field | Description |
|---|---|
| `Decade` | Decade of the commercial |
| `Sequence` | Sequence number within the decade |
| `Title` | Title of the commercial |
| `Category` | Commercial category |
| `Video ID` | Source compilation video ID |
| `URL` | Original YouTube URL |
| `Start` | Original commercial start timestamp |
| `End` | Original commercial end timestamp |
| `Reason` | Download status reason |

Example record:

```json
{"Decade":"1950","Sequence":1,"Title":"Norwich Liquid Peptans","Category":"Health, Beauty & Personal Care","Commercial ID":"tv_com_1950_1","Video ID":"video_0001","URL":"https://youtu.be/G-zZFNf4PqQ","Start":"0:00:00","End":"0:00:59","Download Success":true,"Reason":"Success"}
```

### Eligibility rules

The programme must:

1. Read all records from the NDJSON file.
2. Select only records where `Download Success` is `True`.
3. Ignore records where `Download Success` is `False`, missing, blank, or otherwise not truthy.
4. Validate that each selected record has a non-empty:
   - `Commercial ID`
5. Build one planned audio extraction per valid selected record.
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

If a row has `Download Success = True` but is missing `Commercial ID`:

- it must not be processed;
- it should be marked as `failed_metadata` in the manifest;
- the error should be logged;
- processing should continue for other records.

Rows where `Download Success` is not `True` are not errors. They are expected to be ignored because their source videos were not successfully downloaded.

---

## 3.2 Output

### Audio output directory

Default path:

```text
corpus/03_audio/
```

The programme must create this directory if it does not already exist.

### Per-commercial audio output

Each extracted audio file must be saved as:

```text
<output_dir>/<Commercial ID>.wav
```

Examples:

```text
corpus/03_audio/tv_com_1950_1.wav
corpus/03_audio/tv_com_1950_2.wav
corpus/03_audio/tv_com_1960_1.wav
```

### Source commercial video input directory

Default path:

```text
corpus/02_commercials/
```

Each source commercial video is expected to exist as:

```text
<input_dir>/<Commercial ID>.mp4
```

Examples:

```text
corpus/02_commercials/tv_com_1950_1.mp4
corpus/02_commercials/tv_com_1950_2.mp4
corpus/02_commercials/tv_com_1960_1.mp4
```

### Log file

Default path:

```text
corpus/03_audio/extract_commercials_audio.log
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
corpus/03_audio/extract_commercials_audio_manifest.json
```

This file is overwritten at the end of each run.

#### Per-run manifest

A timestamped copy must also be written using the run ID.

Filename pattern:

```text
extract_commercials_audio_manifest_<run_id>.json
```

Example:

```text
corpus/03_audio/extract_commercials_audio_manifest_20260520T143012Z.json
```

---

# 4. Command-line Interface

## 4.1 Default usage

```bash
python extract_commercials_audio.py
```

Default behaviour:

- metadata path: `corpus/00_sources/tv_commercials.ndjson`
- input directory: `corpus/02_commercials/`
- output directory: `corpus/03_audio/`
- output format: `.wav`
- audio channels: `1`
- audio sample rate: `16000`
- sample format: `s16`
- test mode: enabled
- test limit: 5 commercials
- reprocess: disabled
- existing `.wav` files are skipped
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
corpus/02_commercials/
```

Description:

Directory where extracted commercial video files are stored.

The programme expects source videos to be named:

```text
<Commercial ID>.mp4
```

---

### Output directory

```bash
--output-dir PATH
```

Default:

```text
corpus/03_audio/
```

Description:

Directory where extracted `.wav` audio files will be saved.

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

When test mode is enabled, the programme processes only a limited number of planned audio extractions.

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
python extract_commercials_audio.py --test-limit 10
```

---

### Reprocess existing audio files

```bash
--reprocess
```

Default:

```text
False
```

Description:

When omitted, the programme skips any commercial whose output `.wav` file already exists.

When provided, the programme extracts the audio again and overwrites the existing output file.

Example:

```bash
python extract_commercials_audio.py --reprocess
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

Optional `Commercial ID` from which to start planning audio extraction.

When this option is provided, the programme must preserve metadata order but ignore all eligible commercials that occur before the specified `Commercial ID`. The specified commercial itself must be included in the planning step.

This is useful for resuming a long extraction run from a known point without relying only on existing-file detection.

Example:

```bash
python extract_commercials_audio.py --start-commercial-id tv_com_1950_25
```

If the requested `Commercial ID` is not found among eligible metadata rows, the programme must fail fast with a configuration error.

---

### Log file

```bash
--log-file PATH
```

Default:

```text
corpus/03_audio/extract_commercials_audio.log
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
corpus/03_audio/extract_commercials_audio_manifest.json
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

Maximum allowed time for a single `ffmpeg` audio extraction process.

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

Number of retry attempts after a failed audio extraction command.

For example, with `--max-retries 1`, each failed item may be attempted twice in total:

1. initial attempt;
2. one retry.

Must be zero or a positive integer.

---

## 4.4 Example commands

### Small default test run

```bash
python extract_commercials_audio.py
```

### Test run with 10 commercials

```bash
python extract_commercials_audio.py --test-limit 10
```

### Test run from a specific commercial ID

```bash
python extract_commercials_audio.py \
  --test-limit 3 \
  --start-commercial-id tv_com_1950_25
```

### Full production run

```bash
python extract_commercials_audio.py --no-test-mode
```

### Full production run from a specific commercial ID

```bash
python extract_commercials_audio.py \
  --no-test-mode \
  --start-commercial-id tv_com_1950_25
```

### Full production run with explicit paths

```bash
python extract_commercials_audio.py \
  --metadata corpus/00_sources/tv_commercials.ndjson \
  --input-dir corpus/02_commercials \
  --output-dir corpus/03_audio \
  --no-test-mode
```

### Re-extract audio even if files already exist

```bash
python extract_commercials_audio.py --no-test-mode --reprocess
```

### EC2 full run with `nohup`

```bash
nohup bash run_python_ec2.sh \
  extract_commercials_audio.py \
    --no-test-mode \
> process_output.log 2>&1 &
```

### EC2 full run from a specific commercial ID

```bash
nohup bash run_python_ec2.sh \
  extract_commercials_audio.py \
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
     - compute input path as `<input_dir>/<Commercial ID>.mp4`;
     - compute output path as `<output_dir>/<Commercial ID>.wav`;
     - check whether the source commercial video exists;
     - decide whether to skip or extract audio.
   - If the input source commercial video is missing:
     - mark the item as `missing_input`;
     - log the missing input;
     - do not run `ffmpeg` for that item.
   - If the output audio file exists and `--reprocess` is not enabled:
     - mark the item as `skipped_existing`.
   - If the output file does not exist or `--reprocess` is enabled:
     - plan the item for audio extraction.
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
     - skipped existing audio files;
     - planned audio extractions;
     - attempted audio extractions;
     - successful audio extractions;
     - failed audio extractions.
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
    """Parse command-line arguments for the commercial audio extraction programme."""
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
def plan_audio_extractions(
    commercials: list[dict],
    input_dir: Path,
    output_dir: Path,
    test_mode: bool,
    test_limit: int,
    reprocess: bool,
    start_commercial_id: str | None = None
) -> tuple[list[dict], list[dict], list[dict]]:
    """Create planned, skipped, and missing-input commercial audio extraction records."""
```

Suggested return values:

```text
planned, skipped_existing, missing_input
```

### Core audio extraction function

Responsible for extracting audio from a single commercial video.

It should:

- build the `ffmpeg` command;
- run the command using `subprocess`;
- capture return code, stdout, stderr;
- detect failure;
- return a structured result;
- not terminate the whole programme on failure.

Suggested function:

```python
def extract_one_audio(
    commercial_id: str,
    input_path: Path,
    output_path: Path,
    timeout: int,
    max_retries: int,
    retry_delay: int
) -> dict:
    """Extract one Whisper-ready WAV audio file with ffmpeg and return a structured result."""
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
    """Run the batch commercial audio extraction workflow and return an exit code."""
```

---

# 8. Audio Extraction Behaviour

## 8.1 Base command

For each eligible commercial, the programme must run:

```bash
ffmpeg -y -i "<input_path>" -vn -ac 1 -ar 16000 -sample_fmt s16 "<output_path>"
```

Example metadata row:

| Decade | Sequence | Title | Category | Commercial ID | Video ID | URL | Start | End | Download Success | Reason |
|---:|---:|---|---|---|---|---|---|---|---|---|
| 1950 | 1 | Norwich Liquid Peptans | Health, Beauty & Personal Care | `tv_com_1950_1` | `video_0001` | `https://youtu.be/G-zZFNf4PqQ` | `0:00:00` | `0:00:59` | `True` | `Success` |

Generated command:

```bash
ffmpeg -y -i "corpus/02_commercials/tv_com_1950_1.mp4" -vn -ac 1 -ar 16000 -sample_fmt s16 "corpus/03_audio/tv_com_1950_1.wav"
```

The command must be built as a list of arguments for `subprocess`, not as a shell string.

Conceptually:

```python
command = [
    "ffmpeg",
    "-y",
    "-i",
    str(input_path),
    "-vn",
    "-ac",
    "1",
    "-ar",
    "16000",
    "-sample_fmt",
    "s16",
    str(output_path),
]
```

---

## 8.2 Input filename

The input filename must be derived from the `Commercial ID`.

Given:

```text
Commercial ID = tv_com_1950_1
```

The input file must be:

```text
tv_com_1950_1.mp4
```

The full default input path must be:

```text
corpus/02_commercials/tv_com_1950_1.mp4
```

---

## 8.3 Output filename

The output filename must also be derived from the `Commercial ID`, but with `.wav` as the extension.

Given:

```text
Commercial ID = tv_com_1950_1
```

The output file must be:

```text
tv_com_1950_1.wav
```

The full default output path must be:

```text
corpus/03_audio/tv_com_1950_1.wav
```

---

## 8.4 Audio format

The output audio must use the following format:

| Property | Value | ffmpeg option |
|---|---:|---|
| Container | WAV | output extension `.wav` |
| Video stream | omitted | `-vn` |
| Channels | mono | `-ac 1` |
| Sample rate | 16000 Hz | `-ar 16000` |
| Sample format | signed 16-bit PCM | `-sample_fmt s16` |

This format is intended to be suitable for Whisper transcription.

---

## 8.5 Existing files

If the output audio file already exists and `--reprocess` is not enabled:

- do not call `ffmpeg`;
- mark the item as `skipped_existing`;
- log the skip;
- include the item in the manifest.

If `--reprocess` is enabled:

- call `ffmpeg`;
- allow the output to be overwritten because the command includes `-y`.

---

## 8.6 Missing source commercial videos

If the expected source commercial video does not exist:

```text
corpus/02_commercials/<Commercial ID>.mp4
```

The programme must:

- not call `ffmpeg`;
- mark the item as `missing_input`;
- include the expected input path in the manifest;
- log the missing input;
- continue processing other commercials.

Missing source videos should cause a non-zero exit code because the corresponding eligible commercial audio could not be extracted.

---

## 8.7 Start commercial ID behaviour

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
python extract_commercials_audio.py \
  --no-test-mode \
  --start-commercial-id tv_com_1950_25
```

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
    "run_id": "20260520T143012Z",
    "tool_name": "extract_commercials_audio.py",
    "tool_version": "v1",
    "start_time": "2026-05-20T14:30:12Z",
    "end_time": "2026-05-20T14:35:42Z",
    "test_mode": true,
    "test_limit": 5,
    "reprocess": false,
    "workers": 1,
    "metadata_path": "corpus/00_sources/tv_commercials.ndjson",
    "input_dir": "corpus/02_commercials",
    "output_dir": "corpus/03_audio",
    "log_file": "corpus/03_audio/extract_commercials_audio.log",
    "manifest_file": "corpus/03_audio/extract_commercials_audio_manifest.json",
    "config": {
      "output_format": "wav",
      "audio_channels": 1,
      "audio_sample_rate": 16000,
      "audio_sample_format": "s16",
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
      "input_path": "corpus/02_commercials/tv_com_1950_1.mp4",
      "output_path": "corpus/03_audio/tv_com_1950_1.wav",
      "status": "success",
      "error": null,
      "return_code": 0,
      "retries": 0,
      "duration_seconds": 2.4,
      "start_time": "2026-05-20T14:30:15Z",
      "end_time": "2026-05-20T14:30:17Z",
      "metadata": {
        "title": "Norwich Liquid Peptans",
        "decade": "1950",
        "sequence": 1,
        "category": "Health, Beauty & Personal Care",
        "video_id": "video_0001",
        "url": "https://youtu.be/G-zZFNf4PqQ",
        "source_start": "0:00:00",
        "source_end": "0:00:59",
        "command": [
          "ffmpeg",
          "-y",
          "-i",
          "corpus/02_commercials/tv_com_1950_1.mp4",
          "-vn",
          "-ac",
          "1",
          "-ar",
          "16000",
          "-sample_fmt",
          "s16",
          "corpus/03_audio/tv_com_1950_1.wav"
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
| `success` | Audio was extracted successfully |
| `failed` | Audio extraction was attempted but `ffmpeg` failed |
| `skipped_existing` | Output audio file already existed and `--reprocess` was not enabled |
| `missing_input` | Source commercial video file was missing |
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
  "input_path": "corpus/02_commercials/tv_com_1950_1.mp4",
  "output_path": "corpus/03_audio/tv_com_1950_1.wav",
  "status": "failed",
  "error": "Invalid data found when processing input",
  "return_code": 1,
  "retries": 1
}
```

---

# 10. Logging Specification

The programme must write an append-only log file.

Default:

```text
corpus/03_audio/extract_commercials_audio.log
```

## Log format

Each line should follow this format:

```text
[YYYY-MM-DD HH:MM:SS] LEVEL  message
```

Example:

```text
[2026-05-20 14:30:12] INFO  Starting extract_commercials_audio.py run_id=20260520T143012Z
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
- audio extraction settings:
  - output format;
  - channel count;
  - sample rate;
  - sample format;
- `ffmpeg` availability and version if available;
- number of metadata records read;
- number of records eligible because `Download Success` is `True`;
- number of records ignored because `Download Success` is not `True`;
- number of invalid metadata records;
- number of planned audio extractions;
- each skipped existing audio file;
- each missing source commercial video;
- each successful audio extraction;
- each failed audio extraction;
- each retry attempt;
- manifest write paths;
- end-of-run summary;
- keyboard interrupts;
- validation/configuration errors.

## Example log lines

```text
[2026-05-20 14:30:12] INFO  Starting extract_commercials_audio.py run_id=20260520T143012Z
[2026-05-20 14:30:12] INFO  Metadata path: corpus/00_sources/tv_commercials.ndjson
[2026-05-20 14:30:12] INFO  Input directory: corpus/02_commercials
[2026-05-20 14:30:12] INFO  Output directory: corpus/03_audio
[2026-05-20 14:30:12] INFO  Audio format: wav; channels=1; sample_rate=16000; sample_fmt=s16
[2026-05-20 14:30:12] INFO  Test mode: true; test_limit=5
[2026-05-20 14:30:12] INFO  Start commercial ID: tv_com_1950_25
[2026-05-20 14:30:13] INFO  Found 960 metadata records; 958 eligible for audio extraction
[2026-05-20 14:30:15] INFO  SUCCESS tv_com_1950_1 -> corpus/03_audio/tv_com_1950_1.wav
[2026-05-20 14:35:42] INFO  Wrote latest manifest: corpus/03_audio/extract_commercials_audio_manifest.json
[2026-05-20 14:35:42] INFO  Finished run: succeeded=4 failed=1 skipped_existing=0 missing_input=0
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

- source commercial video file missing;
- unreadable commercial video file;
- unsupported video format;
- video file with no usable audio stream;
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
| `0` | Completed with no failed attempted audio extractions, no missing inputs, and no invalid eligible metadata rows |
| `1` | Completed, but one or more audio extractions failed, source commercial videos were missing, or eligible metadata rows were invalid |
| `2` | Configuration or validation error |
| `130` | Interrupted by user |

Skipped existing files are not failures.

Rows where `Download Success` is not `True` are not failures.

---

# 12. Docstrings and In-code Documentation

The implementation must include clear docstrings.

## 12.1 Module-level docstring

At the top of `extract_commercials_audio.py`, include a module-level docstring explaining:

- purpose of the programme;
- expected input metadata file;
- source commercial video input directory;
- audio output directory;
- use of `ffmpeg`;
- Whisper-ready audio format;
- default test mode;
- resumability behaviour;
- example commands.

Suggested module docstring:

```python
"""
Extract Whisper-ready audio from television commercial video files.

This script reads commercial metadata from an NDJSON file, selects records where
"Download Success" is true, and extracts one WAV audio file per eligible
commercial using ffmpeg.

Source commercial videos are expected in the input directory as
"<Commercial ID>.mp4". Extracted audio files are written to the output directory
as "<Commercial ID>.wav".

The output audio format is designed for transcription with Whisper:
mono, 16 kHz, signed 16-bit PCM WAV.

By default, the script runs in test mode and attempts only the first 5 planned
commercials. Existing output audio files are skipped unless --reprocess is
provided, making the script safe to re-run.

Use --start-commercial-id to start planning extraction from a specific
Commercial ID onward.

Example:
    python extract_commercials_audio.py

Full run:
    python extract_commercials_audio.py --no-test-mode

Full run from a specific commercial:
    python extract_commercials_audio.py --no-test-mode --start-commercial-id tv_com_1950_25

The script writes an append-only log file and JSON manifests describing
run-level metadata and per-commercial audio extraction status.
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
- `plan_audio_extractions`
- `extract_one_audio`
- `write_manifests`
- `main`

---

# 13. Suggested Constants

The implementation should define constants near the top of the file:

```python
TOOL_NAME = "extract_commercials_audio.py"
TOOL_VERSION = "v1"

DEFAULT_METADATA_PATH = "corpus/00_sources/tv_commercials.ndjson"
DEFAULT_INPUT_DIR = "corpus/02_commercials"
DEFAULT_OUTPUT_DIR = "corpus/03_audio"
DEFAULT_LOG_FILE = "corpus/03_audio/extract_commercials_audio.log"
DEFAULT_MANIFEST_FILE = "corpus/03_audio/extract_commercials_audio_manifest.json"

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 5
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 5

OUTPUT_AUDIO_EXTENSION = ".wav"
INPUT_VIDEO_EXTENSION = ".mp4"

FFMPEG_AUDIO_CHANNELS = "1"
FFMPEG_AUDIO_SAMPLE_RATE = "16000"
FFMPEG_AUDIO_SAMPLE_FORMAT = "s16"
```

---

# 14. Development Notes

## Initial implementation scope

The first implementation should prioritise:

- correct sequential execution;
- reliable metadata filtering by `Download Success`;
- robust input-file checking;
- correct Whisper-ready audio format;
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
   python extract_commercials_audio.py
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

4. The programme uses source commercial videos from:

   ```text
   corpus/02_commercials/
   ```

5. Each source commercial video is expected to exist as:

   ```text
   corpus/02_commercials/<Commercial ID>.mp4
   ```

6. The programme creates the output directory if needed:

   ```text
   corpus/03_audio/
   ```

7. Each extracted audio file is saved as:

   ```text
   corpus/03_audio/<Commercial ID>.wav
   ```

8. The `ffmpeg` command is equivalent to:

   ```bash
   ffmpeg -y -i "corpus/02_commercials/<Commercial ID>.mp4" -vn -ac 1 -ar 16000 -sample_fmt s16 "corpus/03_audio/<Commercial ID>.wav"
   ```

9. The output audio is:
   - WAV;
   - mono;
   - 16 kHz;
   - signed 16-bit PCM.

10. Existing `.wav` files are skipped unless `--reprocess` is used.

11. Failed audio extractions do not stop the full batch.

12. Missing input videos are marked as `missing_input`.

13. Invalid eligible metadata rows are marked as `failed_metadata`.

14. The programme supports starting from a specific commercial ID with:

    ```bash
    --start-commercial-id COMMERCIAL_ID
    ```

15. When `--start-commercial-id COMMERCIAL_ID` is provided, the programme plans audio extraction from that commercial ID onward, preserving metadata order.

16. If `--start-commercial-id COMMERCIAL_ID` is not found among eligible rows, the programme exits with a configuration error.

17. A log file is written at:

    ```text
    corpus/03_audio/extract_commercials_audio.log
    ```

18. A latest manifest is written at:

    ```text
    corpus/03_audio/extract_commercials_audio_manifest.json
    ```

19. A timestamped per-run manifest is also written.

20. The manifest records:
    - run metadata;
    - configuration;
    - start commercial ID, if any;
    - per-commercial status;
    - errors;
    - timings;
    - summary counts;
    - generated `ffmpeg` command.

21. The programme exits with:
    - `0` if all attempted audio extractions succeed or are skipped and there are no missing inputs or invalid eligible metadata rows;
    - `1` if any attempted extraction fails, any eligible input video is missing, or any eligible metadata row is invalid;
    - `2` for configuration errors;
    - `130` for keyboard interruption.

---

# 16. Short README Section

The following section can be added to project documentation.

## Extract commercial audio

The `extract_commercials_audio.py` programme extracts Whisper-ready audio from the individual commercial video files listed in:

```text
corpus/00_sources/tv_commercials.ndjson
```

Only rows where `Download Success` is `True` are processed.

Source commercial videos are read from:

```text
corpus/02_commercials/
```

Each source commercial video is identified by the `Commercial ID` field and expected to exist as:

```text
corpus/02_commercials/<Commercial ID>.mp4
```

Audio files are written to:

```text
corpus/03_audio/
```

Each audio file is named after its `Commercial ID`:

```text
corpus/03_audio/<Commercial ID>.wav
```

The audio extraction command generated for each eligible row is equivalent to:

```bash
ffmpeg -y -i "corpus/02_commercials/<Commercial ID>.mp4" -vn -ac 1 -ar 16000 -sample_fmt s16 "corpus/03_audio/<Commercial ID>.wav"
```

The resulting audio is suitable for Whisper transcription:

- WAV format;
- mono;
- 16 kHz;
- signed 16-bit PCM.

Default test run:

```bash
python extract_commercials_audio.py
```

This processes up to 5 eligible commercials.

Full run:

```bash
python extract_commercials_audio.py --no-test-mode
```

To resume planning from a specific commercial ID onward, use:

```bash
python extract_commercials_audio.py \
  --no-test-mode \
  --start-commercial-id tv_com_1950_25
```

The programme is safe to re-run: existing audio files are skipped by default. To force re-extraction, use:

```bash
python extract_commercials_audio.py --no-test-mode --reprocess
```

The programme writes:

```text
corpus/03_audio/extract_commercials_audio.log
corpus/03_audio/extract_commercials_audio_manifest.json
```

A timestamped per-run manifest is also created for each execution.