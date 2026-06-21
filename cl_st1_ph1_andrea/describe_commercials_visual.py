"""
Generate commercial-specific visual-description prompts and submit selected frames
with audio-derived transcript context to a multimodal OpenAI model.

This programme is the LLM-based visual-description stage of the Phase 1 visual
pipeline. It reads selected commercial metadata, creates one prompt document per
commercial from a Markdown template, inserts product context and a timestamped
Whisper/faster-whisper transcript context block, submits the generated prompt with
selected frames, and writes visual descriptions plus reproducibility metadata.

Default inputs:
    corpus/00_sources/tv_commercials_selected_2.tsv
    describe_commercials_visual_prompts/visual_commercial_description_v5.md
    corpus/05_frames_selected/<Commercial ID>/
    corpus/04_transcripts/<Commercial ID>.json
    corpus/03_audio/<Commercial ID>.wav

Default generated prompts:
    corpus/06_visual_descriptions_prompts/<Commercial ID>.md

Default outputs:
    corpus/06_visual_descriptions/<Commercial ID>.txt
    corpus/06_visual_descriptions/<Commercial ID>.json

Typical usage:
    python describe_commercials_visual.py
    python describe_commercials_visual.py --no-test-mode
    python describe_commercials_visual.py --no-test-mode --workers 4
    python describe_commercials_visual.py --no-test-mode --transcripts-dir corpus/04_transcripts
    python describe_commercials_visual.py --no-test-mode --audio-dir corpus/03_audio
    python describe_commercials_visual.py --no-test-mode --max-frames-per-request 40
    python describe_commercials_visual.py --no-test-mode --reprocess

The programme uses selected frames from corpus/05_frames_selected/. It does not
use the dense sampled-frame directory corpus/05_frames/ for LLM requests.

The original audio file is retained as a provenance artefact, but it is not
submitted to the OpenAI Responses API. Instead, the corresponding Whisper JSON
transcript is inserted into the generated prompt as imperfect audio-derived
supporting context. The selected frames remain the primary evidence for visible
content.

Requires OPENAI_API_KEY in env/.env or the system environment.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import logging
import mimetypes
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PRODUCT_CONTEXT_PLACEHOLDER = (
    "<This is a commercial for LiquidPeptans, from the 1950s. "
    "This antacid product is used for reducing acid acidity to relieve discomfort.>"
)

TRANSCRIPT_CONTEXT_PLACEHOLDER = "<AUDIO_DERIVED_TRANSCRIPT_CONTEXT>"

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
SUPPORTED_AUDIO_EXTENSIONS = {".wav"}
SUPPORTED_TRANSCRIPT_EXTENSIONS = {".json"}


class ConfigurationError(Exception):
    """Raised when programme configuration is invalid."""


@dataclass(frozen=True)
class CommercialMetadata:
    """Metadata for one selected commercial row."""

    commercial_id: str
    description: str
    row_number: int
    row: dict[str, str]


@dataclass(frozen=True)
class FrameInfo:
    """Information about one selected frame to submit to the LLM."""

    filename: str
    path: Path
    frame_index: int | None = None
    timestamp_seconds: float | None = None
    selection_reason: str | None = None


@dataclass(frozen=True)
class AudioInfo:
    """Information about one commercial audio file retained for provenance."""

    filename: str
    path: Path
    format: str
    sha256: str | None


@dataclass(frozen=True)
class TranscriptInfo:
    """Information about one commercial transcript JSON file."""

    filename: str
    path: Path
    commercial_id: str | None
    audio_input_path: str | None
    text_output_path: str | None
    json_output_path: str | None
    model: dict[str, Any]
    transcription: dict[str, Any]
    metadata: dict[str, Any]
    sha256: str


@dataclass(frozen=True)
class WorkItem:
    """Planned work for one commercial visual-description request."""

    commercial_id: str
    description: str
    metadata_row: dict[str, str]
    frame_dir: Path
    audio_path: Path
    transcript_json_path: Path
    prompt_file: Path
    output_text_path: Path
    output_json_path: Path


@dataclass(frozen=True)
class RuntimeConfig:
    """Runtime configuration shared by all worker tasks."""

    metadata_tsv: Path
    prompt_template: Path
    prompt_template_text: str
    prompt_template_sha256: str
    frames_dir: Path
    audio_dir: Path
    transcripts_dir: Path
    prompt_output_dir: Path
    output_dir: Path
    model: str
    image_detail: str
    temperature: float
    max_frames_per_request: int
    max_transcript_segments: int
    max_retries: int
    retry_backoff_seconds: float
    reprocess: bool


@dataclass
class ProcessingResult:
    """Result record for one commercial."""

    commercial_id: str
    input_path: str | None
    audio_path: str | None
    transcript_path: str | None
    output_path: str
    json_path: str
    prompt_path: str
    status: str
    error: str | None
    duration_seconds: float
    submitted_frame_count: int
    submitted_audio: bool
    submitted_transcript_context: bool
    response_id: str | None
    usage: dict[str, Any] | None
    timestamp: str


def utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_id() -> str:
    """Return a filename-safe UTC run identifier."""

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def natural_sort_key(text: str) -> list[int | str]:
    """Return a natural-sort key that treats digit runs as integers."""

    parts = re.split(r"(\d+)", text)
    return [int(part) if part.isdigit() else part.lower() for part in parts]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Generate commercial-specific prompts and visual descriptions from "
            "selected frames and timestamped transcript context."
        )
    )

    parser.add_argument(
        "--prompt-template",
        type=Path,
        default=Path("describe_commercials_visual_prompts/visual_commercial_description_v5.md"),
        help="Markdown prompt template.",
    )
    parser.add_argument(
        "--metadata-tsv",
        type=Path,
        default=Path("corpus/00_sources/tv_commercials_selected_2.tsv"),
        help="Selected commercial metadata TSV.",
    )
    parser.add_argument(
        "--frames-dir",
        type=Path,
        default=Path("corpus/05_frames_selected"),
        help="Directory containing selected frame folders.",
    )
    parser.add_argument(
        "--audio-dir",
        type=Path,
        default=Path("corpus/03_audio"),
        help="Directory containing provenance audio files named <Commercial ID>.wav.",
    )
    parser.add_argument(
        "--transcripts-dir",
        type=Path,
        default=Path("corpus/04_transcripts"),
        help="Directory containing Whisper JSON transcripts named <Commercial ID>.json.",
    )
    parser.add_argument(
        "--prompt-output-dir",
        type=Path,
        default=Path("corpus/06_visual_descriptions_prompts"),
        help="Directory where generated prompt documents are written.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("corpus/06_visual_descriptions"),
        help="Directory where visual descriptions are written.",
    )
    parser.add_argument("--model", default="gpt-5.5", help="OpenAI multimodal model.")
    parser.add_argument(
        "--image-detail",
        choices=("low", "high", "auto"),
        default="low",
        help="Image detail setting for the Responses API.",
    )
    parser.add_argument("--temperature", type=float, default=0.0, help="Generation temperature.")
    parser.add_argument(
        "--test-mode",
        dest="test_mode",
        action="store_true",
        default=True,
        help="Enable test mode.",
    )
    parser.add_argument(
        "--no-test-mode",
        dest="test_mode",
        action="store_false",
        help="Disable test mode and process all planned items.",
    )
    parser.add_argument("--test-limit", type=int, default=5, help="Maximum items to attempt in test mode.")
    parser.add_argument("--start-commercial-id", default=None, help="Start processing from this commercial ID.")
    parser.add_argument("--reprocess", action="store_true", help="Regenerate existing successful outputs.")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker threads.")
    parser.add_argument(
        "--max-frames-per-request",
        type=int,
        default=0,
        help="Optional cap on frames submitted per request; 0 means no cap.",
    )
    parser.add_argument(
        "--max-transcript-segments",
        type=int,
        default=0,
        help="Optional cap on transcript segments inserted into the prompt; 0 means no cap.",
    )
    parser.add_argument("--max-retries", type=int, default=2, help="Maximum API retry attempts.")
    parser.add_argument(
        "--retry-backoff-seconds",
        type=float,
        default=5.0,
        help="Initial retry backoff in seconds.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Log file path. Defaults to <output-dir>/describe_commercials_visual.log.",
    )
    parser.add_argument(
        "--manifest-file",
        type=Path,
        default=None,
        help="Latest run manifest path. Defaults to <output-dir>/describe_commercials_visual_manifest.json.",
    )

    return parser.parse_args()


def load_dotenv(dotenv_path: Path) -> dict[str, str]:
    """Load simple KEY=VALUE pairs from a .env file without logging secrets."""

    loaded: dict[str, str] = {}

    if not dotenv_path.exists():
        return loaded

    with dotenv_path.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()

            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue

            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')

            if key and key not in os.environ:
                os.environ[key] = value
                loaded[key] = value

    return loaded


def configure_logging(log_file: Path) -> None:
    """Configure console and file logging."""

    log_file.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)-5s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )


def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments before processing."""

    if not args.prompt_template.exists():
        raise ConfigurationError(f"Prompt template missing: {args.prompt_template}")

    if not args.prompt_template.is_file():
        raise ConfigurationError(f"Prompt template is not a file: {args.prompt_template}")

    if not args.metadata_tsv.exists():
        raise ConfigurationError(f"Metadata TSV missing: {args.metadata_tsv}")

    if not args.metadata_tsv.is_file():
        raise ConfigurationError(f"Metadata TSV is not a file: {args.metadata_tsv}")

    if not args.frames_dir.exists():
        raise ConfigurationError(f"Selected frames directory missing: {args.frames_dir}")

    if not args.frames_dir.is_dir():
        raise ConfigurationError(f"Selected frames path is not a directory: {args.frames_dir}")

    if not args.audio_dir.exists():
        raise ConfigurationError(f"Audio directory missing: {args.audio_dir}")

    if not args.audio_dir.is_dir():
        raise ConfigurationError(f"Audio path is not a directory: {args.audio_dir}")

    if not args.transcripts_dir.exists():
        raise ConfigurationError(f"Transcripts directory missing: {args.transcripts_dir}")

    if not args.transcripts_dir.is_dir():
        raise ConfigurationError(f"Transcripts path is not a directory: {args.transcripts_dir}")

    if args.test_limit <= 0:
        raise ConfigurationError("--test-limit must be greater than 0")

    if args.workers <= 0:
        raise ConfigurationError("--workers must be greater than 0")

    if args.temperature < 0:
        raise ConfigurationError("--temperature must be greater than or equal to 0")

    if args.max_frames_per_request < 0:
        raise ConfigurationError("--max-frames-per-request must be greater than or equal to 0")

    if args.max_transcript_segments < 0:
        raise ConfigurationError("--max-transcript-segments must be greater than or equal to 0")

    if args.max_retries < 0:
        raise ConfigurationError("--max-retries must be greater than or equal to 0")

    if args.retry_backoff_seconds < 0:
        raise ConfigurationError("--retry-backoff-seconds must be greater than or equal to 0")


