#!/usr/bin/env python3
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

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


TOOL_NAME = "sample_commercials_frames"
TOOL_VERSION = "v2"

DEFAULT_INPUT_DIR = "corpus/02_commercials"
DEFAULT_OUTPUT_DIR = "corpus/05_frames"
DEFAULT_LOG_FILE = "corpus/05_frames/sample_commercials_frames.log"
DEFAULT_MANIFEST_FILE = "corpus/05_frames/sample_commercials_frames_manifest.json"

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 5
DEFAULT_WORKERS = 1

DEFAULT_FRAME_INTERVAL_SECONDS = 0.25
DEFAULT_MAX_FRAMES = 0
DEFAULT_IMAGE_WIDTH = 768
DEFAULT_INCLUDE_FIRST_FRAME = True
DEFAULT_INCLUDE_LAST_FRAME = True
DEFAULT_LAST_FRAME_OFFSET_SECONDS = 1.0
DEFAULT_TIMESTAMP_TOLERANCE_SECONDS = 0.10

SUPPORTED_EXTENSIONS = {".mp4"}

EXIT_SUCCESS = 0
EXIT_PARTIAL_FAILURE = 1
EXIT_CONFIGURATION_ERROR = 2
EXIT_INTERRUPTED = 130


class ConfigurationError(Exception):
    """Raised when command-line arguments or runtime configuration are invalid."""


@dataclass(frozen=True)
class VideoItem:
    """A discovered source commercial video."""

    commercial_id: str
    input_path: Path


@dataclass(frozen=True)
class WorkItem:
    """A planned commercial processing task."""

    commercial_id: str
    input_path: Path
    output_dir: Path
    manifest_path: Path


@dataclass(frozen=True)
class SamplingConfig:
    """Sampling settings used for each commercial."""

    frame_interval_seconds: float
    max_frames: int
    image_width: int
    include_first_frame: bool
    include_last_frame: bool
    last_frame_offset_seconds: float
    timestamp_tolerance_seconds: float


@dataclass(frozen=True)
class CandidateFrame:
    """A candidate frame before final capping and renaming."""

    timestamp_seconds: float
    selection_reason: str
    temp_path: Path


@dataclass(frozen=True)
class SelectedFrame:
    """A final selected frame written to the commercial output directory."""

    frame_index: int
    timestamp_seconds: float
    selection_reason: str
    filename: str
    path: Path


@dataclass(frozen=True)
class ProcessingResult:
    """Structured result returned by per-commercial processing."""

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


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(UTC)


