# Specification: `sample_commercials_frames.py`

## 1. Programme Summary

`sample_commercials_frames.py` samples still frames from individual TV commercial video clips.

The programme is designed as the **first stage** of a two-stage visual analysis pipeline:

```text
Stage 1: sample_commercials_frames.py
    commercial video clips → chronologically ordered frame sequences + manifests

Stage 2: visual interpretation programme
    sampled frames → LLM-based visual description / annotation
```

The purpose of this programme is **not** to interpret the images. Its purpose is to create a reproducible, chronologically ordered visual record for each commercial, suitable for later submission to a multimodal LLM or for manual inspection.

The programme reads commercial video files from an input directory, applies a fixed-interval frame sampling strategy with first/last safeguards, writes selected frames to one subdirectory per commercial, and records all processing decisions in logs and JSON manifests.

The default sampling strategy is:

```text
include first frame: yes
include one frame every: 0.25 seconds
include last frame: yes
last-frame offset: 1.0 second before end
resize width: 768 px
maximum selected frames: no cap
```

The frame cap is configurable. A value of:

```text
--max-frames 0
```

means **no cap**.

---

## 2. High-Level Functionality

For each commercial video clip, the programme should:

1. Discover eligible video files in the input directory.
2. Determine whether the clip should be processed or skipped.
3. Extract a candidate frame set using:
   - first frame;
   - fixed-interval frames every 0.25 seconds by default;
   - final frame near the end.
4. Sort all candidate frames chronologically.
5. Remove duplicate or near-duplicate timestamp entries.
6. Apply an optional maximum frame cap if `--max-frames` is greater than `0`.
7. Write selected frames to an output subdirectory named after the commercial ID.
8. Write a per-commercial frame manifest.
9. Write a run-level manifest.
10. Log all major events, successes, skips, and failures.

The default sampling strategy should be:

```text
include first frame: yes
include one frame every: 0.25 seconds
include last frame: yes
last-frame offset: 1.0 second before end
resize width: 768 px
maximum selected frames per commercial: no cap
```

When a positive frame cap is configured, for example:

```text
--max-frames 30
```

the programme should apply deterministic chronological even downsampling.

---

## 3. Input / Output

## 3.1 Input

### Input directory

Default input directory:

```text
corpus/02_commercials/
```

The input directory contains individual commercial clips, one file per commercial.

Expected file pattern:

```text
corpus/02_commercials/<Commercial ID>.mp4
```

Example:

```text
corpus/02_commercials/tv_com_1950_001.mp4
```

### Supported video formats

The programme should initially support:

```text
.mp4
```

The design should allow future extension to:

```text
.mov
.mkv
.webm
.avi
```

but the default supported extension list should be:

```text
.mp4
```

### Discovery behavior

Default discovery should be **non-recursive**.

Only video files directly inside the input directory should be considered.

Files should be sorted deterministically by filename or inferred commercial ID.

### Optional metadata source

The programme may optionally accept a metadata file in the future, but it should not require one for this version.

If a metadata file is supported later, it should likely be:

```text
corpus/00_sources/tv_commercials.ndjson
```

For this implementation, the commercial ID is inferred from the video filename stem.

Example:

```text
tv_com_1950_001.mp4 → tv_com_1950_001
```

---

## 3.2 Output

### Output directory

Default output directory:

```text
corpus/05_frames/
```

Each commercial receives its own subdirectory:

```text
corpus/05_frames/<Commercial ID>/
```

Example:

```text
corpus/05_frames/tv_com_1950_001/
```

### Frame output naming

Selected frames should be named in chronological order:

```text
frame_0001.jpg
frame_0002.jpg
frame_0003.jpg
...
```

The per-frame manifest records why each frame was selected, so the selection reason does not need to be encoded in the filename.

Recommended initial naming scheme:

```text
frame_0001.jpg
```

Optional future naming pattern:

```text
frame_0001_000000ms_first.jpg
frame_0002_000250ms_interval.jpg
frame_0003_001000ms_interval.jpg
frame_0120_0028840ms_last.jpg
```

### Per-commercial frame manifest

Each commercial output directory should contain:

```text
frames_manifest.json
```

Example:

```text
corpus/05_frames/tv_com_1950_001/frames_manifest.json
```

This manifest records:

- source video path;
- commercial ID;
- video duration;
- sampling parameters;
- candidate frame count;
- selected frame count;
- whether frame cap was applied;
- all selected frames;
- timestamp for each frame;
- selection reason for each frame.

### Run-level outputs

The programme writes:

```text
corpus/05_frames/sample_commercials_frames.log
corpus/05_frames/sample_commercials_frames_manifest.json
```

It also writes a timestamped per-run manifest:

```text
corpus/05_frames/sample_commercials_frames_manifest_<RUN_ID>.json
```

where `RUN_ID` uses UTC time in filename-safe format:

```text
YYYYMMDDTHHMMSSZ
```

Example:

```text
sample_commercials_frames_manifest_20260521T153012Z.json
```

---

# 4. Sampling Strategy

## 4.1 Conceptual goal

The programme should produce a reproducible visual sequence that captures the commercial’s visual progression at regular temporal intervals.

The selected frames should support later LLM-based interpretation while keeping preprocessing deterministic and interpretation-free.

The frame sampling stage should not:

- classify images;
- detect objects;
- infer meaning;
- call an LLM;
- require API credentials.

---

## 4.2 Default strategy

For each video clip:

```text
1. Probe video duration with ffprobe.
2. Extract first frame at 0.0 seconds.
3. Extract fixed-interval frames every 0.25 seconds.
4. Extract a final frame 1.0 second before the end.
5. Merge candidates.
6. Sort by timestamp.
7. Remove duplicate or near-identical timestamp entries.
8. If max_frames > 0 and candidate count exceeds max_frames, apply chronological even downsampling.
9. Save selected frames.
10. Record selected frame metadata in the per-commercial manifest.
```

Default values:

```text
include_first_frame = true
frame_interval_seconds = 0.25
include_last_frame = true
last_frame_offset_seconds = 1.0
image_width = 768
max_frames = 0
```

`max_frames = 0` means:

```text
no cap
```

---

## 4.3 First frame

The first frame should be included by default because it often establishes:

- setting;
- characters;
- product context;
- initial visual situation;
- historical or stylistic cues.

Default:

```text
include_first_frame = true
first_frame_timestamp_seconds = 0.0
```

FFmpeg-equivalent command:

```bash
ffmpeg -y -ss 0.000 -i input.mp4 -frames:v 1 first_frame.jpg
```

The actual implementation does not need to use this exact command if an equivalent approach is more robust.

If fixed-interval sampling would also create a frame at `0.0` seconds, the duplicate should be avoided or deduplicated.

---

## 4.4 Fixed-interval frames

Fixed-interval frames should be extracted at a regular temporal interval.

Default interval:

```text
frame_interval_seconds = 0.25
```

This means the programme should include one interval frame every quarter second, subject to:

- timestamp deduplication;
- optional maximum frame cap, if `--max-frames` is greater than `0`.

The interval should be configurable:

```text
--frame-interval-seconds 0.25
```

Example values:

| Interval | Meaning                        |
|---------:|--------------------------------|
|   `0.25` | one frame every quarter second |
|   `0.50` | one frame every half second    |
|   `1.00` | one frame every second         |

The fixed-interval candidates should be chronologically ordered and should preserve the commercial’s visual progression without relying on scene-change detection.

If the first frame is explicitly included, the interval sequence should avoid creating a duplicate timestamp at `0.0` seconds.

If the last frame is explicitly included using the configured last-frame offset, interval timestamps at or after that last-frame timestamp may be omitted so that the explicit last-frame candidate remains the final safeguard.

---

## 4.5 Last frame

A frame near the end of the commercial should be included by default because commercials often end with:

- product packshot;
- brand logo;
- slogan;
- price or call-to-action;
- final visual resolution.

Default:

```text
include_last_frame = true
last_frame_offset_seconds = 1.0
```

The intended timestamp is:

```text
max(duration_seconds - last_frame_offset_seconds, 0)
```

FFmpeg-equivalent command:

```bash
ffmpeg -y -ss <duration_seconds - 1.0> -i input.mp4 -frames:v 1 last_frame.jpg
```

If `-sseof` is reliable in a future implementation, this equivalent command may also be used:

```bash
ffmpeg -y -sseof -1 -i input.mp4 -frames:v 1 last_frame.jpg
```

If `-sseof` is unreliable for a given file, the programme should compute duration with `ffprobe` and seek explicitly to:

```text
duration_seconds - last_frame_offset_seconds
```

---

## 4.6 Image resizing

Frames should be resized before saving.

Default image width:

```text
image_width = 768
```

The aspect ratio should be preserved.

FFmpeg scale expression:

```text
scale=768:-1
```

If `--image-width 0` is provided, resizing may be disabled.

Recommended default:

```text
--image-width 768
```

Rationale:

- reduces disk usage;
- reduces later API image-token cost;
- preserves enough detail for general visual description.

For small on-screen text, a later stage may choose to use higher-resolution frames or re-sample specific clips.

---

## 4.7 Optional maximum frame cap

The programme should support an optional configurable cap:

```text
--max-frames N
```

Default:

```text
max_frames = 0
```

Meaning:

```text
0 = no cap
positive integer = maximum selected frames per commercial
```

Examples:

```bash
python sample_commercials_frames.py --no-test-mode --max-frames 0
python sample_commercials_frames.py --no-test-mode --max-frames 30
python sample_commercials_frames.py --no-test-mode --max-frames 120
```

If:

```text
max_frames = 0
```

then all deduplicated candidates are selected.

If:

```text
max_frames > 0
```

and the number of candidates is less than or equal to `max_frames`, all candidates are selected.

If:

```text
max_frames > 0
```

and the number of candidates exceeds `max_frames`, the programme applies deterministic chronological even downsampling.

---

## 4.8 Cap policy: chronological even downsampling

When a positive frame cap is configured, the cap policy should be:

```text
chronological_even
```

This means:

1. Preserve chronological coverage across the whole commercial.
2. Avoid selecting only the beginning of the clip.
3. Prefer retaining first and last chronological candidates.
4. Select the remaining frames evenly from the candidate sequence.

Example:

```text
candidate frames: 120
max_frames: 30

selected:
- first chronological candidate
- 28 evenly distributed intermediate candidates
- last chronological candidate
```

If first and last frames are disabled, the first and last chronological candidates from the available candidate list are still protected by the cap algorithm.

