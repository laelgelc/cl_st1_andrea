# Specification: `describe_commercials_visual.py`

## 1. Programme Summary

`describe_commercials_visual.py` performs the **second stage** of the visual analysis pipeline for the TV commercial corpus.

It reads sampled frame sequences produced by `sample_commercials_frames.py`, submits those frames to a multimodal OpenAI model, and writes a visual description of each commercial.

The programme is designed to describe the **visual content** of commercials, not their audio content. It should not infer dialogue, music, voice-over, or slogans unless those are visually present as on-screen text in the sampled frames.

The two-stage pipeline is:

```text
Stage 1: sample_commercials_frames.py
    commercial clips → sampled frame sequences + frame manifests

Stage 2: describe_commercials_visual.py
    sampled frame sequences + prompt file → LLM visual descriptions + manifests
```

This programme does **not** sample frames. It relies on the existing frame directories and `frames_manifest.json` files created by `sample_commercials_frames.py`.

---

## 2. High-Level Functionality

For each commercial frame directory, the programme should:

1. Discover eligible frame directories under the input directory.
2. Read the per-commercial `frames_manifest.json`.
3. Load the sampled frame list from the manifest.
4. Sort frames by `frame_index` or manifest order.
5. Load a prompt from a prompt file.
6. Compute the prompt file’s SHA-256 hash for reproducibility.
7. Submit the prompt and ordered frames to a multimodal OpenAI model.
8. Save the model’s visual description as a `.txt` file.
9. Save a per-commercial `.json` record containing:
   - commercial ID;
   - prompt metadata;
   - model configuration;
   - frame metadata;
   - response text;
   - processing status;
   - error information, if any.
10. Write a run-level log and JSON manifests.
11. Skip already processed commercials unless `--reprocess` is used.

---

## 3. Input / Output

## 3.1 Input

### Input directory

Default input directory:

```text
corpus/05_frames/
```

Each commercial should have its own subdirectory:

```text
corpus/05_frames/<Commercial ID>/
```

Example:

```text
corpus/05_frames/tv_com_1950_001/
```

Each commercial frame directory is expected to contain:

```text
frames_manifest.json
frame_0001.jpg
frame_0002.jpg
frame_0003.jpg
...
```

The programme should not discover images independently unless necessary. It should primarily rely on `frames_manifest.json`.

---

## 3.2 Expected frame manifest

Each commercial directory must contain:

```text
frames_manifest.json
```

The manifest should include:

```json
{
  "commercial_id": "tv_com_1950_001",
  "status": "success",
  "frames": [
    {
      "frame_index": 1,
      "filename": "frame_0001.jpg",
      "path": "corpus/05_frames/tv_com_1950_001/frame_0001.jpg",
      "timestamp_seconds": 0.0,
      "selection_reason": "first_frame"
    }
  ]
}
```

Required fields:

```text
commercial_id
status
frames
```

For each frame:

```text
frame_index
filename or path
```

Optional but preferred fields:

```text
timestamp_seconds
selection_reason
```

Only manifests with:

```json
"status": "success"
```

should be processed by default.

If the manifest is missing, invalid, or has no usable frame entries, the commercial should be marked as failed rather than causing the whole run to stop.

---

## 3.3 Prompt input

Prompt files are stored in:

```text
describe_commercials_visual_prompts/
```

Default prompt file:

```text
describe_commercials_visual_prompts/visual_commercial_description_v1.txt
```

Available initial prompt files:

```text
describe_commercials_visual_prompts/
  visual_commercial_description_v1.txt
  visual_commercial_description_v2_lightly_structured.txt
  visual_commercial_description_v3_json.txt
```

The default prompt is the minimally directive v1 prompt:

```text
You are analyzing a television commercial for corpus-linguistic and multimodal discourse analysis.

You are given sampled frames from a video clip. The frames are in chronological order.
Treat the frames as a temporal sequence from one commercial, not as independent images.

Describe the visual content of the commercial as it unfolds over time.
Describe only what is visually supported by the frames.

Do not guess dialogue, slogans, music, voice-over, or other audio content.
If something is unclear or not visible in the sampled frames, say so.
```

The programme should accept a different prompt file through:

```bash
--prompt-file PATH
```

This allows prompt A/B testing without changing source code.

---

## 3.4 Output directory

Default output directory:

```text
corpus/06_visual_descriptions/
```

Each successfully processed commercial should produce:

```text
corpus/06_visual_descriptions/<Commercial ID>.txt
corpus/06_visual_descriptions/<Commercial ID>.json
```

Example:

```text
corpus/06_visual_descriptions/tv_com_1950_001.txt
corpus/06_visual_descriptions/tv_com_1950_001.json
```

### `.txt` output

The `.txt` file contains only the clean visual description text returned by the model.

### `.json` output

The `.json` file contains a full reproducibility record, including:

