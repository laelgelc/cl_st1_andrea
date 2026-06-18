# Specification: `select_commercials_frames.py`

## 1. Programme Summary

`select_commercials_frames.py` selects useful commercial frames from the sampled-frame output of the previous pipeline stage.

The programme reads commercial frame directories from:

```text
corpus/05_frames/
```

and writes selected, chronologically ordered frame directories to:

```text
corpus/05_frames_selected/
```

The output should preserve the same basic per-commercial structure:

```text
corpus/05_frames/<Commercial ID>/
corpus/05_frames_selected/<Commercial ID>/
```

The purpose of this programme is to remove frames that are unlikely to be useful for later visual analysis, especially:

1. **dark or near-black frames**, including dark sequences at the beginning, middle, or end of a commercial;
2. **visually duplicate or near-duplicate frames**, caused by dense sampling every `0.25` seconds.

The programme should not interpret the images semantically. It should not classify objects, brands, people, products, or scenes. It should only apply image-quality and visual-similarity filtering.

---

## 2. Pipeline Position

The visual pipeline becomes:

```text
Stage 1:
sample_commercials_frames.py
    commercial video clips
    → dense sampled frame sequences in corpus/05_frames/

Stage 2:
select_commercials_frames.py
    dense sampled frame sequences
    → filtered/deduplicated frame sequences in corpus/05_frames_selected/

Stage 3:
describe_commercials_visual.py
    selected frame sequences
    → LLM-based visual descriptions in corpus/06_visual_descriptions/
```

The later visual-description stage should preferably use:

```text
corpus/05_frames_selected/
```

instead of:

```text
corpus/05_frames/
```

once this programme has been run successfully.

---

## 3. Input

## 3.1 Default Input Directory

```text
corpus/05_frames/
```

The input directory contains one subdirectory per commercial:

```text
corpus/05_frames/<Commercial ID>/
```

Each commercial directory is expected to contain:

```text
frame_0001.jpg
frame_0002.jpg
frame_0003.jpg
...
frames_manifest.json
```

Example:

```text
corpus/05_frames/tv_com_1950_001/frame_0001.jpg
corpus/05_frames/tv_com_1950_001/frame_0002.jpg
corpus/05_frames/tv_com_1950_001/frames_manifest.json
```

## 3.2 Supported Image Formats

Initial supported image extensions:

```text
.jpg
.jpeg
```

The design may allow future support for:

```text
.png
.webp
```

but the default should match the frame sampler’s JPEG output.

## 3.3 Discovery Behaviour

The programme should discover commercial directories non-recursively:

```text
corpus/05_frames/<Commercial ID>/
```

Within each commercial directory, it should discover frame files matching:

```text
frame_*.jpg
frame_*.jpeg
```

Frame files should be sorted deterministically by filename.

The programme should read the existing `frames_manifest.json` when available, so that selected-frame metadata can preserve source timestamps and original selection reasons.

If a manifest is missing or corrupt, the programme may still process the image files, but should record that manifest metadata was unavailable.

---

## 4. Output

## 4.1 Default Output Directory

```text
corpus/05_frames_selected/
```

Each commercial receives a matching output directory:

```text
corpus/05_frames_selected/<Commercial ID>/
```

Example:

```text
corpus/05_frames_selected/tv_com_1950_001/
```

## 4.2 Selected Frame Naming

Selected frames should be copied and renamed chronologically:

```text
frame_0001.jpg
frame_0002.jpg
frame_0003.jpg
...
```

The output filenames should represent the selected sequence, not the original input frame number.

For traceability, the manifest should record the original input filename.

Example selected-frame manifest entry:

```json
{
  "frame_index": 1,
  "filename": "frame_0001.jpg",
  "path": "corpus/05_frames_selected/tv_com_1950_001/frame_0001.jpg",
  "source_filename": "frame_0007.jpg",
  "source_path": "corpus/05_frames/tv_com_1950_001/frame_0007.jpg",
  "timestamp_seconds": 1.5,
  "source_selection_reason": "interval",
  "selection_reason": "kept",
  "dark_score": 0.08,
  "duplicate_of_previous_selected": false,
  "similarity_to_previous_selected": 0.21
}
```

## 4.3 Per-Commercial Manifest

Each selected commercial directory should contain:

```text
selected_frames_manifest.json
```

Example:

```text
corpus/05_frames_selected/tv_com_1950_001/selected_frames_manifest.json
```

This manifest should record:

- commercial ID;
- input directory;
- output directory;
- source manifest path, if available;
- input frame count;
- dark-frame rejected count;
- duplicate rejected count;
- selected frame count;
- dark-frame configuration;
- deduplication configuration;
- all selected frames;
- all rejected frames, or optionally a compact rejection summary;
- creation timestamp;
- error status.

## 4.4 Run-Level Outputs

The programme should write:

```text
corpus/05_frames_selected/select_commercials_frames.log
corpus/05_frames_selected/select_commercials_frames_manifest.json
```

It should also write a timestamped run manifest:

```text
corpus/05_frames_selected/select_commercials_frames_manifest_<RUN_ID>.json
```

where `RUN_ID` uses UTC format:

```text
YYYYMMDDTHHMMSSZ
```

Example:

```text
select_commercials_frames_manifest_20260618T142530Z.json
```

---

# 5. Frame Selection Strategy

## 5.1 Conceptual Goal

The programme should select frames that are visually useful and non-redundant.

It should remove:

1. frames that are too dark to provide meaningful visual evidence;
2. frames that are near-duplicates of previously selected frames.

The programme should preserve chronological order.

It should avoid using a frame cap as the main deduplication method. Deduplication should be based on visual similarity, not just position in the sequence.

---

## 5.2 Processing Order

For each commercial:

1. Load input frames in chronological order.
2. Load source frame metadata from `frames_manifest.json`, if available.
3. Compute brightness/darkness metrics for each frame.
4. Reject dark frames.
5. Compare remaining frames sequentially to selected frames.
6. Reject frames visually similar to the most recent selected frame, or optionally to a small lookback window of recent selected frames.
7. Copy selected frames to the output directory using fresh chronological filenames.
8. Write `selected_frames_manifest.json`.
9. Return structured result to the run-level manifest.

Recommended order:

```text
dark-frame filtering → visual deduplication → output writing
```

Rationale:

- dark frames should be excluded regardless of duplication status;
- duplicate detection is more meaningful after low-information dark frames are removed.

---

# 6. Dark Frame Detection

## 6.1 Purpose

Some commercials contain a sequence of black or near-black frames, often at the beginning. These may correspond to fades, cuts, upload artifacts, or pre-roll gaps.

The programme should remove dark frames wherever they occur:

```text
beginning
middle
end
```

Dark-frame filtering should not assume that only leading frames are problematic.

## 6.2 Recommended Metrics

For each image, compute brightness statistics.

Recommended grayscale conversion:

```text
luminance = 0.299 * R + 0.587 * G + 0.114 * B
```

For each frame, compute:

```text
mean_luminance
median_luminance
dark_pixel_ratio
```

Where:

```text
dark_pixel_ratio = proportion of pixels with luminance below dark_pixel_threshold
```

Default values:

```text
dark_pixel_threshold = 30
max_mean_luminance_for_dark = 35
max_median_luminance_for_dark = 30
min_dark_pixel_ratio_for_dark = 0.85
```

A frame should be classified as dark if either of the following is true:

```text
mean_luminance <= max_mean_luminance_for_dark
```

or:

```text
median_luminance <= max_median_luminance_for_dark
and dark_pixel_ratio >= min_dark_pixel_ratio_for_dark
```

This catches both fully black frames and very dark fades.

## 6.3 Default Dark-Frame Policy

