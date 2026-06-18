#!/usr/bin/env python3
"""
Select useful commercial frames from densely sampled frame directories.

This programme reads frame directories created by the previous visual sampling
stage, filters out dark or near-black frames, removes visually duplicate or
near-duplicate frames, and writes cleaner chronologically ordered frame sequences
plus JSON manifests to a new output directory.

Default input:
    corpus/05_frames/

Default output:
    corpus/05_frames_selected/

Default selection strategy:
    exclude dark frames: yes
    deduplicate visually similar frames: yes
    dark pixel threshold: 30
    maximum mean luminance for dark frames: 35
    duplicate distance threshold: 0.035
    signature size: 32 x 32
    deduplication lookback: 1 selected frame
    fallback frame: yes

Typical usage:
    python select_commercials_frames.py
    python select_commercials_frames.py --no-test-mode
    python select_commercials_frames.py --no-test-mode --reprocess
    python select_commercials_frames.py --no-test-mode --duplicate-distance-threshold 0.06
    python select_commercials_frames.py --no-test-mode --no-exclude-dark-frames
    python select_commercials_frames.py --no-test-mode --no-deduplicate-frames

The programme does not call any LLM, does not perform semantic visual
interpretation, and does not require API credentials. It performs deterministic
image-quality and image-similarity filtering only.

Requires Pillow:
    pip install pillow
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

try:
    from PIL import Image
except ImportError:  # pragma: no cover - handled as configuration error at runtime
    Image = None  # type: ignore[assignment]


TOOL_NAME = "select_commercials_frames"
TOOL_VERSION = "v1"

DEFAULT_INPUT_DIR = "corpus/05_frames"
DEFAULT_OUTPUT_DIR = "corpus/05_frames_selected"

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 5
DEFAULT_WORKERS = 1

DEFAULT_EXCLUDE_DARK_FRAMES = True
DEFAULT_DARK_PIXEL_THRESHOLD = 30.0
DEFAULT_MAX_MEAN_LUMINANCE_FOR_DARK = 35.0
DEFAULT_MAX_MEDIAN_LUMINANCE_FOR_DARK = 30.0
DEFAULT_MIN_DARK_PIXEL_RATIO_FOR_DARK = 0.85

DEFAULT_DEDUPLICATE_FRAMES = True
DEFAULT_DUPLICATE_DISTANCE_THRESHOLD = 0.035
DEFAULT_DEDUP_SIGNATURE_SIZE = 32
DEFAULT_DEDUP_LOOKBACK = 1

DEFAULT_ALLOW_FALLBACK_FRAME = True

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg"}

EXIT_SUCCESS = 0
EXIT_PARTIAL_FAILURE = 1
EXIT_CONFIGURATION_ERROR = 2
EXIT_INTERRUPTED = 130


class ConfigurationError(Exception):
    """Raised when command-line arguments or runtime configuration are invalid."""


@dataclass(frozen=True)
class CommercialFrameDirectory:
    """A discovered source commercial frame directory."""

    commercial_id: str
    input_dir: Path
    source_manifest_path: Path | None


@dataclass(frozen=True)
class WorkItem:
    """A planned commercial frame-selection task."""

    commercial_id: str
    input_dir: Path
    output_dir: Path
    source_manifest_path: Path | None
    selected_manifest_path: Path


@dataclass(frozen=True)
class SelectionConfig:
    """Frame-selection settings used for each commercial."""

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
    """A source frame discovered in a sampled commercial frame directory."""

    source_index: int
    filename: str
    path: Path
    timestamp_seconds: float | None
    source_selection_reason: str | None


@dataclass(frozen=True)
class FrameMetrics:
    """Brightness and darkness metrics for a source frame."""

    mean_luminance: float
    median_luminance: float
    dark_pixel_ratio: float
    is_dark: bool


@dataclass(frozen=True)
class CandidateFrame:
    """A source frame with computed metrics and visual signature."""

    source_frame: SourceFrame
    metrics: FrameMetrics
    signature: tuple[float, ...]


@dataclass(frozen=True)
class SelectedFrame:
    """A final selected frame written to the selected output directory."""

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
    """A source frame rejected by dark-frame filtering or duplicate filtering."""

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
class SelectionDecision:
    """A frame-selection decision before final output copying and renaming."""

    source_frame: SourceFrame
    metrics: FrameMetrics
    selection_reason: str
    similarity_to_previous_selected: float | None


@dataclass(frozen=True)
class SelectionOutcome:
    """Selected and rejected frame decisions for one commercial."""

    selected_decisions: list[SelectionDecision]
    rejected_frames: list[RejectedFrame]
    fallback_used: bool


@dataclass(frozen=True)
class ProcessingResult:
    """Structured result returned by per-commercial processing."""

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
        description=(
            "Select useful commercial frames by removing dark frames and visually "
            "duplicate frames from sampled frame directories."
        )
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

    dark_group = parser.add_mutually_exclusive_group()
    dark_group.add_argument(
        "--exclude-dark-frames",
        dest="exclude_dark_frames",
        action="store_true",
        default=DEFAULT_EXCLUDE_DARK_FRAMES,
        help="Exclude dark or near-black frames.",
    )
    dark_group.add_argument(
        "--no-exclude-dark-frames",
        dest="exclude_dark_frames",
        action="store_false",
        help="Keep dark or near-black frames.",
    )

    parser.add_argument(
        "--dark-pixel-threshold",
        type=float,
        default=DEFAULT_DARK_PIXEL_THRESHOLD,
        help="Pixel luminance below this value is counted as dark.",
    )
    parser.add_argument(
        "--max-mean-luminance-for-dark",
        type=float,
        default=DEFAULT_MAX_MEAN_LUMINANCE_FOR_DARK,
        help="Reject frame as dark if mean luminance is at or below this value.",
    )
    parser.add_argument(
        "--max-median-luminance-for-dark",
        type=float,
        default=DEFAULT_MAX_MEDIAN_LUMINANCE_FOR_DARK,
        help="Median-luminance threshold used with dark-pixel ratio.",
    )
    parser.add_argument(
        "--min-dark-pixel-ratio-for-dark",
        type=float,
        default=DEFAULT_MIN_DARK_PIXEL_RATIO_FOR_DARK,
        help="Minimum ratio of dark pixels required for dark-frame classification.",
    )

    dedup_group = parser.add_mutually_exclusive_group()
    dedup_group.add_argument(
        "--deduplicate-frames",
        dest="deduplicate_frames",
        action="store_true",
        default=DEFAULT_DEDUPLICATE_FRAMES,
        help="Remove visually similar frames.",
    )
    dedup_group.add_argument(
        "--no-deduplicate-frames",
        dest="deduplicate_frames",
        action="store_false",
        help="Keep visually similar frames.",
    )

    parser.add_argument(
        "--duplicate-distance-threshold",
        type=float,
        default=DEFAULT_DUPLICATE_DISTANCE_THRESHOLD,
        help="Maximum signature distance for duplicate classification.",
    )
    parser.add_argument(
        "--dedup-signature-size",
        type=int,
        default=DEFAULT_DEDUP_SIGNATURE_SIZE,
        help="Width and height of the resized grayscale image signature.",
    )
    parser.add_argument(
        "--dedup-lookback",
        type=int,
        default=DEFAULT_DEDUP_LOOKBACK,
        help="Number of previous selected frames to compare against.",
    )

    fallback_group = parser.add_mutually_exclusive_group()
    fallback_group.add_argument(
        "--allow-fallback-frame",
        dest="allow_fallback_frame",
        action="store_true",
        default=DEFAULT_ALLOW_FALLBACK_FRAME,
        help="Keep the brightest frame if filtering removes all frames.",
    )
    fallback_group.add_argument(
        "--no-allow-fallback-frame",
        dest="allow_fallback_frame",
        action="store_false",
        help="Fail commercial if no frame survives filtering.",
    )

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments and fail early on configuration errors."""
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if Image is None:
        raise ConfigurationError("Pillow is required. Install with: pip install pillow")
    if not input_dir.exists():
        raise ConfigurationError(f"Input directory does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise ConfigurationError(f"Input path is not a directory: {input_dir}")
    if args.test_limit <= 0:
        raise ConfigurationError("--test-limit must be greater than 0")
    if args.workers <= 0:
        raise ConfigurationError("--workers must be greater than 0")
    if args.dark_pixel_threshold < 0:
        raise ConfigurationError("--dark-pixel-threshold must be non-negative")
    if args.max_mean_luminance_for_dark < 0:
        raise ConfigurationError("--max-mean-luminance-for-dark must be non-negative")
    if args.max_median_luminance_for_dark < 0:
        raise ConfigurationError("--max-median-luminance-for-dark must be non-negative")
    if not 0.0 <= args.min_dark_pixel_ratio_for_dark <= 1.0:
        raise ConfigurationError("--min-dark-pixel-ratio-for-dark must be between 0.0 and 1.0")
    if args.duplicate_distance_threshold < 0:
        raise ConfigurationError("--duplicate-distance-threshold must be non-negative")
    if args.dedup_signature_size <= 0:
        raise ConfigurationError("--dedup-signature-size must be greater than 0")
    if args.dedup_lookback <= 0:
        raise ConfigurationError("--dedup-lookback must be greater than 0")

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(f"Could not create output directory {output_dir}: {exc}") from exc


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


def discover_commercial_frame_dirs(input_dir: Path) -> list[CommercialFrameDirectory]:
    """Discover commercial frame directories non-recursively."""
    items: list[CommercialFrameDirectory] = []

    for path in input_dir.iterdir():
        if not path.is_dir():
            continue

        source_manifest_path = path / "frames_manifest.json"
        if not source_manifest_path.exists():
            source_manifest_path = None

        items.append(
            CommercialFrameDirectory(
                commercial_id=path.name,
                input_dir=path,
                source_manifest_path=source_manifest_path,
            )
        )

    return sorted(items, key=lambda item: item.commercial_id)


def is_valid_existing_selection_manifest(manifest_path: Path) -> bool:
    """Return True if an existing selection manifest indicates complete output."""
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
        items: list[CommercialFrameDirectory],
        output_dir: Path,
        reprocess: bool,
        start_commercial_id: str | None,
        test_mode: bool,
        test_limit: int,
) -> tuple[list[WorkItem], list[ProcessingResult]]:
    """Decide which commercial frame directories should be processed or skipped."""
    planned: list[WorkItem] = []
    skipped: list[ProcessingResult] = []

    for item in items:
        if start_commercial_id and item.commercial_id < start_commercial_id:
            continue

        commercial_output_dir = output_dir / item.commercial_id
        selected_manifest_path = commercial_output_dir / "selected_frames_manifest.json"

        if not reprocess and is_valid_existing_selection_manifest(selected_manifest_path):
            skipped.append(
                ProcessingResult(
                    commercial_id=item.commercial_id,
                    input_dir=item.input_dir,
                    output_dir=commercial_output_dir,
                    manifest_path=selected_manifest_path,
                    status="skipped_existing",
                    error=None,
                    duration_seconds=0.0,
                    input_frame_count=0,
                    dark_rejected_count=0,
                    duplicate_rejected_count=0,
                    selected_frame_count=0,
                    fallback_used=False,
                    timestamp=utc_timestamp(),
                )
            )
            continue

        planned.append(
            WorkItem(
                commercial_id=item.commercial_id,
                input_dir=item.input_dir,
                output_dir=commercial_output_dir,
                source_manifest_path=item.source_manifest_path,
                selected_manifest_path=selected_manifest_path,
            )
        )

        if test_mode and len(planned) >= test_limit:
            break

    return planned, skipped