def utc_timestamp() -> str:
    """Return a UTC timestamp suitable for JSON manifests."""
    return utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def make_run_id() -> str:
    """Return a compact UTC run identifier suitable for filenames."""
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def path_to_str(path: Path) -> str:
    """Convert a path to a stable string for logs and manifests."""
    return str(path)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Sample representative frames from commercial video clips."
    )

    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)

    test_group = parser.add_mutually_exclusive_group()
    test_group.add_argument(
        "--test-mode",
        dest="test_mode",
        action="store_true",
        default=DEFAULT_TEST_MODE,
        help="Limit processing to --test-limit items.",
    )
    test_group.add_argument(
        "--no-test-mode",
        dest="test_mode",
        action="store_false",
        help="Process all eligible items.",
    )

    parser.add_argument("--test-limit", type=int, default=DEFAULT_TEST_LIMIT)
    parser.add_argument("--reprocess", action="store_true", default=False)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--log-file", default=None)
    parser.add_argument("--manifest-file", default=None)
    parser.add_argument("--start-commercial-id", default=None)

    parser.add_argument(
        "--frame-interval-seconds",
        type=float,
        default=DEFAULT_FRAME_INTERVAL_SECONDS,
        help="Extract one interval frame every N seconds.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=DEFAULT_MAX_FRAMES,
        help="Maximum selected frames per commercial. Use 0 for no cap.",
    )
    parser.add_argument("--image-width", type=int, default=DEFAULT_IMAGE_WIDTH)

    first_group = parser.add_mutually_exclusive_group()
    first_group.add_argument(
        "--include-first-frame",
        dest="include_first_frame",
        action="store_true",
        default=DEFAULT_INCLUDE_FIRST_FRAME,
        help="Include the first frame at timestamp 0.0 seconds.",
    )
    first_group.add_argument(
        "--no-include-first-frame",
        dest="include_first_frame",
        action="store_false",
        help="Do not explicitly include the first frame.",
    )

    last_group = parser.add_mutually_exclusive_group()
    last_group.add_argument(
        "--include-last-frame",
        dest="include_last_frame",
        action="store_true",
        default=DEFAULT_INCLUDE_LAST_FRAME,
        help="Include a frame near the end of the clip.",
    )
    last_group.add_argument(
        "--no-include-last-frame",
        dest="include_last_frame",
        action="store_false",
        help="Do not explicitly include a final frame.",
    )

    parser.add_argument(
        "--last-frame-offset-seconds",
        type=float,
        default=DEFAULT_LAST_FRAME_OFFSET_SECONDS,
        help="Seconds before the end of the clip for the explicit final frame.",
    )
    parser.add_argument(
        "--timestamp-tolerance-seconds",
        type=float,
        default=DEFAULT_TIMESTAMP_TOLERANCE_SECONDS,
        help="Deduplicate candidate frames within this timestamp tolerance.",
    )

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments and fail early on configuration errors."""
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        raise ConfigurationError(f"Input directory does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise ConfigurationError(f"Input path is not a directory: {input_dir}")
    if args.test_limit <= 0:
        raise ConfigurationError("--test-limit must be greater than 0")
    if args.workers <= 0:
        raise ConfigurationError("--workers must be greater than 0")
    if args.frame_interval_seconds <= 0:
        raise ConfigurationError("--frame-interval-seconds must be greater than 0")
    if args.max_frames < 0:
        raise ConfigurationError("--max-frames must be greater than or equal to 0")
    if args.image_width < 0:
        raise ConfigurationError("--image-width must be greater than or equal to 0")
    if args.last_frame_offset_seconds < 0:
        raise ConfigurationError("--last-frame-offset-seconds must be non-negative")
    if args.timestamp_tolerance_seconds < 0:
        raise ConfigurationError("--timestamp-tolerance-seconds must be non-negative")

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(f"Could not create output directory {output_dir}: {exc}") from exc


def check_external_tools() -> None:
    """Verify that ffmpeg and ffprobe are available on PATH."""
    missing = [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]
    if missing:
        raise ConfigurationError(f"Missing required external tool(s): {', '.join(missing)}")


def configure_logging(log_file: Path) -> None:
    """Configure append-style file logging plus console logging."""
    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-5s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)


def discover_videos(input_dir: Path, supported_extensions: set[str]) -> list[VideoItem]:
    """Discover eligible video files non-recursively and return sorted items."""
    items: list[VideoItem] = []

    for path in input_dir.iterdir():
        if path.is_file() and path.suffix.lower() in supported_extensions:
            items.append(VideoItem(commercial_id=path.stem, input_path=path))

    return sorted(items, key=lambda item: item.commercial_id)


def is_valid_existing_manifest(manifest_path: Path) -> bool:
    """Return True if an existing per-commercial manifest indicates complete output."""
    if not manifest_path.exists():
        return False

    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False

    if data.get("status") != "success":
        return False

    frames = data.get("frames")
    if not isinstance(frames, list) or not frames:
        return False

    for frame in frames:
        frame_path = frame.get("path")
        if frame_path and Path(frame_path).exists():
            return True

    return False


def plan_work(
        items: list[VideoItem],
        output_dir: Path,
        reprocess: bool,
        start_commercial_id: str | None,
        test_mode: bool,
        test_limit: int,
) -> tuple[list[WorkItem], list[ProcessingResult]]:
    """Decide which items should be processed or skipped."""
    planned: list[WorkItem] = []
    skipped: list[ProcessingResult] = []

    for item in items:
        if start_commercial_id and item.commercial_id < start_commercial_id:
            continue

        commercial_output_dir = output_dir / item.commercial_id
        manifest_path = commercial_output_dir / "frames_manifest.json"

        if not reprocess and is_valid_existing_manifest(manifest_path):
            skipped.append(
                ProcessingResult(
                    commercial_id=item.commercial_id,
                    input_path=item.input_path,
                    output_dir=commercial_output_dir,
                    manifest_path=manifest_path,
                    status="skipped_existing",
                    error=None,
                    duration_seconds=0.0,
                    video_duration_seconds=None,
                    candidate_frame_count=0,
                    selected_frame_count=0,
                    cap_applied=False,
                    timestamp=utc_timestamp(),
                )
            )
            continue

        planned.append(
            WorkItem(
                commercial_id=item.commercial_id,
                input_path=item.input_path,
                output_dir=commercial_output_dir,
                manifest_path=manifest_path,
            )
        )

        if test_mode and len(planned) >= test_limit:
            break

    return planned, skipped


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run an external command and return its completed process object."""
    return subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def probe_duration(video_path: Path) -> float:
    """Return video duration in seconds using ffprobe."""
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = run_command(command)

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")

    try:
        duration = float(result.stdout.strip())
    except ValueError as exc:
        raise RuntimeError(f"ffprobe returned invalid duration: {result.stdout!r}") from exc

    if duration <= 0:
        raise RuntimeError(f"ffprobe returned non-positive duration: {duration}")

    return duration