def load_prompt_template(prompt_template: Path) -> str:
    """Load and validate the Markdown prompt template."""

    text = prompt_template.read_text(encoding="utf-8").strip()

    if not text:
        raise ConfigurationError(f"Prompt template is empty: {prompt_template}")

    if PRODUCT_CONTEXT_PLACEHOLDER not in text:
        raise ConfigurationError(
            "Required product-context placeholder was not found in prompt template: "
            f"{PRODUCT_CONTEXT_PLACEHOLDER}"
        )

    if TRANSCRIPT_CONTEXT_PLACEHOLDER not in text:
        raise ConfigurationError(
            "Required transcript-context placeholder was not found in prompt template: "
            f"{TRANSCRIPT_CONTEXT_PLACEHOLDER}"
        )

    return text


def sha256_text(text: str) -> str:
    """Return the SHA-256 hash of text."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hash of a file."""

    digest = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def read_selected_metadata(metadata_tsv: Path) -> list[CommercialMetadata]:
    """Read selected commercial metadata from TSV and validate required fields."""

    rows: list[CommercialMetadata] = []
    seen_ids: set[str] = set()

    with metadata_tsv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")

        if reader.fieldnames is None:
            raise ConfigurationError(f"Metadata TSV is empty: {metadata_tsv}")

        required_columns = {"Commercial ID", "Description"}
        missing = required_columns.difference(reader.fieldnames)

        if missing:
            missing_list = ", ".join(sorted(missing))
            raise ConfigurationError(f"Metadata TSV is missing required column(s): {missing_list}")

        for row_number, row in enumerate(reader, start=2):
            commercial_id = (row.get("Commercial ID") or "").strip()
            description = (row.get("Description") or "").strip()

            if not commercial_id:
                raise ConfigurationError(f"Empty Commercial ID at TSV row {row_number}")

            if not description:
                raise ConfigurationError(f"Empty Description for {commercial_id} at TSV row {row_number}")

            if commercial_id in seen_ids:
                raise ConfigurationError(f"Duplicate Commercial ID in TSV: {commercial_id}")

            seen_ids.add(commercial_id)

            rows.append(
                CommercialMetadata(
                    commercial_id=commercial_id,
                    description=description,
                    row_number=row_number,
                    row={key: value for key, value in row.items()},
                )
            )

    if not rows:
        raise ConfigurationError(f"No selected commercials found in metadata TSV: {metadata_tsv}")

    return rows


