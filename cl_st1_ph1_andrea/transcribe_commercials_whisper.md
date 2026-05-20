# `transcribe_commercials_whisper.py` — Programme Specification for Development

## 1. High-level Functionality Specification

### Programme Summary

`transcribe_commercials_whisper.py` is a batch-processing programme that transcribes Whisper-ready audio files extracted from individual television commercial video clips.

The programme reads the metadata file:

```text
corpus/00_sources/tv_commercials.ndjson
```

Each record in this metadata file represents one commercial. The programme must process only rows where:

```text
Download Success = True
```

For each eligible row, the programme uses:

- `Commercial ID` to locate the source audio file;
- `Commercial ID` to name the output transcript files;
- optional metadata fields for traceability in the manifest.

The source audio files are stored in:

```text
corpus/03_audio/
```

Each source audio file is expected to be a Whisper-ready WAV file named:

```text
corpus/03_audio/<Commercial ID>.wav
```

The transcripts must be written to:

```text
corpus/04_transcripts/
```

For each commercial, the programme must write:

```text
corpus/04_transcripts/<Commercial ID>.txt
corpus/04_transcripts/<Commercial ID>.json
```

The `.txt` file contains the clean transcript text for corpus analysis. The `.json` file contains detailed transcription metadata, including segment-level timestamps and model information.

The transcription engine is:

```text
Whisper Large v3
```

The recommended implementation backend is:

```text
faster-whisper
```

The intended EC2 deployment environment is:

```text
x86_64 GPU instance
Python 3.11
CUDA-capable NVIDIA GPU
```

The project’s main Python version may remain Python 3.13.11 for non-Whisper pipeline scripts, but the Whisper transcription programme should run in a separate Python 3.11 environment for maximum compatibility with GPU ML packages.

---

## 2. Key Behaviours

The programme must implement the following behaviours:

- Read commercial metadata from an NDJSON file.
- Process only records where `Download Success` is `True`.
- Extract the required field:
  - `Commercial ID`
- Locate source audio files as:

  ```text
  corpus/03_audio/<Commercial ID>.wav
  ```

- Write plain-text transcripts as:

  ```text
  corpus/04_transcripts/<Commercial ID>.txt
  ```

- Write detailed JSON transcripts as:

  ```text
  corpus/04_transcripts/<Commercial ID>.json
  ```

- Create the output directory if it does not already exist.
- Load Whisper Large v3 once at programme startup.
- Use GPU acceleration by default when available.
- Use `faster-whisper` as the recommended transcription backend.
- Set the transcription language to English by default:

  ```text
  language = en
  ```

- Use test mode by default, limiting processing to 5 eligible commercials.
- Skip already-transcribed commercials by default, supporting safe re-runs.
- Allow reprocessing with an explicit command-line option.
- Continue processing remaining commercials if one transcription fails.
- Record progress and errors in an append-only log file.
- Produce a JSON manifest with run-level metadata and item-level results.
- Write both:
  - a timestamped per-run manifest;
  - a latest manifest that is overwritten on each run.
- Exit with status code `0` only when all attempted transcriptions succeed or are skipped.
- Exit with a non-zero status code if one or more attempted transcriptions fail, if source audio is missing, or if there is a configuration/validation error.

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

Other metadata fields may be preserved in the manifest and transcript JSON for traceability:

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
5. Build one planned transcription per valid selected record.
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

- it must not be transcribed;
- it should be marked as `failed_metadata` in the manifest;
- the error should be logged;
- processing should continue for other records.

Rows where `Download Success` is not `True` are not errors. They are expected to be ignored because their source videos were not successfully downloaded.

---

## 3.2 Input audio files

### Audio input directory

Default path:

```text
corpus/03_audio/
```

Each source audio file is expected to exist as:

```text
<input_dir>/<Commercial ID>.wav
```

Examples:

```text
corpus/03_audio/tv_com_1950_1.wav
corpus/03_audio/tv_com_1950_2.wav
corpus/03_audio/tv_com_1960_1.wav
```

The audio files should have been created by the audio extraction step and should preferably use:

| Property | Expected value |
|---|---:|
| Container | WAV |
| Channels | mono |
| Sample rate | 16000 Hz |
| Sample format | signed 16-bit PCM |

The transcription programme may rely on the audio extraction programme to create compatible audio. It does not need to re-validate audio format in the first implementation.

---

## 3.3 Output

### Transcript output directory

Default path:

```text
corpus/04_transcripts/
```

The programme must create this directory if it does not already exist.

### Per-commercial plain-text transcript

Each clean transcript must be saved as:

```text
<output_dir>/<Commercial ID>.txt
```

Examples:

```text
corpus/04_transcripts/tv_com_1950_1.txt
corpus/04_transcripts/tv_com_1950_2.txt
corpus/04_transcripts/tv_com_1960_1.txt
```

The `.txt` file should contain only the transcript text, normalised as a readable plain-text document.

Recommended formatting:

```text
This is the commercial transcript.
```

If segment joining is used, segments should be joined with spaces rather than line breaks unless a future analysis step requires segment boundaries.

### Per-commercial JSON transcript

Each detailed transcript must be saved as:

```text
<output_dir>/<Commercial ID>.json
```

Examples:

```text
corpus/04_transcripts/tv_com_1950_1.json
corpus/04_transcripts/tv_com_1950_2.json
corpus/04_transcripts/tv_com_1960_1.json
```

The `.json` file must include:

- commercial ID;
- input audio path;
- output text path;
- output JSON path;
- model name;
- backend name;
- language setting;
- detected language, if available;
- detected language probability, if available;
- full transcript text;
- segment-level timestamps;
- metadata copied from the NDJSON row.

Suggested structure:

```json
{
  "commercial_id": "tv_com_1950_1",
  "input_path": "corpus/03_audio/tv_com_1950_1.wav",
  "text_output_path": "corpus/04_transcripts/tv_com_1950_1.txt",
  "json_output_path": "corpus/04_transcripts/tv_com_1950_1.json",
  "model": {
    "backend": "faster-whisper",
    "model_name": "large-v3",
    "device": "cuda",
    "compute_type": "float16",
    "language": "en",
    "task": "transcribe",
    "beam_size": 5,
    "vad_filter": true
  },
  "transcription": {
    "text": "Now with new improved flavor...",
    "detected_language": "en",
    "language_probability": 0.998,
    "duration_seconds": 59.0,
    "segments": [
      {
        "id": 1,
        "start": 0.0,
        "end": 4.28,
        "text": "Now with new improved flavor."
      }
    ]
  },
  "metadata": {
    "title": "Norwich Liquid Peptans",
    "decade": "1950",
    "sequence": 1,
    "category": "Health, Beauty & Personal Care",
    "video_id": "video_0001",
    "url": "https://youtu.be/G-zZFNf4PqQ",
    "source_start": "0:00:00",
    "source_end": "0:00:59"
  }
}
```

### Log file

Default path:

```text
corpus/04_transcripts/transcribe_commercials_whisper.log
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
corpus/04_transcripts/transcribe_commercials_whisper_manifest.json
```

This file is overwritten at the end of each run.

#### Per-run manifest

A timestamped copy must also be written using the run ID.

Filename pattern:

```text
transcribe_commercials_whisper_manifest_<run_id>.json
```

Example:

```text
corpus/04_transcripts/transcribe_commercials_whisper_manifest_20260520T143012Z.json
```

---

# 4. Command-line Interface

## 4.1 Default usage

```bash
python transcribe_commercials_whisper.py
```

Default behaviour:

- metadata path: `corpus/00_sources/tv_commercials.ndjson`
- input directory: `corpus/03_audio/`
- output directory: `corpus/04_transcripts/`
- model name: `large-v3`
- backend: `faster-whisper`
- device: `cuda`
- compute type: `float16`
- language: `en`
- task: `transcribe`
- beam size: `5`
- VAD filter: enabled
- test mode: enabled
- test limit: 5 commercials
- reprocess: disabled
- existing transcript `.txt` and `.json` files are skipped
- one worker / sequential processing

---

## 4.2 Required arguments

There are no required command-line arguments if all default paths and settings are used.

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
corpus/03_audio/
```

Description:

Directory where Whisper-ready audio files are stored.

The programme expects source audio files to be named:

```text
<Commercial ID>.wav
```

---

### Output directory

```bash
--output-dir PATH
```

Default:

```text
corpus/04_transcripts/
```

Description:

Directory where `.txt` and `.json` transcript files will be saved.

---

### Model name

```bash
--model-name MODEL
```

Default:

```text
large-v3
```

Description:

Whisper model name to load through the transcription backend.

Recommended value for this project:

```text
large-v3
```

Possible alternative for faster exploratory runs:

```text
large-v3-turbo
```

The final corpus should use a single model consistently.

---

### Device

```bash
--device DEVICE
```

Default:

```text
cuda
```

Description:

Device on which to run transcription.

Recommended values:

```text
cuda
cpu
auto
```

For EC2 GPU transcription, use:

```text
cuda
```

If `--device cuda` is selected but CUDA/GPU transcription is unavailable, the programme must fail fast with a configuration error rather than silently falling back to CPU.

---

### Compute type

```bash
--compute-type COMPUTE_TYPE
```

Default:

```text
float16
```

Description:

Compute type used by `faster-whisper`.

Recommended for GPU:

```text
float16
```

Possible alternatives:

```text
int8_float16
int8
float32
```

The implementation may allow these values but should default to `float16`.

---

### Language

```bash
--language LANGUAGE_CODE
```

Default:

```text
en
```

Description:

Language code passed to Whisper.

For this project, English should be used explicitly:

```text
en
```

Using a fixed language avoids unnecessary language detection variability across the corpus.

If the value is set to:

```text
auto
```

the programme may pass no fixed language to Whisper, allowing language detection. This should not be the default.

---

### Task

```bash
--task TASK
```

Default:

```text
transcribe
```

Description:

Whisper task.

Allowed values:

```text
transcribe
translate
```

For this project, use:

```text
transcribe
```

---

### Beam size

```bash
--beam-size N
```

Default:

```text
5
```

Description:

Beam size for decoding.

Must be a positive integer.

---

### VAD filter

```bash
--vad-filter
--no-vad-filter
```

Default:

```text
--vad-filter
```

Description:

Enable or disable voice activity detection filtering.

Initial recommendation:

```text
--vad-filter
```

However, VAD should be tested on a sample of commercials. If short slogans, jingles, or brief spoken segments are being removed incorrectly, use:

```bash
--no-vad-filter
```

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

When test mode is enabled, the programme processes only a limited number of planned transcriptions.

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
python transcribe_commercials_whisper.py --test-limit 10
```

