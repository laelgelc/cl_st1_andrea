## Redesigned Specification: `describe_commercials_visual.py`

### 1. Programme purpose

`describe_commercials_visual.py` prepares commercial-specific prompt files and submits selected commercial frames, together with the corresponding commercial audio, to a multimodal LLM.

The programme should:

1. Use the Markdown prompt template:

```text
describe_commercials_visual_prompts/visual_commercial_description_v4.md
```

2. Use the selected-commercial metadata table:

```text
corpus/00_sources/tv_commercials_selected_2.tsv
```

3. For each row in the TSV file, create a prompt document specific to that commercial.

4. Save those prompt documents in:

```text
corpus/06_visual_descriptions_prompts/
```

5. Pair each prompt document with:
   - the corresponding selected frames from:

```text
corpus/05_frames_selected/
```

   - the corresponding commercial audio file from:

```text
corpus/03_audio/
```

6. Submit each commercial-specific prompt, its selected frames, and its audio file to the LLM.

7. Save LLM responses in:

```text
corpus/06_visual_descriptions/
```

using the same output pattern currently implemented for visual-description responses.

---

### 2. Inputs

#### 2.1 Prompt template

The programme should read the Markdown prompt template from:

```text
describe_commercials_visual_prompts/visual_commercial_description_v4.md
```

This file contains a placeholder product-context paragraph:

```text
<This is a commercial for LiquidPeptans, from the 1950s. This antacid product is used for reducing acid acidity to relieve discomfort.>
```

For each commercial, this placeholder must be replaced with the value from the `Description` column in the TSV metadata file.

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

Other columns may be present and should be preserved only if needed for logging or metadata.

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

If a per-commercial selected-frame manifest exists, the programme should use it to determine frame order. Otherwise, it should sort frame filenames naturally.

Supported image extensions:

```text
.jpg
.jpeg
.png
```

---

#### 2.4 Commercial audio directory

The programme should use the corresponding commercial audio file from:

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

The audio should be submitted to the LLM together with the commercial-specific prompt and selected frames.

The audio is used only as supporting context, in line with the prompt instructions. The selected frames remain the primary source of evidence for what is visible. The audio may help clarify product names, brand names, slogans, speakers, or ambiguous visual references, but the model should not treat audio-only information as visible.

Supported audio extension for this version:

```text
.wav
```

The programme should fail per commercial, not globally, if the expected audio file is missing, unless an explicit future option such as `--allow-missing-audio` is introduced.

---

### 4. LLM submission

For each commercial listed in `corpus/00_sources/tv_commercials_selected_2.tsv`, the programme should submit to the LLM:

1. The commercial-specific prompt document created in:

```text
corpus/06_visual_descriptions_prompts/<Commercial ID>.md
```

2. The corresponding selected frames from:

```text
corpus/05_frames_selected/<Commercial ID>/
```

3. The corresponding audio file from:

```text
corpus/03_audio/<Commercial ID>.wav
```

Frames must be submitted in chronological order.

The request should include the prompt first, followed by a neutral metadata note, the audio file, and then the ordered frame sequence.

Recommended logical request structure:

```text
[prompt text from generated prompt file]

Commercial ID: tv_com_1950_1
Audio file: corpus/03_audio/tv_com_1950_1.wav
Number of selected frames: 64

[audio input]

Frame 1 — filename: frame_0001.jpg — timestamp: ... — selection reason: ...
[image input]

Frame 2 — filename: frame_0002.jpg — timestamp: ... — selection reason: ...
[image input]

...
```

The request labels should remain factual and neutral. They should not add interpretation.

---

### 5. Frame and audio selection

For each commercial, the programme should locate selected frames under:

```text
corpus/05_frames_selected/<Commercial ID>/
```

and the corresponding audio file at:

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

The audio file should be resolved directly from the commercial ID:

```text
corpus/03_audio/<Commercial ID>.wav
```

If the audio file is missing, the commercial should be marked as failed and processing should continue with the next commercial.

---

### 8. `.json` response metadata output