Default:

```text
exclude_dark_frames = true
```

A CLI option should allow disabling it:

```bash
python select_commercials_frames.py --no-exclude-dark-frames
```

Recommended CLI arguments:

| Argument | Default | Description |
|---|---:|---|
| `--exclude-dark-frames` | enabled | Exclude frames classified as dark |
| `--no-exclude-dark-frames` | disabled | Keep dark frames |
| `--dark-pixel-threshold` | `30` | Pixel luminance below this is counted as dark |
| `--max-mean-luminance-for-dark` | `35` | Reject frame if mean luminance is at or below this value |
| `--max-median-luminance-for-dark` | `30` | Used with dark-pixel ratio |
| `--min-dark-pixel-ratio-for-dark` | `0.85` | Required proportion of dark pixels |

---

# 7. Duplicate / Near-Duplicate Frame Detection

## 7.1 Purpose

Because the previous stage sampled one frame every `0.25` seconds, adjacent frames are often visually similar or identical.

The programme should retain only frames that introduce sufficient visual change.

## 7.2 Recommended Similarity Method

The implementation should use a lightweight image signature based on a downsampled grayscale image.

Recommended method:

1. Open image.
2. Convert to RGB.
3. Convert to grayscale luminance.
4. Resize to a small fixed size, for example:

```text
32 × 32
```

5. Normalize values to range:

```text
0.0–1.0
```

6. Compare two signatures using mean absolute difference.

Similarity distance:

```text
mean_absolute_difference(signature_a, signature_b)
```

This requires only standard image-processing operations and is explainable.

If using Pillow is acceptable, this programme should depend on:

```text
Pillow
```

If avoiding external Python dependencies is preferred, image analysis could be delegated to ImageMagick or FFmpeg, but Pillow is likely simpler and more maintainable.

## 7.3 Duplicate Decision

Default duplicate policy:

```text
Compare each non-dark candidate frame to the most recent selected non-dark frame.
Reject it if visual distance <= duplicate_distance_threshold.
```

Default:

```text
duplicate_distance_threshold = 0.035
```

Interpretation:

- lower threshold = stricter duplicate detection, fewer frames removed;
- higher threshold = more aggressive deduplication, more frames removed.

Recommended CLI argument:

```bash
--duplicate-distance-threshold 0.035
```

## 7.4 Optional Lookback Window

Some sequences may alternate between similar frames. To catch repeated visual states, the programme may compare each candidate against the last `N` selected frames.

Default:

```text
dedup-lookback = 1
```

Meaning:

```text
compare only to the immediately previous selected frame
```

Optional stronger setting:

```bash
python select_commercials_frames.py --dedup-lookback 3
```

If `--dedup-lookback 3`, a candidate is rejected if it is too similar to any of the previous three selected frames.

Recommended CLI argument:

```bash
--dedup-lookback 1
```

## 7.5 Minimum-Keep Safeguard

The programme should avoid producing an empty output if all frames are dark or duplicates.

Recommended behaviour:

1. If at least one non-dark frame exists, select at least one non-dark frame.
2. If all frames are dark and dark-frame exclusion is enabled, either:
   - mark the commercial as `failed_no_selectable_frames`; or
   - optionally keep the least-dark frame if `--allow-fallback-frame` is enabled.

Recommended default:

```text
allow_fallback_frame = true
```

If enabled and no frames survive filtering:

```text
select the frame with the highest mean luminance
selection_reason = "fallback_brightest_frame"
```

This prevents downstream stages from losing a commercial entirely.

---

# 8. Command-Line Interface

## 8.1 Default Test Run

```bash
python select_commercials_frames.py
```

Default behaviour:

```text
input_dir = corpus/05_frames
output_dir = corpus/05_frames_selected
test_mode = true
test_limit = 5
reprocess = false
workers = 1
exclude_dark_frames = true
deduplicate_frames = true
duplicate_distance_threshold = 0.035
dedup_signature_size = 32
dedup_lookback = 1
allow_fallback_frame = true
```

