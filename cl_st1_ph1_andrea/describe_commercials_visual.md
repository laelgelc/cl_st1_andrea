## Redesigned Specification: `describe_commercials_visual.py`

### 1. Programme purpose

`describe_commercials_visual.py` prepares commercial-specific prompt files and submits selected commercial frames, together with audio-derived transcript context, to a multimodal LLM.

The selected frames remain the primary evidence for visible content. The original `.wav` audio file is retained for provenance, but it is **not submitted** to the LLM. Instead, the corresponding Whisper/faster-whisper JSON transcript is converted into a timestamped transcript context block and inserted into the generated prompt.

The programme should:

1. Use the Markdown prompt template:

```text
describe_commercials_visual_prompts/visual_commercial_description_v5.md
```

2. Use the selected-commercial metadata table:

```text
corpus/00_sources/tv_commercials_selected_2.tsv
```

3. For each row in the TSV file, create a prompt document specific to that commercial.

4. Replace the product-context placeholder in the prompt template with the row’s `Description` value.

5. Replace the audio-derived transcript placeholder in the prompt template with a formatted context block generated from the corresponding transcript JSON file:

```text
corpus/04_transcripts/<Commercial ID>.json
```

6. Save generated prompt documents in:

```text
corpus/06_visual_descriptions_prompts/
```

7. Pair each generated prompt document with:
   - the corresponding selected frames from:

```text
corpus/05_frames_selected/
```

   - the corresponding transcript JSON file from:

```text
corpus/04_transcripts/
```

   - the corresponding commercial audio file from:

```text
corpus/03_audio/
```

8. Submit each commercial-specific prompt and selected frame sequence to the LLM.

9. Do **not** submit the raw `.wav` audio file to the LLM.

10. Save LLM responses in:

```text
corpus/06_visual_descriptions/
```

using the same output pattern currently implemented for visual-description responses.

---

### 2. Inputs

#### 2.1 Prompt template

The programme should read the Markdown prompt template from:

```text
describe_commercials_visual_prompts/visual_commercial_description_v5.md
```

This file contains a placeholder product-context paragraph:

```text
<This is a commercial for LiquidPeptans, from the 1950s. This antacid product is used for reducing acid acidity to relieve discomfort.>
```

For each commercial, this placeholder must be replaced with the value from the `Description` column in the TSV metadata file.

The prompt template also contains the audio-derived transcript context placeholder:

```text
<AUDIO_DERIVED_TRANSCRIPT_CONTEXT>
```

For each commercial, this placeholder must be replaced with a formatted Markdown context block generated from the corresponding transcript JSON file.

The programme should fail early with a clear error if:

- the prompt template file is missing;
- the prompt template is empty;
- the product-context placeholder is not found;
- the transcript-context placeholder is not found.

---

#### 2.2 Selected-commercial metadata

The programme should read:

```text
corpus/00_sources/tv_commercials_selected_2.tsv
```

The TSV file is expected to contain at least these columns:

```text
Commercial ID
Description
```

Other columns may be present and should be preserved in the per-commercial JSON metadata output where useful.

Each row represents one commercial to process.

The programme should fail early with a clear error if:

- the TSV file is missing;
- the TSV file is empty;
- the `Commercial ID` column is missing;
- the `Description` column is missing;
- a row has an empty `Commercial ID`;
- a row has an empty `Description`;
- duplicate `Commercial ID` values are present.

---

#### 2.3 Selected frame directory

The programme should use selected frames from:

```text
corpus/05_frames_selected/
```

For each commercial ID, the programme expects a directory:

```text
corpus/05_frames_selected/<Commercial ID>/
```

Example:

```text
corpus/05_frames_selected/tv_com_1950_1/
```

Each directory should contain selected image frames, typically:

```text
frame_0001.jpg
frame_0002.jpg
frame_0003.jpg
...
```