- commercial ID;
- source frame manifest path;
- output text path;
- output JSON path;
- model;
- image detail level;
- prompt file;
- prompt SHA-256;
- prompt text;
- frames submitted;
- response text;
- status;
- error;
- timing;
- creation timestamp.

---

## 3.5 Run-level outputs

The programme writes:

```text
corpus/06_visual_descriptions/describe_commercials_visual.log
corpus/06_visual_descriptions/describe_commercials_visual_manifest.json
```

It also writes a timestamped per-run manifest:

```text
corpus/06_visual_descriptions/describe_commercials_visual_manifest_<RUN_ID>.json
```

where `RUN_ID` uses UTC time in filename-safe format:

```text
YYYYMMDDTHHMMSSZ
```

Example:

```text
describe_commercials_visual_manifest_20260522T141533Z.json
```

---

# 4. LLM Request Design

## 4.1 Model

Default model:

```text
gpt-5.5
```

The programme should accept a model argument:

```bash
--model gpt-5.5
```

The model must support image inputs.

---

## 4.2 Image detail

Default image detail:

```text
low
```

Allowed values:

```text
low
high
auto
```

Argument:

```bash
--image-detail low
```

Rationale:

- `low` is cost-conscious;
- `high` can be used for tests where visual text, labels, or small objects are important;
- `auto` allows the API/model to decide when supported.

---

## 4.3 Request content order

For each commercial, the request should include:

1. The prompt text loaded from the prompt file.
2. A short neutral note identifying the frame sequence.
3. For each frame, in chronological order:
   - a text label with frame metadata;
   - the image itself.

Example logical request structure:

```text
[prompt text from file]

Frame sequence metadata:
Commercial ID: tv_com_1950_001
Number of sampled frames: 8

Frame 1 — timestamp 0.000s — selection reason: first_frame
[image frame_0001.jpg]

Frame 2 — timestamp 2.400s — selection reason: scene_change
[image frame_0002.jpg]

Frame 3 — timestamp 28.840s — selection reason: last_frame
[image frame_0003.jpg]
```

The frame labels should be factual and neutral. They should not add interpretation.

---

## 4.4 Image encoding

The programme should submit local image files as base64-encoded data URLs.

Supported image input extensions:

```text
.jpg
.jpeg
.png
```

The default frame sampler writes `.jpg`, but `.jpeg` and `.png` support allows future flexibility.

---

## 4.5 Frame count

The programme should rely on the frame cap already applied by `sample_commercials_frames.py`.

However, Stage 2 should also include a safety cap:

```text
--max-frames-per-request
```

Default:

```text
0
```

Meaning:

```text
0 = no additional cap; use all frames listed in the frame manifest
```

If `--max-frames-per-request N` is greater than zero and the manifest contains more than `N` frames, the programme should select frames using deterministic chronological even downsampling, preserving first and last frames when possible.

This provides an additional budget safeguard without changing Stage 1 outputs.

---

## 4.6 Temperature and generation settings

Default:

```text
temperature = 0
```

Argument:

```bash
--temperature 0
```

Rationale:

- visual descriptions should be stable and reproducible;
- lower temperature reduces unnecessary variation.

If a specific model does not support `temperature`, the implementation should either omit the parameter or fail clearly, depending on the API behavior.

Optional future arguments:

```text
--max-output-tokens
--top-p
```

For the first implementation, only `--temperature` is required.

---

# 5. Command-Line Interface

## 5.1 Default test run

```bash
python describe_commercials_visual.py
```

Default behavior:

```text
input_dir = corpus/05_frames/
output_dir = corpus/06_visual_descriptions/
prompt_file = describe_commercials_visual_prompts/visual_commercial_description_v1.txt
model = gpt-5.5
image_detail = low
temperature = 0
test_mode = true
test_limit = 5
reprocess = false
workers = 1
```

---

## 5.2 Full run

```bash
python describe_commercials_visual.py --no-test-mode
```

---

## 5.3 Use a different prompt

```bash
python describe_commercials_visual.py \
  --prompt-file describe_commercials_visual_prompts/visual_commercial_description_v2_lightly_structured.txt
```

---

## 5.4 Use a structured JSON prompt

```bash
python describe_commercials_visual.py \
  --prompt-file describe_commercials_visual_prompts/visual_commercial_description_v3_json.txt
```

If the prompt asks for JSON, the programme should still save:

```text
<Commercial ID>.txt
<Commercial ID>.json
```

The `.txt` file contains the raw model output. The `.json` file wraps that output in the programme’s metadata structure. The first implementation does not need to validate the model-generated JSON.

---

## 5.5 Reprocess existing descriptions

```bash
python describe_commercials_visual.py --no-test-mode --reprocess
```

---

## 5.6 Change model

```bash
python describe_commercials_visual.py \
  --no-test-mode \
  --model gpt-5.5
```

---

## 5.7 Use higher image detail

```bash
python describe_commercials_visual.py \
  --no-test-mode \
  --image-detail high
```

---

## 5.8 Add a Stage 2 safety frame cap