If no cap is configured:

```text
max_frames = 0
cap_policy = none
cap_applied = false
```

The downsampling algorithm should be deterministic.

---

## 4.9 Duplicate handling

The programme should avoid duplicate or near-duplicate timestamp entries caused by overlap between:

- first frame and interval frame at or near `0.0`;
- interval frame and last frame;
- very short clips where first and last safeguards may overlap.

Minimum requirement:

```text
deduplicate by timestamp within tolerance
```

Default timestamp tolerance:

```text
timestamp_tolerance_seconds = 0.10
```

If two candidate frames are within the tolerance, keep the one with the higher-priority selection reason.

Suggested priority:

```text
first_frame > last_frame > interval
```

Alternative future extension:

```text
perceptual hash deduplication
```

This should not be required for this version.

---

# 5. Command-Line Interface

## 5.1 Default test run

```bash
python sample_commercials_frames.py
```

Default behavior:

```text
input_dir = corpus/02_commercials/
output_dir = corpus/05_frames/
test_mode = true
test_limit = 5
reprocess = false
frame_interval_seconds = 0.25
image_width = 768
max_frames = 0
workers = 1
include_first_frame = true
include_last_frame = true
last_frame_offset_seconds = 1.0
```

`max_frames = 0` means no cap.

---

## 5.2 Full run

```bash
python sample_commercials_frames.py --no-test-mode
```

This processes all eligible commercials that need processing.

---

## 5.3 Reprocess existing outputs

```bash
python sample_commercials_frames.py --no-test-mode --reprocess
```

When `--reprocess` is provided, existing frame directories and manifests for the selected commercials should be overwritten or safely cleared and regenerated.

---

## 5.4 Explicit no-cap run

```bash
python sample_commercials_frames.py \
  --no-test-mode \
  --max-frames 0
```

This saves all deduplicated fixed-interval candidates.

---

## 5.5 Custom frame cap

```bash
python sample_commercials_frames.py \
  --no-test-mode \
  --max-frames 30
```

This applies chronological even downsampling if a commercial has more than 30 deduplicated candidate frames.

---

## 5.6 Custom interval sampling

```bash
python sample_commercials_frames.py \
  --no-test-mode \
  --frame-interval-seconds 0.50
```

This samples one interval frame every 0.50 seconds instead of the default 0.25 seconds.

---

## 5.7 Disable resizing

```bash
python sample_commercials_frames.py \
  --no-test-mode \
  --image-width 0
```

This disables frame resizing.

---

## 5.8 Parallel processing

```bash
python sample_commercials_frames.py \
  --no-test-mode \
  --workers 4
```

---

## 5.9 Resume from a specific commercial ID

The programme should support:

```bash
python sample_commercials_frames.py \
  --no-test-mode \
  --start-commercial-id tv_com_1950_025
```

This should process only commercials whose inferred commercial ID is greater than or equal to the provided ID in sorted order.

This is useful for long corpus runs.

---

# 6. CLI Arguments

## 6.1 Standard arguments

| Argument                   |                                                Default | Description                                   |
|----------------------------|-------------------------------------------------------:|-----------------------------------------------|
| `--input-dir PATH`         |                                `corpus/02_commercials` | Directory containing commercial video clips   |
| `--output-dir PATH`        |                                     `corpus/05_frames` | Directory where sampled frames are written    |
| `--test-mode`              |                                                enabled | Limit processing to `--test-limit` items      |
| `--no-test-mode`           |                                               disabled | Process all eligible items                    |
| `--test-limit N`           |                                                    `5` | Maximum items to attempt in test mode         |
| `--reprocess`              |                                                `False` | Regenerate outputs even if they already exist |
| `--workers N`              |                                                    `1` | Number of worker processes                    |
| `--log-file PATH`          |           `<output-dir>/sample_commercials_frames.log` | Log file path                                 |
| `--manifest-file PATH`     | `<output-dir>/sample_commercials_frames_manifest.json` | Latest run manifest                           |
| `--start-commercial-id ID` |                                                 `None` | Resume from this commercial ID onward         |

---

## 6.2 Sampling arguments

| Argument                              |  Default | Description                                                                      |
|---------------------------------------|---------:|----------------------------------------------------------------------------------|
| `--frame-interval-seconds FLOAT`      |   `0.25` | Extract one interval frame every N seconds                                       |
| `--max-frames N`                      |      `0` | Maximum selected frames per commercial; `0` means no cap                         |
| `--image-width N`                     |    `768` | Resize output frames to this width; preserve aspect ratio; `0` disables resizing |
| `--include-first-frame`               |  enabled | Include frame at start of clip                                                   |
| `--no-include-first-frame`            | disabled | Do not explicitly include first frame                                            |
| `--include-last-frame`                |  enabled | Include frame near end of clip                                                   |
| `--no-include-last-frame`             | disabled | Do not explicitly include last frame                                             |
| `--last-frame-offset-seconds FLOAT`   |    `1.0` | Seconds before end for final frame                                               |
| `--timestamp-tolerance-seconds FLOAT` |   `0.10` | Deduplication tolerance for near-identical timestamps                            |

---

## 6.3 Advanced / future arguments

These do not need to be implemented in this version, but the design should allow them later:

| Argument                                           | Purpose                                                     |
|----------------------------------------------------|-------------------------------------------------------------|
| `--metadata-file PATH`                             | Use source metadata file to restrict or annotate processing |
| `--supported-extensions EXT...`                    | Override supported video extensions                         |
| `--cap-policy chronological_even/random_even/none` | Choose frame cap strategy                                   |
| `--save-candidates`                                | Save all candidate frames before capping                    |
| `--candidate-dir PATH`                             | Separate directory for uncapped candidates                  |
| `--perceptual-dedup`                               | Enable perceptual hash duplicate removal                    |
| `--dry-run`                                        | Plan processing without writing frames                      |

---

# 7. Argument Validation

The programme should fail early with clear errors if:

- `--input-dir` does not exist;
- `--input-dir` is not a directory;
- `--output-dir` cannot be created;
- `--test-limit <= 0`;
- `--workers <= 0`;
- `--frame-interval-seconds <= 0`;
- `--max-frames < 0`;
- `--image-width < 0`;
- `--last-frame-offset-seconds < 0`;
- `--timestamp-tolerance-seconds < 0`;
- `ffmpeg` is not available;
- `ffprobe` is not available.

The programme should check `ffmpeg` and `ffprobe` availability during startup.

---

# 8. External Dependencies

The programme requires command-line FFmpeg tools:

```text
ffmpeg
ffprobe
```

These must be installed on the system and available on `PATH`.

The Python implementation should use only standard library modules, for example:

```text
argparse
concurrent.futures
dataclasses
datetime
json
logging
pathlib
shutil
subprocess
sys
tempfile
time
```

No LLM API dependency is needed for this programme.

No OpenAI API key is needed for this programme.

---

# 9. Environment and Configuration

This programme should not require secrets or API credentials.

It may optionally load configuration from environment variables in the future, but this version should be fully controlled by CLI arguments and defaults.

The priority order should be:

```text
CLI arguments > environment variables, if later added > hard-coded defaults
```

No sensitive values should be logged.

---

# 10. Processing Architecture

## 10.1 Startup

At startup, the programme should:

1. Parse CLI arguments.
2. Validate arguments.
3. Create the output directory if needed.
4. Configure logging.
5. Create a run ID.
6. Build the sampling configuration.
7. Log configuration summary.
8. Check for `ffmpeg`.
9. Check for `ffprobe`.

Example startup log:

```text
[2026-05-21 15:30:12] INFO   Starting frame sampling run
[2026-05-21 15:30:12] INFO   Input dir: corpus/02_commercials
[2026-05-21 15:30:12] INFO   Output dir: corpus/05_frames
[2026-05-21 15:30:12] INFO   Test mode: True (limit=5)
[2026-05-21 15:30:12] INFO   Reprocess existing: False
[2026-05-21 15:30:12] INFO   Workers: 1
[2026-05-21 15:30:12] INFO   Frame interval seconds: 0.25
[2026-05-21 15:30:12] INFO   Max frames: no cap
[2026-05-21 15:30:12] INFO   Image width: 768
[2026-05-21 15:30:12] INFO   Include first frame: True
[2026-05-21 15:30:12] INFO   Include last frame: True
[2026-05-21 15:30:12] INFO   Last frame offset seconds: 1.0
```

---

## 10.2 Discovery

The programme should:

1. List files directly in `--input-dir`.
2. Keep files whose extension is in supported extensions.
3. Infer `commercial_id` from filename stem.
4. Sort by `commercial_id` or filename.
5. Apply `--start-commercial-id`, if provided.

Example:

```text
corpus/02_commercials/tv_com_1950_001.mp4
```

becomes:

```text
commercial_id = tv_com_1950_001
```

Discovery summary should be logged:

```text
[2026-05-21 15:30:13] INFO   Discovered 742 commercial video files
```

---

## 10.3 Planning

For each discovered commercial, determine:

```text
input_path
commercial_id
commercial_output_dir
commercial_manifest_path
status: process or skipped_existing
```

A commercial should be skipped if all of the following are true:

- `--reprocess` is false;
- `frames_manifest.json` exists;
- the manifest status indicates prior success;
- at least one selected frame listed in the manifest exists on disk.

If outputs are incomplete or the manifest is missing/corrupt, the programme should reprocess the item unless explicitly configured otherwise.

Recommended behavior:

```text
Apply test limit to items that would be attempted, not to already-skipped items.
```

This makes test mode useful even when earlier files are already complete.

---

## 10.4 Execution

### Sequential mode

If:

```text
workers = 1
```

the programme processes commercials sequentially.

### Parallel mode

If:

```text
workers > 1
```

the programme should use `ProcessPoolExecutor`.

Worker processes should:

- process one commercial at a time;
- call `ffprobe` to determine duration;
- call `ffmpeg` to extract candidate frames;
- apply deduplication;
- apply optional capping;
- write selected frames;
- write per-commercial manifest data;
- return structured result to the main process.

To avoid interleaved logs, workers should avoid writing directly to the shared log file where practical. The main process should log results returned by workers.

---

# 11. Per-Commercial Processing Details

## 11.1 Obtain video duration

Use `ffprobe` to obtain clip duration in seconds.

Equivalent command:

```bash
ffprobe -v error \
  -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 \
  input.mp4
```

If duration cannot be obtained, mark the item as failed.