---

### Reprocess existing transcripts

```bash
--reprocess
```

Default:

```text
False
```

Description:

When omitted, the programme skips any commercial whose output `.txt` and `.json` transcript files already exist.

When provided, the programme transcribes the audio again and overwrites the existing transcript files.

Example:

```bash
python transcribe_commercials_whisper.py --reprocess
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

Optional `Commercial ID` from which to start planning transcription.

When this option is provided, the programme must preserve metadata order but ignore all eligible commercials that occur before the specified `Commercial ID`. The specified commercial itself must be included in the planning step.

This is useful for resuming a long transcription run from a known point without relying only on existing-file detection.

Example:

```bash
python transcribe_commercials_whisper.py --start-commercial-id tv_com_1950_25
```

If the requested `Commercial ID` is not found among eligible metadata rows, the programme must fail fast with a configuration error.

---

### Log file

```bash
--log-file PATH
```

Default:

```text
corpus/04_transcripts/transcribe_commercials_whisper.log
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
corpus/04_transcripts/transcribe_commercials_whisper_manifest.json
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

Important note:

The first implementation should load the Whisper model once and process audio sequentially. Parallel transcription with multiple workers can cause excessive GPU memory use and should not be enabled initially.

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

Maximum allowed time for a single transcription.

If the timeout is reached:

- mark the item as failed;
- log the timeout;
- continue with the next commercial.

Implementation note:

Unlike an external subprocess, `faster-whisper` inference runs inside the Python process. Strict per-item timeout enforcement is more difficult than for `ffmpeg`. The first implementation may record the timeout setting in the manifest but not enforce it strictly. If strict timeout enforcement is required later, transcription can be isolated in subprocesses.

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

Number of retry attempts after a failed transcription.

For example, with `--max-retries 1`, each failed item may be attempted twice in total:

1. initial attempt;
2. one retry.

Must be zero or a positive integer.

---

## 4.4 Example commands

### Small default test run

```bash
python transcribe_commercials_whisper.py
```

### Test run with 10 commercials

```bash
python transcribe_commercials_whisper.py --test-limit 10
```

### Test run from a specific commercial ID

```bash
python transcribe_commercials_whisper.py \
  --test-limit 3 \
  --start-commercial-id tv_com_1950_25
```

### Full production run on EC2 GPU

```bash
python transcribe_commercials_whisper.py --no-test-mode
```

### Full production run from a specific commercial ID

```bash
python transcribe_commercials_whisper.py \
  --no-test-mode \
  --start-commercial-id tv_com_1950_25
```

### Full production run with explicit paths

```bash
python transcribe_commercials_whisper.py \
  --metadata corpus/00_sources/tv_commercials.ndjson \
  --input-dir corpus/03_audio \
  --output-dir corpus/04_transcripts \
  --model-name large-v3 \
  --device cuda \
  --compute-type float16 \
  --language en \
  --no-test-mode
```

### Re-transcribe commercials even if transcript files already exist

```bash
python transcribe_commercials_whisper.py --no-test-mode --reprocess
```

### Run without VAD filtering

```bash
python transcribe_commercials_whisper.py \
  --no-test-mode \
  --no-vad-filter
```

### EC2 full run with `nohup`

```bash
nohup bash run_python_ec2.sh \
  transcribe_commercials_whisper.py \
    --no-test-mode \
> whisper_transcription_output.log 2>&1 &
```

### EC2 full run from a specific commercial ID

```bash
nohup bash run_python_ec2.sh \
  transcribe_commercials_whisper.py \
    --no-test-mode \
    --start-commercial-id tv_com_1950_25 \
> whisper_transcription_output.log 2>&1 &
```

### EC2 run inside `tmux`

```bash
tmux new -s whisper
conda activate whisper_lg_v3
cd ~/cl_st1_ph1_andrea
python transcribe_commercials_whisper.py --no-test-mode
```

Detach:

```text
Ctrl+B, then D
```

Reattach:

```bash
tmux attach -t whisper
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
- `--model-name` is missing or blank;
- `--device` is missing or blank;
- `--compute-type` is missing or blank;
- `--language` is missing or blank;
- `--task` is not one of:
  - `transcribe`
  - `translate`
- `--beam-size` is less than or equal to zero;
- `--test-limit` is less than or equal to zero;
- `--workers` is less than or equal to zero;
- `--workers` is not `1` in the current sequential implementation;
- `--timeout` is less than or equal to zero;
- `--max-retries` is negative;
- `--start-commercial-id` is provided but empty;
- `--start-commercial-id` is provided but the commercial ID is not found among eligible metadata rows;
- the `faster_whisper` Python package is not installed;
- `--device cuda` is requested but CUDA/GPU transcription is unavailable;
- Whisper model loading fails.

A validation error should:

- be printed clearly to the console;
- be written to the log if logging has already been configured;
- cause the programme to exit with a non-zero status code.

---

# 6. Environment and Configuration

## 6.1 Recommended EC2 environment

Recommended EC2 deployment:

```text
Architecture: x86_64
Instance type: g5.xlarge
GPU: NVIDIA A10G, 24 GB VRAM
AMI: AWS Deep Learning AMI GPU, Ubuntu
Python: 3.11
Environment manager: conda
```

Recommended environment name:

```text
whisper_lg_v3
```

Suggested setup:

```bash
conda create -n whisper_lg_v3 python=3.11 -y
conda activate whisper_lg_v3
pip install --upgrade pip
pip install faster-whisper tqdm
```

The project’s other scripts may continue to use Python 3.13.11, but this programme should use the separate Whisper environment on EC2.

## 6.2 Required Python package

The programme depends on:

```text
faster-whisper
```

Recommended import:

```python
from faster_whisper import WhisperModel
```

## 6.3 GPU check

The programme should verify that GPU execution is available when:

```text
--device cuda
```

is selected.

Suggested checks:

- attempt to initialise `WhisperModel` with `device="cuda"`;
- fail fast if model loading raises a CUDA/device-related error.

Optional diagnostic command outside Python:

```bash
nvidia-smi
```

## 6.4 Recommended standard-library modules

Use the Python standard library where possible:

- `argparse`
- `json`
- `logging`
- `pathlib`
- `datetime`
- `time`
- `sys`
- `traceback`
- `importlib.util`

Additional non-standard dependency:

- `faster_whisper`

Optional progress display:

- `tqdm`

If `tqdm` is unavailable, the programme should still work without a progress bar.

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
   - Check that the transcription backend dependency is installed.
   - Validate GPU/model configuration.

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
     - compute input audio path as `<input_dir>/<Commercial ID>.wav`;
     - compute output text path as `<output_dir>/<Commercial ID>.txt`;
     - compute output JSON path as `<output_dir>/<Commercial ID>.json`;
     - check whether the source audio exists;
     - decide whether to skip or transcribe.
   - If the input source audio is missing:
     - mark the item as `missing_input`;
     - log the missing input;
     - do not run Whisper for that item.
   - If both output transcript files exist and `--reprocess` is not enabled:
     - mark the item as `skipped_existing`.
   - If either output file is missing, or `--reprocess` is enabled:
     - plan the item for transcription.
   - If test mode is enabled:
     - limit the planned transcription list to `--test-limit`.

5. **Model loading**
   - Load the Whisper model once after planning and before item execution.
   - Use configured:
     - `model_name`
     - `device`
     - `compute_type`
   - If model loading fails:
     - log the error;
     - write a manifest if possible;
     - exit with configuration error.

6. **Execution**
   - For each planned item:
     - call the model transcription method;
     - collect segments;
     - join segment text into a clean transcript;
     - write `<Commercial ID>.txt`;
     - write `<Commercial ID>.json`;
     - capture timing and any exception;
     - retry according to `--max-retries`;
     - mark the item as `success` or `failed`.

7. **End-of-run summary**
   - Count:
     - total metadata records;
     - eligible metadata records;
     - ignored records where `Download Success` is not `True`;
     - invalid metadata rows;
     - missing input audio files;
     - skipped existing transcripts;
     - planned transcriptions;
     - attempted transcriptions;
     - successful transcriptions;
     - failed transcriptions.
   - Write the latest manifest.
   - Write the per-run manifest.
   - Log the final summary.
   - Exit with an appropriate status code.

8. **Interrupt handling**
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
    """Parse command-line arguments for the Whisper transcription programme."""
```

### Validation

Responsible for:

- checking file paths;
- checking numeric arguments;
- checking model/backend arguments;
- checking start commercial ID syntax;
- checking Python dependency availability.

Suggested function:

```python
def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments and transcription environment before processing."""
```

### Logging setup

Responsible for:

- creating the log file parent directory if needed;
- configuring file and console logging;
- ensuring append-only UTF-8 logging.

Suggested function:

```python
def setup_logging(log_file: Path) -> None:
    """Configure append-only file logging and console logging."""
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
def plan_transcriptions(
    commercials: list[dict],
    input_dir: Path,
    output_dir: Path,
    test_mode: bool,
    test_limit: int,
    reprocess: bool,
    start_commercial_id: str | None = None
) -> tuple[list[dict], list[dict], list[dict]]:
    """Create planned, skipped, and missing-input transcription records."""
```

Suggested return values:

```text
planned, skipped_existing, missing_input
```

### Model loading

Responsible for:

- importing `faster_whisper`;
- loading the model;
- validating device and compute configuration.

Suggested function:

```python
def load_whisper_model(
    model_name: str,
    device: str,
    compute_type: str
) -> Any:
    """Load the faster-whisper model once for batch transcription."""
```

### Core transcription function

Responsible for transcribing a single audio file.

It should:

- call `model.transcribe`;
- collect segment text and timestamps;
- write `.txt`;
- write `.json`;
- capture exceptions;
- return a structured result;
- not terminate the whole programme on failure.