```bash
python describe_commercials_visual.py \
  --no-test-mode \
  --max-frames-per-request 20
```

---

## 5.9 Resume from a specific commercial ID

```bash
python describe_commercials_visual.py \
  --no-test-mode \
  --start-commercial-id tv_com_1950_025
```

This should process only commercials whose inferred commercial ID is greater than or equal to the provided ID in sorted order.

---

# 6. CLI Arguments

## 6.1 Required arguments

No CLI arguments are required for the default test run, provided that:

- `corpus/05_frames/` exists;
- the default prompt file exists;
- `OPENAI_API_KEY` is available.

---

## 6.2 Standard arguments

| Argument | Default | Description |
|---|---:|---|
| `--input-dir PATH` | `corpus/05_frames` | Directory containing per-commercial sampled frame folders |
| `--output-dir PATH` | `corpus/06_visual_descriptions` | Directory where descriptions are written |
| `--prompt-file PATH` | `describe_commercials_visual_prompts/visual_commercial_description_v1.txt` | Prompt text file |
| `--model MODEL` | `gpt-5.5` | OpenAI multimodal model |
| `--image-detail {low,high,auto}` | `low` | Image detail level |
| `--temperature FLOAT` | `0` | Generation temperature |
| `--test-mode` | enabled | Limit processing to `--test-limit` items |
| `--no-test-mode` | disabled | Process all eligible items |
| `--test-limit N` | `5` | Maximum items to attempt in test mode |
| `--reprocess` | `False` | Regenerate outputs even if they already exist |
| `--workers N` | `1` | Number of worker processes or threads |
| `--log-file PATH` | `<output-dir>/describe_commercials_visual.log` | Log file path |
| `--manifest-file PATH` | `<output-dir>/describe_commercials_visual_manifest.json` | Latest run manifest |
| `--start-commercial-id ID` | `None` | Resume from this commercial ID onward |
| `--max-frames-per-request N` | `0` | Optional extra cap on frames sent to the model; `0` means no cap |

---

## 6.3 Optional future arguments

| Argument | Purpose |
|---|---|
| `--max-output-tokens N` | Limit response length |
| `--timeout SECONDS` | Per-request timeout |
| `--max-retries N` | Retry transient API failures |
| `--retry-backoff-seconds FLOAT` | Initial backoff for retries |
| `--metadata-file PATH` | Enrich descriptions with commercial metadata |
| `--response-format text/json` | Request or validate a particular output shape |
| `--dry-run` | Plan processing without API calls |
| `--save-request-json` | Save sanitized request payloads for debugging |
| `--no-prompt-text-in-json` | Do not store full prompt text in per-commercial JSON |

For the first implementation, retry support is recommended but not strictly required.

---

# 7. Argument Validation

The programme should fail early with clear messages if:

- `--input-dir` does not exist;
- `--input-dir` is not readable;
- `--prompt-file` does not exist;
- `--prompt-file` is empty;
- `--output-dir` cannot be created;
- `--test-limit <= 0`;
- `--workers <= 0`;
- `--image-detail` is not one of `low`, `high`, or `auto`;
- `--temperature < 0`;
- `--max-frames-per-request < 0`;
- `OPENAI_API_KEY` is missing;
- the OpenAI Python package is unavailable.

The programme should not begin API processing unless these configuration checks pass.

---

# 8. Environment and Configuration

## 8.1 API key

The programme requires:

```text
OPENAI_API_KEY
```

The key should be loaded using this priority order:

```text
1. env/.env, if present
2. system environment variables
```

System environment variables should override values from `env/.env`.

The `.env` loader can be lightweight and standard-library based.

Expected `.env` format:

```text
OPENAI_API_KEY=sk-...
```

Lines beginning with `#` should be ignored.

Blank lines should be ignored.

The programme must not log the API key.

---

## 8.2 Prompt configuration

The prompt file path is provided through:

```bash
--prompt-file
```

The programme should record:

- prompt file path;
- prompt SHA-256;
- prompt text, unless disabled in a future option.

This ensures prompt reproducibility.

---

# 9. External Dependencies

The programme requires the OpenAI Python SDK.

Expected import:

```python
from openai import OpenAI
```

No FFmpeg dependency is required for this stage.

The programme does not perform video decoding or frame sampling.

It reads existing image files.

---

# 10. Processing Architecture

## 10.1 Startup

At startup, the programme should:

1. Parse CLI arguments.
2. Load `env/.env`, if present.
3. Validate arguments.
4. Verify `OPENAI_API_KEY`.
5. Load and validate prompt file.
6. Compute prompt SHA-256.
7. Create the output directory if needed.
8. Configure logging.
9. Create a run ID.
10. Log configuration summary.

Example startup log:

