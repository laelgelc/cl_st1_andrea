## Redesigned Specification: `sample_commercials_frames.py`

### 1. Programme purpose

`sample_commercials_frames.py` should be redesigned to support the next visual-description stage of the commercial-analysis pipeline.

The programme should now prepare **commercial-specific prompt files** and organise the inputs needed for submitting selected commercial frames to a multimodal LLM.

It should:

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
06_visual_descriptions_prompts/
```

5. Pair each prompt document with the corresponding selected frames from:

```text
05_frames_selected/
```

6. Submit each commercial-specific prompt plus its corresponding frames to the LLM.

7. Save LLM responses in:

```text
06_visual_descriptions/
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
05_frames_selected/
```

For each commercial ID, the programme expects a directory:

```text
05_frames_selected/<Commercial ID>/
```

Example:

```text
05_frames_selected/tv_com_1950_1/
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

### 3. Prompt generation

For every row in `corpus/00_sources/tv_commercials_selected_2.tsv`, the programme should create a commercial-specific prompt file.

#### 3.1 Prompt replacement rule

In the template prompt, replace exactly this placeholder text:

```text
<This is a commercial for LiquidPeptans, from the 1950s. This antacid product is used for reducing acid acidity to relieve discomfort.>
```

with the row’s `Description` value.

For example, if the TSV row contains:

```text
Commercial ID: tv_com_1950_1
Description: This is a commercial for Liquid Peptans, from the 1950s. This antacid product is used for reducing stomach acidity to relieve discomfort.
```

then the generated prompt should contain:

```text
## Product context:
This is a commercial for Liquid Peptans, from the 1950s. This antacid product is used for reducing stomach acidity to relieve discomfort.
```

The generated prompt should preserve the rest of the Markdown template unchanged.

---

#### 3.2 Prompt output directory

Generated prompt documents should be saved in:

```text
06_visual_descriptions_prompts/
```

The directory should be created if it does not already exist.

---

#### 3.3 Prompt filename

Each generated prompt file should be named after the `Commercial ID` column.

Example:

```text
06_visual_descriptions_prompts/tv_com_1950_1.md
06_visual_descriptions_prompts/tv_com_1950_3.md
06_visual_descriptions_prompts/tv_com_1950_5.md
```

The programme should sanitise filenames only if necessary, but the expected commercial IDs are already filesystem-safe.

---

#### 3.4 Prompt overwrite behaviour

By default, existing prompt files may be skipped if their content already matches the newly generated content.

If the content differs, the programme should overwrite the file when `--reprocess` is used.

Recommended behaviour:

| Situation                              | Default behaviour | With `--reprocess` |
|----------------------------------------|-------------------|--------------------|
| Prompt file missing                    | Create it         | Create it          |
| Prompt file exists and content matches | Leave unchanged   | Rewrite allowed    |
| Prompt file exists and content differs | Skip or warn      | Overwrite          |

A simple implementation may overwrite prompts every run, provided this is logged clearly.

---

### 4. LLM submission

For each commercial listed in `corpus/00_sources/tv_commercials_selected_2.tsv`, the programme should submit to the LLM:

1. The commercial-specific prompt document created in:

```text
06_visual_descriptions_prompts/<Commercial ID>.md
```

2. The corresponding selected frames from:

```text
05_frames_selected/<Commercial ID>/
```

Frames must be submitted in chronological order.

The prompt should be submitted as the textual instruction, followed by the ordered images.

---

### 5. Frame selection and ordering

For each commercial, the programme should locate selected frames under:

```text
05_frames_selected/<Commercial ID>/
```