If a per-commercial selected-frame manifest exists, the programme should use it to determine frame order and frame metadata. Otherwise, it should sort frame filenames naturally.

Supported image extensions:

```text
.jpg
.jpeg
.png
```

The programme should not use the dense original frames from:

```text
corpus/05_frames/
```

for LLM submission.

It should use:

```text
corpus/05_frames_selected/
```

only.

---

#### 2.4 Commercial audio directory

The programme should locate the corresponding commercial audio file from:

```text
corpus/03_audio/
```

Each audio file is named after the `Commercial ID` column and has the `.wav` extension.

Expected path pattern:

```text
corpus/03_audio/<Commercial ID>.wav
```

Example:

```text
corpus/03_audio/tv_com_1950_1.wav
```

The audio file is retained as a provenance artefact only. It should be validated and hashed, and its path should be recorded in output metadata, but it should **not** be uploaded or submitted to the LLM.

Supported audio extension for this version:

```text
.wav
```

The programme should fail per commercial, not globally, if the expected audio file is missing, unless an explicit future option such as `--allow-missing-audio-provenance` is introduced.

---

#### 2.5 Transcript JSON directory

The programme should use the corresponding transcript JSON file from:

```text
corpus/04_transcripts/
```

Each transcript JSON file is named after the `Commercial ID` column and has the `.json` extension.

Expected path pattern:

```text
corpus/04_transcripts/<Commercial ID>.json
```

Example:

```text
corpus/04_transcripts/tv_com_1950_1.json
```

The JSON transcript is expected to contain:

- `commercial_id`;
- `input_path`;
- `text_output_path`;
- `json_output_path`;
- `model`;
- `transcription`;
- `transcription.text`;
- `transcription.detected_language`;
- `transcription.language_probability`;
- `transcription.duration_seconds`;
- `transcription.segments`;
- `metadata`.

The `transcription.segments` list should contain timestamped transcript segments with at least:

```text
start
end
text
```

The programme should convert these segments into a Markdown transcript context block and insert it into the generated prompt.

The transcript is treated as imperfect audio-derived supporting context, not as equivalent to the original audio signal. It may help clarify product names, brand names, slogans, speakers, spoken references, or ambiguous visual references, but it should not be treated as visible evidence.

Supported transcript extension for this version:

```text
.json
```

The programme should fail per commercial, not globally, if the expected transcript JSON file is missing or invalid.

---

### 3. Prompt generation

For each commercial listed in:

```text
corpus/00_sources/tv_commercials_selected_2.tsv
```

the programme should create a generated prompt file:

```text
corpus/06_visual_descriptions_prompts/<Commercial ID>.md
```

Prompt generation should:

1. Load the v5 prompt template.
2. Replace the product-context placeholder with the commercial’s `Description`.
3. Load the corresponding transcript JSON file.
4. Build the audio-derived transcript context block.
5. Replace `<AUDIO_DERIVED_TRANSCRIPT_CONTEXT>` with that context block.
6. Write the generated prompt file.

The generated prompt file should therefore be a self-contained record of:

- the task instructions;
- the commercial-specific product context;
- the audio-derived transcript context used by the LLM;
- the methodological note that the transcript is imperfect and not equivalent to the original audio.

If `--reprocess` is not provided and an existing generated prompt file has identical content, the file may be left unchanged. If an existing generated prompt file differs and `--reprocess` is not provided, the programme may leave it unchanged and log a warning. For full reproducibility, reprocessing should be used when changing the prompt template or transcript-context formatting.

---

### 4. Transcript context block formatting

The transcript context block should be generated from:

```text
corpus/04_transcripts/<Commercial ID>.json
```

The block should include:

- methodological note;
- audio file source path;
- transcript JSON source path;
- transcription backend;
- transcription model;
- language setting;
- detected language;
- language probability;
- VAD filter setting;
- duration;
- transcript metadata where available;
- timestamped transcript segments.