def format_seconds(seconds: float | int | None) -> str:
    """Format seconds as a three-decimal timestamp string."""

    if seconds is None:
        return "unknown"

    try:
        return f"{float(seconds):.3f}"
    except (TypeError, ValueError):
        return "unknown"


def resolve_audio_file(audio_path: Path) -> AudioInfo:
    """Resolve and validate a commercial audio file retained for provenance."""

    if not audio_path.exists():
        raise FileNotFoundError(f"Missing audio file: {audio_path}")

    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio path is not a file: {audio_path}")

    suffix = audio_path.suffix.lower()

    if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError(f"Unsupported audio extension: {audio_path}")

    return AudioInfo(
        filename=audio_path.name,
        path=audio_path,
        format=suffix.lstrip("."),
        sha256=sha256_file(audio_path),
    )


def load_transcript_json(transcript_json_path: Path) -> TranscriptInfo:
    """Load and validate a Whisper/faster-whisper transcript JSON file."""

    if not transcript_json_path.exists():
        raise FileNotFoundError(f"Missing transcript JSON file: {transcript_json_path}")

    if not transcript_json_path.is_file():
        raise FileNotFoundError(f"Transcript JSON path is not a file: {transcript_json_path}")

    if transcript_json_path.suffix.lower() not in SUPPORTED_TRANSCRIPT_EXTENSIONS:
        raise ValueError(f"Unsupported transcript extension: {transcript_json_path}")

    with transcript_json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Transcript JSON root must be an object: {transcript_json_path}")

    transcription = data.get("transcription")
    if not isinstance(transcription, dict):
        raise ValueError(f"Transcript JSON missing transcription object: {transcript_json_path}")

    segments = transcription.get("segments")
    if not isinstance(segments, list):
        raise ValueError(f"Transcript JSON missing transcription.segments list: {transcript_json_path}")

    return TranscriptInfo(
        filename=transcript_json_path.name,
        path=transcript_json_path,
        commercial_id=data.get("commercial_id") if isinstance(data.get("commercial_id"), str) else None,
        audio_input_path=data.get("input_path") if isinstance(data.get("input_path"), str) else None,
        text_output_path=data.get("text_output_path") if isinstance(data.get("text_output_path"), str) else None,
        json_output_path=data.get("json_output_path") if isinstance(data.get("json_output_path"), str) else None,
        model=data.get("model") if isinstance(data.get("model"), dict) else {},
        transcription=transcription,
        metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
        sha256=sha256_file(transcript_json_path),
    )


def transcript_segments(transcript_info: TranscriptInfo, max_segments: int) -> tuple[list[dict[str, Any]], bool]:
    """Return transcript segments, optionally capped from the end of the list."""

    raw_segments = transcript_info.transcription.get("segments", [])

    usable_segments = [
        segment
        for segment in raw_segments
        if isinstance(segment, dict) and str(segment.get("text", "")).strip()
    ]

    if max_segments == 0 or len(usable_segments) <= max_segments:
        return usable_segments, False

    return usable_segments[:max_segments], True


def build_transcript_context_block(
        transcript_info: TranscriptInfo,
        audio_info: AudioInfo,
        max_segments: int,
) -> tuple[str, dict[str, Any]]:
    """
    Build a concise Markdown context block from a Whisper/faster-whisper transcript JSON.

    The block is inserted into the generated prompt in place of
    <AUDIO_DERIVED_TRANSCRIPT_CONTEXT>. It is explicitly framed as imperfect
    audio-derived supporting context, not as a substitute for the raw audio signal.

    Timestamped transcript segment lines are separated by blank lines so that
    Markdown renderers preserve them as visually distinct lines rather than joining
    them into one paragraph.
    """

    model = transcript_info.model
    transcription = transcript_info.transcription
    metadata = transcript_info.metadata
    segments, cap_applied = transcript_segments(transcript_info, max_segments)

    backend = model.get("backend", "unknown")
    model_name = model.get("model_name", "unknown")
    language_setting = model.get("language", "unknown")
    vad_filter = model.get("vad_filter", "unknown")
    detected_language = transcription.get("detected_language", "unknown")
    language_probability = transcription.get("language_probability", "unknown")
    duration_seconds = transcription.get("duration_seconds", "unknown")

    lines = [
        (
            "The following transcript was generated automatically from the commercial audio "
            "using Whisper/faster-whisper. It is provided only as imperfect supporting context. "
            "It may contain transcription errors and does not preserve the full audio signal."
        ),
        "",
        f"Audio file source: {audio_info.path}",
        "",
        f"Transcript JSON source: {transcript_info.path}",
        "",
        f"Transcription backend: {backend}",
        "",
        f"Transcription model: {model_name}",
        "",
        f"Language setting: {language_setting}",
        "",
        f"Detected language: {detected_language}",
        "",
        f"Language probability: {language_probability}",
        "",
        f"VAD filter: {vad_filter}",
        "",
        f"Duration: {duration_seconds} seconds",
    ]

    if metadata:
        title = metadata.get("title")
        decade = metadata.get("decade")
        category = metadata.get("category")
        if title or decade or category:
            lines.extend(
                [
                    "",
                    "Transcript metadata:",
                    "",
                    f"Title: {title if title is not None else 'unknown'}",
                    "",
                    f"Decade: {decade if decade is not None else 'unknown'}",
                    "",
                    f"Category: {category if category is not None else 'unknown'}",
                ]
            )

    if cap_applied:
        lines.extend(
            [
                "",
                (
                    "Timestamped transcript segments "
                    f"(first {len(segments)} of {len(transcript_info.transcription.get('segments', []))} usable segments):"
                ),
                "",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Timestamped transcript segments:",
                "",
            ]
        )

    if not segments:
        lines.extend(
            [
                "[No usable transcript segments were available.]",
                "",
            ]
        )
    else:
        for segment in segments:
            start = format_seconds(segment.get("start"))
            end = format_seconds(segment.get("end"))
            text = " ".join(str(segment.get("text", "")).strip().split())
            lines.extend(
                [
                    f"[{start}–{end}] {text}",
                    "",
                ]
            )

    context_block = "\n".join(lines).rstrip()

    metadata_record = {
        "transcript_context_inserted": True,
        "transcript_context_sha256": sha256_text(context_block),
        "segment_count_available": len(
            [
                segment
                for segment in transcript_info.transcription.get("segments", [])
                if isinstance(segment, dict) and str(segment.get("text", "")).strip()
            ]
        ),
        "segment_count_inserted": len(segments),
        "segment_cap_applied": cap_applied,
        "max_transcript_segments": max_segments,
        "segment_markdown_spacing": "blank_line_between_segments",
    }

    return context_block, metadata_record