The `.json` output should preserve the current metadata style and add prompt-generation, frame-submission, and audio-submission traceability.

Recommended fields:

```json
{
  "commercial_id": "tv_com_1950_1",
  "status": "success",
  "input": {
    "metadata_tsv": "corpus/00_sources/tv_commercials_selected_2.tsv",
    "frame_dir": "corpus/05_frames_selected/tv_com_1950_1",
    "audio_file": "corpus/03_audio/tv_com_1950_1.wav",
    "prompt_template": "describe_commercials_visual_prompts/visual_commercial_description_v4.md",
    "generated_prompt_file": "corpus/06_visual_descriptions_prompts/tv_com_1950_1.md"
  },
  "commercial_metadata": {
    "description": "This is a commercial for Liquid Peptans, from the 1950s. This antacid product is used for reducing stomach acidity to relieve discomfort."
  },
  "prompt": {
    "template_sha256": "...",
    "generated_prompt_sha256": "...",
    "placeholder_replaced": true
  },
  "audio": {
    "filename": "tv_com_1950_1.wav",
    "path": "corpus/03_audio/tv_com_1950_1.wav",
    "submitted": true
  },
  "frames": [
    {
      "filename": "frame_0001.jpg",
      "path": "corpus/05_frames_selected/tv_com_1950_1/frame_0001.jpg"
    }
  ],
  "frame_counts": {
    "submitted_frame_count": 64
  },
  "model": "gpt-5.5",
  "response_text": "The commercial opens with...",
  "api_metadata": {},
  "created_at": "2026-06-21T00:00:00Z",
  "error": null
}
```

For failures caused by a missing audio file, the `.json` file should record:

```json
{
  "commercial_id": "tv_com_1950_1",
  "status": "failed",
  "input": {
    "audio_file": "corpus/03_audio/tv_com_1950_1.wav"
  },
  "error": "Missing audio file: corpus/03_audio/tv_com_1950_1.wav"
}
```

A failed `.txt` file is not required.

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
- audio input directory;
- generated prompt directory;
- visual description output directory;
- model configuration;
- number of TSV rows read;
- number of prompt files generated;
- number of commercials planned;
- number skipped;
- number submitted to LLM;
- number succeeded;
- number failed;
- number failed because of missing audio;
- number failed because of missing frames.

---

### 10. Processing order

Commercials should be processed in TSV row order unless an explicit natural-sort option is used.

Recommended default:

1. Read TSV rows.
2. Validate required columns.
3. Generate one prompt file per row.
4. For each commercial:
   - locate selected frames;
   - locate the corresponding audio file;
   - skip if successful outputs already exist, unless `--reprocess`;
   - submit prompt, audio, and frames to the LLM;
   - save `.txt` and `.json` outputs.

---

### 12. Command-line interface

Recommended CLI arguments:

| Argument                         |                                                                   Default | Purpose                                        |
|----------------------------------|--------------------------------------------------------------------------:|------------------------------------------------|
| `--prompt-template PATH`         | `describe_commercials_visual_prompts/visual_commercial_description_v4.md` | Markdown prompt template                       |
| `--metadata-tsv PATH`            |                         `corpus/00_sources/tv_commercials_selected_2.tsv` | Selected commercial metadata                   |
| `--frames-dir PATH`              |                                               `corpus/05_frames_selected` | Selected frames input directory                |
| `--audio-dir PATH`               |                                                         `corpus/03_audio` | Commercial audio input directory               |
| `--prompt-output-dir PATH`       |                                   `corpus/06_visual_descriptions_prompts` | Generated prompt documents                     |
| `--output-dir PATH`              |                                           `corpus/06_visual_descriptions` | LLM response output directory                  |
| `--model MODEL`                  |                                                                 `gpt-5.5` | Multimodal LLM model                           |
| `--image-detail {low,high,auto}` |                                                                     `low` | Image detail setting                           |
| `--temperature FLOAT`            |                                                                       `0` | Generation temperature, omitted if unsupported |
| `--test-mode`                    |                                                                   enabled | Process limited number of rows                 |
| `--no-test-mode`                 |                                                                  disabled | Process all rows                               |
| `--test-limit N`                 |                                                                       `5` | Number of rows to attempt in test mode         |
| `--start-commercial-id ID`       |                                                                    `None` | Resume from a commercial ID                    |
| `--reprocess`                    |                                                                   `False` | Regenerate existing outputs                    |
| `--workers N`                    |                                                                       `1` | Number of concurrent workers                   |
| `--max-frames-per-request N`     |                                                                       `0` | Optional cap on submitted frames               |
| `--max-retries N`                |                                                                       `2` | API retry attempts                             |
| `--retry-backoff-seconds FLOAT`  |                                                                     `5.0` | Initial retry backoff                          |