```text
[2026-05-22 14:15:33] INFO   Starting visual description run
[2026-05-22 14:15:33] INFO   Model: gpt-5.5
[2026-05-22 14:15:33] INFO   Input dir: corpus/05_frames
[2026-05-22 14:15:33] INFO   Output dir: corpus/06_visual_descriptions
[2026-05-22 14:15:33] INFO   Prompt file: describe_commercials_visual_prompts/visual_commercial_description_v1.txt
[2026-05-22 14:15:33] INFO   Prompt SHA-256: 5f...
[2026-05-22 14:15:33] INFO   Image detail: low
[2026-05-22 14:15:33] INFO   Test mode: True (limit=5)
[2026-05-22 14:15:33] INFO   Reprocess existing: False
[2026-05-22 14:15:33] INFO   Workers: 1
```

---

## 10.2 Discovery

The programme should:

1. List subdirectories directly under `--input-dir`.
2. Keep only those containing `frames_manifest.json`.
3. Read commercial ID from the manifest when possible.
4. Fall back to directory name if needed.
5. Sort deterministically by commercial ID.
6. Apply `--start-commercial-id`, if provided.

Discovery summary:

```text
[2026-05-22 14:15:34] INFO   Discovered 742 commercial frame directories
```

---

## 10.3 Planning

For each discovered commercial, determine:

```text
commercial_id
frame_dir
frame_manifest_path
output_text_path
output_json_path
status: process or skipped_existing
```

A commercial should be skipped if all of the following are true:

- `--reprocess` is false;
- `<Commercial ID>.txt` exists;
- `<Commercial ID>.json` exists;
- the JSON output status indicates prior success.

If outputs are incomplete or JSON is missing/corrupt, the item should be reprocessed.

Test mode should apply to items that would be attempted, not to already-skipped items.

---

## 10.4 Execution model

### Recommended initial implementation

Because each item requires an external API call, the programme can support:

```text
workers = 1
```

as the safest default.

If `--workers > 1` is implemented, use a `ThreadPoolExecutor`, not `ProcessPoolExecutor`, because the workload is primarily network-bound.

Workers should:

- load frame images;
- encode images as base64 data URLs;
- call the OpenAI API;
- return structured result data.

The main process should:

- plan work;
- log results;
- write outputs and manifests when practical.

It is acceptable for workers to write per-commercial `.txt` and `.json` outputs if each worker writes to distinct paths.

---

# 11. Per-Commercial Processing Details

## 11.1 Read frame manifest

The programme should read:

```text
corpus/05_frames/<Commercial ID>/frames_manifest.json
```

It should require:

```json
"status": "success"
```

It should read frames from:

```json
"frames"
```

The frame list should be sorted by:

```text
frame_index
```

If `frame_index` is missing, use manifest order.

---

## 11.2 Resolve frame paths

Each frame entry may contain:

```json
"path": "corpus/05_frames/tv_com_1950_001/frame_0001.jpg"
```

or:

```json
"filename": "frame_0001.jpg"
```

Resolution rules:

1. If `path` exists, use it.
2. Else, if `filename` exists, resolve relative to the frame directory.
3. Else, mark the item as failed.

If any listed frame file is missing, mark the item as failed.

Supported frame extensions:

```text
.jpg
.jpeg
.png
```

---

## 11.3 Optional Stage 2 frame cap

If:

```text
--max-frames-per-request 0
```

send all frames from the manifest.

If:

```text
--max-frames-per-request N
```

and the frame count exceeds `N`, apply chronological even downsampling.

This should preserve the first and last frames when possible.

The per-commercial JSON output should record:

```json
"stage2_frame_cap_applied": true
```

and:

```json
"submitted_frame_count": 20
```

---

## 11.4 Build request content

The programme should build a multimodal request containing:

1. Prompt text.
2. Frame sequence metadata.
3. Alternating frame labels and image inputs.

Each frame label should include:

```text
Frame <frame_index> — timestamp <timestamp_seconds>s — selection reason: <selection_reason>
```

If timestamp is missing:

```text
Frame <frame_index> — timestamp unknown — selection reason: <selection_reason>
```

If selection reason is missing:

```text
selection reason: unknown
```

Example:

```text
Frame 1 — timestamp 0.000s — selection reason: first_frame
```

The frame label should be sent as text immediately before the corresponding image.

---

## 11.5 API call

The first implementation should use the OpenAI Responses API.

Conceptual structure:

```python
client.responses.create(
    model=args.model,
    input=[
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt_text},
                {"type": "input_text", "text": "Commercial ID: ..."},
                {"type": "input_text", "text": "Frame 1 — timestamp ..."},
                {"type": "input_image", "image_url": "...", "detail": "low"},
                ...
            ],
        }
    ],
)
```

The programme should extract the final text from:

```python
response.output_text
```

If `response.output_text` is unavailable, the programme should fail clearly for that item and record the error.

---

## 11.6 Save outputs

For each successful commercial, write:

```text
corpus/06_visual_descriptions/<Commercial ID>.txt
corpus/06_visual_descriptions/<Commercial ID>.json
```

The `.txt` file should contain exactly the model’s visual description text, stripped of leading/trailing whitespace and ending with a newline.