Recommended structure:

```markdown
The following transcript was generated automatically from the commercial audio using Whisper/faster-whisper. It is provided only as imperfect supporting context. It may contain transcription errors and does not preserve the full audio signal.

Audio file source: corpus/03_audio/tv_com_1950_1.wav

Transcript JSON source: corpus/04_transcripts/tv_com_1950_1.json

Transcription backend: faster-whisper

Transcription model: large-v3

Language setting: en

Detected language: en

Language probability: 1

VAD filter: False

Duration: 59.025125 seconds

Transcript metadata:

Title: Norwich Liquid Peptans

Decade: 1950

Category: Health, Beauty & Personal Care

Timestamped transcript segments:

[0.400–7.000] Where does it all start? Sometimes here with an acid stomach or here with tense

[7.000–12.200] upset digestive nerves. It may even reach here with that fuzzy achy feeling in the

[12.200–17.840] head. Soon you seem to feel sick all over. It's the acid tension pain trouble
```

The timestamped segment lines should be separated by a blank line. This prevents Markdown renderers from collapsing all transcript segments into a single paragraph.

The programme should record in output metadata that transcript segment Markdown spacing uses:

```text
blank_line_between_segments
```

If `--max-transcript-segments` is greater than `0`, only the first N usable transcript segments should be inserted. If `--max-transcript-segments` is `0`, all usable transcript segments should be inserted.

---

### 5. LLM submission

For each commercial listed in `corpus/00_sources/tv_commercials_selected_2.tsv`, the programme should submit to the LLM:

1. The generated commercial-specific prompt document created in:

```text
corpus/06_visual_descriptions_prompts/<Commercial ID>.md
```

2. A neutral metadata note recording:
   - commercial ID;
   - audio provenance path;
   - transcript JSON source;
   - number of selected frames;
   - reminder that selected frames are primary evidence.

3. The corresponding selected frames from:

```text
corpus/05_frames_selected/<Commercial ID>/
```

Frames must be submitted in chronological order.

The `.wav` audio file should **not** be submitted. The transcript context is already included in the generated prompt as text.

Recommended logical request structure:

```text
[prompt text from generated prompt file, including product context and transcript context]

Commercial sequence metadata:
Commercial ID: tv_com_1950_1
Audio provenance file: corpus/03_audio/tv_com_1950_1.wav
Transcript JSON source: corpus/04_transcripts/tv_com_1950_1.json
Number of selected frames: 64

The original audio file is retained for provenance but is not submitted.
The generated prompt contains an imperfect audio-derived transcript context block.
Use selected frames as the primary evidence for visible content.

Frame 1 — filename: frame_0001.jpg — timestamp: ... — selection reason: ...
[image input]

Frame 2 — filename: frame_0002.jpg — timestamp: ... — selection reason: ...
[image input]

...
```

The request labels should remain factual and neutral. They should not add interpretation.

---

### 6. Frame, transcript, and audio selection

For each commercial, the programme should locate selected frames under:

```text
corpus/05_frames_selected/<Commercial ID>/
```

the corresponding transcript JSON file at:

```text
corpus/04_transcripts/<Commercial ID>.json
```

and the corresponding audio provenance file at:

```text
corpus/03_audio/<Commercial ID>.wav
```

If a selected-frame manifest exists, such as:

```text
selected_frames_manifest.json
```

the programme should use the manifest’s selected-frame order.

If no manifest exists, frames should be ordered by natural filename sorting:

```text
frame_0001.jpg
frame_0002.jpg
frame_0003.jpg
...
frame_0010.jpg
```

The programme should not use:

```text
corpus/05_frames/
```

for LLM requests.

If the transcript JSON file is missing or invalid, the commercial should be marked as failed and processing should continue with the next commercial.

If the audio provenance file is missing, the commercial should be marked as failed and processing should continue with the next commercial.

---

### 7. Output files