## 8.2 Full Run

```bash
python select_commercials_frames.py --no-test-mode
```

## 8.3 Reprocess Existing Outputs

```bash
python select_commercials_frames.py --no-test-mode --reprocess
```

## 8.4 Resume from Specific Commercial ID

```bash
python select_commercials_frames.py \
  --no-test-mode \
  --start-commercial-id tv_com_1950_025
```

## 8.5 Disable Dark-Frame Filtering

```bash
python select_commercials_frames.py \
  --no-test-mode \
  --no-exclude-dark-frames
```

## 8.6 Disable Duplicate Filtering

```bash
python select_commercials_frames.py \
  --no-test-mode \
  --no-deduplicate-frames
```

## 8.7 More Aggressive Deduplication

```bash
python select_commercials_frames.py \
  --no-test-mode \
  --duplicate-distance-threshold 0.06
```

## 8.8 More Conservative Deduplication

```bash
python select_commercials_frames.py \
  --no-test-mode \
  --duplicate-distance-threshold 0.02
```

## 8.9 Parallel Processing

```bash
python select_commercials_frames.py \
  --no-test-mode \
  --workers 4
```

---

# 9. CLI Arguments

## 9.1 Standard Arguments

| Argument | Default | Description |
|---|---:|---|
| `--input-dir PATH` | `corpus/05_frames` | Directory containing sampled frame directories |
| `--output-dir PATH` | `corpus/05_frames_selected` | Directory for selected frame directories |
| `--test-mode` | enabled | Limit processing to `--test-limit` commercials |
| `--no-test-mode` | disabled | Process all eligible commercials |
| `--test-limit N` | `5` | Maximum commercials to attempt in test mode |
| `--reprocess` | `False` | Regenerate existing selected outputs |
| `--workers N` | `1` | Number of worker processes |
| `--log-file PATH` | `<output-dir>/select_commercials_frames.log` | Log file path |
| `--manifest-file PATH` | `<output-dir>/select_commercials_frames_manifest.json` | Latest run manifest |
| `--start-commercial-id ID` | `None` | Resume from this commercial ID onward |

## 9.2 Dark-Frame Arguments

| Argument | Default | Description |
|---|---:|---|
| `--exclude-dark-frames` | enabled | Remove dark or near-black frames |
| `--no-exclude-dark-frames` | disabled | Keep dark frames |
| `--dark-pixel-threshold FLOAT` | `30` | Luminance threshold for dark pixels |
| `--max-mean-luminance-for-dark FLOAT` | `35` | Reject frame if mean luminance is at or below this |
| `--max-median-luminance-for-dark FLOAT` | `30` | Used with dark-pixel ratio |
| `--min-dark-pixel-ratio-for-dark FLOAT` | `0.85` | Minimum dark-pixel ratio for darkness classification |

## 9.3 Deduplication Arguments

| Argument | Default | Description |
|---|---:|---|
| `--deduplicate-frames` | enabled | Remove visually similar frames |
| `--no-deduplicate-frames` | disabled | Keep visually similar frames |
| `--duplicate-distance-threshold FLOAT` | `0.035` | Maximum signature distance for duplicate classification |
| `--dedup-signature-size N` | `32` | Width and height of resized grayscale signature |
| `--dedup-lookback N` | `1` | Number of previous selected frames to compare against |

## 9.4 Fallback Arguments

| Argument | Default | Description |
|---|---:|---|
| `--allow-fallback-frame` | enabled | Keep one fallback frame if filtering removes all frames |
| `--no-allow-fallback-frame` | disabled | Fail commercial if no frames survive filtering |

---

# 10. Argument Validation

The programme should fail early if:

- `--input-dir` does not exist;
- `--input-dir` is not a directory;
- `--output-dir` cannot be created;
- `--test-limit <= 0`;
- `--workers <= 0`;
- `--dark-pixel-threshold < 0`;
- `--max-mean-luminance-for-dark < 0`;
- `--max-median-luminance-for-dark < 0`;
- `--min-dark-pixel-ratio-for-dark` is outside `0.0–1.0`;
- `--duplicate-distance-threshold < 0`;
- `--dedup-signature-size <= 0`;
- `--dedup-lookback <= 0`.

If Pillow is used, the programme should fail clearly if it is not installed:

```text
Configuration error: Pillow is required. Install with: pip install pillow
```

---

# 11. External Dependencies

Recommended Python dependency:

```text
Pillow
```

Standard library modules likely needed:

```text
argparse
concurrent.futures
dataclasses
datetime
json
logging
math
pathlib
shutil
sys
time
```

The programme should not require:

```text
ffmpeg
ffprobe
OpenAI API key
LLM API access
```

because it works from already-sampled image files.

---

# 12. Data Classes

Suggested data classes:

```python
@dataclass(frozen=True)
class CommercialFrameDirectory:
    commercial_id: str
    input_dir: Path
    source_manifest_path: Path | None


@dataclass(frozen=True)
class WorkItem:
    commercial_id: str
    input_dir: Path
    output_dir: Path
    source_manifest_path: Path | None
    selected_manifest_path: Path


@dataclass(frozen=True)
class SelectionConfig:
    exclude_dark_frames: bool
    dark_pixel_threshold: float
    max_mean_luminance_for_dark: float
    max_median_luminance_for_dark: float
    min_dark_pixel_ratio_for_dark: float
    deduplicate_frames: bool
    duplicate_distance_threshold: float
    dedup_signature_size: int
    dedup_lookback: int
    allow_fallback_frame: bool


@dataclass(frozen=True)
class SourceFrame:
    source_index: int
    filename: str
    path: Path
    timestamp_seconds: float | None
    source_selection_reason: str | None


@dataclass(frozen=True)
class FrameMetrics:
    mean_luminance: float
    median_luminance: float
    dark_pixel_ratio: float
    is_dark: bool


@dataclass(frozen=True)
class CandidateFrame:
    source_frame: SourceFrame
    metrics: FrameMetrics
    signature: tuple[float, ...]


@dataclass(frozen=True)
class SelectedFrame:
    frame_index: int
    filename: str
    path: Path
    source_filename: str
    source_path: Path
    timestamp_seconds: float | None
    source_selection_reason: str | None
    selection_reason: str
    mean_luminance: float
    median_luminance: float
    dark_pixel_ratio: float
    similarity_to_previous_selected: float | None


@dataclass(frozen=True)
class RejectedFrame:
    source_filename: str
    source_path: Path
    timestamp_seconds: float | None
    rejection_reason: str
    mean_luminance: float
    median_luminance: float
    dark_pixel_ratio: float
    similarity_to_selected_frame: float | None
    duplicate_of_source_filename: str | None


@dataclass(frozen=True)
class ProcessingResult:
    commercial_id: str
    input_dir: Path
    output_dir: Path
    manifest_path: Path
    status: str
    error: str | None
    duration_seconds: float
    input_frame_count: int
    dark_rejected_count: int
    duplicate_rejected_count: int
    selected_frame_count: int
    fallback_used: bool
    timestamp: str
```

---

# 13. Recommended Internal Functions

Suggested function structure:

```python
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""


def validate_args(args: argparse.Namespace) -> None:
    """Validate CLI arguments and fail early on configuration errors."""


def configure_logging(log_file: Path) -> None:
    """Configure append-style file and console logging."""


def discover_commercial_frame_dirs(input_dir: Path) -> list[CommercialFrameDirectory]:
    """Discover commercial frame directories non-recursively."""


def is_valid_existing_selection_manifest(manifest_path: Path) -> bool:
    """Return True if an existing selection manifest indicates complete output."""


def plan_work(...) -> tuple[list[WorkItem], list[ProcessingResult]]:
    """Decide which commercials should be processed or skipped."""


def load_source_manifest(manifest_path: Path | None) -> dict[str, Any] | None:
    """Load the original frame manifest if available."""


def discover_source_frames(input_dir: Path, source_manifest: dict[str, Any] | None) -> list[SourceFrame]:
    """Discover frame files and attach timestamp metadata where possible."""


def compute_frame_metrics(image_path: Path, config: SelectionConfig) -> FrameMetrics:
    """Compute luminance and darkness metrics for one frame."""


def compute_image_signature(image_path: Path, signature_size: int) -> tuple[float, ...]:
    """Compute a compact grayscale image signature for similarity comparison."""


def signature_distance(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """Return mean absolute distance between two image signatures."""


def is_duplicate_candidate(...) -> tuple[bool, float | None, SourceFrame | None]:
    """Determine whether a candidate is visually duplicate of recent selected frames."""


def select_frames(source_frames: list[SourceFrame], config: SelectionConfig) -> tuple[list[SelectedFrame], list[RejectedFrame], bool]:
    """Apply dark-frame filtering and visual deduplication."""


def write_selected_frames(...) -> list[SelectedFrame]:
    """Copy selected frames to final chronological filenames."""


def write_commercial_manifest(...) -> None:
    """Write selected_frames_manifest.json for one commercial."""


def process_commercial(work_item: WorkItem, config: SelectionConfig, reprocess: bool) -> ProcessingResult:
    """Process one commercial frame directory."""


def write_run_manifest(...) -> None:
    """Write latest and timestamped run manifests."""


def main() -> int:
    """Main orchestration entry point."""
```

---

# 14. Per-Commercial Manifest Example

```json
{
  "commercial_id": "tv_com_1950_001",
  "status": "success",
  "source_dir": "corpus/05_frames/tv_com_1950_001",
  "source_manifest": "corpus/05_frames/tv_com_1950_001/frames_manifest.json",
  "output_dir": "corpus/05_frames_selected/tv_com_1950_001",
  "selection_config": {
    "exclude_dark_frames": true,
    "dark_pixel_threshold": 30,
    "max_mean_luminance_for_dark": 35,
    "max_median_luminance_for_dark": 30,
    "min_dark_pixel_ratio_for_dark": 0.85,
    "deduplicate_frames": true,
    "duplicate_distance_threshold": 0.035,
    "dedup_signature_size": 32,
    "dedup_lookback": 1,
    "allow_fallback_frame": true
  },
  "input_frame_count": 120,
  "dark_rejected_count": 8,
  "duplicate_rejected_count": 61,
  "selected_frame_count": 51,
  "fallback_used": false,
  "frames": [
    {
      "frame_index": 1,
      "filename": "frame_0001.jpg",
      "path": "corpus/05_frames_selected/tv_com_1950_001/frame_0001.jpg",
      "source_filename": "frame_0009.jpg",
      "source_path": "corpus/05_frames/tv_com_1950_001/frame_0009.jpg",
      "timestamp_seconds": 2.0,
      "source_selection_reason": "interval",
      "selection_reason": "kept",
      "mean_luminance": 84.72,
      "median_luminance": 79.0,
      "dark_pixel_ratio": 0.12,
      "similarity_to_previous_selected": null
    }
  ],
  "rejected_frames": [
    {
      "source_filename": "frame_0001.jpg",
      "source_path": "corpus/05_frames/tv_com_1950_001/frame_0001.jpg",
      "timestamp_seconds": 0.0,
      "rejection_reason": "dark_frame",
      "mean_luminance": 4.25,
      "median_luminance": 3.0,
      "dark_pixel_ratio": 0.98,
      "similarity_to_selected_frame": null,
      "duplicate_of_source_filename": null
    },
    {
      "source_filename": "frame_0010.jpg",
      "source_path": "corpus/05_frames/tv_com_1950_001/frame_0010.jpg",
      "timestamp_seconds": 2.25,
      "rejection_reason": "duplicate_frame",
      "mean_luminance": 86.12,
      "median_luminance": 80.0,
      "dark_pixel_ratio": 0.11,
      "similarity_to_selected_frame": 0.018,
      "duplicate_of_source_filename": "frame_0009.jpg"
    }
  ],
  "created_at": "2026-06-18T14:25:30Z",
  "error": null
}
```