If a manifest exists, such as:

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
05_frames/
```

for LLM submission.

It should use:

```text
05_frames_selected/
```

only.

---

### 6. Output directory

LLM responses should be saved in:

```text
06_visual_descriptions/
```

The directory should be created if needed.

The programme should preserve the current response-output structure.

For each commercial, it should write at least:

```text
06_visual_descriptions/<Commercial ID>.txt
06_visual_descriptions/<Commercial ID>.json
```

Example:

```text
06_visual_descriptions/tv_com_1950_1.txt
06_visual_descriptions/tv_com_1950_1.json
```

---

### 7. `.txt` response output

The `.txt` file should contain only the model’s generated visual description.

It should:

- be UTF-8 encoded;
- be stripped of leading and trailing whitespace;
- end with exactly one newline;
- contain no programme metadata.

Example:

```text
06_visual_descriptions/tv_com_1950_1.txt
```

---

### 8. `.json` response metadata output

The `.json` output should preserve the current metadata style and add prompt-generation traceability.

Recommended fields:

```json
{
  "commercial_id": "tv_com_1950_1",
  "status": "success",
  "input": {
    "metadata_tsv": "corpus/00_sources/tv_commercials_selected_2.tsv",
    "frame_dir": "05_frames_selected/tv_com_1950_1",
    "prompt_template": "describe_commercials_visual_prompts/visual_commercial_description_v4.md",
    "generated_prompt_file": "06_visual_descriptions_prompts/tv_com_1950_1.md"
  },
  "commercial_metadata": {
    "description": "This is a commercial for Liquid Peptans, from the 1950s. This antacid product is used for reducing stomach acidity to relieve discomfort."
  },
  "prompt": {
    "template_sha256": "...",
    "generated_prompt_sha256": "...",
    "placeholder_replaced": true
  },
  "frames": [
    {
      "filename": "frame_0001.jpg",
      "path": "05_frames_selected/tv_com_1950_1/frame_0001.jpg"
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

For failures, the `.json` file should record:

```json
{
  "commercial_id": "tv_com_1950_1",
  "status": "failed",
  "error": "Missing selected frame directory: 05_frames_selected/tv_com_1950_1"
}
```

A failed `.txt` file is not required.

---

### 9. Run-level outputs

The programme should continue to write run-level logs and manifests in:

```text
06_visual_descriptions/
```

Recommended files:

```text
06_visual_descriptions/describe_commercials_visual.log
06_visual_descriptions/describe_commercials_visual_manifest.json
06_visual_descriptions/describe_commercials_visual_manifest_<RUN_ID>.json
```

The run manifest should include:

- run ID;
- start time;
- end time;
- prompt template path;
- prompt template hash;
- metadata TSV path;
- selected frame input directory;
- generated prompt directory;
- visual description output directory;
- model configuration;
- number of TSV rows read;
- number of prompt files generated;
- number of commercials planned;
- number skipped;
- number submitted to LLM;
- number succeeded;
- number failed.

---

### 10. Processing order

Commercials should be processed in TSV row order unless an explicit natural-sort option is used.

Recommended default:

1. Read TSV rows.
2. Validate required columns.
3. Generate one prompt file per row.
4. For each commercial:
   - locate selected frames;
   - skip if successful outputs already exist, unless `--reprocess`;
   - submit prompt and frames to the LLM;
   - save `.txt` and `.json` outputs.

---

### 11. Resume and reprocessing behaviour

The programme should remain safe to rerun.

By default, a commercial should be skipped if:

```text
06_visual_descriptions/<Commercial ID>.txt
06_visual_descriptions/<Commercial ID>.json
```

both exist, and the JSON file has:

```json
"status": "success"
```

Use:

```bash
python sample_commercials_frames.py --reprocess
```

to regenerate:

- prompt files;
- LLM response files;
- per-commercial JSON metadata.

Failed prior outputs should not be treated as complete.

---

### 12. Command-line interface

Recommended CLI arguments:

| Argument                         |                                                                   Default | Purpose                                        |
|----------------------------------|--------------------------------------------------------------------------:|------------------------------------------------|
| `--prompt-template PATH`         | `describe_commercials_visual_prompts/visual_commercial_description_v4.md` | Markdown prompt template                       |
| `--metadata-tsv PATH`            |                         `corpus/00_sources/tv_commercials_selected_2.tsv` | Selected commercial metadata                   |
| `--frames-dir PATH`              |                                                      `05_frames_selected` | Selected frames input directory                |
| `--prompt-output-dir PATH`       |                                          `06_visual_descriptions_prompts` | Generated prompt documents                     |
| `--output-dir PATH`              |                                                  `06_visual_descriptions` | LLM response output directory                  |
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

---

### 13. Example commands

#### Default test run

```bash
python sample_commercials_frames.py
```

This should:

- read `corpus/00_sources/tv_commercials_selected_2.tsv`;
- generate prompt documents in `06_visual_descriptions_prompts/`;
- process up to 5 commercials;
- use frames from `05_frames_selected/`;
- save responses in `06_visual_descriptions/`.

#### Full run

```bash
python sample_commercials_frames.py --no-test-mode
```

#### Reprocess all prompts and responses

```bash
python sample_commercials_frames.py --no-test-mode --reprocess
```

#### Start from a specific commercial

```bash
python sample_commercials_frames.py \
  --no-test-mode \
  --start-commercial-id tv_com_1960_54
```

#### Use a frame cap for cost control

```bash
python sample_commercials_frames.py \
  --no-test-mode \
  --max-frames-per-request 40
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
5. Prompt files are saved in `06_visual_descriptions_prompts/`.
6. The product-context placeholder is replaced with the row’s `Description`.
7. The programme uses frames from `05_frames_selected/`.
8. The programme does not submit frames from `05_frames/`.
9. Each LLM request contains the commercial-specific prompt and that commercial’s selected frames.
10. Responses are saved in `06_visual_descriptions/`.
11. Response naming follows the existing `<Commercial ID>.txt` and `<Commercial ID>.json` pattern.
12. Existing successful outputs are skipped unless `--reprocess` is used.
13. Per-commercial failures are logged and do not stop the whole run.
14. Prompt hashes and generated prompt paths are recorded for reproducibility.
15. The programme writes a run-level manifest and log.
16. The programme supports test mode and full-run mode.
17. The programme supports resuming from a commercial ID.
18. The programme does not log the API key.