def generate_prompt_text(
        template_text: str,
        description: str,
        transcript_context_block: str,
) -> str:
    """Generate a commercial-specific prompt by replacing template placeholders."""

    prompt_text = template_text.replace(PRODUCT_CONTEXT_PLACEHOLDER, description)
    prompt_text = prompt_text.replace(TRANSCRIPT_CONTEXT_PLACEHOLDER, transcript_context_block)

    return prompt_text


def write_prompt_file(
        prompt_file: Path,
        prompt_text: str,
        reprocess: bool,
) -> bool:
    """
    Write a generated prompt file if needed.

    Returns True if the file was written, False if an existing matching prompt was left unchanged.
    """

    prompt_file.parent.mkdir(parents=True, exist_ok=True)

    if prompt_file.exists() and not reprocess:
        existing_text = prompt_file.read_text(encoding="utf-8")

        if existing_text == prompt_text:
            return False

        logging.warning("Prompt file exists with different content; leaving unchanged: %s", prompt_file)
        return False

    prompt_file.write_text(prompt_text, encoding="utf-8")
    return True


def successful_existing_output(text_path: Path, json_path: Path) -> bool:
    """Return True if existing output files represent a prior successful run."""

    if not text_path.exists() or not json_path.exists():
        return False

    try:
        with json_path.open("r", encoding="utf-8") as f:
            record = json.load(f)
    except Exception:
        return False

    return record.get("status") == "success"


def plan_work(
        metadata_rows: list[CommercialMetadata],
        config: RuntimeConfig,
        start_commercial_id: str | None,
        test_mode: bool,
        test_limit: int,
) -> tuple[list[WorkItem], list[ProcessingResult]]:
    """
    Plan work items and skipped-existing records.

    Test mode is applied to items that would be attempted, not to existing skipped items.
    """

    work_items: list[WorkItem] = []
    skipped_results: list[ProcessingResult] = []

    start_seen = start_commercial_id is None

    for item in metadata_rows:
        commercial_id = item.commercial_id

        if not start_seen:
            if commercial_id == start_commercial_id:
                start_seen = True
            else:
                continue

        prompt_file = config.prompt_output_dir / f"{commercial_id}.md"
        frame_dir = config.frames_dir / commercial_id
        audio_path = config.audio_dir / f"{commercial_id}.wav"
        transcript_json_path = config.transcripts_dir / f"{commercial_id}.json"
        output_text_path = config.output_dir / f"{commercial_id}.txt"
        output_json_path = config.output_dir / f"{commercial_id}.json"

        if not config.reprocess and successful_existing_output(output_text_path, output_json_path):
            skipped_results.append(
                ProcessingResult(
                    commercial_id=commercial_id,
                    input_path=str(frame_dir),
                    audio_path=str(audio_path),
                    transcript_path=str(transcript_json_path),
                    output_path=str(output_text_path),
                    json_path=str(output_json_path),
                    prompt_path=str(prompt_file),
                    status="skipped_existing",
                    error=None,
                    duration_seconds=0.0,
                    submitted_frame_count=0,
                    submitted_audio=False,
                    submitted_transcript_context=False,
                    response_id=None,
                    usage=None,
                    timestamp=utc_timestamp(),
                )
            )
            continue

        work_items.append(
            WorkItem(
                commercial_id=commercial_id,
                description=item.description,
                metadata_row=item.row,
                frame_dir=frame_dir,
                audio_path=audio_path,
                transcript_json_path=transcript_json_path,
                prompt_file=prompt_file,
                output_text_path=output_text_path,
                output_json_path=output_json_path,
            )
        )

        if test_mode and len(work_items) >= test_limit:
            break

    return work_items, skipped_results


def read_selected_frame_manifest(manifest_path: Path) -> dict[str, Any] | None:
    """Read selected frame manifest if present."""

    if not manifest_path.exists():
        return None

    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def frame_path_from_manifest_entry(frame_dir: Path, entry: dict[str, Any]) -> Path:
    """Resolve a frame path from a selected-frame manifest entry."""

    candidate_values = [
        entry.get("path"),
        entry.get("selected_path"),
        entry.get("output_path"),
        entry.get("filename"),
    ]

    for value in candidate_values:
        if not value:
            continue

        candidate = Path(str(value))

        if candidate.is_absolute() and candidate.exists():
            return candidate

        if candidate.exists():
            return candidate

        local_candidate = frame_dir / candidate.name

        if local_candidate.exists():
            return local_candidate

    raise FileNotFoundError(f"Cannot resolve frame path from manifest entry: {entry}")