For large runs, the programme could optionally support:

```bash
--no-write-rejected-frames
```

to keep manifests smaller, but the default should include enough rejection detail for auditability.

---

# 15. Run-Level Manifest Example

```json
{
  "run_metadata": {
    "run_id": "20260618T142530Z",
    "tool_name": "select_commercials_frames",
    "version": "v1",
    "start_time": "2026-06-18T14:25:30Z",
    "end_time": "2026-06-18T14:31:42Z",
    "test_mode": true,
    "test_limit": 5,
    "reprocess": false,
    "workers": 1,
    "input_source": "corpus/05_frames",
    "output_dir": "corpus/05_frames_selected",
    "config": {
      "exclude_dark_frames": true,
      "dark_pixel_threshold": 30,
      "max_mean_luminance_for_dark": 35,
      "max_median_luminance_for_dark": 30,
      "min_dark_pixel_ratio_for_dark": 0.85,
      "deduplicate_frames": true,
      "duplicate_distance_threshold": 0.035,
      "dedup_signature_size": 32,
      "dedup_lookback": 1,
      "allow_fallback_frame": true
    }
  },
  "files": [
    {
      "commercial_id": "tv_com_1950_001",
      "input_path": "corpus/05_frames/tv_com_1950_001",
      "output_path": "corpus/05_frames_selected/tv_com_1950_001",
      "manifest_path": "corpus/05_frames_selected/tv_com_1950_001/selected_frames_manifest.json",
      "status": "success",
      "error": null,
      "duration_seconds": 1.42,
      "timestamp": "2026-06-18T14:25:42Z",
      "metadata": {
        "input_frame_count": 120,
        "dark_rejected_count": 8,
        "duplicate_rejected_count": 61,
        "selected_frame_count": 51,
        "fallback_used": false
      }
    }
  ],
  "summary": {
    "discovered": 824,
    "planned": 5,
    "skipped_existing": 0,
    "attempted": 5,
    "succeeded": 5,
    "failed": 0
  }
}
```

---

# 16. Logging Specification

Default log file:

```text
corpus/05_frames_selected/select_commercials_frames.log
```

Minimum log events:

- startup;
- configuration summary;
- input/output paths;
- discovery count;
- planning count;
- per-commercial skip;
- per-commercial success;
- per-commercial failure;
- dark-frame and duplicate counts;
- manifest writing;
- completion summary.

Example:

```text
[2026-06-18 14:25:30] INFO   Starting commercial frame selection run
[2026-06-18 14:25:30] INFO   Input dir: corpus/05_frames
[2026-06-18 14:25:30] INFO   Output dir: corpus/05_frames_selected
[2026-06-18 14:25:30] INFO   Test mode: True (limit=5)
[2026-06-18 14:25:30] INFO   Exclude dark frames: True
[2026-06-18 14:25:30] INFO   Deduplicate frames: True
[2026-06-18 14:25:30] INFO   Duplicate distance threshold: 0.035
[2026-06-18 14:25:31] INFO   Discovered 824 commercial frame directories
[2026-06-18 14:25:31] INFO   Planned 5 commercials for processing
[2026-06-18 14:25:42] INFO   SUCCESS tv_com_1950_001 input=120 dark_rejected=8 duplicate_rejected=61 selected=51
[2026-06-18 14:25:44] INFO   SUCCESS tv_com_1950_002 input=84 dark_rejected=0 duplicate_rejected=39 selected=45
[2026-06-18 14:31:42] INFO   Wrote manifest: corpus/05_frames_selected/select_commercials_frames_manifest.json
[2026-06-18 14:31:42] INFO   Completed frame selection run: attempted=5 succeeded=5 failed=0 skipped_existing=0
```