---

## 11.2 Temporary working directory

Each commercial should be processed in a temporary working directory.

Example:

```text
/tmp/sample_commercials_frames_<commercial_id>_<random>/
```

or a similar system temporary directory.

The programme should:

1. extract candidate frames to the temporary directory;
2. select final frames;
3. write final frames to the commercial output directory;
4. remove the temporary directory on success;
5. clean temporary files on failure according to implementation choice.

Recommended default:

```text
clean temporary files on both success and failure
```

Log enough detail to debug failures.

---

## 11.3 Candidate frame representation

Internally, each candidate frame should have:

```json
{
  "timestamp_seconds": 4.75,
  "selection_reason": "interval",
  "source_temp_path": "/tmp/.../interval_000019.jpg"
}
```

Minimum required fields:

```text
timestamp_seconds
selection_reason
source_temp_path
```

Supported `selection_reason` values:

```text
first_frame
interval
last_frame
```

---

## 11.4 Timestamp extraction

The programme should record timestamps for each selected frame.

For fixed-interval sampling, timestamps are derived from the requested seek timestamps:

```text
0.0
0.25
0.50
0.75
...
duration_seconds - last_frame_offset_seconds
```

The manifest should include:

```json
"timestamp_precision": "approximate"
```

because extracted frame timestamps may not exactly match the requested seek time depending on codec, keyframes, and FFmpeg behavior.

The implementation should not falsely claim exact timestamps if it uses requested seek timestamps only.

---

## 11.5 Candidate extraction

This version uses direct candidate extraction:

- Extract first frame directly, if enabled.
- Extract fixed-interval frames directly.
- Extract last frame directly, if enabled.
- Merge candidates.
- Deduplicate by timestamp tolerance.
- Optionally cap selected frames.
- Write final selected frames.

This approach is simple and deterministic.

A future implementation may generate timestamp candidates first, cap them, and then extract only selected frames for greater disk and processing efficiency.

---

# 12. Frame Capping Algorithm

## 12.1 Inputs

```text
candidates: sorted list of candidate frames
max_frames: integer >= 0
```

## 12.2 Behavior

If:

```text
max_frames = 0
```

then:

```text
selected = candidates
cap_applied = false
cap_policy = none
```

If:

```text
max_frames > 0
len(candidates) <= max_frames
```

then:

```text
selected = candidates
cap_applied = false
cap_policy = chronological_even
```

If:

```text
max_frames > 0
len(candidates) > max_frames
```

then:

```text
selected = chronological_even_downsample(candidates, max_frames)
cap_applied = true
cap_policy = chronological_even
```

---

## 12.3 Chronological even downsampling

Recommended algorithm:

1. Sort candidates by timestamp.
2. If `max_frames = 0`, return all candidates.
3. If `len(candidates) <= max_frames`, return all candidates.
4. If `max_frames = 1`, return the first chronological candidate.
5. Otherwise, protect the first and last chronological candidates.
6. Compute the remaining number of slots.
7. Select evenly spaced indices from the unprotected middle candidates.
8. Merge protected and selected middle candidates.
9. Sort final selection by timestamp.
10. Remove any accidental duplicates if needed.

Example:

```text
candidate_count = 120
max_frames = 30
protected = first + last
remaining_slots = 28
middle_candidates = candidates[1:-1]
select 28 evenly spaced candidates from middle_candidates
```

The algorithm should be deterministic and documented in the function docstring.

---

# 13. Output Manifest Design

## 13.1 Per-commercial manifest

Path:

```text
corpus/05_frames/<Commercial ID>/frames_manifest.json
```

Example structure for default no-cap sampling:

```json
{
  "commercial_id": "tv_com_1950_001",
  "status": "success",
  "source_video": "corpus/02_commercials/tv_com_1950_001.mp4",
  "output_dir": "corpus/05_frames/tv_com_1950_001",
  "duration_seconds": 29.84,
  "timestamp_precision": "approximate",
  "sampling_config": {
    "strategy": "fixed_interval_with_first_last",
    "frame_interval_seconds": 0.25,
    "include_first_frame": true,
    "include_last_frame": true,
    "last_frame_offset_seconds": 1.0,
    "image_width": 768,
    "max_frames": 0,
    "max_frames_meaning": "no_cap",
    "cap_policy": "none",
    "timestamp_tolerance_seconds": 0.1
  },
  "candidate_frame_count": 117,
  "selected_frame_count": 117,
  "cap_applied": false,
  "frames": [
    {
      "frame_index": 1,
      "filename": "frame_0001.jpg",
      "path": "corpus/05_frames/tv_com_1950_001/frame_0001.jpg",
      "timestamp_seconds": 0.0,
      "selection_reason": "first_frame"
    },
    {
      "frame_index": 2,
      "filename": "frame_0002.jpg",
      "path": "corpus/05_frames/tv_com_1950_001/frame_0002.jpg",
      "timestamp_seconds": 0.25,
      "selection_reason": "interval"
    },
    {
      "frame_index": 117,
      "filename": "frame_0117.jpg",
      "path": "corpus/05_frames/tv_com_1950_001/frame_0117.jpg",
      "timestamp_seconds": 28.84,
      "selection_reason": "last_frame"
    }
  ],
  "created_at": "2026-05-21T15:30:34Z",
  "error": null
}
```