Suggested function:

```python
def transcribe_one_commercial(
    model: Any,
    commercial: dict,
    input_path: Path,
    text_output_path: Path,
    json_output_path: Path,
    model_config: dict,
    max_retries: int,
    retry_delay: int
) -> dict:
    """Transcribe one commercial audio file and return a structured result."""
```

### Transcript writing

Responsible for:

- writing the clean `.txt` transcript;
- writing detailed `.json` transcript;
- preserving UTF-8 encoding.

Suggested function:

```python
def write_transcript_outputs(
    text: str,
    transcript_json: dict,
    text_output_path: Path,
    json_output_path: Path
) -> None:
    """Write text and JSON transcript outputs for one commercial."""
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
    """Run the batch Whisper transcription workflow and return an exit code."""
```

---

# 8. Transcription Behaviour

## 8.1 Model backend

The recommended backend is:

```text
faster-whisper
```

The model should be loaded as:

```python
WhisperModel(
    model_name,
    device=device,
    compute_type=compute_type,
)
```

Default values:

```text
model_name = large-v3
device = cuda
compute_type = float16
```

---

## 8.2 Transcription call

For each eligible commercial, the conceptual transcription call should be:

```python
segments, info = model.transcribe(
    str(input_path),
    language="en",
    task="transcribe",
    beam_size=5,
    vad_filter=True,
)
```

If:

```text
--language auto
```

is used, the programme should allow Whisper to detect the language by passing no fixed language argument, or by passing the backend’s equivalent language-detection option.

---

## 8.3 Input filename

The input filename must be derived from the `Commercial ID`.

Given:

```text
Commercial ID = tv_com_1950_1
```

The input audio file must be:

```text
tv_com_1950_1.wav
```

The full default input path must be:

```text
corpus/03_audio/tv_com_1950_1.wav
```

---

## 8.4 Output filenames

The output filenames must also be derived from the `Commercial ID`.

Given:

```text
Commercial ID = tv_com_1950_1
```

The output files must be:

```text
tv_com_1950_1.txt
tv_com_1950_1.json
```

The full default output paths must be:

```text
corpus/04_transcripts/tv_com_1950_1.txt
corpus/04_transcripts/tv_com_1950_1.json
```

---

## 8.5 Existing files

If both output transcript files already exist and `--reprocess` is not enabled:

- do not call Whisper;
- mark the item as `skipped_existing`;
- log the skip;
- include the item in the manifest.

If only one of the two output files exists:

- treat the commercial as incomplete;
- transcribe again unless both outputs exist;
- overwrite the incomplete outputs.

If `--reprocess` is enabled:

- call Whisper;
- overwrite both existing output files.

---

## 8.6 Missing source audio

If the expected source audio does not exist:

```text
corpus/03_audio/<Commercial ID>.wav
```

The programme must:

- not call Whisper;
- mark the item as `missing_input`;
- include the expected input path in the manifest;
- log the missing input;
- continue processing other commercials.

Missing source audio files should cause a non-zero exit code because the corresponding eligible commercial could not be transcribed.

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
python transcribe_commercials_whisper.py \
  --no-test-mode \
  --start-commercial-id tv_com_1950_25