def discover_frames_from_manifest(frame_dir: Path, manifest: dict[str, Any]) -> list[FrameInfo]:
    """Discover selected frames from a selected-frame manifest."""

    frames_source = None

    for key in ("selected_frames", "frames"):
        if isinstance(manifest.get(key), list):
            frames_source = manifest[key]
            break

    if frames_source is None:
        raise ValueError("Manifest does not contain a selected_frames or frames list")

    frames: list[FrameInfo] = []

    for index, entry in enumerate(frames_source, start=1):
        if not isinstance(entry, dict):
            continue

        try:
            path = frame_path_from_manifest_entry(frame_dir, entry)
        except FileNotFoundError:
            source_filename = (
                    entry.get("filename")
                    or entry.get("selected_filename")
                    or entry.get("output_filename")
            )

            if source_filename:
                path = frame_dir / Path(str(source_filename)).name
            else:
                raise

        if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            continue

        if not path.exists():
            raise FileNotFoundError(f"Missing selected frame file: {path}")

        frame_index = entry.get("frame_index")
        if frame_index is None:
            frame_index = entry.get("selected_frame_index")
        if frame_index is None:
            frame_index = index

        timestamp_seconds = entry.get("timestamp_seconds")
        if timestamp_seconds is None:
            timestamp_seconds = entry.get("source_timestamp_seconds")

        selection_reason = entry.get("selection_reason")
        if selection_reason is None:
            selection_reason = entry.get("source_selection_reason")

        frames.append(
            FrameInfo(
                filename=path.name,
                path=path,
                frame_index=int(frame_index) if str(frame_index).isdigit() else index,
                timestamp_seconds=float(timestamp_seconds) if timestamp_seconds is not None else None,
                selection_reason=str(selection_reason) if selection_reason is not None else None,
            )
        )

    if not frames:
        raise ValueError(f"No usable selected frames found in manifest for {frame_dir}")

    return sorted(frames, key=lambda frame: frame.frame_index if frame.frame_index is not None else 0)


def discover_frames_by_filename(frame_dir: Path) -> list[FrameInfo]:
    """Discover selected frames by natural filename sorting."""

    paths = [
        path
        for path in frame_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
    ]

    paths.sort(key=lambda path: natural_sort_key(path.name))

    if not paths:
        raise ValueError(f"No supported selected frame files found in {frame_dir}")

    return [
        FrameInfo(
            filename=path.name,
            path=path,
            frame_index=index,
            timestamp_seconds=None,
            selection_reason=None,
        )
        for index, path in enumerate(paths, start=1)
    ]


def discover_selected_frames(frame_dir: Path) -> list[FrameInfo]:
    """Discover selected frames for a commercial using the manifest when available."""

    if not frame_dir.exists():
        raise FileNotFoundError(f"Missing selected frame directory: {frame_dir}")

    if not frame_dir.is_dir():
        raise NotADirectoryError(f"Selected frame path is not a directory: {frame_dir}")

    manifest_path = frame_dir / "selected_frames_manifest.json"
    manifest = read_selected_frame_manifest(manifest_path)

    if manifest is not None:
        return discover_frames_from_manifest(frame_dir, manifest)

    return discover_frames_by_filename(frame_dir)


def cap_frames_evenly(frames: list[FrameInfo], max_frames: int) -> tuple[list[FrameInfo], bool]:
    """Apply optional deterministic chronological even downsampling."""

    if max_frames == 0 or len(frames) <= max_frames:
        return frames, False

    if max_frames == 1:
        return [frames[0]], True

    last_index = len(frames) - 1
    selected_indices = {0, last_index}
    remaining_slots = max_frames - 2

    if remaining_slots > 0:
        middle_count = len(frames) - 2

        if middle_count <= remaining_slots:
            selected_indices.update(range(1, len(frames) - 1))
        else:
            for slot in range(remaining_slots):
                position = 1 + round(slot * (middle_count - 1) / max(remaining_slots - 1, 1))
                selected_indices.add(position)

    selected = [frames[index] for index in sorted(selected_indices)]

    if len(selected) > max_frames:
        selected = selected[:max_frames]

    return selected, True


def image_to_data_url(image_path: Path) -> str:
    """Encode a local image as a base64 data URL."""

    mime_type, _ = mimetypes.guess_type(str(image_path))

    if mime_type is None:
        suffix = image_path.suffix.lower()

        if suffix in {".jpg", ".jpeg"}:
            mime_type = "image/jpeg"
        elif suffix == ".png":
            mime_type = "image/png"
        else:
            raise ValueError(f"Unsupported image extension: {image_path}")

    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def build_request_content(
        prompt_text: str,
        commercial_id: str,
        frames: list[FrameInfo],
        transcript_info: TranscriptInfo,
        audio_info: AudioInfo,
        image_detail: str,
) -> list[dict[str, Any]]:
    """Build OpenAI Responses API multimodal request content."""

    content: list[dict[str, Any]] = [
        {"type": "input_text", "text": prompt_text},
        {
            "type": "input_text",
            "text": (
                "Commercial sequence metadata:\n"
                f"Commercial ID: {commercial_id}\n"
                f"Audio provenance file: {audio_info.path}\n"
                f"Transcript JSON source: {transcript_info.path}\n"
                f"Number of selected frames: {len(frames)}\n\n"
                "The original audio file is retained for provenance but is not submitted. "
                "The generated prompt contains an imperfect audio-derived transcript context block. "
                "Use selected frames as the primary evidence for visible content."
            ),
        },
    ]

    for index, frame in enumerate(frames, start=1):
        timestamp = (
            f"{frame.timestamp_seconds:.3f}s"
            if frame.timestamp_seconds is not None
            else "unknown"
        )
        reason = frame.selection_reason or "unknown"
        label = (
            f"Frame {index} — filename: {frame.filename} — "
            f"timestamp: {timestamp} — selection reason: {reason}"
        )

        content.append({"type": "input_text", "text": label})
        content.append(
            {
                "type": "input_image",
                "image_url": image_to_data_url(frame.path),
                "detail": image_detail,
            }
        )

    return content


def model_supports_temperature(model: str) -> bool:
    """Return whether the selected model should receive a temperature parameter."""

    model_lower = model.lower()
    return not model_lower.startswith("gpt-5")


def extract_response_metadata(response: Any) -> dict[str, Any]:
    """Extract useful metadata from an OpenAI response object."""

    metadata: dict[str, Any] = {}

    response_id = getattr(response, "id", None)
    if response_id is not None:
        metadata["response_id"] = response_id

    usage = getattr(response, "usage", None)
    if usage is not None:
        if hasattr(usage, "model_dump"):
            metadata["usage"] = usage.model_dump()
        elif isinstance(usage, dict):
            metadata["usage"] = usage
        else:
            metadata["usage"] = str(usage)

    return metadata