The `.json` file should contain the full programme metadata and response text.

---

# 12. Per-Commercial JSON Output

Example:

```json
{
  "commercial_id": "tv_com_1950_001",
  "status": "success",
  "model": "gpt-5.5",
  "image_detail": "low",
  "temperature": 0,
  "prompt": {
    "prompt_file": "describe_commercials_visual_prompts/visual_commercial_description_v1.txt",
    "prompt_sha256": "abc123...",
    "prompt_text": "You are analyzing..."
  },
  "input": {
    "frame_dir": "corpus/05_frames/tv_com_1950_001",
    "frame_manifest_path": "corpus/05_frames/tv_com_1950_001/frames_manifest.json",
    "source_video": "corpus/02_commercials/tv_com_1950_001.mp4",
    "stage1_sampling_config": {
      "strategy": "scene_change_with_first_last",
      "scene_threshold": 0.25,
      "max_frames": 30
    }
  },
  "frames": [
    {
      "frame_index": 1,
      "filename": "frame_0001.jpg",
      "path": "corpus/05_frames/tv_com_1950_001/frame_0001.jpg",
      "timestamp_seconds": 0.0,
      "selection_reason": "first_frame"
    }
  ],
  "frame_counts": {
    "manifest_frame_count": 8,
    "submitted_frame_count": 8,
    "stage2_frame_cap_applied": false,
    "max_frames_per_request": 0
  },
  "output": {
    "text_path": "corpus/06_visual_descriptions/tv_com_1950_001.txt",
    "json_path": "corpus/06_visual_descriptions/tv_com_1950_001.json",
    "response_text": "The commercial opens with..."
  },
  "api_metadata": {
    "response_id": "resp_...",
    "usage": {
      "input_tokens": 1234,
      "output_tokens": 432,
      "total_tokens": 1666
    }
  },
  "duration_seconds": 8.42,
  "created_at": "2026-05-22T14:17:02Z",
  "error": null
}
```

If failed:

```json
{
  "commercial_id": "tv_com_1950_001",
  "status": "failed",
  "error": "Missing frame file: corpus/05_frames/tv_com_1950_001/frame_0003.jpg",
  "created_at": "2026-05-22T14:17:02Z"
}
```

Failed per-commercial JSON files are optional but recommended.

---

# 13. Run-Level Manifest

The latest manifest should be written to:

```text
corpus/06_visual_descriptions/describe_commercials_visual_manifest.json
```

A timestamped manifest should also be written to:

```text
corpus/06_visual_descriptions/describe_commercials_visual_manifest_<RUN_ID>.json
```

Example structure:

```json
{
  "run_metadata": {
    "run_id": "20260522T141533Z",
    "tool_name": "describe_commercials_visual",
    "version": "v1",
    "start_time": "2026-05-22T14:15:33Z",
    "end_time": "2026-05-22T14:30:11Z",
    "test_mode": true,
    "test_limit": 5,
    "reprocess": false,
    "workers": 1,
    "input_source": "corpus/05_frames",
    "output_dir": "corpus/06_visual_descriptions",
    "config": {
      "model": "gpt-5.5",
      "image_detail": "low",
      "temperature": 0,
      "prompt_file": "describe_commercials_visual_prompts/visual_commercial_description_v1.txt",
      "prompt_sha256": "abc123...",
      "max_frames_per_request": 0
    }
  },
  "files": [
    {
      "commercial_id": "tv_com_1950_001",
      "input_path": "corpus/05_frames/tv_com_1950_001",
      "output_path": "corpus/06_visual_descriptions/tv_com_1950_001.txt",
      "json_path": "corpus/06_visual_descriptions/tv_com_1950_001.json",
      "status": "success",
      "error": null,
      "duration_seconds": 8.42,
      "timestamp": "2026-05-22T14:17:02Z",
      "metadata": {
        "model": "gpt-5.5",
        "manifest_frame_count": 8,
        "submitted_frame_count": 8,
        "stage2_frame_cap_applied": false,
        "response_id": "resp_...",
        "usage": {
          "input_tokens": 1234,
          "output_tokens": 432,
          "total_tokens": 1666
        }
      }
    }
  ],
  "summary": {
    "discovered": 742,
    "planned": 5,
    "skipped_existing": 0,
    "attempted": 5,
    "succeeded": 5,
    "failed": 0
  }
}
```

---

# 14. Logging Specification

The programme should write logs to:

```text
corpus/06_visual_descriptions/describe_commercials_visual.log
```

Log format:

```text
[YYYY-MM-DD HH:MM:SS] LEVEL  message
```

Minimum log events:

- startup;
- configuration summary;
- prompt file and prompt hash;
- API key presence check, without printing the key;
- discovery summary;
- planning summary;
- test-mode status;
- per-item skip;
- per-item success;
- per-item failure;
- retry attempts, if implemented;
- manifest writing;
- end-of-run summary;
- keyboard interrupt;
- fatal configuration errors.