```

---

## 8.8 Transcript text normalisation

The plain-text transcript should be produced by:

1. Collecting all segment texts in order.
2. Stripping leading/trailing whitespace from each segment.
3. Removing empty segment texts.
4. Joining remaining segment texts with a single space.
5. Collapsing repeated whitespace.
6. Writing the result with a trailing newline.

Example:

```text
Now with new improved flavor. Ask your pharmacist today.
```

The implementation should not perform heavy linguistic normalisation at this stage.

It should not:

- lowercase text;
- remove punctuation;
- remove fillers;
- remove brand names;
- stem or lemmatise words;
- remove stopwords.

Those operations belong to later corpus-analysis stages.

---

## 8.9 Segment timestamps

The JSON transcript must preserve segment timestamps.

Each segment should include at least:

```json
{
  "id": 1,
  "start": 0.0,
  "end": 4.28,
  "text": "Now with new improved flavor."
}
```

If the backend provides additional useful fields, they may be included, but the first implementation should keep the JSON simple and stable.

---

## 8.10 Whisper failures

If Whisper transcription raises an exception, returns invalid output, or cannot write transcript files, the programme must:

- capture the failure;
- mark the commercial as `failed`;
- save a short error summary in the manifest;
- log the failure;
- continue with the next commercial.

The programme must not stop the entire batch because one commercial fails.

---

## 8.11 Retries

For failures that may be transient, the programme should retry up to `--max-retries`.

Retry behaviour:

- retry failed transcription attempts;
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
    "tool_name": "transcribe_commercials_whisper.py",
    "tool_version": "v1",
    "start_time": "2026-05-20T14:30:12Z",
    "end_time": "2026-05-20T15:42:08Z",
    "test_mode": true,
    "test_limit": 5,
    "reprocess": false,
    "workers": 1,
    "metadata_path": "corpus/00_sources/tv_commercials.ndjson",
    "input_dir": "corpus/03_audio",
    "output_dir": "corpus/04_transcripts",
    "log_file": "corpus/04_transcripts/transcribe_commercials_whisper.log",
    "manifest_file": "corpus/04_transcripts/transcribe_commercials_whisper_manifest.json",
    "config": {
      "backend": "faster-whisper",
      "model_name": "large-v3",
      "device": "cuda",
      "compute_type": "float16",
      "language": "en",
      "task": "transcribe",
      "beam_size": 5,
      "vad_filter": true,
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
      "input_path": "corpus/03_audio/tv_com_1950_1.wav",
      "text_output_path": "corpus/04_transcripts/tv_com_1950_1.txt",
      "json_output_path": "corpus/04_transcripts/tv_com_1950_1.json",
      "status": "success",
      "error": null,
      "return_code": null,
      "retries": 0,
      "duration_seconds": 4.83,
      "start_time": "2026-05-20T14:30:15Z",
      "end_time": "2026-05-20T14:30:20Z",
      "transcript_characters": 248,
      "segment_count": 8,
      "detected_language": "en",
      "language_probability": 0.998,
      "metadata": {
        "title": "Norwich Liquid Peptans",
        "decade": "1950",
        "sequence": 1,
        "category": "Health, Beauty & Personal Care",
        "video_id": "video_0001",
        "url": "https://youtu.be/G-zZFNf4PqQ",
        "source_start": "0:00:00",
        "source_end": "0:00:59"
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
| `success` | Commercial audio was transcribed successfully |
| `failed` | Transcription was attempted but failed |
| `skipped_existing` | Transcript files already existed and `--reprocess` was not enabled |
| `missing_input` | Source audio file was missing |
| `failed_metadata` | Metadata record was invalid and could not be planned |

---

## 9.3 Error field

The `error` field must be:

- `null` when there is no error;
- a short string when an error occurs.

Example:

```json
{
  "commercial_id": "tv_com_1950_1",
  "input_path": "corpus/03_audio/tv_com_1950_1.wav",
  "text_output_path": "corpus/04_transcripts/tv_com_1950_1.txt",
  "json_output_path": "corpus/04_transcripts/tv_com_1950_1.json",
  "status": "failed",
  "error": "CUDA out of memory while transcribing audio",
  "return_code": null,
  "retries": 1
}
```

---

# 10. Logging Specification

The programme must write an append-only log file.

Default:

```text
corpus/04_transcripts/transcribe_commercials_whisper.log
```

## Log format

Each line should follow this format:

```text
[YYYY-MM-DD HH:MM:SS] LEVEL  message
```

Example:

```text
[2026-05-20 14:30:12] INFO  Starting transcribe_commercials_whisper.py run_id=20260520T143012Z
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
- transcription backend;
- model name;
- device;
- compute type;
- language;
- task;
- beam size;
- VAD setting;
- dependency availability;
- model loading start;
- model loading success;
- model loading failure;
- number of metadata records read;
- number of records eligible because `Download Success` is `True`;
- number of records ignored because `Download Success` is not `True`;
- number of invalid metadata records;
- number of planned transcriptions;
- each skipped existing transcript;
- each missing source audio file;
- each successful transcription;
- each failed transcription;
- each retry attempt;
- manifest write paths;
- end-of-run summary;
- keyboard interrupts;
- validation/configuration errors.

## Example log lines

```text
[2026-05-20 14:30:12] INFO  Starting transcribe_commercials_whisper.py run_id=20260520T143012Z
[2026-05-20 14:30:12] INFO  Metadata path: corpus/00_sources/tv_commercials.ndjson
[2026-05-20 14:30:12] INFO  Input directory: corpus/03_audio
[2026-05-20 14:30:12] INFO  Output directory: corpus/04_transcripts
[2026-05-20 14:30:12] INFO  Model: backend=faster-whisper model=large-v3 device=cuda compute_type=float16
[2026-05-20 14:30:12] INFO  Transcription: language=en task=transcribe beam_size=5 vad_filter=true
[2026-05-20 14:30:12] INFO  Test mode: true; test_limit=5
[2026-05-20 14:30:13] INFO  Loading Whisper model large-v3
[2026-05-20 14:30:22] INFO  Whisper model loaded successfully
[2026-05-20 14:30:23] INFO  Found 960 metadata records; 958 eligible for transcription
[2026-05-20 14:30:28] INFO  SUCCESS tv_com_1950_1 -> corpus/04_transcripts/tv_com_1950_1.txt
[2026-05-20 15:42:08] INFO  Wrote latest manifest: corpus/04_transcripts/transcribe_commercials_whisper_manifest.json
[2026-05-20 15:42:08] INFO  Finished run: succeeded=5 failed=0 skipped_existing=0 missing_input=0
```

---

# 11. Error Handling and Resiliency

## 11.1 Configuration errors

Configuration errors must stop the programme before transcription begins.

Examples:

- metadata file missing;
- metadata file unreadable;
- metadata file contains invalid JSON;
- input directory missing;
- output directory cannot be created;
- invalid command-line arguments;
- start commercial ID not found when `--start-commercial-id` is provided;
- `faster_whisper` is not installed;
- CUDA requested but not available;
- Whisper model cannot be loaded.