def scale_filter(image_width: int) -> str | None:
    """Return an ffmpeg scale filter expression, or None if resizing is disabled."""
    if image_width == 0:
        return None
    return f"scale={image_width}:-1"


def extract_frame_at_timestamp(
        video_path: Path,
        timestamp_seconds: float,
        output_path: Path,
        image_width: int,
) -> None:
    """Extract one frame at a given timestamp using ffmpeg."""
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{timestamp_seconds:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
    ]

    scale = scale_filter(image_width)
    if scale:
        command.extend(["-vf", scale])

    command.append(str(output_path))

    result = run_command(command)
    if result.returncode != 0 or not output_path.exists():
        raise RuntimeError(f"ffmpeg frame extraction failed: {result.stderr.strip()}")


def extract_first_frame(video_path: Path, temp_dir: Path, image_width: int) -> CandidateFrame:
    """Extract the first frame and return candidate metadata."""
    output_path = temp_dir / "first_frame.jpg"
    extract_frame_at_timestamp(video_path, 0.0, output_path, image_width)
    return CandidateFrame(
        timestamp_seconds=0.0,
        selection_reason="first_frame",
        temp_path=output_path,
    )


def extract_last_frame(
        video_path: Path,
        temp_dir: Path,
        duration_seconds: float,
        offset_seconds: float,
        image_width: int,
) -> CandidateFrame:
    """Extract a frame near the end of the video and return candidate metadata."""
    timestamp_seconds = max(duration_seconds - offset_seconds, 0.0)
    output_path = temp_dir / "last_frame.jpg"
    extract_frame_at_timestamp(video_path, timestamp_seconds, output_path, image_width)
    return CandidateFrame(
        timestamp_seconds=timestamp_seconds,
        selection_reason="last_frame",
        temp_path=output_path,
    )


def interval_timestamps(
        duration_seconds: float,
        interval_seconds: float,
        include_start: bool,
        last_frame_timestamp_seconds: float | None,
) -> list[float]:
    """Return fixed-interval timestamps within the video duration.

    The generated interval timestamps start at 0.0 when include_start is true,
    otherwise at the first interval. If a last-frame timestamp is provided,
    interval timestamps at or after that point are omitted so that the explicit
    last-frame candidate remains the end safeguard.
    """
    timestamps: list[float] = []

    timestamp = 0.0 if include_start else interval_seconds
    upper_bound = duration_seconds

    if last_frame_timestamp_seconds is not None:
        upper_bound = min(upper_bound, last_frame_timestamp_seconds)

    while timestamp < upper_bound:
        timestamps.append(round(timestamp, 3))
        timestamp += interval_seconds

    return timestamps


