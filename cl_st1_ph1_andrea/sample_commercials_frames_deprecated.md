# Specification: `sample_commercials_frames.py`

## 1. Programme Summary

`sample_commercials_frames.py` samples representative still frames from individual TV commercial video clips.

The programme is designed as the **first stage** of a two-stage visual analysis pipeline:

```text
Stage 1: sample_commercials_frames.py
    commercial video clips → representative frame sequences + manifests

Stage 2: visual interpretation programme
    sampled frames → LLM-based visual description / annotation
```

The purpose of this programme is **not** to interpret the images. Its purpose is to create a reproducible, cost-aware, chronologically ordered storyboard for each commercial, suitable for later submission to a multimodal LLM.

The programme reads commercial video files from an input directory, applies a scene-change-based frame sampling strategy with safeguards, writes selected frames to one subdirectory per commercial, and records all processing decisions in logs and JSON manifests.

---

## 2. High-Level Functionality

For each commercial video clip, the programme should:

1. Discover eligible video files in the input directory.
2. Determine whether the clip should be processed or skipped.
3. Extract a candidate frame set using:
   - first frame;
   - scene-change frames;
   - final frame near the end.
4. Sort all candidate frames chronologically.
5. Remove exact duplicate timestamps or duplicate output entries if needed.
6. Apply a maximum frame cap if too many frames were selected.
7. Write selected frames to an output subdirectory named after the commercial ID.
8. Write a per-commercial frame manifest.
9. Write a run-level manifest.
10. Log all major events, successes, skips, and failures.

The default sampling strategy should be:

```text
include first frame: yes
include scene-change frames: yes
scene threshold: 0.25
include last frame: yes
last-frame offset: 1.0 second before end
resize width: 768 px
maximum selected frames per commercial: 30
```

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

Files should be sorted deterministically by filename.

### Optional metadata source

The programme may optionally accept a metadata file, but it should not require one for its initial version.

If a metadata file is supported later, it should likely be:

```text
corpus/00_sources/tv_commercials.ndjson
```

For the first implementation, the commercial ID can be inferred from the video filename stem.

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

Optional future naming pattern:

```text
frame_0001_000000ms_first.jpg
frame_0002_0002450ms_scene.jpg
frame_0003_0028800ms_last.jpg
```

However, the recommended initial naming scheme is the simpler:

```text
frame_0001.jpg
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
- duration;
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

The programme should produce a compact visual storyboard that captures the commercial’s main visual progression while avoiding unnecessary frame volume.

The selected frames should support later LLM-based interpretation while controlling image-token cost.

The frame sampling stage should remain **interpretation-free**. It should not classify images, detect objects, infer meaning, or call an LLM.

---

## 4.2 Default strategy

For each video clip:

```text
1. Extract first frame.
2. Extract scene-change frames using FFmpeg scene detection.
3. Extract a final frame near the end.
4. Merge candidates.
5. Sort by timestamp.
6. Remove duplicate or near-identical timestamp entries.
7. If candidate count exceeds max_frames, apply chronological even downsampling.
8. Save selected frames.
9. Record all selected and discarded candidate metadata in the manifest.
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
ffmpeg -y -i input.mp4 -frames:v 1 first_frame.jpg
```

The actual implementation does not need to use this exact command if an equivalent approach is more robust.

---

## 4.4 Scene-change frames

Scene-change frames should be extracted using FFmpeg’s `select` video filter.

Default scene threshold:

```text
scene_threshold = 0.25
```

FFmpeg-equivalent command:

```bash
ffmpeg -i input.mp4 \
  -vf "select='gt(scene,0.25)',scale=768:-1" \
  -vsync vfr \
  scene_%04d.jpg
```

The threshold should be configurable.

Suggested threshold meanings:

| Threshold | Behavior |
|---:|---|
| `0.15` | Sensitive; many frames |
| `0.20` | Moderately sensitive |
| `0.25` | Balanced default |
| `0.30` | Conservative |
| `0.40` | Very conservative |

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
ffmpeg -y -sseof -1 -i input.mp4 -frames:v 1 last_frame.jpg
```

If `-sseof` is unreliable for a given file, the programme may compute the duration with `ffprobe` and seek explicitly to:

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

For small on-screen text, a later LLM stage may choose to use higher-resolution frames or re-sample specific clips.

---

## 4.7 Maximum frame cap