Example structure when a positive cap is applied:

```json
{
  "commercial_id": "tv_com_1950_001",
  "status": "success",
  "source_video": "corpus/02_commercials/tv_com_1950_001.mp4",
  "output_dir": "corpus/05_frames/tv_com_1950_001",
  "duration_seconds": 29.84,
  "timestamp_precision": "approximate",
  "sampling_config": {
    "strategy": "fixed_interval_with_first_last",
    "frame_interval_seconds": 0.25,
    "include_first_frame": true,
    "include_last_frame": true,
    "last_frame_offset_seconds": 1.0,
    "image_width": 768,
    "max_frames": 30,
    "max_frames_meaning": "maximum_selected_frames",
    "cap_policy": "chronological_even",
    "timestamp_tolerance_seconds": 0.1
  },
  "candidate_frame_count": 117,
  "selected_frame_count": 30,
  "cap_applied": true,
  "frames": [
    {
      "frame_index": 1,
      "filename": "frame_0001.jpg",
      "path": "corpus/05_frames/tv_com_1950_001/frame_0001.jpg",
      "timestamp_seconds": 0.0,
      "selection_reason": "first_frame"
    },
    {
      "frame_index": 2,
      "filename": "frame_0002.jpg",
      "path": "corpus/05_frames/tv_com_1950_001/frame_0002.jpg",
      "timestamp_seconds": 1.0,
      "selection_reason": "interval"
    },
    {
      "frame_index": 30,
      "filename": "frame_0030.jpg",
      "path": "corpus/05_frames/tv_com_1950_001/frame_0030.jpg",
      "timestamp_seconds": 28.84,
      "selection_reason": "last_frame"
    }
  ],
  "created_at": "2026-05-21T15:30:34Z",
  "error": null
}
```

---

## 13.2 Run-level manifest

The latest manifest should be written to:

```text
corpus/05_frames/sample_commercials_frames_manifest.json
```

A timestamped manifest should also be written to:

```text
corpus/05_frames/sample_commercials_frames_manifest_<RUN_ID>.json
```

Example structure:

```json
{
  "run_metadata": {
    "run_id": "20260521T153012Z",
    "tool_name": "sample_commercials_frames",
    "version": "v2",
    "start_time": "2026-05-21T15:30:12Z",
    "end_time": "2026-05-21T15:35:48Z",
    "test_mode": true,
    "test_limit": 5,
    "reprocess": false,
    "workers": 1,
    "input_source": "corpus/02_commercials",
    "output_dir": "corpus/05_frames",
    "config": {
      "supported_extensions": [".mp4"],
      "strategy": "fixed_interval_with_first_last",
      "frame_interval_seconds": 0.25,
      "include_first_frame": true,
      "include_last_frame": true,
      "last_frame_offset_seconds": 1.0,
      "image_width": 768,
      "max_frames": 0,
      "max_frames_meaning": "no_cap",
      "cap_policy": "none",
      "timestamp_tolerance_seconds": 0.1
    }
  },
  "files": [
    {
      "commercial_id": "tv_com_1950_001",
      "input_path": "corpus/02_commercials/tv_com_1950_001.mp4",
      "output_path": "corpus/05_frames/tv_com_1950_001",
      "manifest_path": "corpus/05_frames/tv_com_1950_001/frames_manifest.json",
      "status": "success",
      "error": null,
      "duration_seconds": 2.84,
      "timestamp": "2026-05-21T15:30:34Z",
      "metadata": {
        "video_duration_seconds": 29.84,
        "candidate_frame_count": 117,
        "selected_frame_count": 117,
        "cap_applied": false
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
corpus/05_frames/sample_commercials_frames.log
```

Log format:

```text
[YYYY-MM-DD HH:MM:SS] LEVEL  message
```

Minimum log events:

- startup;
- parsed configuration summary;
- FFmpeg/FFprobe availability;
- discovery summary;
- planning summary;
- test-mode summary;
- per-item skip;
- per-item success;
- per-item failure;
- manifest writing;
- end-of-run summary;
- keyboard interrupt;
- fatal configuration errors.

Example:

```text
[2026-05-21 15:30:12] INFO   Starting frame sampling run
[2026-05-21 15:30:12] INFO   Input dir: corpus/02_commercials
[2026-05-21 15:30:12] INFO   Output dir: corpus/05_frames
[2026-05-21 15:30:12] INFO   Frame interval seconds: 0.25
[2026-05-21 15:30:12] INFO   Max frames: no cap
[2026-05-21 15:30:12] INFO   Image width: 768
[2026-05-21 15:30:13] INFO   Discovered 742 commercial video files
[2026-05-21 15:30:13] INFO   Planned 5 commercials for processing
[2026-05-21 15:30:34] INFO   SUCCESS tv_com_1950_001 candidates=117 selected=117 cap_applied=False
[2026-05-21 15:30:51] INFO   SUCCESS tv_com_1950_002 candidates=57 selected=57 cap_applied=False
[2026-05-21 15:35:48] INFO   Wrote manifest: corpus/05_frames/sample_commercials_frames_manifest.json
[2026-05-21 15:35:48] INFO   Completed frame sampling run: attempted=5 succeeded=5 failed=0 skipped_existing=0
```

Failure example:

```text
[2026-05-21 15:31:18] ERROR  FAILED tv_com_1950_003 ffprobe could not determine duration
```

Skip example:

```text
[2026-05-21 15:31:18] INFO   SKIPPED_EXISTING tv_com_1950_004 corpus/05_frames/tv_com_1950_004
```

---

# 15. Error Handling

## 15.1 Configuration errors

Configuration errors should stop the programme before processing begins.

Examples:

- missing input directory;
- invalid frame interval;
- invalid frame cap;
- missing `ffmpeg`;
- missing `ffprobe`;
- output directory cannot be created.

Exit code:

```text
2
```

---

## 15.2 Per-item errors

Per-commercial errors should not abort the whole run.

If one commercial fails:

1. Mark it as `failed`.
2. Record the error in the run manifest.
3. Log the error.
4. Continue with the next commercial.

Examples:

- corrupt video file;
- `ffprobe` cannot read duration;
- `ffmpeg` exits non-zero;
- no frames could be extracted;
- output directory cannot be written.

Exit code should be non-zero if any attempted item failed.

Recommended:

```text
0 = all attempted items succeeded or were skipped
1 = one or more per-item failures
2 = configuration or argument error
130 = interrupted by user
```

---

## 15.3 Keyboard interrupt

On `KeyboardInterrupt`, the programme should:

1. Stop submitting new work where practical.
2. Allow current item to finish if practical, or terminate workers.
3. Write a partial run manifest if possible.
4. Log interruption.
5. Exit with code `130`.

---

# 16. Resumability and Safe Re-runs

By default, the programme must be safe to re-run.

If a commercial already has a valid successful manifest and selected frame files, it should be skipped.

Default behavior:

```text
reprocess = false
```

To force regeneration:

```bash
python sample_commercials_frames.py --reprocess
```

When reprocessing, the programme should:

1. remove or replace existing frame files for that commercial;
2. regenerate frames;
3. overwrite `frames_manifest.json`.

To avoid mixed old/new outputs, the programme should preferably clear the final output directory before writing regenerated outputs.

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
python sample_commercials_frames.py
```

should process up to 5 commercials that need processing.

Full run:

```bash
python sample_commercials_frames.py --no-test-mode
```

The log should clearly indicate when test mode is enabled:

```text
[2026-05-21 15:30:12] INFO   Test mode: True (limit=5)
```

Test mode should count attempted items, not already-skipped items.

---

# 18. Docstring Requirements

The implementation must include a module-level docstring explaining:

- purpose of the programme;
- input directory and expected video files;
- output directory and frame structure;
- default sampling strategy;
- example commands;
- `--max-frames 0` meaning no cap;
- note that this programme does not call an LLM;
- dependency on `ffmpeg` and `ffprobe`.

Example content for the module-level docstring:

```python
"""
Sample representative frames from TV commercial clips.

This programme reads individual commercial video files from an input directory,
extracts a reproducible storyboard using first-frame, fixed-interval, and
last-frame sampling, and writes selected JPEG frames plus JSON manifests to an
output directory.

Default input:
    corpus/02_commercials/

Default output:
    corpus/05_frames/

Default sampling strategy:
    include first frame: yes
    include one frame every: 0.25 seconds
    include last frame: yes
    last-frame offset: 1.0 second before end
    resize width: 768 px
    maximum selected frames: no cap

Typical usage:
    python sample_commercials_frames.py
    python sample_commercials_frames.py --no-test-mode
    python sample_commercials_frames.py --no-test-mode --frame-interval-seconds 0.50
    python sample_commercials_frames.py --no-test-mode --max-frames 0
    python sample_commercials_frames.py --no-test-mode --max-frames 120

The programme does not call any LLM or perform visual interpretation. It prepares
ordered frame sequences for a later multimodal analysis stage.

Requires ffmpeg and ffprobe on PATH.
"""
```

Core functions should also include docstrings, especially:

- argument parsing;
- FFmpeg/FFprobe checks;
- video discovery;
- planning;
- duration probing;
- frame extraction;
- interval timestamp generation;
- candidate deduplication;
- optional frame capping;
- per-commercial processing;
- manifest writing;
- main orchestration.

---

# 19. Recommended Internal Functions

The implementation should be organized around small, testable functions.

Suggested functions:

```python
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""


def validate_args(args: argparse.Namespace) -> None:
    """Validate CLI arguments and fail early on configuration errors."""


def check_external_tools() -> None:
    """Verify that ffmpeg and ffprobe are available on PATH."""


def discover_videos(input_dir: Path, supported_extensions: set[str]) -> list[VideoItem]:
    """Discover eligible video files non-recursively and return sorted items."""


def plan_work(...) -> tuple[list[WorkItem], list[ProcessingResult]]:
    """Decide which items should be processed or skipped."""


def probe_duration(video_path: Path) -> float:
    """Return video duration in seconds using ffprobe."""


def extract_frame_at_timestamp(...) -> None:
    """Extract one frame at a given timestamp using ffmpeg."""


def extract_first_frame(...) -> CandidateFrame:
    """Extract the first frame and return candidate metadata."""


def extract_last_frame(...) -> CandidateFrame:
    """Extract a frame near the end and return candidate metadata."""


def interval_timestamps(...) -> list[float]:
    """Return fixed-interval timestamps within the video duration."""


