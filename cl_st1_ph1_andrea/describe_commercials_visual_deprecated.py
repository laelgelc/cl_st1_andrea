#!/usr/bin/env python3
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

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import mimetypes
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


TOOL_NAME = "describe_commercials_visual"
TOOL_VERSION = "v1"

DEFAULT_INPUT_DIR = "corpus/05_frames"
DEFAULT_OUTPUT_DIR = "corpus/06_visual_descriptions"
DEFAULT_PROMPT_FILE = (
    "describe_commercials_visual_prompts/visual_commercial_description_v1.txt"
)

DEFAULT_MODEL = "gpt-5.5"
DEFAULT_IMAGE_DETAIL = "low"
DEFAULT_TEMPERATURE = 0.0

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 5
DEFAULT_WORKERS = 1
DEFAULT_MAX_FRAMES_PER_REQUEST = 0
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BACKOFF_SECONDS = 5.0

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
IMAGE_DETAIL_CHOICES = {"low", "high", "auto"}

EXIT_SUCCESS = 0
EXIT_PARTIAL_FAILURE = 1
EXIT_CONFIGURATION_ERROR = 2
EXIT_INTERRUPTED = 130


try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - handled during validation
    OpenAI = None  # type: ignore[assignment]


class ConfigurationError(Exception):
    """Raised when command-line arguments or runtime configuration are invalid."""


@dataclass(frozen=True)
class FrameItem:
    """A discovered commercial frame directory."""

    commercial_id: str
    frame_dir: Path
    frame_manifest_path: Path


@dataclass(frozen=True)
class WorkItem:
    """A planned visual-description task."""

    commercial_id: str
    frame_dir: Path
    frame_manifest_path: Path
    output_text_path: Path
    output_json_path: Path


@dataclass(frozen=True)
class FrameInfo:
    """A frame listed in a Stage 1 frame manifest."""

    frame_index: int
    filename: str
    path: Path
    timestamp_seconds: float | None
    selection_reason: str | None


@dataclass(frozen=True)
class RuntimeConfig:
    """Runtime settings for visual description requests."""

    model: str
    image_detail: str
    temperature: float
    prompt_file: Path
    prompt_text: str
    prompt_sha256: str
    max_frames_per_request: int
    max_retries: int
    retry_backoff_seconds: float


@dataclass(frozen=True)
class ProcessingResult:
    """Structured result returned by per-commercial processing."""

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
    usage: dict[str, Any] | None
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


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Describe visual content of sampled commercial frames with an OpenAI model."
    )

    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--prompt-file", default=DEFAULT_PROMPT_FILE)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--image-detail",
        default=DEFAULT_IMAGE_DETAIL,
        choices=sorted(IMAGE_DETAIL_CHOICES),
    )
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)

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
        "--max-frames-per-request",
        type=int,
        default=DEFAULT_MAX_FRAMES_PER_REQUEST,
    )
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument(
        "--retry-backoff-seconds",
        type=float,
        default=DEFAULT_RETRY_BACKOFF_SECONDS,
    )

    return parser.parse_args()


def load_dotenv(dotenv_path: Path) -> dict[str, str]:
    """Load simple KEY=VALUE pairs from env/.env without logging secrets."""
    values: dict[str, str] = {}

    if not dotenv_path.exists():
        return values

    with dotenv_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key:
                values[key] = value

    return values


def apply_dotenv(dotenv_path: Path) -> None:
    """Apply env/.env values without overriding existing system environment variables."""
    for key, value in load_dotenv(dotenv_path).items():
        os.environ.setdefault(key, value)