def is_transient_api_error(exc: Exception) -> bool:
    """Return True if an exception appears to be a transient API failure."""

    text = str(exc).lower()
    transient_markers = [
        "rate limit",
        "429",
        "timeout",
        "timed out",
        "temporarily",
        "temporary",
        "server error",
        "internal server error",
        "bad gateway",
        "service unavailable",
        "gateway timeout",
        "connection",
        "502",
        "503",
        "504",
    ]
    return any(marker in text for marker in transient_markers)


def call_openai_visual_description(
        client: Any,
        model: str,
        content: list[dict[str, Any]],
        temperature: float,
        max_retries: int,
        retry_backoff_seconds: float,
) -> tuple[str, dict[str, Any]]:
    """Call the OpenAI Responses API and return response text plus metadata."""

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

            if model_supports_temperature(model):
                kwargs["temperature"] = temperature

            response = client.responses.create(**kwargs)
            response_text = getattr(response, "output_text", None)

            if not isinstance(response_text, str) or not response_text.strip():
                raise RuntimeError("OpenAI response did not contain usable output_text")

            return response_text.strip(), extract_response_metadata(response)

        except Exception as exc:
            last_error = exc

            if attempt >= max_retries or not is_transient_api_error(exc):
                break

            sleep_seconds = retry_backoff_seconds * (2**attempt)
            logging.warning(
                "Transient API error; retrying in %.1fs (attempt %s/%s): %s",
                sleep_seconds,
                attempt + 1,
                max_retries,
                exc,
                )
            time.sleep(sleep_seconds)

    raise RuntimeError(f"OpenAI visual description request failed: {last_error}")