def extract_interval_frames(...) -> list[CandidateFrame]:
    """Extract fixed-interval frames and return candidate metadata."""


def deduplicate_candidates(...) -> list[CandidateFrame]:
    """Remove duplicate candidates by timestamp tolerance and reason priority."""


def cap_candidates_evenly(...) -> tuple[list[CandidateFrame], bool]:
    """Apply optional deterministic chronological even downsampling."""


def write_selected_frames(...) -> list[SelectedFrame]:
    """Write selected frames to final output names."""


def process_commercial(...) -> ProcessingResult:
    """Process one commercial and return a structured result."""


def write_commercial_manifest(...) -> None:
    """Write frames_manifest.json for one commercial."""


def write_run_manifest(...) -> None:
    """Write latest and timestamped run manifests."""


def main() -> int:
    """Main orchestration entry point."""
```

Suggested data classes:

```python
@dataclass(frozen=True)
class VideoItem:
    commercial_id: str
    input_path: Path


@dataclass(frozen=True)
class WorkItem:
    commercial_id: str
    input_path: Path
    output_dir: Path
    manifest_path: Path


@dataclass(frozen=True)
class SamplingConfig:
    frame_interval_seconds: float
    max_frames: int
    image_width: int
    include_first_frame: bool
    include_last_frame: bool
    last_frame_offset_seconds: float
    timestamp_tolerance_seconds: float


@dataclass(frozen=True)
class CandidateFrame:
    timestamp_seconds: float
    selection_reason: str
    temp_path: Path


@dataclass(frozen=True)
class SelectedFrame:
    frame_index: int
    timestamp_seconds: float
    selection_reason: str
    filename: str
    path: Path


@dataclass(frozen=True)
class ProcessingResult:
    commercial_id: str
    input_path: Path
    output_dir: Path
    manifest_path: Path
    status: str
    error: str | None
    duration_seconds: float
    video_duration_seconds: float | None
    candidate_frame_count: int
    selected_frame_count: int
    cap_applied: bool
    timestamp: str
```

---

# 20. README Section

A short README section should be added or updated when the programme is implemented.

Suggested README text:

```markdown
### Sample commercial frames

The `sample_commercials_frames.py` programme samples frames from commercial clips in
`corpus/02_commercials/` and writes ordered frame sequences to `corpus/05_frames/`.

The sampler uses a fixed-interval strategy with safeguards:

- first frame;
- one frame every 0.25 seconds by default;
- final frame 1.0 second before the end;
- resize width of 768 px;
- optional maximum frame cap with chronological even downsampling.

By default, `--max-frames 0` means no cap, so all deduplicated sampled frames are saved.

Default test run:

```bash
python sample_commercials_frames.py
```

Full run:

```bash
python sample_commercials_frames.py --no-test-mode
```

Use a different interval:

```bash
python sample_commercials_frames.py --no-test-mode --frame-interval-seconds 0.50
```

Apply a frame cap:

```bash
python sample_commercials_frames.py --no-test-mode --max-frames 30
```

Explicitly disable the cap:

```bash
python sample_commercials_frames.py --no-test-mode --max-frames 0
```

Outputs are written to:

```text
corpus/05_frames/<Commercial ID>/
```

Each commercial directory contains selected JPEG frames and a `frames_manifest.json`
file recording timestamps, selection reasons, frame counts, and sampling parameters.
```

---

# 21. Acceptance Criteria

The implementation is acceptable when:

1. `python sample_commercials_frames.py` runs in test mode by default.
2. The programme discovers `.mp4` files in `corpus/02_commercials/`.
3. The programme processes up to 5 eligible commercials by default.
4. Each processed commercial gets an output directory under `corpus/05_frames/`.
5. Each output directory contains selected `.jpg` frames.
6. Each output directory contains `frames_manifest.json`.
7. First frame and last frame are included by default when extraction succeeds.
8. Fixed-interval frames are extracted every `--frame-interval-seconds`, defaulting to `0.25`.
9. Output frames are resized to width `768` by default.
10. `--image-width 0` disables resizing.
11. `--max-frames 0` means no cap.
12. When `--max-frames 0`, all deduplicated candidates are selected.
13. When `--max-frames` is positive, no more than that many frames are selected per commercial.
14. Frame cap, when applied, preserves chronological coverage.
15. Existing successful outputs are skipped unless `--reprocess` is used.
16. The programme writes an append-style log file.
17. The programme writes latest and timestamped run manifests.
18. Per-item failures do not stop the full run.
19. The programme exits non-zero if any attempted item fails.
20. The code includes clear module-level and function docstrings.
21. The programme does not call an LLM or require API credentials.

---

# 22. Design Rationale

This programme separates visual preprocessing from LLM interpretation.

That separation is important because:

- frame sampling is deterministic and reproducible;
- fixed-interval sampling provides regular temporal coverage;
- the sampled frames can be inspected manually;
- image-token cost can be estimated before LLM calls;
- interval and cap settings can be tuned empirically;
- later visual interpretation prompts can evolve independently;
- manifests preserve the exact visual evidence given to the model.

The selected default strategy, **fixed-interval sampling every 0.25 seconds with first/last safeguards and no cap**, is designed to provide dense, regular visual coverage of short TV commercials.

A positive `--max-frames` value remains available for cost control or smaller storyboard generation.