def load_source_manifest(manifest_path: Path | None) -> dict[str, Any] | None:
    """Load the original frame manifest if available and readable."""
    if manifest_path is None or not manifest_path.exists():
        return None

    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
        return None

    return data


def source_manifest_frame_lookup(source_manifest: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Return source frame metadata keyed by filename."""
    if not source_manifest:
        return {}

    frames = source_manifest.get("frames")
    if not isinstance(frames, list):
        return {}

    lookup: dict[str, dict[str, Any]] = {}
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        filename = frame.get("filename")
        if isinstance(filename, str):
            lookup[filename] = frame

    return lookup


def discover_source_frames(
        input_dir: Path,
        source_manifest: dict[str, Any] | None,
) -> list[SourceFrame]:
    """Discover frame files and attach timestamp metadata where possible."""
    manifest_lookup = source_manifest_frame_lookup(source_manifest)
    frame_paths: list[Path] = []

    for path in input_dir.iterdir():
        if (
                path.is_file()
                and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
                and path.name.startswith("frame_")
        ):
            frame_paths.append(path)

    source_frames: list[SourceFrame] = []

    for index, path in enumerate(sorted(frame_paths, key=lambda p: p.name), start=1):
        manifest_frame = manifest_lookup.get(path.name, {})
        timestamp_seconds = manifest_frame.get("timestamp_seconds")
        source_selection_reason = manifest_frame.get("selection_reason")

        if not isinstance(timestamp_seconds, (int, float)):
            timestamp_seconds = None
        if not isinstance(source_selection_reason, str):
            source_selection_reason = None

        source_frames.append(
            SourceFrame(
                source_index=index,
                filename=path.name,
                path=path,
                timestamp_seconds=timestamp_seconds,
                source_selection_reason=source_selection_reason,
            )
        )

    return source_frames


def image_luminance_values(image_path: Path) -> list[float]:
    """Return all luminance values for an image using ITU-R BT.601-style weights."""
    assert Image is not None
    with Image.open(image_path) as image:
        rgb_image = image.convert("RGB")
        pixels = rgb_image.getdata()

    return [
        0.299 * red + 0.587 * green + 0.114 * blue
        for red, green, blue in pixels
    ]


def compute_frame_metrics(image_path: Path, config: SelectionConfig) -> FrameMetrics:
    """Compute luminance and darkness metrics for one frame."""
    luminance_values = image_luminance_values(image_path)

    if not luminance_values:
        raise RuntimeError(f"Image has no pixels: {image_path}")

    mean_luminance = sum(luminance_values) / len(luminance_values)
    median_luminance = float(median(luminance_values))
    dark_pixel_count = sum(
        1 for value in luminance_values
        if value < config.dark_pixel_threshold
    )
    dark_pixel_ratio = dark_pixel_count / len(luminance_values)

    is_dark = (
            mean_luminance <= config.max_mean_luminance_for_dark
            or (
                    median_luminance <= config.max_median_luminance_for_dark
                    and dark_pixel_ratio >= config.min_dark_pixel_ratio_for_dark
            )
    )

    return FrameMetrics(
        mean_luminance=round(mean_luminance, 3),
        median_luminance=round(median_luminance, 3),
        dark_pixel_ratio=round(dark_pixel_ratio, 6),
        is_dark=is_dark,
    )


def compute_image_signature(image_path: Path, signature_size: int) -> tuple[float, ...]:
    """Compute a compact grayscale image signature for similarity comparison."""
    assert Image is not None
    with Image.open(image_path) as image:
        grayscale = image.convert("L")
        resized = grayscale.resize((signature_size, signature_size), Image.Resampling.LANCZOS)
        values = resized.getdata()

    return tuple(value / 255.0 for value in values)


def signature_distance(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """Return mean absolute distance between two equal-length image signatures."""
    if len(a) != len(b):
        raise ValueError("Image signatures must have the same length")
    if not a:
        raise ValueError("Image signatures must not be empty")

    return sum(abs(left - right) for left, right in zip(a, b)) / len(a)


def make_rejected_frame(
        candidate: CandidateFrame,
        rejection_reason: str,
        similarity_to_selected_frame: float | None,
        duplicate_of_source_filename: str | None,
) -> RejectedFrame:
    """Create a rejected-frame record from a candidate and reason."""
    return RejectedFrame(
        source_filename=candidate.source_frame.filename,
        source_path=candidate.source_frame.path,
        timestamp_seconds=candidate.source_frame.timestamp_seconds,
        rejection_reason=rejection_reason,
        mean_luminance=candidate.metrics.mean_luminance,
        median_luminance=candidate.metrics.median_luminance,
        dark_pixel_ratio=candidate.metrics.dark_pixel_ratio,
        similarity_to_selected_frame=(
            round(similarity_to_selected_frame, 6)
            if similarity_to_selected_frame is not None
            else None
        ),
        duplicate_of_source_filename=duplicate_of_source_filename,
    )


def is_duplicate_candidate(
        candidate: CandidateFrame,
        selected_candidates: list[CandidateFrame],
        config: SelectionConfig,
) -> tuple[bool, float | None, SourceFrame | None]:
    """Determine whether a candidate is visually duplicate of recent selected frames."""
    if not config.deduplicate_frames or not selected_candidates:
        return False, None, None

    lookback_candidates = selected_candidates[-config.dedup_lookback:]
    closest_distance: float | None = None
    closest_frame: SourceFrame | None = None

    for selected_candidate in lookback_candidates:
        distance = signature_distance(candidate.signature, selected_candidate.signature)

        if closest_distance is None or distance < closest_distance:
            closest_distance = distance
            closest_frame = selected_candidate.source_frame

    if closest_distance is not None and closest_distance <= config.duplicate_distance_threshold:
        return True, closest_distance, closest_frame

    return False, closest_distance, closest_frame


def build_candidate(source_frame: SourceFrame, config: SelectionConfig) -> CandidateFrame:
    """Compute metrics and signature for a source frame."""
    metrics = compute_frame_metrics(source_frame.path, config)
    signature = compute_image_signature(source_frame.path, config.dedup_signature_size)
    return CandidateFrame(
        source_frame=source_frame,
        metrics=metrics,
        signature=signature,
    )


def select_frames(
        source_frames: list[SourceFrame],
        config: SelectionConfig,
) -> SelectionOutcome:
    """Apply dark-frame filtering and visual deduplication to source frames."""
    candidates = [build_candidate(source_frame, config) for source_frame in source_frames]

    selected_candidates: list[CandidateFrame] = []
    selected_decisions: list[SelectionDecision] = []
    rejected_frames: list[RejectedFrame] = []
    fallback_used = False

    for candidate in candidates:
        if config.exclude_dark_frames and candidate.metrics.is_dark:
            rejected_frames.append(
                make_rejected_frame(
                    candidate=candidate,
                    rejection_reason="dark_frame",
                    similarity_to_selected_frame=None,
                    duplicate_of_source_filename=None,
                )
            )
            continue

        is_duplicate, distance, duplicate_of = is_duplicate_candidate(
            candidate=candidate,
            selected_candidates=selected_candidates,
            config=config,
        )

        if is_duplicate:
            rejected_frames.append(
                make_rejected_frame(
                    candidate=candidate,
                    rejection_reason="duplicate_frame",
                    similarity_to_selected_frame=distance,
                    duplicate_of_source_filename=duplicate_of.filename if duplicate_of else None,
                )
            )
            continue

        selected_candidates.append(candidate)
        selected_decisions.append(
            SelectionDecision(
                source_frame=candidate.source_frame,
                metrics=candidate.metrics,
                selection_reason="kept",
                similarity_to_previous_selected=round(distance, 6) if distance is not None else None,
            )
        )

    if not selected_decisions and candidates and config.allow_fallback_frame:
        fallback_candidate = max(candidates, key=lambda item: item.metrics.mean_luminance)
        selected_decisions.append(
            SelectionDecision(
                source_frame=fallback_candidate.source_frame,
                metrics=fallback_candidate.metrics,
                selection_reason="fallback_brightest_frame",
                similarity_to_previous_selected=None,
            )
        )
        rejected_frames = [
            frame for frame in rejected_frames
            if frame.source_filename != fallback_candidate.source_frame.filename
        ]
        fallback_used = True

    return SelectionOutcome(
        selected_decisions=selected_decisions,
        rejected_frames=rejected_frames,
        fallback_used=fallback_used,
    )


def clear_output_dir(output_dir: Path) -> None:
    """Remove an existing output directory before regeneration."""
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def write_selected_frames(
        selected_decisions: list[SelectionDecision],
        output_dir: Path,
) -> list[SelectedFrame]:
    """Copy selected frames to final chronological filenames."""
    output_dir.mkdir(parents=True, exist_ok=True)

    selected_frames: list[SelectedFrame] = []

    for index, decision in enumerate(selected_decisions, start=1):
        filename = f"frame_{index:04d}.jpg"
        final_path = output_dir / filename
        shutil.copy2(decision.source_frame.path, final_path)

        selected_frames.append(
            SelectedFrame(
                frame_index=index,
                filename=filename,
                path=final_path,
                source_filename=decision.source_frame.filename,
                source_path=decision.source_frame.path,
                timestamp_seconds=decision.source_frame.timestamp_seconds,
                source_selection_reason=decision.source_frame.source_selection_reason,
                selection_reason=decision.selection_reason,
                mean_luminance=decision.metrics.mean_luminance,
                median_luminance=decision.metrics.median_luminance,
                dark_pixel_ratio=decision.metrics.dark_pixel_ratio,
                similarity_to_previous_selected=decision.similarity_to_previous_selected,
            )
        )

    return selected_frames


def selection_config_to_dict(config: SelectionConfig) -> dict[str, Any]:
    """Return manifest-ready selection configuration."""
    return {
        "exclude_dark_frames": config.exclude_dark_frames,
        "dark_pixel_threshold": config.dark_pixel_threshold,
        "max_mean_luminance_for_dark": config.max_mean_luminance_for_dark,
        "max_median_luminance_for_dark": config.max_median_luminance_for_dark,
        "min_dark_pixel_ratio_for_dark": config.min_dark_pixel_ratio_for_dark,
        "deduplicate_frames": config.deduplicate_frames,
        "duplicate_distance_threshold": config.duplicate_distance_threshold,
        "dedup_signature_size": config.dedup_signature_size,
        "dedup_lookback": config.dedup_lookback,
        "allow_fallback_frame": config.allow_fallback_frame,
    }


def selected_frame_to_dict(frame: SelectedFrame) -> dict[str, Any]:
    """Convert a selected frame to a manifest dictionary."""
    return {
        "frame_index": frame.frame_index,
        "filename": frame.filename,
        "path": path_to_str(frame.path),
        "source_filename": frame.source_filename,
        "source_path": path_to_str(frame.source_path),
        "timestamp_seconds": frame.timestamp_seconds,
        "source_selection_reason": frame.source_selection_reason,
        "selection_reason": frame.selection_reason,
        "mean_luminance": frame.mean_luminance,
        "median_luminance": frame.median_luminance,
        "dark_pixel_ratio": frame.dark_pixel_ratio,
        "similarity_to_previous_selected": frame.similarity_to_previous_selected,
    }


def rejected_frame_to_dict(frame: RejectedFrame) -> dict[str, Any]:
    """Convert a rejected frame to a manifest dictionary."""
    return {
        "source_filename": frame.source_filename,
        "source_path": path_to_str(frame.source_path),
        "timestamp_seconds": frame.timestamp_seconds,
        "rejection_reason": frame.rejection_reason,
        "mean_luminance": frame.mean_luminance,
        "median_luminance": frame.median_luminance,
        "dark_pixel_ratio": frame.dark_pixel_ratio,
        "similarity_to_selected_frame": frame.similarity_to_selected_frame,
        "duplicate_of_source_filename": frame.duplicate_of_source_filename,
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Write a dictionary as indented UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_commercial_manifest(
        work_item: WorkItem,
        config: SelectionConfig,
        source_manifest_available: bool,
        input_frame_count: int,
        selected_frames: list[SelectedFrame],
        rejected_frames: list[RejectedFrame],
        fallback_used: bool,
) -> None:
    """Write selected_frames_manifest.json for one commercial."""
    dark_rejected_count = sum(
        1 for frame in rejected_frames
        if frame.rejection_reason == "dark_frame"
    )
    duplicate_rejected_count = sum(
        1 for frame in rejected_frames
        if frame.rejection_reason == "duplicate_frame"
    )

    manifest = {
        "commercial_id": work_item.commercial_id,
        "status": "success",
        "source_dir": path_to_str(work_item.input_dir),
        "source_manifest": (
            path_to_str(work_item.source_manifest_path)
            if work_item.source_manifest_path is not None
            else None
        ),
        "source_manifest_available": source_manifest_available,
        "output_dir": path_to_str(work_item.output_dir),
        "selection_config": selection_config_to_dict(config),
        "input_frame_count": input_frame_count,
        "dark_rejected_count": dark_rejected_count,
        "duplicate_rejected_count": duplicate_rejected_count,
        "selected_frame_count": len(selected_frames),
        "fallback_used": fallback_used,
        "frames": [selected_frame_to_dict(frame) for frame in selected_frames],
        "rejected_frames": [rejected_frame_to_dict(frame) for frame in rejected_frames],
        "created_at": utc_timestamp(),
        "error": None,
    }

    write_json(work_item.selected_manifest_path, manifest)


def process_commercial(
        work_item: WorkItem,
        config: SelectionConfig,
        reprocess: bool,
) -> ProcessingResult:
    """Process one commercial frame directory and return a structured result."""
    start = time.time()

    try:
        if reprocess:
            clear_output_dir(work_item.output_dir)
        else:
            work_item.output_dir.mkdir(parents=True, exist_ok=True)

        source_manifest = load_source_manifest(work_item.source_manifest_path)
        source_frames = discover_source_frames(work_item.input_dir, source_manifest)

        if not source_frames:
            raise RuntimeError("No source frame files were discovered")

        outcome = select_frames(source_frames, config)

        if not outcome.selected_decisions:
            raise RuntimeError("No selectable frames remained after filtering")

        clear_output_dir(work_item.output_dir)
        selected_frames = write_selected_frames(
            selected_decisions=outcome.selected_decisions,
            output_dir=work_item.output_dir,
        )

        write_commercial_manifest(
            work_item=work_item,
            config=config,
            source_manifest_available=source_manifest is not None,
            input_frame_count=len(source_frames),
            selected_frames=selected_frames,
            rejected_frames=outcome.rejected_frames,
            fallback_used=outcome.fallback_used,
        )

        dark_rejected_count = sum(
            1 for frame in outcome.rejected_frames
            if frame.rejection_reason == "dark_frame"
        )
        duplicate_rejected_count = sum(
            1 for frame in outcome.rejected_frames
            if frame.rejection_reason == "duplicate_frame"
        )

        return ProcessingResult(
            commercial_id=work_item.commercial_id,
            input_dir=work_item.input_dir,
            output_dir=work_item.output_dir,
            manifest_path=work_item.selected_manifest_path,
            status="success",
            error=None,
            duration_seconds=round(time.time() - start, 3),
            input_frame_count=len(source_frames),
            dark_rejected_count=dark_rejected_count,
            duplicate_rejected_count=duplicate_rejected_count,
            selected_frame_count=len(selected_frames),
            fallback_used=outcome.fallback_used,
            timestamp=utc_timestamp(),
        )

    except Exception as exc:
        return ProcessingResult(
            commercial_id=work_item.commercial_id,
            input_dir=work_item.input_dir,
            output_dir=work_item.output_dir,
            manifest_path=work_item.selected_manifest_path,
            status="failed",
            error=str(exc),
            duration_seconds=round(time.time() - start, 3),
            input_frame_count=0,
            dark_rejected_count=0,
            duplicate_rejected_count=0,
            selected_frame_count=0,
            fallback_used=False,
            timestamp=utc_timestamp(),
        )


def result_to_manifest_entry(result: ProcessingResult) -> dict[str, Any]:
    """Convert a processing result to a run-manifest file entry."""
    return {
        "commercial_id": result.commercial_id,
        "input_path": path_to_str(result.input_dir),
        "output_path": path_to_str(result.output_dir),
        "manifest_path": path_to_str(result.manifest_path),
        "status": result.status,
        "error": result.error,
        "duration_seconds": result.duration_seconds,
        "timestamp": result.timestamp,
        "metadata": {
            "input_frame_count": result.input_frame_count,
            "dark_rejected_count": result.dark_rejected_count,
            "duplicate_rejected_count": result.duplicate_rejected_count,
            "selected_frame_count": result.selected_frame_count,
            "fallback_used": result.fallback_used,
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
        config: SelectionConfig,
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
                "supported_image_extensions": sorted(SUPPORTED_IMAGE_EXTENSIONS),
                **selection_config_to_dict(config),
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
        config: SelectionConfig,
        log_file: Path,
        manifest_file: Path,
) -> None:
    """Log startup configuration."""
    logging.info("Starting commercial frame selection run")
    logging.info("Input dir: %s", args.input_dir)
    logging.info("Output dir: %s", args.output_dir)
    logging.info("Log file: %s", log_file)
    logging.info("Manifest file: %s", manifest_file)
    logging.info("Test mode: %s (limit=%s)", args.test_mode, args.test_limit)
    logging.info("Reprocess existing: %s", args.reprocess)
    logging.info("Workers: %s", args.workers)
    logging.info("Supported image extensions: %s", ", ".join(sorted(SUPPORTED_IMAGE_EXTENSIONS)))
    logging.info("Exclude dark frames: %s", config.exclude_dark_frames)
    logging.info("Dark pixel threshold: %s", config.dark_pixel_threshold)
    logging.info("Max mean luminance for dark: %s", config.max_mean_luminance_for_dark)
    logging.info("Max median luminance for dark: %s", config.max_median_luminance_for_dark)
    logging.info("Min dark pixel ratio for dark: %s", config.min_dark_pixel_ratio_for_dark)
    logging.info("Deduplicate frames: %s", config.deduplicate_frames)
    logging.info("Duplicate distance threshold: %s", config.duplicate_distance_threshold)
    logging.info("Dedup signature size: %s", config.dedup_signature_size)
    logging.info("Dedup lookback: %s", config.dedup_lookback)
    logging.info("Allow fallback frame: %s", config.allow_fallback_frame)


def log_result(result: ProcessingResult) -> None:
    """Log a per-commercial result in the main process."""
    if result.status == "success":
        logging.info(
            "SUCCESS %s input=%s dark_rejected=%s duplicate_rejected=%s selected=%s fallback=%s",
            result.commercial_id,
            result.input_frame_count,
            result.dark_rejected_count,
            result.duplicate_rejected_count,
            result.selected_frame_count,
            result.fallback_used,
        )
    elif result.status == "skipped_existing":
        logging.info("SKIPPED_EXISTING %s %s", result.commercial_id, result.output_dir)
    else:
        logging.error("FAILED %s %s", result.commercial_id, result.error)


def run_processing(
        planned: list[WorkItem],
        config: SelectionConfig,
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


def build_selection_config(args: argparse.Namespace) -> SelectionConfig:
    """Build a SelectionConfig from parsed CLI arguments."""
    return SelectionConfig(
        exclude_dark_frames=args.exclude_dark_frames,
        dark_pixel_threshold=args.dark_pixel_threshold,
        max_mean_luminance_for_dark=args.max_mean_luminance_for_dark,
        max_median_luminance_for_dark=args.max_median_luminance_for_dark,
        min_dark_pixel_ratio_for_dark=args.min_dark_pixel_ratio_for_dark,
        deduplicate_frames=args.deduplicate_frames,
        duplicate_distance_threshold=args.duplicate_distance_threshold,
        dedup_signature_size=args.dedup_signature_size,
        dedup_lookback=args.dedup_lookback,
        allow_fallback_frame=args.allow_fallback_frame,
    )


def main() -> int:
    """Main orchestration entry point."""
    args = parse_args()

    if args.log_file is None:
        args.log_file = str(Path(args.output_dir) / "select_commercials_frames.log")
    if args.manifest_file is None:
        args.manifest_file = str(
            Path(args.output_dir) / "select_commercials_frames_manifest.json"
        )

    log_file = Path(args.log_file)
    manifest_file = Path(args.manifest_file)
    output_dir = Path(args.output_dir)
    input_dir = Path(args.input_dir)

    run_id = make_run_id()
    start_time = utc_timestamp()
    config = build_selection_config(args)

    try:
        validate_args(args)
        configure_logging(log_file)
        log_startup(args, config, log_file, manifest_file)

        items = discover_commercial_frame_dirs(input_dir)
        logging.info("Discovered %s commercial frame directories", len(items))

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
            1 for result in all_results
            if result.status == "skipped_existing"
        )

        logging.info("Wrote manifest: %s", manifest_file)
        logging.info("Wrote manifest: %s", timestamped_manifest_path(manifest_file, run_id))
        logging.info(
            "Completed frame selection run: attempted=%s succeeded=%s failed=%s skipped_existing=%s",
            len(processed),
            succeeded_count,
            failed_count,
            skipped_count,
        )

        return EXIT_PARTIAL_FAILURE if failed_count else EXIT_SUCCESS

    except KeyboardInterrupt:
        end_time = utc_timestamp()

        try:
            logging.error("Interrupted by user")
        except Exception:
            print("Interrupted by user", file=sys.stderr)

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