def write_success_outputs(
        work_item: WorkItem,
        config: RuntimeConfig,
        frames: list[FrameInfo],
        audio_info: AudioInfo,
        transcript_info: TranscriptInfo,
        transcript_context_metadata: dict[str, Any],
        response_text: str,
        api_metadata: dict[str, Any],
        duration_seconds: float,
) -> None:
    """Write successful .txt and .json outputs for one commercial."""

    work_item.output_text_path.parent.mkdir(parents=True, exist_ok=True)
    generated_prompt_text = work_item.prompt_file.read_text(encoding="utf-8")
    generated_prompt_sha256 = sha256_text(generated_prompt_text)

    work_item.output_text_path.write_text(response_text.strip() + "\n", encoding="utf-8")

    record = {
        "commercial_id": work_item.commercial_id,
        "status": "success",
        "input": {
            "metadata_tsv": str(config.metadata_tsv),
            "frame_dir": str(work_item.frame_dir),
            "audio_file": str(audio_info.path),
            "transcript_json_file": str(transcript_info.path),
            "prompt_template": str(config.prompt_template),
            "generated_prompt_file": str(work_item.prompt_file),
        },
        "commercial_metadata": {
            "description": work_item.description,
            "row": work_item.metadata_row,
        },
        "prompt": {
            "template_sha256": config.prompt_template_sha256,
            "generated_prompt_sha256": generated_prompt_sha256,
            "product_context_placeholder_replaced": PRODUCT_CONTEXT_PLACEHOLDER not in generated_prompt_text,
            "transcript_context_placeholder_replaced": TRANSCRIPT_CONTEXT_PLACEHOLDER not in generated_prompt_text,
        },
        "audio": {
            "filename": audio_info.filename,
            "path": str(audio_info.path),
            "format": audio_info.format,
            "sha256": audio_info.sha256,
            "submitted": False,
            "role": "provenance_only",
        },
        "transcript": {
            "filename": transcript_info.filename,
            "path": str(transcript_info.path),
            "sha256": transcript_info.sha256,
            "audio_input_path_recorded_in_transcript": transcript_info.audio_input_path,
            "text_output_path_recorded_in_transcript": transcript_info.text_output_path,
            "json_output_path_recorded_in_transcript": transcript_info.json_output_path,
            "model": transcript_info.model,
            "metadata": transcript_info.metadata,
            "transcription_summary": {
                "detected_language": transcript_info.transcription.get("detected_language"),
                "language_probability": transcript_info.transcription.get("language_probability"),
                "duration_seconds": transcript_info.transcription.get("duration_seconds"),
                "text_sha256": sha256_text(str(transcript_info.transcription.get("text", ""))),
            },
            "context": transcript_context_metadata,
            "submitted_as_prompt_text": True,
        },
        "frames": [
            {
                "filename": frame.filename,
                "path": str(frame.path),
                "frame_index": frame.frame_index,
                "timestamp_seconds": frame.timestamp_seconds,
                "selection_reason": frame.selection_reason,
            }
            for frame in frames
        ],
        "frame_counts": {
            "submitted_frame_count": len(frames),
            "max_frames_per_request": config.max_frames_per_request,
        },
        "model": config.model,
        "image_detail": config.image_detail,
        "temperature": config.temperature,
        "temperature_sent_to_api": model_supports_temperature(config.model),
        "response_text": response_text,
        "api_metadata": api_metadata,
        "duration_seconds": round(duration_seconds, 3),
        "created_at": utc_timestamp(),
        "error": None,
    }

    with work_item.output_json_path.open("w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


def write_failure_output(
        work_item: WorkItem,
        config: RuntimeConfig,
        error: str,
        duration_seconds: float,
) -> None:
    """Write failed per-commercial JSON output."""

    work_item.output_json_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "commercial_id": work_item.commercial_id,
        "status": "failed",
        "input": {
            "metadata_tsv": str(config.metadata_tsv),
            "frame_dir": str(work_item.frame_dir),
            "audio_file": str(work_item.audio_path),
            "transcript_json_file": str(work_item.transcript_json_path),
            "prompt_template": str(config.prompt_template),
            "generated_prompt_file": str(work_item.prompt_file),
        },
        "commercial_metadata": {
            "description": work_item.description,
            "row": work_item.metadata_row,
        },
        "audio": {
            "filename": work_item.audio_path.name,
            "path": str(work_item.audio_path),
            "submitted": False,
            "role": "provenance_only",
        },
        "transcript": {
            "filename": work_item.transcript_json_path.name,
            "path": str(work_item.transcript_json_path),
            "submitted_as_prompt_text": False,
        },
        "output": {
            "text_path": str(work_item.output_text_path),
            "json_path": str(work_item.output_json_path),
        },
        "duration_seconds": round(duration_seconds, 3),
        "created_at": utc_timestamp(),
        "error": error,
    }

    with work_item.output_json_path.open("w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


def process_commercial_visual(work_item: WorkItem, config: RuntimeConfig) -> ProcessingResult:
    """Process one commercial prompt, selected-frame sequence, and transcript context."""

    start = time.time()

    try:
        from openai import OpenAI

        frames = discover_selected_frames(work_item.frame_dir)
        submitted_frames, _cap_applied = cap_frames_evenly(frames, config.max_frames_per_request)

        audio_info = resolve_audio_file(work_item.audio_path)
        transcript_info = load_transcript_json(work_item.transcript_json_path)

        transcript_context_block, transcript_context_metadata = build_transcript_context_block(
            transcript_info=transcript_info,
            audio_info=audio_info,
            max_segments=config.max_transcript_segments,
        )

        prompt_text = generate_prompt_text(
            template_text=config.prompt_template_text,
            description=work_item.description,
            transcript_context_block=transcript_context_block,
        )

        write_prompt_file(
            prompt_file=work_item.prompt_file,
            prompt_text=prompt_text,
            reprocess=config.reprocess,
        )

        prompt_text = work_item.prompt_file.read_text(encoding="utf-8")

        client = OpenAI()

        content = build_request_content(
            prompt_text=prompt_text,
            commercial_id=work_item.commercial_id,
            frames=submitted_frames,
            transcript_info=transcript_info,
            audio_info=audio_info,
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

        write_success_outputs(
            work_item=work_item,
            config=config,
            frames=submitted_frames,
            audio_info=audio_info,
            transcript_info=transcript_info,
            transcript_context_metadata=transcript_context_metadata,
            response_text=response_text,
            api_metadata=api_metadata,
            duration_seconds=duration_seconds,
        )

        return ProcessingResult(
            commercial_id=work_item.commercial_id,
            input_path=str(work_item.frame_dir),
            audio_path=str(audio_info.path),
            transcript_path=str(transcript_info.path),
            output_path=str(work_item.output_text_path),
            json_path=str(work_item.output_json_path),
            prompt_path=str(work_item.prompt_file),
            status="success",
            error=None,
            duration_seconds=round(duration_seconds, 3),
            submitted_frame_count=len(submitted_frames),
            submitted_audio=False,
            submitted_transcript_context=True,
            response_id=api_metadata.get("response_id"),
            usage=api_metadata.get("usage"),
            timestamp=utc_timestamp(),
        )

    except Exception as exc:
        duration_seconds = time.time() - start
        error = str(exc)

        try:
            write_failure_output(
                work_item=work_item,
                config=config,
                error=error,
                duration_seconds=duration_seconds,
            )
        except Exception:
            pass

        return ProcessingResult(
            commercial_id=work_item.commercial_id,
            input_path=str(work_item.frame_dir),
            audio_path=str(work_item.audio_path),
            transcript_path=str(work_item.transcript_json_path),
            output_path=str(work_item.output_text_path),
            json_path=str(work_item.output_json_path),
            prompt_path=str(work_item.prompt_file),
            status="failed",
            error=error,
            duration_seconds=round(duration_seconds, 3),
            submitted_frame_count=0,
            submitted_audio=False,
            submitted_transcript_context=False,
            response_id=None,
            usage=None,
            timestamp=utc_timestamp(),
        )


def write_run_manifest(
        manifest_file: Path,
        timestamped_manifest_file: Path,
        run_metadata: dict[str, Any],
        results: list[ProcessingResult],
        summary: dict[str, int],
) -> None:
    """Write latest and timestamped run manifests."""

    manifest_file.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_metadata": run_metadata,
        "files": [asdict(result) for result in results],
        "summary": summary,
    }

    for path in (manifest_file, timestamped_manifest_file):
        with path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        logging.info("Wrote manifest: %s", path)


def ensure_openai_available_and_configured() -> None:
    """Verify OpenAI package and API key availability."""

    try:
        import openai  # noqa: F401
    except Exception as exc:
        raise ConfigurationError(f"OpenAI Python SDK is unavailable: {exc}") from exc

    if not os.environ.get("OPENAI_API_KEY"):
        raise ConfigurationError("OPENAI_API_KEY is missing from env/.env or system environment")


def main() -> int:
    """Main orchestration entry point."""

    args = parse_args()
    log_file = args.log_file or args.output_dir / "describe_commercials_visual.log"
    manifest_file = args.manifest_file or args.output_dir / "describe_commercials_visual_manifest.json"
    current_run_id = run_id()
    timestamped_manifest_file = (
            manifest_file.parent / f"describe_commercials_visual_manifest_{current_run_id}.json"
    )
    start_time = utc_timestamp()

    try:
        load_dotenv(Path("env/.env"))
        validate_args(args)

        args.output_dir.mkdir(parents=True, exist_ok=True)
        args.prompt_output_dir.mkdir(parents=True, exist_ok=True)

        configure_logging(log_file)

        ensure_openai_available_and_configured()

        prompt_template_text = load_prompt_template(args.prompt_template)
        prompt_template_sha256 = sha256_text(prompt_template_text)
        metadata_rows = read_selected_metadata(args.metadata_tsv)

        config = RuntimeConfig(
            metadata_tsv=args.metadata_tsv,
            prompt_template=args.prompt_template,
            prompt_template_text=prompt_template_text,
            prompt_template_sha256=prompt_template_sha256,
            frames_dir=args.frames_dir,
            audio_dir=args.audio_dir,
            transcripts_dir=args.transcripts_dir,
            prompt_output_dir=args.prompt_output_dir,
            output_dir=args.output_dir,
            model=args.model,
            image_detail=args.image_detail,
            temperature=args.temperature,
            max_frames_per_request=args.max_frames_per_request,
            max_transcript_segments=args.max_transcript_segments,
            max_retries=args.max_retries,
            retry_backoff_seconds=args.retry_backoff_seconds,
            reprocess=args.reprocess,
        )

        logging.info("Starting visual description run")
        logging.info("Metadata TSV: %s", args.metadata_tsv)
        logging.info("Prompt template: %s", args.prompt_template)
        logging.info("Prompt template SHA-256: %s", prompt_template_sha256)
        logging.info("Selected frames dir: %s", args.frames_dir)
        logging.info("Audio provenance dir: %s", args.audio_dir)
        logging.info("Transcripts dir: %s", args.transcripts_dir)
        logging.info("Generated prompts dir: %s", args.prompt_output_dir)
        logging.info("Output dir: %s", args.output_dir)
        logging.info("Model: %s", args.model)
        logging.info("Image detail: %s", args.image_detail)
        logging.info("Temperature: %s", args.temperature)
        logging.info("Temperature sent to API: %s", model_supports_temperature(args.model))
        logging.info("Max transcript segments: %s", args.max_transcript_segments or "no cap")
        logging.info("Test mode: %s (limit=%s)", args.test_mode, args.test_limit)
        logging.info("Reprocess existing: %s", args.reprocess)
        logging.info("Workers: %s", args.workers)
        logging.info("OPENAI_API_KEY is configured")
        logging.info("Raw audio files will not be submitted; transcript JSON will be inserted into prompts")

        work_items, skipped_results = plan_work(
            metadata_rows=metadata_rows,
            config=config,
            start_commercial_id=args.start_commercial_id,
            test_mode=args.test_mode,
            test_limit=args.test_limit,
        )

        logging.info("Read %s selected metadata rows", len(metadata_rows))
        logging.info("Planned %s commercials for processing", len(work_items))
        logging.info("Skipped existing successful outputs: %s", len(skipped_results))

        results: list[ProcessingResult] = list(skipped_results)

        for skipped in skipped_results:
            logging.info("SKIPPED_EXISTING %s %s", skipped.commercial_id, skipped.output_path)

        if args.workers == 1:
            for work_item in work_items:
                result = process_commercial_visual(work_item, config)
                results.append(result)

                if result.status == "success":
                    logging.info(
                        "SUCCESS %s frames=%s transcript_context=%s response_id=%s",
                        result.commercial_id,
                        result.submitted_frame_count,
                        result.submitted_transcript_context,
                        result.response_id,
                    )
                else:
                    logging.error("FAILED %s %s", result.commercial_id, result.error)
        else:
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                future_to_item = {
                    executor.submit(process_commercial_visual, work_item, config): work_item
                    for work_item in work_items
                }

                for future in as_completed(future_to_item):
                    result = future.result()
                    results.append(result)

                    if result.status == "success":
                        logging.info(
                            "SUCCESS %s frames=%s transcript_context=%s response_id=%s",
                            result.commercial_id,
                            result.submitted_frame_count,
                            result.submitted_transcript_context,
                            result.response_id,
                        )
                    else:
                        logging.error("FAILED %s %s", result.commercial_id, result.error)

        attempted = len(work_items)
        succeeded = sum(1 for result in results if result.status == "success")
        failed = sum(1 for result in results if result.status == "failed")
        skipped_existing = sum(1 for result in results if result.status == "skipped_existing")
        missing_audio_failures = sum(
            1
            for result in results
            if result.status == "failed"
            and result.error is not None
            and "missing audio file" in result.error.lower()
        )
        missing_transcript_failures = sum(
            1
            for result in results
            if result.status == "failed"
            and result.error is not None
            and (
                    "missing transcript json file" in result.error.lower()
                    or "transcript json" in result.error.lower()
            )
        )
        missing_frame_failures = sum(
            1
            for result in results
            if result.status == "failed"
            and result.error is not None
            and (
                    "missing selected frame directory" in result.error.lower()
                    or "missing selected frame file" in result.error.lower()
                    or "no supported selected frame files" in result.error.lower()
                    or "no usable selected frames" in result.error.lower()
            )
        )

        end_time = utc_timestamp()

        run_metadata = {
            "run_id": current_run_id,
            "tool_name": "describe_commercials_visual",
            "version": "v5_prompt_selected_frames_transcript_context",
            "start_time": start_time,
            "end_time": end_time,
            "test_mode": args.test_mode,
            "test_limit": args.test_limit,
            "reprocess": args.reprocess,
            "workers": args.workers,
            "strategy": {
                "primary_evidence": "selected_frames",
                "supporting_context": "timestamped_whisper_json_transcript_inserted_into_prompt",
                "audio_file_role": "provenance_only_not_submitted",
            },
            "config": {
                "metadata_tsv": str(args.metadata_tsv),
                "prompt_template": str(args.prompt_template),
                "prompt_template_sha256": prompt_template_sha256,
                "frames_dir": str(args.frames_dir),
                "audio_dir": str(args.audio_dir),
                "transcripts_dir": str(args.transcripts_dir),
                "prompt_output_dir": str(args.prompt_output_dir),
                "output_dir": str(args.output_dir),
                "model": args.model,
                "image_detail": args.image_detail,
                "temperature": args.temperature,
                "temperature_sent_to_api": model_supports_temperature(args.model),
                "max_frames_per_request": args.max_frames_per_request,
                "max_transcript_segments": args.max_transcript_segments,
                "max_retries": args.max_retries,
                "retry_backoff_seconds": args.retry_backoff_seconds,
            },
        }

        summary = {
            "metadata_rows": len(metadata_rows),
            "planned": len(work_items),
            "skipped_existing": skipped_existing,
            "attempted": attempted,
            "succeeded": succeeded,
            "failed": failed,
            "missing_audio_failures": missing_audio_failures,
            "missing_transcript_failures": missing_transcript_failures,
            "missing_frame_failures": missing_frame_failures,
        }

        write_run_manifest(
            manifest_file=manifest_file,
            timestamped_manifest_file=timestamped_manifest_file,
            run_metadata=run_metadata,
            results=results,
            summary=summary,
        )

        logging.info(
            "Completed visual description run: attempted=%s succeeded=%s failed=%s skipped_existing=%s",
            attempted,
            succeeded,
            failed,
            skipped_existing,
        )

        return 1 if failed else 0

    except KeyboardInterrupt:
        try:
            logging.error("Interrupted by user")
        except Exception:
            pass
        return 130

    except ConfigurationError as exc:
        try:
            configure_logging(log_file)
            logging.error("Configuration error: %s", exc)
        except Exception:
            print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    except Exception as exc:
        try:
            configure_logging(log_file)
            logging.exception("Fatal error: %s", exc)
        except Exception:
            print(f"Fatal error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())