def extract_interval_frames(
        video_path: Path,
        temp_dir: Path,
        duration_seconds: float,
        interval_seconds: float,
        image_width: int,
        include_start: bool,
        last_frame_timestamp_seconds: float | None,
) -> list[CandidateFrame]:
    """Extract fixed-interval frames and return candidate metadata."""
    candidates: list[CandidateFrame] = []

    timestamps = interval_timestamps(
        duration_seconds=duration_seconds,
        interval_seconds=interval_seconds,
        include_start=include_start,
        last_frame_timestamp_seconds=last_frame_timestamp_seconds,
    )

    for index, timestamp_seconds in enumerate(timestamps, start=1):
        output_path = temp_dir / f"interval_{index:06d}.jpg"
        extract_frame_at_timestamp(
            video_path=video_path,
            timestamp_seconds=timestamp_seconds,
            output_path=output_path,
            image_width=image_width,
        )
        candidates.append(
            CandidateFrame(
                timestamp_seconds=timestamp_seconds,
                selection_reason="interval",
                temp_path=output_path,
            )
        )

    return candidates


def deduplicate_candidates(
        candidates: list[CandidateFrame],
        tolerance_seconds: float,
) -> list[CandidateFrame]:
    """Remove duplicate candidates by timestamp tolerance and reason priority."""
    if not candidates:
        return []

    priority = {
        "first_frame": 3,
        "last_frame": 2,
        "interval": 1,
    }

    sorted_candidates = sorted(
        candidates,
        key=lambda c: (
            c.timestamp_seconds,
            -priority.get(c.selection_reason, 0),
        ),
    )

    deduplicated: list[CandidateFrame] = []

    for candidate in sorted_candidates:
        if not deduplicated:
            deduplicated.append(candidate)
            continue

        previous = deduplicated[-1]
        if abs(candidate.timestamp_seconds - previous.timestamp_seconds) <= tolerance_seconds:
            if priority.get(candidate.selection_reason, 0) > priority.get(
                    previous.selection_reason, 0
            ):
                deduplicated[-1] = candidate
        else:
            deduplicated.append(candidate)

    return deduplicated