def validate_args(args: argparse.Namespace) -> None:
    """Validate CLI arguments and fail early on configuration errors."""
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    prompt_file = Path(args.prompt_file)

    if not input_dir.exists():
        raise ConfigurationError(f"Input directory does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise ConfigurationError(f"Input path is not a directory: {input_dir}")
    if not prompt_file.exists():
        raise ConfigurationError(f"Prompt file does not exist: {prompt_file}")
    if not prompt_file.is_file():
        raise ConfigurationError(f"Prompt path is not a file: {prompt_file}")
    if args.test_limit <= 0:
        raise ConfigurationError("--test-limit must be greater than 0")
    if args.workers <= 0:
        raise ConfigurationError("--workers must be greater than 0")
    if args.image_detail not in IMAGE_DETAIL_CHOICES:
        raise ConfigurationError(
            f"--image-detail must be one of: {', '.join(sorted(IMAGE_DETAIL_CHOICES))}"
        )
    if args.temperature < 0:
        raise ConfigurationError("--temperature must be non-negative")
    if args.max_frames_per_request < 0:
        raise ConfigurationError("--max-frames-per-request must be non-negative")
    if args.max_retries < 0:
        raise ConfigurationError("--max-retries must be non-negative")
    if args.retry_backoff_seconds < 0:
        raise ConfigurationError("--retry-backoff-seconds must be non-negative")
    if not os.environ.get("OPENAI_API_KEY"):
        raise ConfigurationError("OPENAI_API_KEY is missing from env/.env or environment")
    if OpenAI is None:
        raise ConfigurationError(
            "OpenAI Python package is unavailable. Install/configure the OpenAI SDK."
        )

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(f"Could not create output directory {output_dir}: {exc}") from exc


def load_prompt(prompt_file: Path) -> str:
    """Load and validate the prompt text."""
    try:
        prompt_text = prompt_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ConfigurationError(f"Could not read prompt file {prompt_file}: {exc}") from exc

    if not prompt_text:
        raise ConfigurationError(f"Prompt file is empty: {prompt_file}")

    return prompt_text


def sha256_text(text: str) -> str:
    """Return the SHA-256 hash of prompt text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def read_json(path: Path) -> dict[str, Any]:
    """Read a UTF-8 JSON object from disk."""
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"JSON file is not an object: {path}")

    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Write a dictionary as indented UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def natural_sort_key(text: str) -> list[int | str]:
    """Return a natural-sort key that treats digit runs as integers."""
    parts = re.split(r"(\d+)", text)
    return [int(part) if part.isdigit() else part.lower() for part in parts]


def discover_frame_dirs(input_dir: Path) -> list[FrameItem]:
    """Discover commercial frame directories containing frames_manifest.json."""
    items: list[FrameItem] = []

    for path in input_dir.iterdir():
        if not path.is_dir():
            continue

        manifest_path = path / "frames_manifest.json"
        if not manifest_path.exists():
            continue

        commercial_id = path.name

        try:
            manifest = read_json(manifest_path)
            manifest_commercial_id = manifest.get("commercial_id")
            if isinstance(manifest_commercial_id, str) and manifest_commercial_id.strip():
                commercial_id = manifest_commercial_id.strip()
        except (OSError, json.JSONDecodeError, ValueError):
            commercial_id = path.name

        items.append(
            FrameItem(
                commercial_id=commercial_id,
                frame_dir=path,
                frame_manifest_path=manifest_path,
            )
        )

    return sorted(items, key=lambda item: natural_sort_key(item.commercial_id))


def is_successful_existing_output(output_text_path: Path, output_json_path: Path) -> bool:
    """Return True if existing output files represent a successful prior run."""
    if not output_text_path.exists() or not output_json_path.exists():
        return False

    try:
        data = read_json(output_json_path)
    except (OSError, json.JSONDecodeError, ValueError):
        return False

    return data.get("status") == "success"


def should_start_from(commercial_id: str, start_commercial_id: str | None) -> bool:
    """Return True if a commercial ID is at or after the optional start ID."""
    if not start_commercial_id:
        return True

    return natural_sort_key(commercial_id) >= natural_sort_key(start_commercial_id)


def plan_work(
        items: list[FrameItem],
        output_dir: Path,
        reprocess: bool,
        start_commercial_id: str | None,
        test_mode: bool,
        test_limit: int,
) -> tuple[list[WorkItem], list[ProcessingResult]]:
    """Determine which commercials should be processed or skipped."""
    planned: list[WorkItem] = []
    skipped: list[ProcessingResult] = []

    for item in items:
        if not should_start_from(item.commercial_id, start_commercial_id):
            continue

        output_text_path = output_dir / f"{item.commercial_id}.txt"
        output_json_path = output_dir / f"{item.commercial_id}.json"

        if (
                not reprocess
                and is_successful_existing_output(output_text_path, output_json_path)
        ):
            skipped.append(
                ProcessingResult(
                    commercial_id=item.commercial_id,
                    input_path=item.frame_dir,
                    output_path=output_text_path,
                    json_path=output_json_path,
                    status="skipped_existing",
                    error=None,
                    duration_seconds=0.0,
                    manifest_frame_count=0,
                    submitted_frame_count=0,
                    stage2_frame_cap_applied=False,
                    response_id=None,
                    usage=None,
                    timestamp=utc_timestamp(),
                )
            )
            continue

        planned.append(
            WorkItem(
                commercial_id=item.commercial_id,
                frame_dir=item.frame_dir,
                frame_manifest_path=item.frame_manifest_path,
                output_text_path=output_text_path,
                output_json_path=output_json_path,
            )
        )

        if test_mode and len(planned) >= test_limit:
            break

    return planned, skipped


def read_frame_manifest(manifest_path: Path) -> dict[str, Any]:
    """Read and validate a Stage 1 frames_manifest.json file."""
    manifest = read_json(manifest_path)

    if manifest.get("status") != "success":
        raise ValueError(f"Frame manifest status is not success: {manifest_path}")

    frames = manifest.get("frames")
    if not isinstance(frames, list) or not frames:
        raise ValueError(f"Frame manifest has no usable frames list: {manifest_path}")

    return manifest


def resolve_frame_paths(frame_dir: Path, manifest: dict[str, Any]) -> list[FrameInfo]:
    """Resolve frame paths listed in the Stage 1 manifest."""
    raw_frames = manifest.get("frames")
    if not isinstance(raw_frames, list):
        raise ValueError("Frame manifest 'frames' field is not a list")

    frames: list[FrameInfo] = []

    for manifest_order, raw_frame in enumerate(raw_frames, start=1):
        if not isinstance(raw_frame, dict):
            raise ValueError(f"Frame entry is not an object at position {manifest_order}")

        frame_index_raw = raw_frame.get("frame_index", manifest_order)
        try:
            frame_index = int(frame_index_raw)
        except (TypeError, ValueError):
            frame_index = manifest_order

        filename_raw = raw_frame.get("filename")
        path_raw = raw_frame.get("path")

        candidate_path: Path | None = None

        if isinstance(path_raw, str) and path_raw.strip():
            path_value = Path(path_raw)
            if path_value.exists():
                candidate_path = path_value
            else:
                fallback = frame_dir / path_value.name
                if fallback.exists():
                    candidate_path = fallback

        if candidate_path is None and isinstance(filename_raw, str) and filename_raw.strip():
            candidate_path = frame_dir / filename_raw

        if candidate_path is None:
            raise ValueError(f"Frame entry has neither usable path nor filename: {raw_frame}")

        if not candidate_path.exists():
            raise FileNotFoundError(f"Missing frame file: {candidate_path}")

        suffix = candidate_path.suffix.lower()
        if suffix not in SUPPORTED_IMAGE_EXTENSIONS:
            raise ValueError(f"Unsupported image extension {suffix}: {candidate_path}")

        timestamp_raw = raw_frame.get("timestamp_seconds")
        timestamp_seconds: float | None
        try:
            timestamp_seconds = (
                float(timestamp_raw) if timestamp_raw is not None else None
            )
        except (TypeError, ValueError):
            timestamp_seconds = None

        selection_reason_raw = raw_frame.get("selection_reason")
        selection_reason = (
            str(selection_reason_raw) if selection_reason_raw is not None else None
        )

        filename = (
            str(filename_raw)
            if isinstance(filename_raw, str) and filename_raw.strip()
            else candidate_path.name
        )

        frames.append(
            FrameInfo(
                frame_index=frame_index,
                filename=filename,
                path=candidate_path,
                timestamp_seconds=timestamp_seconds,
                selection_reason=selection_reason,
            )
        )

    return sorted(frames, key=lambda frame: frame.frame_index)


def evenly_spaced_indices(length: int, count: int) -> list[int]:
    """Return deterministic, evenly spaced indices for a sequence."""
    if count <= 0 or length <= 0:
        return []
    if count >= length:
        return list(range(length))
    if count == 1:
        return [length // 2]

    indices = {
        round(i * (length - 1) / (count - 1))
        for i in range(count)
    }
    return sorted(indices)


def cap_frames_evenly(
        frames: list[FrameInfo],
        max_frames: int,
) -> tuple[list[FrameInfo], bool]:
    """Apply optional Stage 2 chronological even frame capping."""
    if max_frames <= 0 or len(frames) <= max_frames:
        return frames, False

    if max_frames == 1:
        return [frames[0]], True

    first = frames[0]
    last = frames[-1]
    middle = frames[1:-1]
    remaining_slots = max_frames - 2

    if remaining_slots <= 0:
        return [first, last][:max_frames], True

    selected_middle = [
        middle[index]
        for index in evenly_spaced_indices(len(middle), remaining_slots)
    ]

    selected = [first, *selected_middle, last]
    return selected[:max_frames], True


def image_to_data_url(image_path: Path) -> str:
    """Encode a local image as a base64 data URL."""
    mime_type = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"

    with image_path.open("rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime_type};base64,{encoded}"


def format_frame_label(frame: FrameInfo) -> str:
    """Return a neutral frame label for the model request."""
    timestamp = (
        f"{frame.timestamp_seconds:.3f}s"
        if frame.timestamp_seconds is not None
        else "unknown"
    )
    selection_reason = frame.selection_reason or "unknown"

    return (
        f"Frame {frame.frame_index} — timestamp {timestamp} — "
        f"selection reason: {selection_reason}"
    )


def build_request_content(
        prompt_text: str,
        commercial_id: str,
        frames: list[FrameInfo],
        image_detail: str,
) -> list[dict[str, Any]]:
    """Build multimodal request content with prompt, frame labels, and images."""
    content: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": prompt_text,
        },
        {
            "type": "input_text",
            "text": (
                "Frame sequence metadata:\n"
                f"Commercial ID: {commercial_id}\n"
                f"Number of sampled frames: {len(frames)}"
            ),
        },
    ]

    for frame in frames:
        content.append(
            {
                "type": "input_text",
                "text": format_frame_label(frame),
            }
        )
        content.append(
            {
                "type": "input_image",
                "image_url": image_to_data_url(frame.path),
                "detail": image_detail,
            }
        )

    return content


def usage_to_dict(usage: Any) -> dict[str, Any] | None:
    """Convert an OpenAI response usage object to a JSON-serializable dictionary."""
    if usage is None:
        return None

    if isinstance(usage, dict):
        return usage

    if hasattr(usage, "model_dump"):
        return usage.model_dump()

    if hasattr(usage, "dict"):
        return usage.dict()

    return {
        key: value
        for key, value in vars(usage).items()
        if not key.startswith("_")
    }


def extract_response_metadata(response: Any) -> dict[str, Any]:
    """Extract response ID and usage metadata from an OpenAI response object."""
    return {
        "response_id": getattr(response, "id", None),
        "usage": usage_to_dict(getattr(response, "usage", None)),
    }


def is_transient_api_error(exc: Exception) -> bool:
    """Return True when an exception appears to be a transient API failure."""
    name = exc.__class__.__name__.lower()
    message = str(exc).lower()

    transient_markers = [
        "rate",
        "timeout",
        "temporar",
        "connection",
        "server",
        "service unavailable",
        "gateway",
        "429",
        "500",
        "502",
        "503",
        "504",
    ]

    return any(marker in name or marker in message for marker in transient_markers)


def model_supports_temperature(model: str) -> bool:
    """Return whether the selected model should receive a temperature parameter.

    Some newer multimodal/reasoning models, including gpt-5.5 in this project,
    reject the Responses API `temperature` parameter. For those models, the
    programme omits the parameter rather than failing the request.
    """
    normalized_model = model.strip().lower()
    models_without_temperature = {
        "gpt-5.5",
    }

    return normalized_model not in models_without_temperature


def call_openai_visual_description(
        client: Any,
        model: str,
        content: list[dict[str, Any]],
        temperature: float,
        max_retries: int,
        retry_backoff_seconds: float,
) -> tuple[str, dict[str, Any]]:
    """Call the OpenAI Responses API and return response text and metadata."""
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "input": [
                    {
                        "role": "user",
                        "content": content,
                    }
                ],
            }

            if temperature is not None and model_supports_temperature(model):
                kwargs["temperature"] = temperature

            response = client.responses.create(**kwargs)
            response_text = getattr(response, "output_text", None)

            if not isinstance(response_text, str) or not response_text.strip():
                raise RuntimeError("OpenAI response did not contain output_text")

            return response_text.strip(), extract_response_metadata(response)

        except Exception as exc:
            last_error = exc

            if attempt >= max_retries or not is_transient_api_error(exc):
                break

            sleep_seconds = retry_backoff_seconds * (2 ** attempt)
            logging.warning(
                "Transient API error; retrying in %.1fs (attempt %s/%s): %s",
                sleep_seconds,
                attempt + 1,
                max_retries,
                exc,
                )
            time.sleep(sleep_seconds)

    raise RuntimeError(f"OpenAI visual description request failed: {last_error}")


def frame_to_json(frame: FrameInfo) -> dict[str, Any]:
    """Convert FrameInfo to a JSON-serializable dictionary."""
    return {
        "frame_index": frame.frame_index,
        "filename": frame.filename,
        "path": str(frame.path),
        "timestamp_seconds": frame.timestamp_seconds,
        "selection_reason": frame.selection_reason,
    }


def write_per_commercial_success_outputs(
        work_item: WorkItem,
        config: RuntimeConfig,
        manifest: dict[str, Any],
        frames: list[FrameInfo],
        manifest_frame_count: int,
        stage2_frame_cap_applied: bool,
        response_text: str,
        api_metadata: dict[str, Any],
        duration_seconds: float,
) -> None:
    """Write .txt and .json success outputs for one commercial."""
    work_item.output_text_path.parent.mkdir(parents=True, exist_ok=True)

    work_item.output_text_path.write_text(
        response_text.strip() + "\n",
        encoding="utf-8",
        )

    data = {
        "commercial_id": work_item.commercial_id,
        "status": "success",
        "model": config.model,
        "image_detail": config.image_detail,
        "temperature": config.temperature,
        "temperature_sent_to_api": model_supports_temperature(config.model),
        "prompt": {
            "prompt_file": str(config.prompt_file),
            "prompt_sha256": config.prompt_sha256,
            "prompt_text": config.prompt_text,
        },
        "input": {
            "frame_dir": str(work_item.frame_dir),
            "frame_manifest_path": str(work_item.frame_manifest_path),
            "source_video": manifest.get("source_video"),
            "stage1_sampling_config": manifest.get("sampling_config"),
        },
        "frames": [frame_to_json(frame) for frame in frames],
        "frame_counts": {
            "manifest_frame_count": manifest_frame_count,
            "submitted_frame_count": len(frames),
            "stage2_frame_cap_applied": stage2_frame_cap_applied,
            "max_frames_per_request": config.max_frames_per_request,
        },
        "output": {
            "text_path": str(work_item.output_text_path),
            "json_path": str(work_item.output_json_path),
            "response_text": response_text,
        },
        "api_metadata": api_metadata,
        "duration_seconds": round(duration_seconds, 3),
        "created_at": utc_timestamp(),
        "error": None,
    }

    write_json(work_item.output_json_path, data)


def write_per_commercial_failure_output(
        work_item: WorkItem,
        error: str,
        duration_seconds: float,
) -> None:
    """Write a per-commercial failure JSON record."""
    data = {
        "commercial_id": work_item.commercial_id,
        "status": "failed",
        "input": {
            "frame_dir": str(work_item.frame_dir),
            "frame_manifest_path": str(work_item.frame_manifest_path),
        },
        "output": {
            "text_path": str(work_item.output_text_path),
            "json_path": str(work_item.output_json_path),
        },
        "duration_seconds": round(duration_seconds, 3),
        "created_at": utc_timestamp(),
        "error": error,
    }

    write_json(work_item.output_json_path, data)


def process_commercial_visual(
        work_item: WorkItem,
        config: RuntimeConfig,
) -> ProcessingResult:
    """Process one commercial frame sequence and return a structured result."""
    start = time.time()

    try:
        client = OpenAI()

        manifest = read_frame_manifest(work_item.frame_manifest_path)
        frames = resolve_frame_paths(work_item.frame_dir, manifest)
        manifest_frame_count = len(frames)
        submitted_frames, stage2_frame_cap_applied = cap_frames_evenly(
            frames,
            config.max_frames_per_request,
        )

        content = build_request_content(
            prompt_text=config.prompt_text,
            commercial_id=work_item.commercial_id,
            frames=submitted_frames,
            image_detail=config.image_detail,
        )

        response_text, api_metadata = call_openai_visual_description(
            client=client,
            model=config.model,
            content=content,
            temperature=config.temperature,
            max_retries=config.max_retries,
            retry_backoff_seconds=config.retry_backoff_seconds,
        )

        duration_seconds = time.time() - start

        write_per_commercial_success_outputs(
            work_item=work_item,
            config=config,
            manifest=manifest,
            frames=submitted_frames,
            manifest_frame_count=manifest_frame_count,
            stage2_frame_cap_applied=stage2_frame_cap_applied,
            response_text=response_text,
            api_metadata=api_metadata,
            duration_seconds=duration_seconds,
        )

        return ProcessingResult(
            commercial_id=work_item.commercial_id,
            input_path=work_item.frame_dir,
            output_path=work_item.output_text_path,
            json_path=work_item.output_json_path,
            status="success",
            error=None,
            duration_seconds=round(duration_seconds, 3),
            manifest_frame_count=manifest_frame_count,
            submitted_frame_count=len(submitted_frames),
            stage2_frame_cap_applied=stage2_frame_cap_applied,
            response_id=api_metadata.get("response_id"),
            usage=api_metadata.get("usage"),
            timestamp=utc_timestamp(),
        )

    except Exception as exc:
        duration_seconds = time.time() - start
        error = str(exc)

        try:
            write_per_commercial_failure_output(
                work_item=work_item,
                error=error,
                duration_seconds=duration_seconds,
            )
        except Exception:
            pass

        return ProcessingResult(
            commercial_id=work_item.commercial_id,
            input_path=work_item.frame_dir,
            output_path=work_item.output_text_path,
            json_path=work_item.output_json_path,
            status="failed",
            error=error,
            duration_seconds=round(duration_seconds, 3),
            manifest_frame_count=0,
            submitted_frame_count=0,
            stage2_frame_cap_applied=False,
            response_id=None,
            usage=None,
            timestamp=utc_timestamp(),
        )


def result_to_manifest_entry(result: ProcessingResult, config: RuntimeConfig) -> dict[str, Any]:
    """Convert a processing result to a run-manifest file entry."""
    return {
        "commercial_id": result.commercial_id,
        "input_path": str(result.input_path),
        "output_path": str(result.output_path),
        "json_path": str(result.json_path),
        "status": result.status,
        "error": result.error,
        "duration_seconds": result.duration_seconds,
        "timestamp": result.timestamp,
        "metadata": {
            "model": config.model if result.status != "skipped_existing" else None,
            "manifest_frame_count": result.manifest_frame_count,
            "submitted_frame_count": result.submitted_frame_count,
            "stage2_frame_cap_applied": result.stage2_frame_cap_applied,
            "response_id": result.response_id,
            "usage": result.usage,
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
        config: RuntimeConfig,
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
                "model": config.model,
                "image_detail": config.image_detail,
                "temperature": config.temperature,
                "temperature_sent_to_api": model_supports_temperature(config.model),
                "prompt_file": str(config.prompt_file),
                "prompt_sha256": config.prompt_sha256,
                "max_frames_per_request": config.max_frames_per_request,
                "max_retries": config.max_retries,
                "retry_backoff_seconds": config.retry_backoff_seconds,
            },
        },
        "files": [result_to_manifest_entry(result, config) for result in results],
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


def build_runtime_config(args: argparse.Namespace, prompt_text: str) -> RuntimeConfig:
    """Build runtime configuration from CLI arguments and prompt text."""
    return RuntimeConfig(
        model=args.model,
        image_detail=args.image_detail,
        temperature=args.temperature,
        prompt_file=Path(args.prompt_file),
        prompt_text=prompt_text,
        prompt_sha256=sha256_text(prompt_text),
        max_frames_per_request=args.max_frames_per_request,
        max_retries=args.max_retries,
        retry_backoff_seconds=args.retry_backoff_seconds,
    )


def log_startup(
        args: argparse.Namespace,
        config: RuntimeConfig,
        log_file: Path,
        manifest_file: Path,
) -> None:
    """Log startup configuration without logging secrets."""
    logging.info("Starting visual description run")
    logging.info("Model: %s", config.model)
    logging.info("Input dir: %s", args.input_dir)
    logging.info("Output dir: %s", args.output_dir)
    logging.info("Log file: %s", log_file)
    logging.info("Manifest file: %s", manifest_file)
    logging.info("Prompt file: %s", config.prompt_file)
    logging.info("Prompt SHA-256: %s", config.prompt_sha256)
    logging.info("Image detail: %s", config.image_detail)
    logging.info("Temperature: %s", config.temperature)

    if not model_supports_temperature(config.model):
        logging.info(
            "Temperature parameter will be omitted because model %s does not support it",
            config.model,
        )

    logging.info("Max frames per request: %s", config.max_frames_per_request)
    logging.info("Test mode: %s (limit=%s)", args.test_mode, args.test_limit)
    logging.info("Reprocess existing: %s", args.reprocess)
    logging.info("Workers: %s", args.workers)
    logging.info("OPENAI_API_KEY is configured")


def log_result(result: ProcessingResult) -> None:
    """Log a per-commercial result in the main process."""
    if result.status == "success":
        logging.info(
            "SUCCESS %s frames=%s response_id=%s",
            result.commercial_id,
            result.submitted_frame_count,
            result.response_id,
        )
    elif result.status == "skipped_existing":
        logging.info(
            "SKIPPED_EXISTING %s %s",
            result.commercial_id,
            result.output_path,
        )
    else:
        logging.error("FAILED %s %s", result.commercial_id, result.error)


def run_processing(
        planned: list[WorkItem],
        config: RuntimeConfig,
        workers: int,
) -> list[ProcessingResult]:
    """Run per-commercial visual description sequentially or with threads."""
    results: list[ProcessingResult] = []

    if workers == 1:
        for work_item in planned:
            result = process_commercial_visual(work_item, config)
            results.append(result)
            log_result(result)
        return results

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(process_commercial_visual, work_item, config): work_item
            for work_item in planned
        }

        for future in as_completed(future_map):
            result = future.result()
            results.append(result)
            log_result(result)

    return sorted(results, key=lambda result: natural_sort_key(result.commercial_id))


def main() -> int:
    """Main orchestration entry point."""
    args = parse_args()

    if args.log_file is None:
        args.log_file = str(Path(args.output_dir) / "describe_commercials_visual.log")
    if args.manifest_file is None:
        args.manifest_file = str(
            Path(args.output_dir) / "describe_commercials_visual_manifest.json"
        )

    log_file = Path(args.log_file)
    manifest_file = Path(args.manifest_file)
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    run_id = make_run_id()
    start_time = utc_timestamp()

    try:
        apply_dotenv(Path("env/.env"))
        validate_args(args)
        prompt_text = load_prompt(Path(args.prompt_file))
        config = build_runtime_config(args, prompt_text)

        configure_logging(log_file)
        log_startup(args, config, log_file, manifest_file)

        items = discover_frame_dirs(input_dir)
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
            workers=args.workers,
        )

        all_results = sorted(
            [*skipped, *processed],
            key=lambda result: natural_sort_key(result.commercial_id),
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
            "Completed visual description run: attempted=%s succeeded=%s failed=%s skipped_existing=%s",
            len(processed),
            succeeded_count,
            failed_count,
            skipped_count,
        )

        return EXIT_PARTIAL_FAILURE if failed_count else EXIT_SUCCESS

    except KeyboardInterrupt:
        try:
            logging.error("Interrupted by user")
        except Exception:
            print("Interrupted by user", file=sys.stderr)

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