The programme should support a configurable cap:

```text
--max-frames 30
```

Default:

```text
max_frames = 30
```

If the number of candidate frames is less than or equal to `max_frames`, all candidates are selected.

If the number of candidate frames exceeds `max_frames`, the programme applies a deterministic downsampling policy.

---

## 4.8 Cap policy: chronological even downsampling

The default cap policy should be:

```text
chronological_even
```

This means:

1. Preserve chronological coverage across the whole commercial.
2. Avoid selecting only the beginning of the clip.
3. Prefer retaining first and last frames when they are enabled.
4. Select the remaining frames evenly from the candidate sequence.

Example:

```text
candidate frames: 82
max_frames: 30

selected:
- first frame
- 28 evenly distributed intermediate frames
- last frame
```

If first and last frames are disabled, select `max_frames` evenly distributed frames from the full candidate list.

The downsampling algorithm should be deterministic.

---

## 4.9 Duplicate handling

The programme should avoid duplicate or near-duplicate timestamp entries caused by overlap between:

- first frame and scene-change frame;
- scene-change frame and last frame;
- repeated FFmpeg selections near cuts or fades.

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
first_frame > last_frame > scene_change
```

Alternative future extension:

```text
perceptual hash deduplication
```

This should not be required for the initial version.

---

## 4.10 Optional minimum time gap

The initial version may include, or leave for future implementation, a minimum time gap between selected scene-change frames.

Optional parameter:

```text
--min-scene-gap-seconds 0.0
```

Default:

```text
0.0
```

If enabled, scene-change candidates less than this many seconds apart should be filtered before the frame cap is applied.

Potential values:

```text
0.5
0.75
1.0
```

This can help with rapid cuts, flashes, fades, or noisy scene detection.

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
scene_threshold = 0.25
image_width = 768
max_frames = 30
workers = 1
```

---

## 5.2 Full run

```bash
python sample_commercials_frames.py --no-test-mode
```

---

## 5.3 Reprocess existing outputs

```bash
python sample_commercials_frames.py --no-test-mode --reprocess
```

When `--reprocess` is provided, existing frame directories and manifests for the selected commercial should be overwritten or safely cleared and regenerated.

---

## 5.4 Custom frame cap

```bash
python sample_commercials_frames.py \
  --no-test-mode \
  --max-frames 20
```

---

## 5.5 More conservative scene detection

```bash
python sample_commercials_frames.py \
  --no-test-mode \
  --scene-threshold 0.30
```

---

## 5.6 More sensitive scene detection

```bash
python sample_commercials_frames.py \
  --no-test-mode \
  --scene-threshold 0.20
```

---

## 5.7 Parallel processing

```bash
python sample_commercials_frames.py \
  --no-test-mode \
  --workers 4
```

---

## 5.8 Resume from a specific commercial ID

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

| Argument | Default | Description |
|---|---:|---|
| `--input-dir PATH` | `corpus/02_commercials` | Directory containing commercial video clips |
| `--output-dir PATH` | `corpus/05_frames` | Directory where sampled frames are written |
| `--test-mode` | enabled | Limit processing to `--test-limit` items |
| `--no-test-mode` | disabled | Process all eligible items |
| `--test-limit N` | `5` | Maximum items to attempt in test mode |
| `--reprocess` | `False` | Regenerate outputs even if they already exist |
| `--workers N` | `1` | Number of worker processes |
| `--log-file PATH` | `<output-dir>/sample_commercials_frames.log` | Log file path |
| `--manifest-file PATH` | `<output-dir>/sample_commercials_frames_manifest.json` | Latest run manifest |
| `--start-commercial-id ID` | `None` | Resume from this commercial ID onward |

---

## 6.2 Sampling arguments

| Argument | Default | Description |
|---|---:|---|
| `--scene-threshold FLOAT` | `0.25` | FFmpeg scene-change threshold |
| `--max-frames N` | `30` | Maximum selected frames per commercial |
| `--image-width N` | `768` | Resize output frames to this width; preserve aspect ratio |
| `--include-first-frame` | enabled | Include frame at start of clip |
| `--no-include-first-frame` | disabled | Do not force first frame |
| `--include-last-frame` | enabled | Include frame near end of clip |
| `--no-include-last-frame` | disabled | Do not force last frame |
| `--last-frame-offset-seconds FLOAT` | `1.0` | Seconds before end for final frame |
| `--timestamp-tolerance-seconds FLOAT` | `0.10` | Deduplication tolerance for near-identical timestamps |
| `--min-scene-gap-seconds FLOAT` | `0.0` | Optional minimum gap between scene-change candidates |