def evenly_spaced_indices(length: int, count: int) -> list[int]:
    """Return deterministic, evenly spaced indices for a sequence."""
    if count <= 0 or length <= 0:
        return []
    if count >= length:
        return list(range(length))
    if count == 1:
        return [length // 2]

    return sorted(
        {
            round(i * (length - 1) / (count - 1))
            for i in range(count)
        }
    )


def cap_candidates_evenly(
        candidates: list[CandidateFrame],
        max_frames: int,
) -> tuple[list[CandidateFrame], bool]:
    """Apply deterministic chronological even downsampling.

    If max_frames is 0, no cap is applied and all candidates are returned.

    If max_frames is positive and the candidate count exceeds max_frames, the
    first and last chronological candidates are protected. Remaining frame slots
    are filled with evenly spaced candidates from the middle of the sequence.
    """
    sorted_candidates = sorted(candidates, key=lambda c: c.timestamp_seconds)

    if max_frames == 0:
        return sorted_candidates, False

    if len(sorted_candidates) <= max_frames:
        return sorted_candidates, False

    if max_frames == 1:
        return [sorted_candidates[0]], True

    protected_first = sorted_candidates[0]
    protected_last = sorted_candidates[-1]
    middle = sorted_candidates[1:-1]
    remaining_slots = max_frames - 2

    if remaining_slots <= 0:
        selected = [protected_first, protected_last][:max_frames]
    else:
        indices = evenly_spaced_indices(len(middle), remaining_slots)
        selected = [protected_first]
        selected.extend(middle[index] for index in indices)
        selected.append(protected_last)

    selected = sorted(selected, key=lambda c: c.timestamp_seconds)
    return selected[:max_frames], True


def write_selected_frames(
        selected_candidates: list[CandidateFrame],
        output_dir: Path,
) -> list[SelectedFrame]:
    """Write selected frames to final chronological frame filenames."""
    output_dir.mkdir(parents=True, exist_ok=True)

    selected_frames: list[SelectedFrame] = []

    for index, candidate in enumerate(selected_candidates, start=1):
        filename = f"frame_{index:04d}.jpg"
        final_path = output_dir / filename
        shutil.copy2(candidate.temp_path, final_path)

        selected_frames.append(
            SelectedFrame(
                frame_index=index,
                timestamp_seconds=round(candidate.timestamp_seconds, 3),
                selection_reason=candidate.selection_reason,
                filename=filename,
                path=final_path,
            )
        )

    return selected_frames


def cap_policy_name(max_frames: int) -> str:
    """Return the manifest cap policy name for the configured max frame count."""
    if max_frames == 0:
        return "none"
    return "chronological_even"


def sampling_config_to_dict(config: SamplingConfig) -> dict[str, Any]:
    """Return manifest-ready sampling configuration."""
    return {
        "strategy": "fixed_interval_with_first_last",
        "frame_interval_seconds": config.frame_interval_seconds,
        "include_first_frame": config.include_first_frame,
        "include_last_frame": config.include_last_frame,
        "last_frame_offset_seconds": config.last_frame_offset_seconds,
        "image_width": config.image_width,
        "max_frames": config.max_frames,
        "max_frames_meaning": "no_cap" if config.max_frames == 0 else "maximum_selected_frames",
        "cap_policy": cap_policy_name(config.max_frames),
        "timestamp_tolerance_seconds": config.timestamp_tolerance_seconds,
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Write a dictionary as indented UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_commercial_manifest(
        work_item: WorkItem,
        config: SamplingConfig,
        video_duration_seconds: float,
        candidate_frame_count: int,
        selected_frames: list[SelectedFrame],
        cap_applied: bool,
) -> None:
    """Write frames_manifest.json for one commercial."""
    manifest = {
        "commercial_id": work_item.commercial_id,
        "status": "success",
        "source_video": path_to_str(work_item.input_path),
        "output_dir": path_to_str(work_item.output_dir),
        "duration_seconds": round(video_duration_seconds, 3),
        "timestamp_precision": "approximate",
        "sampling_config": sampling_config_to_dict(config),
        "candidate_frame_count": candidate_frame_count,
        "selected_frame_count": len(selected_frames),
        "cap_applied": cap_applied,
        "frames": [
            {
                "frame_index": frame.frame_index,
                "filename": frame.filename,
                "path": path_to_str(frame.path),
                "timestamp_seconds": frame.timestamp_seconds,
                "selection_reason": frame.selection_reason,
            }
            for frame in selected_frames
        ],
        "created_at": utc_timestamp(),
        "error": None,
    }

    write_json(work_item.manifest_path, manifest)


def clear_output_dir(output_dir: Path) -> None:
    """Remove an existing output directory before regeneration."""
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def process_commercial(
        work_item: WorkItem,
        config: SamplingConfig,
        reprocess: bool,
) -> ProcessingResult:
    """Process one commercial and return a structured result.

    This function performs all per-item video processing: duration probing,
    frame extraction, candidate deduplication, optional frame capping, final frame
    writing, and per-commercial manifest writing. It does not log directly.
    """
    start = time.time()

    try:
        if reprocess:
            clear_output_dir(work_item.output_dir)
        else:
            work_item.output_dir.mkdir(parents=True, exist_ok=True)

        video_duration_seconds = probe_duration(work_item.input_path)

        with tempfile.TemporaryDirectory(
                prefix=f"{TOOL_NAME}_{work_item.commercial_id}_"
        ) as temp_name:
            temp_dir = Path(temp_name)
            candidates: list[CandidateFrame] = []

            last_frame_timestamp_seconds = None
            if config.include_last_frame:
                last_frame_timestamp_seconds = max(
                    video_duration_seconds - config.last_frame_offset_seconds,
                    0.0,
                    )

            if config.include_first_frame:
                candidates.append(
                    extract_first_frame(
                        video_path=work_item.input_path,
                        temp_dir=temp_dir,
                        image_width=config.image_width,
                    )
                )

            interval_candidates = extract_interval_frames(
                video_path=work_item.input_path,
                temp_dir=temp_dir,
                duration_seconds=video_duration_seconds,
                interval_seconds=config.frame_interval_seconds,
                image_width=config.image_width,
                include_start=not config.include_first_frame,
                last_frame_timestamp_seconds=last_frame_timestamp_seconds,
            )
            candidates.extend(interval_candidates)

            if config.include_last_frame:
                candidates.append(
                    extract_last_frame(
                        video_path=work_item.input_path,
                        temp_dir=temp_dir,
                        duration_seconds=video_duration_seconds,
                        offset_seconds=config.last_frame_offset_seconds,
                        image_width=config.image_width,
                    )
                )

            candidates = deduplicate_candidates(
                candidates,
                tolerance_seconds=config.timestamp_tolerance_seconds,
            )

            if not candidates:
                raise RuntimeError("No candidate frames were extracted")

            candidate_frame_count = len(candidates)
            selected_candidates, cap_applied = cap_candidates_evenly(
                candidates,
                max_frames=config.max_frames,
            )

            clear_output_dir(work_item.output_dir)
            selected_frames = write_selected_frames(selected_candidates, work_item.output_dir)

            write_commercial_manifest(
                work_item=work_item,
                config=config,
                video_duration_seconds=video_duration_seconds,
                candidate_frame_count=candidate_frame_count,
                selected_frames=selected_frames,
                cap_applied=cap_applied,
            )

        return ProcessingResult(
            commercial_id=work_item.commercial_id,
            input_path=work_item.input_path,
            output_dir=work_item.output_dir,
            manifest_path=work_item.manifest_path,
            status="success",
            error=None,
            duration_seconds=round(time.time() - start, 3),
            video_duration_seconds=round(video_duration_seconds, 3),
            candidate_frame_count=candidate_frame_count,
            selected_frame_count=len(selected_frames),
            cap_applied=cap_applied,
            timestamp=utc_timestamp(),
        )

    except Exception as exc:
        return ProcessingResult(
            commercial_id=work_item.commercial_id,
            input_path=work_item.input_path,
            output_dir=work_item.output_dir,
            manifest_path=work_item.manifest_path,
            status="failed",
            error=str(exc),
            duration_seconds=round(time.time() - start, 3),
            video_duration_seconds=None,
            candidate_frame_count=0,
            selected_frame_count=0,
            cap_applied=False,
            timestamp=utc_timestamp(),
        )


def result_to_manifest_entry(result: ProcessingResult) -> dict[str, Any]:
    """Convert a processing result to a run-manifest file entry."""
    return {
        "commercial_id": result.commercial_id,
        "input_path": path_to_str(result.input_path),
        "output_path": path_to_str(result.output_dir),
        "manifest_path": path_to_str(result.manifest_path),
        "status": result.status,
        "error": result.error,
        "duration_seconds": result.duration_seconds,
        "timestamp": result.timestamp,
        "metadata": {
            "video_duration_seconds": result.video_duration_seconds,
            "candidate_frame_count": result.candidate_frame_count,
            "selected_frame_count": result.selected_frame_count,
            "cap_applied": result.cap_applied,
        },
    }


def timestamped_manifest_path(manifest_file: Path, run_id: str) -> Path:
    """Return the timestamped per-run manifest path."""
    return manifest_file.with_name(f"{manifest_file.stem}_{run_id}{manifest_file.suffix}")


def write_run_manifest(
        manifest_file: Path,
        run_id: str,
        start_time: str,
        end_time: str,
        args: argparse.Namespace,
        config: SamplingConfig,
        discovered_count: int,
        planned_count: int,
        results: list[ProcessingResult],
) -> None:
    """Write latest and timestamped run manifests."""
    skipped_count = sum(1 for result in results if result.status == "skipped_existing")
    attempted_count = sum(1 for result in results if result.status in {"success", "failed"})
    succeeded_count = sum(1 for result in results if result.status == "success")
    failed_count = sum(1 for result in results if result.status == "failed")

    data = {
        "run_metadata": {
            "run_id": run_id,
            "tool_name": TOOL_NAME,
            "version": TOOL_VERSION,
            "start_time": start_time,
            "end_time": end_time,
            "test_mode": args.test_mode,
            "test_limit": args.test_limit,
            "reprocess": args.reprocess,
            "workers": args.workers,
            "input_source": args.input_dir,
            "output_dir": args.output_dir,
            "config": {
                "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
                **sampling_config_to_dict(config),
            },
        },
        "files": [result_to_manifest_entry(result) for result in results],
        "summary": {
            "discovered": discovered_count,
            "planned": planned_count,
            "skipped_existing": skipped_count,
            "attempted": attempted_count,
            "succeeded": succeeded_count,
            "failed": failed_count,
        },
    }

    write_json(manifest_file, data)
    write_json(timestamped_manifest_path(manifest_file, run_id), data)


def log_startup(
        args: argparse.Namespace,
        config: SamplingConfig,
        log_file: Path,
        manifest_file: Path,
) -> None:
    """Log startup configuration."""
    logging.info("Starting frame sampling run")
    logging.info("Input dir: %s", args.input_dir)
    logging.info("Output dir: %s", args.output_dir)
    logging.info("Log file: %s", log_file)
    logging.info("Manifest file: %s", manifest_file)
    logging.info("Test mode: %s (limit=%s)", args.test_mode, args.test_limit)
    logging.info("Reprocess existing: %s", args.reprocess)
    logging.info("Workers: %s", args.workers)
    logging.info("Supported extensions: %s", ", ".join(sorted(SUPPORTED_EXTENSIONS)))
    logging.info("Frame interval seconds: %s", config.frame_interval_seconds)
    logging.info(
        "Max frames: %s",
        "no cap" if config.max_frames == 0 else config.max_frames,
    )
    logging.info("Image width: %s", config.image_width)
    logging.info("Include first frame: %s", config.include_first_frame)
    logging.info("Include last frame: %s", config.include_last_frame)
    logging.info("Last frame offset seconds: %s", config.last_frame_offset_seconds)
    logging.info("Timestamp tolerance seconds: %s", config.timestamp_tolerance_seconds)


def run_processing(
        planned: list[WorkItem],
        config: SamplingConfig,
        reprocess: bool,
        workers: int,
) -> list[ProcessingResult]:
    """Run per-commercial processing sequentially or in parallel."""
    results: list[ProcessingResult] = []

    if workers == 1:
        for work_item in planned:
            result = process_commercial(work_item, config, reprocess)
            results.append(result)
            log_result(result)
        return results

    with ProcessPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(process_commercial, work_item, config, reprocess): work_item
            for work_item in planned
        }

        for future in as_completed(future_map):
            result = future.result()
            results.append(result)
            log_result(result)

    return sorted(results, key=lambda result: result.commercial_id)


def log_result(result: ProcessingResult) -> None:
    """Log a per-commercial result in the main process."""
    if result.status == "success":
        logging.info(
            "SUCCESS %s candidates=%s selected=%s cap_applied=%s",
            result.commercial_id,
            result.candidate_frame_count,
            result.selected_frame_count,
            result.cap_applied,
        )
    elif result.status == "skipped_existing":
        logging.info("SKIPPED_EXISTING %s %s", result.commercial_id, result.output_dir)
    else:
        logging.error("FAILED %s %s", result.commercial_id, result.error)


def build_sampling_config(args: argparse.Namespace) -> SamplingConfig:
    """Build a SamplingConfig from parsed CLI arguments."""
    return SamplingConfig(
        frame_interval_seconds=args.frame_interval_seconds,
        max_frames=args.max_frames,
        image_width=args.image_width,
        include_first_frame=args.include_first_frame,
        include_last_frame=args.include_last_frame,
        last_frame_offset_seconds=args.last_frame_offset_seconds,
        timestamp_tolerance_seconds=args.timestamp_tolerance_seconds,
    )


def main() -> int:
    """Main orchestration entry point."""
    args = parse_args()

    if args.log_file is None:
        args.log_file = str(Path(args.output_dir) / "sample_commercials_frames.log")
    if args.manifest_file is None:
        args.manifest_file = str(
            Path(args.output_dir) / "sample_commercials_frames_manifest.json"
        )

    log_file = Path(args.log_file)
    manifest_file = Path(args.manifest_file)
    output_dir = Path(args.output_dir)
    input_dir = Path(args.input_dir)

    run_id = make_run_id()
    start_time = utc_timestamp()
    config = build_sampling_config(args)

    try:
        validate_args(args)
        configure_logging(log_file)
        log_startup(args, config, log_file, manifest_file)

        check_external_tools()
        logging.info("ffmpeg and ffprobe are available")

        items = discover_videos(input_dir, SUPPORTED_EXTENSIONS)
        logging.info("Discovered %s commercial video files", len(items))

        planned, skipped = plan_work(
            items=items,
            output_dir=output_dir,
            reprocess=args.reprocess,
            start_commercial_id=args.start_commercial_id,
            test_mode=args.test_mode,
            test_limit=args.test_limit,
        )

        for skipped_result in skipped:
            log_result(skipped_result)

        logging.info("Planned %s commercials for processing", len(planned))

        processed = run_processing(
            planned=planned,
            config=config,
            reprocess=args.reprocess,
            workers=args.workers,
        )

        all_results = sorted(
            [*skipped, *processed],
            key=lambda result: result.commercial_id,
        )

        end_time = utc_timestamp()
        write_run_manifest(
            manifest_file=manifest_file,
            run_id=run_id,
            start_time=start_time,
            end_time=end_time,
            args=args,
            config=config,
            discovered_count=len(items),
            planned_count=len(planned),
            results=all_results,
        )

        failed_count = sum(1 for result in all_results if result.status == "failed")
        succeeded_count = sum(1 for result in all_results if result.status == "success")
        skipped_count = sum(
            1 for result in all_results if result.status == "skipped_existing"
        )

        logging.info("Wrote manifest: %s", manifest_file)
        logging.info("Wrote manifest: %s", timestamped_manifest_path(manifest_file, run_id))
        logging.info(
            "Completed frame sampling run: attempted=%s succeeded=%s failed=%s skipped_existing=%s",
            len(processed),
            succeeded_count,
            failed_count,
            skipped_count,
        )

        return EXIT_PARTIAL_FAILURE if failed_count else EXIT_SUCCESS

    except KeyboardInterrupt:
        end_time = utc_timestamp()
        logging.error("Interrupted by user")

        try:
            write_run_manifest(
                manifest_file=manifest_file,
                run_id=run_id,
                start_time=start_time,
                end_time=end_time,
                args=args,
                config=config,
                discovered_count=0,
                planned_count=0,
                results=[],
            )
        except Exception:
            pass

        return EXIT_INTERRUPTED

    except ConfigurationError as exc:
        try:
            configure_logging(log_file)
            logging.error("Configuration error: %s", exc)
        except Exception:
            print(f"Configuration error: {exc}", file=sys.stderr)
        return EXIT_CONFIGURATION_ERROR


if __name__ == "__main__":
    sys.exit(main())