---

# 17. Error Handling

## 17.1 Configuration Errors

Configuration errors should stop the programme before processing begins.

Exit code:

```text
2
```

Examples:

- input directory does not exist;
- invalid threshold values;
- output directory cannot be created;
- Pillow is unavailable, if Pillow is required.

## 17.2 Per-Commercial Errors

Per-commercial errors should not abort the full run.

If one commercial fails:

1. mark it as `failed`;
2. record the error in the run manifest;
3. log the error;
4. continue processing remaining commercials.

Exit code:

```text
1
```

if any attempted commercial fails.

## 17.3 Keyboard Interrupt

On interruption:

```text
exit code 130
```

The programme should attempt to write a partial run manifest.

---

# 18. Resumability and Safe Re-Runs

By default, the programme should skip a commercial if:

- `--reprocess` is false;
- `selected_frames_manifest.json` exists;
- the manifest status is `success`;
- at least one selected frame listed in the manifest exists on disk.

To regenerate outputs:

```bash
python select_commercials_frames.py --no-test-mode --reprocess
```

When reprocessing, the programme should clear the existing output directory for that commercial before writing new selected frames.

---

# 19. README Addition

Suggested README section:

```markdown
### Select commercial frames

The `select_commercials_frames.py` programme filters the dense sampled-frame output
from `corpus/05_frames/` and writes cleaner selected frame sequences to
`corpus/05_frames_selected/`.

It removes:

- dark or near-black frames, including dark sequences at the beginning, middle, or end;
- visually duplicate or near-duplicate frames caused by dense 0.25-second sampling.

Default test run:

```bash
python select_commercials_frames.py
```

Full run:

```bash
python select_commercials_frames.py --no-test-mode
```

Force regeneration:

```bash
python select_commercials_frames.py --no-test-mode --reprocess
```

Use more aggressive duplicate removal:

```bash
python select_commercials_frames.py \
  --no-test-mode \
  --duplicate-distance-threshold 0.06
```

Outputs are written to:

```text
corpus/05_frames_selected/<Commercial ID>/
```

Each commercial directory contains selected JPEG frames and a
`selected_frames_manifest.json` file recording source frames, rejected frames,
darkness metrics, duplicate metrics, and selection settings.

---

# 20. Acceptance Criteria

The implementation is acceptable when:

1. `python select_commercials_frames.py` runs in test mode by default.
2. The programme reads commercial frame directories from `corpus/05_frames/`.
3. The programme writes selected frame directories to `corpus/05_frames_selected/`.
4. The output preserves one subdirectory per commercial.
5. Selected frames are renamed chronologically as `frame_0001.jpg`, `frame_0002.jpg`, etc.
6. Dark frames are excluded by default.
7. Dark-frame detection applies to all positions in the sequence, not only the beginning.
8. Duplicate or near-duplicate frames are excluded by default.
9. Deduplication is based on image similarity, not just filename or timestamp.
10. The programme preserves timestamp metadata from the source manifest when available.
11. Each processed commercial writes `selected_frames_manifest.json`.
12. The run writes latest and timestamped run manifests.
13. The run writes an append-style log file.
14. Existing successful outputs are skipped unless `--reprocess` is used.
15. Per-commercial failures do not stop the full run.
16. The programme exits non-zero if any attempted commercial fails.
17. The programme does not call an LLM.
18. The programme does not require API credentials.
19. The code includes clear module-level and function docstrings.
20. The selected output can be used as the preferred input to the visual-description stage.