---

## 6.3 Advanced / future arguments

These do not need to be implemented in the first version, but the design should allow them later:

| Argument | Purpose |
|---|---|
| `--metadata-file PATH` | Use source metadata file to restrict or annotate processing |
| `--supported-extensions EXT...` | Override supported video extensions |
| `--cap-policy chronological_even/random_even/none` | Choose frame cap strategy |
| `--save-candidates` | Save all candidate frames before capping |
| `--candidate-dir PATH` | Separate directory for uncapped candidates |
| `--perceptual-dedup` | Enable perceptual hash duplicate removal |
| `--dry-run` | Plan processing without writing frames |

---

# 7. Argument Validation

The programme should fail early with clear errors if:

- `--input-dir` does not exist;
- `--input-dir` is not readable;
- `--output-dir` cannot be created;
- `--test-limit <= 0`;
- `--workers <= 0`;
- `--scene-threshold <= 0` or `--scene-threshold >= 1`;
- `--max-frames <= 0`;
- `--image-width < 0`;
- `--last-frame-offset-seconds < 0`;
- `--timestamp-tolerance-seconds < 0`;
- `--min-scene-gap-seconds < 0`;
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

The Python implementation should use only standard library modules where possible, for example:

```text
argparse
concurrent.futures
dataclasses
datetime
json
logging
math
os
pathlib
shutil
subprocess
sys
tempfile
time
traceback
```

No LLM API dependency is needed for this programme.

No OpenAI API key is needed for this programme.

---

# 9. Environment and Configuration

This programme should not require secrets or API credentials.

It may optionally load configuration from environment variables in the future, but the first version should be fully controlled by CLI arguments and defaults.

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
3. Check for `ffmpeg`.
4. Check for `ffprobe`.
5. Create the output directory if needed.
6. Configure logging.
7. Create a run ID.
8. Log configuration summary.

Example startup log:

```text
[2026-05-21 15:30:12] INFO   Starting frame sampling run
[2026-05-21 15:30:12] INFO   Input dir: corpus/02_commercials
[2026-05-21 15:30:12] INFO   Output dir: corpus/05_frames
[2026-05-21 15:30:12] INFO   Test mode: True (limit=5)
[2026-05-21 15:30:12] INFO   Reprocess existing: False
[2026-05-21 15:30:12] INFO   Workers: 1
[2026-05-21 15:30:12] INFO   Scene threshold: 0.25
[2026-05-21 15:30:12] INFO   Max frames: 30
[2026-05-21 15:30:12] INFO   Image width: 768
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
- output subdirectory exists;
- `frames_manifest.json` exists;
- the manifest status indicates prior success;
- at least one selected frame listed in the manifest exists on disk.

If outputs are incomplete or manifest is missing/corrupt, the programme should reprocess the item unless explicitly configured otherwise.

Test mode should apply after skip planning or before skip planning?

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
- apply deduplication and capping;
- write selected frames;
- write or return per-commercial manifest data;
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
corpus/05_frames/.tmp_<commercial_id>_<run_id>/
```

or system temp directory.

The programme should:

1. extract candidate frames to the temporary directory;
2. select final frames;
3. write final frames to the commercial output directory;
4. remove the temporary directory on success;
5. preserve or clean the temporary directory on failure according to implementation choice.

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
  "candidate_id": "scene_0004",
  "timestamp_seconds": 4.72,
  "selection_reason": "scene_change",
  "source_temp_path": "/tmp/.../scene_0004.jpg",
  "scene_score": null
}
```

`scene_score` may be unavailable in the first implementation.

Minimum required fields:

```text
timestamp_seconds
selection_reason
source_temp_path
```

---

## 11.4 Timestamp extraction

The programme should attempt to record timestamps for each selected frame.

Preferred approaches:

1. Use FFmpeg output naming with PTS if reliable.
2. Use `showinfo` logs to capture timestamps.
3. Approximate timestamps when exact extraction is impractical.

For the first version, acceptable timestamp precision is approximate, provided the manifest includes:

```json
"timestamp_precision": "approximate"
```

If exact timestamps are available:

```json
"timestamp_precision": "pts"
```

The implementation should not falsely claim exact timestamps if it uses approximate frame ordering only.

---

## 11.5 Candidate extraction

The programme may implement extraction either as:

### Approach A: Extract each selected candidate directly

- Extract first frame directly.
- Extract last frame directly.
- Extract scene-change frames directly.
- Then merge and cap.

### Approach B: Generate a candidate list first, then extract selected frames

- Detect scene-change timestamps.
- Add first/last timestamps.
- Deduplicate and cap timestamp list.
- Extract only selected frames.

Approach B is more disk-efficient, but Approach A may be easier initially.

The specification allows either approach as long as:

- selected frames are correctly written;
- manifest records selected frames;
- cap is enforced;
- results are deterministic.

---

# 12. Frame Capping Algorithm

## 12.1 Inputs

```text
candidates: sorted list of candidate frames
max_frames: positive integer
include_first_frame: bool
include_last_frame: bool
```

## 12.2 Behavior

If:

```text
len(candidates) <= max_frames
```

then:

```text
selected = candidates
cap_applied = false
```

If:

```text
len(candidates) > max_frames
```

then:

```text
selected = chronological_even_downsample(candidates, max_frames)
cap_applied = true
```

---

## 12.3 Chronological even downsampling

Recommended algorithm:

1. Sort candidates by timestamp.
2. If first and last candidates are protected, reserve them.
3. Compute the remaining number of slots.
4. Select evenly spaced indices from the unprotected middle candidates.
5. Merge protected and selected middle candidates.
6. Sort final selection by timestamp.
7. Remove any accidental duplicates.

For example:

```text
candidate_count = 82
max_frames = 30
protected = first + last
remaining_slots = 28
middle_candidates = candidates[1:-1]
select 28 evenly spaced candidates from middle_candidates
```

The algorithm should be deterministic and documented in the module/function docstring.

---

# 13. Output Manifest Design

## 13.1 Per-commercial manifest

Path:

```text
corpus/05_frames/<Commercial ID>/frames_manifest.json
```

Example structure:

```json
{
  "commercial_id": "tv_com_1950_001",
  "status": "success",
  "source_video": "corpus/02_commercials/tv_com_1950_001.mp4",
  "output_dir": "corpus/05_frames/tv_com_1950_001",
  "duration_seconds": 29.84,
  "timestamp_precision": "approximate",
  "sampling_config": {
    "strategy": "scene_change_with_first_last",
    "scene_threshold": 0.25,
    "include_first_frame": true,
    "include_last_frame": true,
    "last_frame_offset_seconds": 1.0,
    "image_width": 768,
    "max_frames": 30,
    "cap_policy": "chronological_even",
    "timestamp_tolerance_seconds": 0.1,
    "min_scene_gap_seconds": 0.0
  },
  "candidate_frame_count": 42,
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
      "timestamp_seconds": 2.4,
      "selection_reason": "scene_change"
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
    "version": "v1",
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
      "strategy": "scene_change_with_first_last",
      "scene_threshold": 0.25,
      "include_first_frame": true,
      "include_last_frame": true,
      "last_frame_offset_seconds": 1.0,
      "image_width": 768,
      "max_frames": 30,
      "cap_policy": "chronological_even",
      "timestamp_tolerance_seconds": 0.1,
      "min_scene_gap_seconds": 0.0
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
        "candidate_frame_count": 42,
        "selected_frame_count": 30,
        "cap_applied": true
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
[2026-05-21 15:30:13] INFO   Discovered 742 commercial video files
[2026-05-21 15:30:13] INFO   Planned 5 commercials for processing
[2026-05-21 15:30:34] INFO   SUCCESS tv_com_1950_001 candidates=42 selected=30 cap_applied=True
[2026-05-21 15:30:51] INFO   SUCCESS tv_com_1950_002 candidates=12 selected=12 cap_applied=False
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
- invalid threshold;
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

1. Stop submitting new work.
2. Allow current item to finish if practical, or terminate workers.
3. Write a partial run manifest.
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

To avoid mixed old/new outputs, the programme should preferably write to a temporary directory first and then atomically replace the final directory where feasible.

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

---

# 18. Docstring Requirements

The implementation must include a module-level docstring explaining:

- purpose of the programme;
- input directory and expected video files;
- output directory and frame structure;
- default sampling strategy;
- example commands;
- note that this programme does not call an LLM;
- dependency on `ffmpeg` and `ffprobe`.

Example content for the module-level docstring:

```python
"""
Sample representative frames from TV commercial clips.

This programme reads individual commercial video files from an input directory,
extracts a cost-aware storyboard using first-frame, scene-change, and last-frame
sampling, and writes selected JPEG frames plus JSON manifests to an output
directory.

Default input:
    corpus/02_commercials/

Default output:
    corpus/05_frames/

Typical usage:
    python sample_commercials_frames.py
    python sample_commercials_frames.py --no-test-mode
    python sample_commercials_frames.py --no-test-mode --max-frames 20

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
- candidate deduplication;
- frame capping;
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


def plan_work(items: list[VideoItem], args: argparse.Namespace) -> list[WorkItem]:
    """Decide which items should be processed or skipped."""


def probe_duration(video_path: Path) -> float:
    """Return video duration in seconds using ffprobe."""


def extract_first_frame(...) -> CandidateFrame:
    """Extract the first frame and return candidate metadata."""


def extract_scene_change_frames(...) -> list[CandidateFrame]:
    """Extract scene-change frames and return candidate metadata."""


def extract_last_frame(...) -> CandidateFrame:
    """Extract a frame near the end and return candidate metadata."""


def deduplicate_candidates(...) -> list[CandidateFrame]:
    """Remove duplicate candidates by timestamp tolerance and reason priority."""


def cap_candidates_evenly(...) -> tuple[list[CandidateFrame], bool]:
    """Apply deterministic chronological even downsampling."""


def write_selected_frames(...) -> list[SelectedFrame]:
    """Write selected frames to final output names."""


def process_commercial(work_item: WorkItem, config: SamplingConfig) -> ProcessingResult:
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
@dataclass
class VideoItem:
    commercial_id: str
    input_path: Path


@dataclass
class CandidateFrame:
    timestamp_seconds: float
    selection_reason: str
    temp_path: Path
    scene_score: float | None = None


@dataclass
class SelectedFrame:
    frame_index: int
    timestamp_seconds: float
    selection_reason: str
    filename: str
    path: Path


@dataclass
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
```

---

# 20. README Section

A short README section should be added when the programme is implemented.

Suggested README text:

```markdown
### Sample commercial frames

The `sample_commercials_frames.py` programme samples representative frames from
commercial clips in `corpus/02_commercials/` and writes ordered frame sequences to
`corpus/05_frames/`.

The sampler uses a scene-change strategy with safeguards:

- first frame;
- scene-change frames;
- final frame near the end;
- maximum frame cap with chronological even downsampling.

Default test run:

```bash
python sample_commercials_frames.py
```

Full run:

```bash
python sample_commercials_frames.py --no-test-mode
```

Use a lower frame cap to reduce later LLM image-token cost:

```bash
python sample_commercials_frames.py --no-test-mode --max-frames 20
```

Use a more conservative scene-change threshold:

```bash
python sample_commercials_frames.py --no-test-mode --scene-threshold 0.30
```

Outputs are written to:

```text
corpus/05_frames/<Commercial ID>/
```

Each commercial directory contains selected JPEG frames and a `frames_manifest.json`
file recording timestamps, selection reasons, frame counts, and sampling parameters.

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
8. Scene-change frames are extracted using the configured threshold.
9. No more than `--max-frames` frames are selected per commercial.
10. Frame cap, when applied, preserves chronological coverage.
11. Existing successful outputs are skipped unless `--reprocess` is used.
12. The programme writes an append-style log file.
13. The programme writes latest and timestamped run manifests.
14. Per-item failures do not stop the full run.
15. The programme exits non-zero if any attempted item fails.
16. The code includes clear module-level and function docstrings.
17. The programme does not call an LLM or require API credentials.

---

# 22. Design Rationale

This programme separates visual preprocessing from LLM interpretation.

That separation is important because:

- frame sampling is deterministic and reproducible;
- the sampled frames can be inspected manually;
- image-token cost can be estimated before LLM calls;
- thresholds and caps can be tuned empirically;
- later visual interpretation prompts can evolve independently;
- manifests preserve the exact visual evidence given to the model.

The recommended default strategy, **scene-change sampling with first/last safeguards and a frame cap**, is well suited to TV commercials because commercials are typically constructed from visually meaningful shots, rapid edits, product close-ups, and final brand frames.