The programme must exit non-zero.

---

## 11.2 Per-commercial errors

Per-commercial errors must not stop the full run.

Examples:

- source audio file missing;
- unreadable audio file;
- unsupported audio format;
- corrupted audio;
- audio file with no speech;
- CUDA out-of-memory error during one item;
- backend transcription exception;
- output text file cannot be written;
- output JSON file cannot be written.

For each per-commercial error:

- mark the item as one of:
  - `missing_input`
  - `failed_metadata`
  - `failed`
- capture a short error message;
- log the error;
- continue to the next item.

---

## 11.3 Empty or no-speech transcriptions

If Whisper returns no segments or an empty transcript:

- the item may still be marked as `success` if the backend completed without error;
- the `.txt` file should be written as an empty or near-empty UTF-8 file with a trailing newline;
- the `.json` file should record:
  - empty text;
  - zero segments;
  - detected language information if available.

This situation should be logged as a warning:

```text
WARNING Empty transcript for tv_com_1950_1
```

Empty transcripts should not automatically be treated as programme failures because some commercials may contain music, jingles, or little/no speech.

---

## 11.4 Keyboard interruption

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

## 11.5 Exit codes

The programme must use the following exit-code conventions:

| Exit code | Meaning |
|---:|---|
| `0` | Completed with no failed attempted transcriptions, no missing inputs, and no invalid eligible metadata rows |
| `1` | Completed, but one or more transcriptions failed, source audio files were missing, or eligible metadata rows were invalid |
| `2` | Configuration or validation error |
| `130` | Interrupted by user |

Skipped existing files are not failures.

Rows where `Download Success` is not `True` are not failures.

Empty transcripts are not failures if transcription completed normally.

---

# 12. Docstrings and In-code Documentation

The implementation must include clear docstrings.

## 12.1 Module-level docstring

At the top of `transcribe_commercials_whisper.py`, include a module-level docstring explaining:

- purpose of the programme;
- expected input metadata file;
- source audio input directory;
- transcript output directory;
- use of Whisper Large v3;
- use of `faster-whisper`;
- EC2/GPU recommendation;
- default test mode;
- resumability behaviour;
- example commands.

Suggested module docstring:

```python
"""
Transcribe television commercial audio files with Whisper Large v3.

This script reads commercial metadata from an NDJSON file, selects records where
"Download Success" is true, and transcribes one WAV audio file per eligible
commercial using Whisper Large v3 through the faster-whisper backend.

Source audio files are expected in the input directory as "<Commercial ID>.wav".
Transcript outputs are written to the output directory as "<Commercial ID>.txt"
and "<Commercial ID>.json".

The plain-text transcript is intended for corpus linguistic analysis. The JSON
transcript preserves segment timestamps, model configuration, and source
metadata for reproducibility.

By default, the script runs in test mode and attempts only the first 5 planned
commercials. Existing transcript files are skipped unless --reprocess is
provided, making the script safe to re-run.

The recommended deployment environment is an x86_64 EC2 GPU instance using a
Python 3.11 environment with faster-whisper installed.

Example:
    python transcribe_commercials_whisper.py

Full run:
    python transcribe_commercials_whisper.py --no-test-mode

Full run from a specific commercial:
    python transcribe_commercials_whisper.py --no-test-mode --start-commercial-id tv_com_1950_25

The script writes an append-only log file and JSON manifests describing
run-level metadata and per-commercial transcription status.
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
- `plan_transcriptions`
- `load_whisper_model`
- `transcribe_one_commercial`
- `write_transcript_outputs`
- `write_manifests`
- `main`

---

# 13. Suggested Constants

The implementation should define constants near the top of the file:

```python
TOOL_NAME = "transcribe_commercials_whisper.py"
TOOL_VERSION = "v1"

DEFAULT_METADATA_PATH = "corpus/00_sources/tv_commercials.ndjson"
DEFAULT_INPUT_DIR = "corpus/03_audio"
DEFAULT_OUTPUT_DIR = "corpus/04_transcripts"
DEFAULT_LOG_FILE = "corpus/04_transcripts/transcribe_commercials_whisper.log"
DEFAULT_MANIFEST_FILE = "corpus/04_transcripts/transcribe_commercials_whisper_manifest.json"

DEFAULT_MODEL_NAME = "large-v3"
DEFAULT_BACKEND = "faster-whisper"
DEFAULT_DEVICE = "cuda"
DEFAULT_COMPUTE_TYPE = "float16"
DEFAULT_LANGUAGE = "en"
DEFAULT_TASK = "transcribe"
DEFAULT_BEAM_SIZE = 5
DEFAULT_VAD_FILTER = True

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 5
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 5