Example:

```text
[2026-05-22 14:15:33] INFO   Starting visual description run
[2026-05-22 14:15:33] INFO   Model: gpt-5.5
[2026-05-22 14:15:33] INFO   Prompt file: describe_commercials_visual_prompts/visual_commercial_description_v1.txt
[2026-05-22 14:15:33] INFO   Prompt SHA-256: abc123...
[2026-05-22 14:15:33] INFO   Image detail: low
[2026-05-22 14:15:34] INFO   Discovered 742 commercial frame directories
[2026-05-22 14:15:34] INFO   Planned 5 commercials for processing
[2026-05-22 14:17:02] INFO   SUCCESS tv_com_1950_001 frames=8 response_id=resp_...
[2026-05-22 14:17:11] INFO   SUCCESS tv_com_1950_002 frames=11 response_id=resp_...
[2026-05-22 14:30:11] INFO   Wrote manifest: corpus/06_visual_descriptions/describe_commercials_visual_manifest.json
[2026-05-22 14:30:11] INFO   Completed visual description run: attempted=5 succeeded=5 failed=0 skipped_existing=0
```

Failure example:

```text
[2026-05-22 14:18:09] ERROR  FAILED tv_com_1950_003 Missing frame file: corpus/05_frames/tv_com_1950_003/frame_0004.jpg
```

Skip example:

```text
[2026-05-22 14:18:09] INFO   SKIPPED_EXISTING tv_com_1950_004 corpus/06_visual_descriptions/tv_com_1950_004.txt
```

---

# 15. Error Handling

## 15.1 Configuration errors

Configuration errors should stop the programme before processing begins.

Examples:

- missing input directory;
- missing prompt file;
- empty prompt file;
- missing `OPENAI_API_KEY`;
- missing OpenAI Python package;
- output directory cannot be created;
- invalid CLI argument values.

Exit code:

```text
2
```

---

## 15.2 Per-item errors

Per-commercial errors should not abort the whole run.

If one commercial fails:

1. Mark it as `failed`.
2. Write a failure record to the run manifest.
3. Optionally write a per-commercial failure JSON.
4. Log the error.
5. Continue with the next commercial.

Examples:

- missing `frames_manifest.json`;
- invalid frame manifest JSON;
- Stage 1 manifest status not `success`;
- missing frame file;
- unsupported image extension;
- OpenAI API request fails;
- model response has no text output.

Exit code should be non-zero if any attempted item failed.

Recommended exit codes:

```text
0 = all attempted items succeeded or were skipped
1 = one or more per-item failures
2 = configuration or argument error
130 = interrupted by user
```

---

## 15.3 Retry behavior

The first implementation may include basic retry support.

Recommended arguments:

```text
--max-retries 2
--retry-backoff-seconds 5
```

If implemented, retry only likely transient API failures, such as:

- rate limits;
- temporary service errors;
- network timeouts.

Do not retry permanent local failures, such as:

- missing frame files;
- invalid manifest;
- empty prompt;
- unsupported image extension.

Retry attempts should be logged at `WARNING` level.

---

## 15.4 Keyboard interrupt

On `KeyboardInterrupt`, the programme should:

1. Stop submitting new work.
2. Allow current item to finish if practical.
3. Write a partial run manifest.
4. Log interruption.
5. Exit with code `130`.

---

# 16. Resumability and Safe Re-runs

By default, the programme must be safe to re-run.

If a commercial already has successful outputs, it should be skipped.

A commercial is considered successfully processed if:

- `<Commercial ID>.txt` exists;
- `<Commercial ID>.json` exists;
- the JSON output has:

```json
"status": "success"
```

Default:

```text
reprocess = false
```

To force regeneration:

```bash
python describe_commercials_visual.py --no-test-mode --reprocess
```

When reprocessing, the programme should overwrite both the `.txt` and `.json` outputs for that commercial.

---

# 17. Test Mode

Test mode is enabled by default.

Default:

```text
test_mode = true
test_limit = 5
```

Default command:

```bash
python describe_commercials_visual.py
```

should process up to 5 commercials that need processing.

Full run:

```bash
python describe_commercials_visual.py --no-test-mode
```

The log should clearly indicate when test mode is enabled:

```text
[2026-05-22 14:15:33] INFO   Test mode: True (limit=5)
```

Test mode should apply to items that would be attempted, not to already-skipped existing outputs.

---

# 18. Parallel Processing

The default worker count should be:

```text
workers = 1
```

If multiple workers are used:

```bash
python describe_commercials_visual.py --no-test-mode --workers 4
```

the programme should use a `ThreadPoolExecutor`.

Rationale:

- API calls are network-bound;
- image encoding and request submission do not require separate processes;
- thread workers avoid unnecessary process overhead.

The programme should be careful with API rate limits when `workers > 1`.

If retry support is implemented, it should work safely in parallel mode.

---

# 19. Docstring Requirements