For each successful commercial, the programme should write:

```text
corpus/06_visual_descriptions/<Commercial ID>.txt
corpus/06_visual_descriptions/<Commercial ID>.json
```

The `.txt` file should contain only the clean visual description returned by the model.

The `.json` file should contain full reproducibility metadata, including:

- commercial ID;
- status;
- input paths;
- commercial metadata row;
- prompt template path;
- prompt template hash;
- generated prompt path;
- generated prompt hash;
- placeholder replacement status;
- audio provenance metadata;
- transcript metadata;
- transcript context metadata;
- selected frames submitted;
- frame counts;
- model configuration;
- response metadata;
- response text;
- errors, if any.

A failed `.txt` file is not required. A failed `.json` file should still be written where possible.

---

### 8. `.json` response metadata output

The `.json` output should preserve the current metadata style and add prompt-generation, transcript-context, frame-submission, and audio-provenance traceability.

Recommended success structure:

```json
{
  "commercial_id": "tv_com_1950_1",
  "status": "success",
  "input": {
    "metadata_tsv": "corpus/00_sources/tv_commercials_selected_2.tsv",
    "frame_dir": "corpus/05_frames_selected/tv_com_1950_1",
    "audio_file": "corpus/03_audio/tv_com_1950_1.wav",
    "transcript_json_file": "corpus/04_transcripts/tv_com_1950_1.json",
    "prompt_template": "describe_commercials_visual_prompts/visual_commercial_description_v5.md",
    "generated_prompt_file": "corpus/06_visual_descriptions_prompts/tv_com_1950_1.md"
  },
  "commercial_metadata": {
    "description": "This is a commercial for Liquid Peptans, from the 1950s. This antacid product is used for reducing stomach acidity to relieve discomfort.",
    "row": {}
  },
  "prompt": {
    "template_sha256": "...",
    "generated_prompt_sha256": "...",
    "product_context_placeholder_replaced": true,
    "transcript_context_placeholder_replaced": true
  },
  "audio": {
    "filename": "tv_com_1950_1.wav",
    "path": "corpus/03_audio/tv_com_1950_1.wav",
    "format": "wav",
    "sha256": "...",
    "submitted": false,
    "role": "provenance_only"
  },
  "transcript": {
    "filename": "tv_com_1950_1.json",
    "path": "corpus/04_transcripts/tv_com_1950_1.json",
    "sha256": "...",
    "audio_input_path_recorded_in_transcript": "corpus/03_audio/tv_com_1950_1.wav",
    "model": {},
    "metadata": {},
    "transcription_summary": {
      "detected_language": "en",
      "language_probability": 1,
      "duration_seconds": 59.025125,
      "text_sha256": "..."
    },
    "context": {
      "transcript_context_inserted": true,
      "transcript_context_sha256": "...",
      "segment_count_available": 12,
      "segment_count_inserted": 12,
      "segment_cap_applied": false,
      "max_transcript_segments": 0,
      "segment_markdown_spacing": "blank_line_between_segments"
    },
    "submitted_as_prompt_text": true
  },
  "frames": [
    {
      "filename": "frame_0001.jpg",
      "path": "corpus/05_frames_selected/tv_com_1950_1/frame_0001.jpg",
      "frame_index": 1,
      "timestamp_seconds": 0.0,
      "selection_reason": "first_frame"
    }
  ],
  "frame_counts": {
    "submitted_frame_count": 64,
    "max_frames_per_request": 0
  },
  "model": "gpt-5.5",
  "image_detail": "low",
  "temperature": 0,
  "temperature_sent_to_api": false,
  "response_text": "The commercial opens with...",
  "api_metadata": {},
  "duration_seconds": 12.345,
  "created_at": "2026-06-21T00:00:00Z",
  "error": null
}
```

Recommended failure structure:

```json
{
  "commercial_id": "tv_com_1950_1",
  "status": "failed",
  "input": {
    "metadata_tsv": "corpus/00_sources/tv_commercials_selected_2.tsv",
    "frame_dir": "corpus/05_frames_selected/tv_com_1950_1",
    "audio_file": "corpus/03_audio/tv_com_1950_1.wav",
    "transcript_json_file": "corpus/04_transcripts/tv_com_1950_1.json",
    "prompt_template": "describe_commercials_visual_prompts/visual_commercial_description_v5.md",
    "generated_prompt_file": "corpus/06_visual_descriptions_prompts/tv_com_1950_1.md"
  },
  "audio": {
    "filename": "tv_com_1950_1.wav",
    "path": "corpus/03_audio/tv_com_1950_1.wav",
    "submitted": false,
    "role": "provenance_only"
  },
  "transcript": {
    "filename": "tv_com_1950_1.json",
    "path": "corpus/04_transcripts/tv_com_1950_1.json",
    "submitted_as_prompt_text": false
  },
  "error": "Missing transcript JSON file: corpus/04_transcripts/tv_com_1950_1.json"
}
```

---

### 9. Run-level outputs

The programme should continue to write run-level logs and manifests in:

```text
corpus/06_visual_descriptions/
```

Recommended files:

```text
corpus/06_visual_descriptions/describe_commercials_visual.log
corpus/06_visual_descriptions/describe_commercials_visual_manifest.json
corpus/06_visual_descriptions/describe_commercials_visual_manifest_<RUN_ID>.json
```

The run manifest should include:

- run ID;
- start time;
- end time;
- prompt template path;
- prompt template hash;
- metadata TSV path;
- selected frame input directory;
- audio provenance directory;
- transcript JSON directory;
- generated prompt directory;
- visual description output directory;
- model configuration;
- processing strategy;
- number of TSV rows read;
- number of commercials planned;
- number skipped;
- number submitted to LLM;
- number succeeded;
- number failed;
- number failed because of missing audio provenance;
- number failed because of missing or invalid transcript JSON;
- number failed because of missing frames.

The run metadata should record the strategy:

```json
{
  "strategy": {
    "primary_evidence": "selected_frames",
    "supporting_context": "timestamped_whisper_json_transcript_inserted_into_prompt",
    "audio_file_role": "provenance_only_not_submitted"
  }
}
```

---

### 10. Processing order

Commercials should be processed in TSV row order unless an explicit natural-sort option is introduced later.

Recommended default:

1. Read TSV rows.
2. Validate required columns.
3. For each commercial:
   - locate selected frames;
   - locate the corresponding audio provenance file;
   - locate the corresponding transcript JSON file;
   - build the transcript context block;
   - generate the commercial-specific prompt;
   - skip if successful outputs already exist, unless `--reprocess`;
   - submit prompt and frames to the LLM;
   - save `.txt` and `.json` outputs.
4. Write run-level manifest and logs.

Generated prompt files should be created during per-commercial processing, because prompt generation now depends on the transcript JSON file as well as the metadata description.

---

### 11. Existing-output skipping

Existing successful outputs should be skipped unless `--reprocess` is used.

A commercial may be skipped if:

```text
corpus/06_visual_descriptions/<Commercial ID>.txt
corpus/06_visual_descriptions/<Commercial ID>.json
```

exist and the JSON output records:

```json
"status": "success"
```

Skipped items should still be included in the run manifest with status:

```text
skipped_existing
```

---

### 12. Command-line interface

Recommended CLI arguments:

| Argument                         |                                                                   Default | Purpose                                               |
|----------------------------------|--------------------------------------------------------------------------:|-------------------------------------------------------|
| `--prompt-template PATH`         | `describe_commercials_visual_prompts/visual_commercial_description_v5.md` | Markdown prompt template                              |
| `--metadata-tsv PATH`            |                         `corpus/00_sources/tv_commercials_selected_2.tsv` | Selected commercial metadata                          |
| `--frames-dir PATH`              |                                               `corpus/05_frames_selected` | Selected frames input directory                       |
| `--audio-dir PATH`               |                                                         `corpus/03_audio` | Commercial audio provenance directory                 |
| `--transcripts-dir PATH`         |                                                   `corpus/04_transcripts` | Whisper JSON transcript directory                     |
| `--prompt-output-dir PATH`       |                                   `corpus/06_visual_descriptions_prompts` | Generated prompt documents                            |
| `--output-dir PATH`              |                                           `corpus/06_visual_descriptions` | LLM response output directory                         |
| `--model MODEL`                  |                                                                 `gpt-5.5` | Multimodal LLM model                                  |
| `--image-detail {low,high,auto}` |                                                                     `low` | Image detail setting                                  |
| `--temperature FLOAT`            |                                                                       `0` | Generation temperature, omitted if unsupported        |
| `--test-mode`                    |                                                                   enabled | Process limited number of rows                        |
| `--no-test-mode`                 |                                                                  disabled | Process all rows                                      |
| `--test-limit N`                 |                                                                       `5` | Number of rows to attempt in test mode                |
| `--start-commercial-id ID`       |                                                                    `None` | Resume from a commercial ID                           |
| `--reprocess`                    |                                                                   `False` | Regenerate existing outputs                           |
| `--workers N`                    |                                                                       `1` | Number of concurrent workers                          |
| `--max-frames-per-request N`     |                                                                       `0` | Optional cap on submitted frames; `0` means no cap    |
| `--max-transcript-segments N`    |                                                                       `0` | Optional cap on transcript segments; `0` means no cap |
| `--max-retries N`                |                                                                       `2` | API retry attempts                                    |
| `--retry-backoff-seconds FLOAT`  |                                                                     `5.0` | Initial retry backoff                                 |
| `--log-file PATH`                |                                                   `<output-dir>/... .log` | Optional explicit log file path                       |
| `--manifest-file PATH`           |                                                  `<output-dir>/... .json` | Optional explicit run manifest path                   |

Optional future arguments:

| Argument                           | Purpose                                                                                                                            |
|------------------------------------|------------------------------------------------------------------------------------------------------------------------------------|
| `--allow-missing-audio-provenance` | Continue processing a commercial without audio provenance if the `.wav` file is missing. This should not be enabled by default.    |
| `--allow-missing-transcript`       | Continue processing a commercial without transcript context if the `.json` file is missing. This should not be enabled by default. |
| `--transcript-format`              | Select an alternative transcript-context format, if needed later.                                                                  |

---

### 13. Example commands

#### Default test run

```bash
python describe_commercials_visual.py
```

This should:

- read `corpus/00_sources/tv_commercials_selected_2.tsv`;
- use `describe_commercials_visual_prompts/visual_commercial_description_v5.md`;
- generate prompt documents in `corpus/06_visual_descriptions_prompts/`;
- process up to 5 commercials;
- use frames from `corpus/05_frames_selected/`;
- use transcript JSON files from `corpus/04_transcripts/`;
- retain audio provenance from `corpus/03_audio/`;
- submit generated prompts and selected frames to the LLM;
- not submit `.wav` audio files;
- save responses in `corpus/06_visual_descriptions/`.

#### Full run

```bash
python describe_commercials_visual.py --no-test-mode
```

#### Reprocess all prompts and responses

```bash
python describe_commercials_visual.py --no-test-mode --reprocess
```

#### Start from a specific commercial

```bash
python describe_commercials_visual.py \
  --no-test-mode \
  --start-commercial-id tv_com_1960_54
```

#### Use a frame cap for cost control

```bash
python describe_commercials_visual.py \
  --no-test-mode \
  --max-frames-per-request 40
```

#### Use a transcript segment cap

```bash
python describe_commercials_visual.py \
  --no-test-mode \
  --max-transcript-segments 40
```