INPUT_AUDIO_EXTENSION = ".wav"
OUTPUT_TEXT_EXTENSION = ".txt"
OUTPUT_JSON_EXTENSION = ".json"
```

---

# 14. Development Notes

## Initial implementation scope

The first implementation should prioritise:

- correct sequential execution;
- loading the model only once;
- reliable metadata filtering by `Download Success`;
- robust input-file checking;
- clean `.txt` transcript output;
- detailed `.json` transcript output;
- reliable logging;
- robust manifest output;
- safe resumability;
- optional start-commercial-ID support;
- clear error handling.

Parallel transcription should not be implemented in the first version because GPU memory management is simpler and safer with sequential processing.

## Recommended implementation approach

Use the Python standard library where possible:

- `argparse`
- `json`
- `logging`
- `pathlib`
- `datetime`
- `time`
- `sys`
- `traceback`
- `importlib.util`

Use the required transcription backend:

- `faster_whisper`

Optional:

- `tqdm`

If `tqdm` is installed, it may be used for progress display. If not installed, the programme should still work.

---

# 15. Acceptance Criteria

The programme is considered complete when the following conditions are met:

1. Running:

   ```bash
   python transcribe_commercials_whisper.py
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

4. The programme uses source audio from:

   ```text
   corpus/03_audio/
   ```

5. Each source audio file is expected to exist as:

   ```text
   corpus/03_audio/<Commercial ID>.wav
   ```

6. The programme creates the output directory if needed:

   ```text
   corpus/04_transcripts/
   ```

7. Each successful transcription writes:

   ```text
   corpus/04_transcripts/<Commercial ID>.txt
   corpus/04_transcripts/<Commercial ID>.json
   ```

8. The default model is:

   ```text
   large-v3
   ```

9. The default backend is:

   ```text
   faster-whisper
   ```

10. The default device is:

    ```text
    cuda
    ```

11. The default compute type is:

    ```text
    float16
    ```

12. The default language is:

    ```text
    en
    ```

13. The default task is:

    ```text
    transcribe
    ```

14. Existing `.txt` and `.json` transcript files are skipped unless `--reprocess` is used.

15. If only one transcript output exists, the item is treated as incomplete and planned for transcription.

16. Failed transcriptions do not stop the full batch.

17. Missing input audio files are marked as `missing_input`.

18. Invalid eligible metadata rows are marked as `failed_metadata`.

19. Empty transcripts are allowed if transcription completes normally, and are logged as warnings.

20. The programme supports starting from a specific commercial ID with:

    ```bash
    --start-commercial-id COMMERCIAL_ID
    ```

21. When `--start-commercial-id COMMERCIAL_ID` is provided, the programme plans transcription from that commercial ID onward, preserving metadata order.

22. If `--start-commercial-id COMMERCIAL_ID` is not found among eligible rows, the programme exits with a configuration error.

23. A log file is written at:

    ```text
    corpus/04_transcripts/transcribe_commercials_whisper.log
    ```

24. A latest manifest is written at:

    ```text
    corpus/04_transcripts/transcribe_commercials_whisper_manifest.json
    ```

25. A timestamped per-run manifest is also written.

26. The manifest records:
    - run metadata;
    - transcription configuration;
    - start commercial ID, if any;
    - per-commercial status;
    - errors;
    - timings;
    - transcript output paths;
    - transcript character counts;
    - segment counts;
    - detected language information, if available;
    - summary counts.

27. The programme exits with:
    - `0` if all attempted transcriptions succeed or are skipped and there are no missing inputs or invalid eligible metadata rows;
    - `1` if any attempted transcription fails, any eligible input audio is missing, or any eligible metadata row is invalid;
    - `2` for configuration errors;
    - `130` for keyboard interruption.

---

# 16. Short README Section

The following section can be added to project documentation.

## Transcribe commercial audio with Whisper

The `transcribe_commercials_whisper.py` programme transcribes Whisper-ready audio files listed in:

```text
corpus/00_sources/tv_commercials.ndjson
```

Only rows where `Download Success` is `True` are processed.

Source audio files are read from:

```text
corpus/03_audio/
```

Each source audio file is identified by the `Commercial ID` field and expected to exist as:

```text
corpus/03_audio/<Commercial ID>.wav
```

Transcripts are written to:

```text
corpus/04_transcripts/
```

Each successful transcription writes both:

```text
corpus/04_transcripts/<Commercial ID>.txt
corpus/04_transcripts/<Commercial ID>.json
```

The `.txt` file contains clean transcript text for corpus analysis. The `.json` file preserves segment timestamps, model configuration, and source metadata.

The default transcription model is:

```text
Whisper Large v3
```

through the `faster-whisper` backend.

Recommended EC2 environment:

```text
x86_64 GPU instance
Python 3.11
faster-whisper
CUDA-capable NVIDIA GPU
```

Default test run:

```bash
python transcribe_commercials_whisper.py
```

This processes up to 5 eligible commercials.

Full run:

```bash
python transcribe_commercials_whisper.py --no-test-mode
```

To resume planning from a specific commercial ID onward, use:

```bash
python transcribe_commercials_whisper.py \
  --no-test-mode \
  --start-commercial-id tv_com_1950_25
```

The programme is safe to re-run: existing complete transcript outputs are skipped by default. To force re-transcription, use:

```bash
python transcribe_commercials_whisper.py --no-test-mode --reprocess
```

The programme writes:

```text
corpus/04_transcripts/transcribe_commercials_whisper.log
corpus/04_transcripts/transcribe_commercials_whisper_manifest.json
```

A timestamped per-run manifest is also created for each execution.