Optional future argument:

| Argument                | Purpose                                                                                                                                   |
|-------------------------|-------------------------------------------------------------------------------------------------------------------------------------------|
| `--allow-missing-audio` | Continue processing a commercial without audio if the `.wav` file is missing. The first implementation should not enable this by default. |

---

### 13. Example commands

#### Default test run

```bash
python describe_commercials_visual.py
```

This should:

- read `corpus/00_sources/tv_commercials_selected_2.tsv`;
- generate prompt documents in `corpus/06_visual_descriptions_prompts/`;
- process up to 5 commercials;
- use frames from `corpus/05_frames_selected/`;
- use audio from `corpus/03_audio/`;
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

#### Use a non-default audio directory

```bash
python describe_commercials_visual.py \
  --no-test-mode \
  --audio-dir corpus/03_audio
```

---

### 14. Validation rules

The programme should fail before API calls if:

- the prompt template file does not exist;
- the prompt template is empty;
- the required placeholder text is not found in the prompt template;
- the TSV file does not exist;
- the TSV file is empty;
- the TSV file lacks `Commercial ID`;
- the TSV file lacks `Description`;
- the selected-frame directory does not exist;
- the audio directory does not exist;
- the prompt-output directory cannot be created;
- the response-output directory cannot be created;
- `OPENAI_API_KEY` is missing;
- the OpenAI Python SDK is unavailable;
- `--test-limit <= 0`;
- `--workers <= 0`;
- `--max-frames-per-request < 0`;
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
- the corresponding audio file is missing from `corpus/03_audio/`;
- the corresponding audio file is not a supported audio format;
- the generated prompt file cannot be written;
- the LLM request fails after retries;
- the LLM response contains no usable text.

Each failure should be written to the run manifest and to a per-commercial JSON file.

---

### 16. Acceptance criteria

The redesign is acceptable when:

1. The programme reads `describe_commercials_visual_prompts/visual_commercial_description_v4.md`.
2. The programme reads `corpus/00_sources/tv_commercials_selected_2.tsv`.
3. One Markdown prompt file is created per TSV row.
4. Each generated prompt file is named after `Commercial ID`.
5. Prompt files are saved in `corpus/06_visual_descriptions_prompts/`.
6. The product-context placeholder is replaced with the row’s `Description`.
7. The programme uses frames from `corpus/05_frames_selected/`.
8. The programme does not submit frames from `corpus/05_frames/`.
9. The programme locates the corresponding audio file as `corpus/03_audio/<Commercial ID>.wav`.
10. Each LLM request contains the commercial-specific prompt, the commercial audio file, and that commercial’s selected frames.
11. Responses are saved in `corpus/06_visual_descriptions/`.
12. Response naming follows the existing `<Commercial ID>.txt` and `<Commercial ID>.json` pattern.
13. Existing successful outputs are skipped unless `--reprocess` is used.
14. Per-commercial failures are logged and do not stop the whole run.
15. Prompt hashes, generated prompt paths, audio paths, and submitted frame paths are recorded for reproducibility.
16. The programme writes a run-level manifest and log.
17. The programme supports test mode and full-run mode.
18. The programme supports resuming from a commercial ID.
19. The programme does not log the API key.