#### Use a non-default audio provenance directory

```bash
python describe_commercials_visual.py \
  --no-test-mode \
  --audio-dir corpus/03_audio
```

#### Use a non-default transcript directory

```bash
python describe_commercials_visual.py \
  --no-test-mode \
  --transcripts-dir corpus/04_transcripts
```

---

### 14. Validation rules

The programme should fail before API calls if:

- the prompt template file does not exist;
- the prompt template is empty;
- the product-context placeholder is not found in the prompt template;
- the transcript-context placeholder is not found in the prompt template;
- the TSV file does not exist;
- the TSV file is empty;
- the TSV file lacks `Commercial ID`;
- the TSV file lacks `Description`;
- the selected-frame directory does not exist;
- the audio provenance directory does not exist;
- the transcript JSON directory does not exist;
- the prompt-output directory cannot be created;
- the response-output directory cannot be created;
- `OPENAI_API_KEY` is missing;
- the OpenAI Python SDK is unavailable;
- `--test-limit <= 0`;
- `--workers <= 0`;
- `--max-frames-per-request < 0`;
- `--max-transcript-segments < 0`;
- `--temperature < 0`;
- `--max-retries < 0`;
- `--retry-backoff-seconds < 0`.

Per-commercial failures should not stop the full run.

---

### 15. Per-commercial failure handling

A commercial should be marked as failed, but the run should continue, if:

- no selected-frame directory exists for the commercial;
- the selected-frame directory contains no supported image files;
- the selected-frame manifest is invalid;
- one or more manifest-listed frame files are missing;
- the corresponding audio provenance file is missing from `corpus/03_audio/`;
- the corresponding audio provenance file is not a supported audio format;
- the corresponding transcript JSON file is missing from `corpus/04_transcripts/`;
- the transcript JSON file is not valid JSON;
- the transcript JSON root is not an object;
- the transcript JSON lacks a `transcription` object;
- the transcript JSON lacks a `transcription.segments` list;
- the generated prompt file cannot be written;
- the LLM request fails after retries;
- the LLM response contains no usable text.

Each failure should be written to the run manifest and to a per-commercial JSON file.

---

### 16. Acceptance criteria

The redesign is acceptable when:

1. The programme reads `describe_commercials_visual_prompts/visual_commercial_description_v5.md`.
2. The programme reads `corpus/00_sources/tv_commercials_selected_2.tsv`.
3. Each generated prompt file is named after `Commercial ID`.
4. Prompt files are saved in `corpus/06_visual_descriptions_prompts/`.
5. The product-context placeholder is replaced with the row’s `Description`.
6. The transcript-context placeholder is replaced with a generated transcript context block.
7. The transcript context block is generated from `corpus/04_transcripts/<Commercial ID>.json`.
8. Timestamped transcript segment lines are separated by blank lines.
9. The programme uses frames from `corpus/05_frames_selected/`.
10. The programme does not submit frames from `corpus/05_frames/`.
11. The programme locates the corresponding audio provenance file as `corpus/03_audio/<Commercial ID>.wav`.
12. The programme does not upload or submit the `.wav` audio file to the LLM.
13. Each LLM request contains the generated commercial-specific prompt and that commercial’s selected frames.
14. Responses are saved in `corpus/06_visual_descriptions/`.
15. Response naming follows the `<Commercial ID>.txt` and `<Commercial ID>.json` pattern.
16. Existing successful outputs are skipped unless `--reprocess` is used.
17. Per-commercial failures are logged and do not stop the whole run.
18. Prompt hashes, generated prompt paths, audio provenance paths, transcript paths, transcript hashes, transcript-context hashes, and submitted frame paths are recorded for reproducibility.
19. The programme writes a run-level manifest and log.
20. The programme supports test mode and full-run mode.
21. The programme supports resuming from a commercial ID.
22. The programme does not log the API key.