The implementation must include a module-level docstring explaining:

- purpose of the programme;
- role as Stage 2 after frame sampling;
- input directory and expected frame structure;
- output directory and output files;
- prompt file behavior;
- model behavior;
- example commands;
- note that this programme does not sample frames;
- note that it requires `OPENAI_API_KEY`.

Example module-level docstring:

```python
"""
Describe the visual content of sampled TV commercial frames using a multimodal LLM.

This programme is Stage 2 of the visual analysis pipeline. It reads frame
directories produced by sample_commercials_frames.py, submits ordered sampled
frames to an OpenAI multimodal model, and writes a visual description for each
commercial.

Default input:
    corpus/05_frames/

Default output:
    corpus/06_visual_descriptions/

Default prompt:
    describe_commercials_visual_prompts/visual_commercial_description_v1.txt

Typical usage:
    python describe_commercials_visual.py
    python describe_commercials_visual.py --no-test-mode
    python describe_commercials_visual.py --prompt-file describe_commercials_visual_prompts/visual_commercial_description_v2_lightly_structured.txt

The programme does not sample video frames. It uses existing frames and
frames_manifest.json files created by the frame sampling stage.

Requires OPENAI_API_KEY in env/.env or the system environment.
"""
```

Core functions should include docstrings, especially:

- argument parsing;
- environment loading;
- prompt loading;
- prompt hashing;
- discovery;
- planning;
- frame manifest reading;
- frame path resolution;
- image encoding;
- request construction;
- API submission;
- per-commercial output writing;
- run manifest writing;
- main orchestration.

---

# 20. Recommended Internal Functions

The implementation should be organized around small, testable functions.

Suggested functions:

```python
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""


def load_dotenv(dotenv_path: Path) -> dict[str, str]:
    """Load simple KEY=VALUE pairs from env/.env without logging secrets."""


def validate_args(args: argparse.Namespace) -> None:
    """Validate CLI arguments and fail early on configuration errors."""


def load_prompt(prompt_file: Path) -> str:
    """Load and validate the prompt text."""


def sha256_text(text: str) -> str:
    """Return the SHA-256 hash of prompt text."""


def discover_frame_dirs(input_dir: Path) -> list[FrameItem]:
    """Discover commercial frame directories containing frames_manifest.json."""


def plan_work(items: list[FrameItem], args: argparse.Namespace) -> list[WorkItem]:
    """Determine which commercials should be processed or skipped."""


def read_frame_manifest(manifest_path: Path) -> dict:
    """Read and validate a Stage 1 frames_manifest.json file."""


def resolve_frame_paths(frame_dir: Path, manifest: dict) -> list[FrameInfo]:
    """Resolve frame paths listed in the Stage 1 manifest."""


def cap_frames_evenly(frames: list[FrameInfo], max_frames: int) -> tuple[list[FrameInfo], bool]:
    """Apply optional Stage 2 chronological even frame capping."""


def image_to_data_url(image_path: Path) -> str:
    """Encode a local image as a base64 data URL."""


def build_request_content(
    prompt_text: str,
    commercial_id: str,
    frames: list[FrameInfo],
    image_detail: str,
) -> list[dict]:
    """Build multimodal request content with prompt, frame labels, and images."""


def call_openai_visual_description(
    client: OpenAI,
    model: str,
    content: list[dict],
    temperature: float,
) -> tuple[str, dict]:
    """Call the OpenAI Responses API and return response text and metadata."""


def process_commercial_visual(
    work_item: WorkItem,
    config: RuntimeConfig,
) -> ProcessingResult:
    """Process one commercial frame sequence and return a structured result."""


def write_per_commercial_outputs(...) -> None:
    """Write .txt and .json outputs for one commercial."""


def write_run_manifest(...) -> None:
    """Write latest and timestamped run manifests."""


def main() -> int:
    """Main orchestration entry point."""
```

Suggested data classes:

```python
@dataclass
class FrameItem:
    commercial_id: str
    frame_dir: Path
    frame_manifest_path: Path


@dataclass
class WorkItem:
    commercial_id: str
    frame_dir: Path
    frame_manifest_path: Path
    output_text_path: Path
    output_json_path: Path


@dataclass
class FrameInfo:
    frame_index: int
    filename: str
    path: Path
    timestamp_seconds: float | None
    selection_reason: str | None


@dataclass
class RuntimeConfig:
    model: str
    image_detail: str
    temperature: float
    prompt_file: Path
    prompt_text: str
    prompt_sha256: str
    max_frames_per_request: int
    max_retries: int
    retry_backoff_seconds: float


@dataclass
class ProcessingResult:
    commercial_id: str
    input_path: Path
    output_path: Path
    json_path: Path
    status: str
    error: str | None
    duration_seconds: float
    manifest_frame_count: int
    submitted_frame_count: int
    stage2_frame_cap_applied: bool
    response_id: str | None
    usage: dict | None
    timestamp: str
```

---

# 21. Prompt Files

The initial prompt directory should contain:

```text
describe_commercials_visual_prompts/
  visual_commercial_description_v1.txt
  visual_commercial_description_v2_lightly_structured.txt
  visual_commercial_description_v3_json.txt
```

## 21.1 Default prompt: v1

Path:

```text
describe_commercials_visual_prompts/visual_commercial_description_v1.txt
```

Purpose:

- minimally directive;
- open visual description;
- focuses on visual evidence only;
- avoids audio hallucination.

## 21.2 Lightly structured prompt: v2

Path:

```text
describe_commercials_visual_prompts/visual_commercial_description_v2_lightly_structured.txt
```

Purpose:

- produces more comparable outputs;
- still avoids imposing detailed theory;
- useful for later corpus inspection.

## 21.3 JSON prompt: v3

Path:

```text
describe_commercials_visual_prompts/visual_commercial_description_v3_json.txt
```

Purpose:

- produces machine-readable model output;
- useful for later structured analysis;
- first implementation does not need to validate the returned JSON.

---

# 22. README Section

A short README section should be added when the programme is implemented.

Suggested README text:

```markdown
### Describe commercial visuals

The `describe_commercials_visual.py` programme describes the visual content of
sampled commercial frames using a multimodal OpenAI model.

It is Stage 2 of the visual analysis pipeline:

1. `sample_commercials_frames.py` samples representative frames from each commercial.
2. `describe_commercials_visual.py` submits those frames to a multimodal model and
   writes a visual description.

Default input:

```text
corpus/05_frames/
```

Default output:

```text
corpus/06_visual_descriptions/
```

Default prompt:

```text
describe_commercials_visual_prompts/visual_commercial_description_v1.txt
```

Default test run:

```bash
python describe_commercials_visual.py
```

Full run:

```bash
python describe_commercials_visual.py --no-test-mode
```

Use a different prompt:

```bash
python describe_commercials_visual.py \
  --prompt-file describe_commercials_visual_prompts/visual_commercial_description_v2_lightly_structured.txt
```

Use a lower frame cap for cost control:

```bash
python describe_commercials_visual.py \
  --no-test-mode \
  --max-frames-per-request 20
```

The programme writes one `.txt` and one `.json` output per commercial:

```text
corpus/06_visual_descriptions/<Commercial ID>.txt
corpus/06_visual_descriptions/<Commercial ID>.json
```

The `.txt` file contains the visual description. The `.json` file records model,
prompt, frame, response, and reproducibility metadata.

Requires `OPENAI_API_KEY` in `env/.env` or the system environment.
```

---

# 23. Acceptance Criteria

The implementation is acceptable when:

1. `python describe_commercials_visual.py` runs in test mode by default.
2. The programme reads frame directories from `corpus/05_frames/`.
3. The programme uses `frames_manifest.json` to determine frame order.
4. The programme uses the default prompt file:
   ```text
   describe_commercials_visual_prompts/visual_commercial_description_v1.txt
   ```
5. The programme computes and records the prompt SHA-256 hash.
6. The programme submits frames in chronological order.
7. The programme labels frames with timestamp and selection-reason metadata when available.
8. The programme uses `gpt-5.5` by default.
9. The programme uses `image_detail = low` by default.
10. The programme saves:
    ```text
    corpus/06_visual_descriptions/<Commercial ID>.txt
    corpus/06_visual_descriptions/<Commercial ID>.json
    ```
11. Existing successful outputs are skipped unless `--reprocess` is used.
12. The programme writes an append-style log file.
13. The programme writes latest and timestamped run manifests.
14. Per-item failures do not stop the full run.
15. The programme exits non-zero if any attempted item fails.
16. The programme supports test mode and full-run mode.
17. The programme supports changing prompt file through `--prompt-file`.
18. The programme supports optional Stage 2 frame capping through `--max-frames-per-request`.
19. The programme does not resample video frames.
20. The programme does not require FFmpeg.
21. The programme does not log `OPENAI_API_KEY`.
22. The code includes clear module-level and function docstrings.

---

# 24. Design Rationale

This programme deliberately separates **visual input preparation** from **LLM interpretation**.

The preceding frame-sampling stage is deterministic and reproducible. This programme then uses those frozen frame sequences as evidence for LLM-based visual description.

Using prompt files rather than hard-coded prompts is important because:

- prompts can be tested without changing code;
- prompt versions can be compared;
- prompt hashes make runs reproducible;
- output differences can be traced to prompt changes.

The default prompt is intentionally minimally directive. It asks the model to describe the commercial visually, as a temporal sequence, while avoiding unsupported audio inference. This is appropriate for the first implementation because the aim is to establish a reliable baseline before introducing more structured or theory-driven prompts.

The per-commercial JSON output and run-level manifest ensure that each generated description can be traced back to:

- the exact frame manifest;
- the exact sampled frames;
- the exact prompt file;
- the prompt hash;
- the model;
- the image detail setting;
- the API response metadata.