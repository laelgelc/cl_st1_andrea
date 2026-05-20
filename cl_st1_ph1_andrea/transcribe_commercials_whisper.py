#!/usr/bin/env python3
"""
Transcribe television commercial audio files with Whisper Large v3.

This script reads commercial metadata from an NDJSON file, selects records where
"Download Success" is true, and transcribes one WAV audio file per eligible
commercial using Whisper Large v3 through the faster-whisper backend.

Source audio files are expected in the input directory as "<Commercial ID>.wav".
Transcript outputs are written to the output directory as "<Commercial ID>.txt"
and "<Commercial ID>.json".

The plain-text transcript is intended for corpus linguistic analysis. The JSON
transcript preserves segment timestamps, model configuration, and source
metadata for reproducibility.

By default, the script runs in test mode and attempts only the first 5 planned
commercials. Existing transcript files are skipped unless --reprocess is
provided, making the script safe to re-run.

The recommended deployment environment is an x86_64 EC2 GPU instance using a
Python 3.11 environment with faster-whisper installed.

Example:
    python transcribe_commercials_whisper.py

Full run:
    python transcribe_commercials_whisper.py --no-test-mode

Full run from a specific commercial:
    python transcribe_commercials_whisper.py --no-test-mode --start-commercial-id tv_com_1950_25

The script writes an append-only log file and JSON manifests describing
run-level metadata and per-commercial transcription status.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


TOOL_NAME = "transcribe_commercials_whisper.py"
TOOL_VERSION = "v1"

DEFAULT_METADATA_PATH = "corpus/00_sources/tv_commercials.ndjson"
DEFAULT_INPUT_DIR = "corpus/03_audio"
DEFAULT_OUTPUT_DIR = "corpus/04_transcripts"
DEFAULT_LOG_FILE = "corpus/04_transcripts/transcribe_commercials_whisper.log"
DEFAULT_MANIFEST_FILE = "corpus/04_transcripts/transcribe_commercials_whisper_manifest.json"

DEFAULT_MODEL_NAME = "large-v3"
DEFAULT_BACKEND = "faster-whisper"
DEFAULT_DEVICE = "cuda"
DEFAULT_COMPUTE_TYPE = "float16"
DEFAULT_LANGUAGE = "en"
DEFAULT_TASK = "transcribe"
DEFAULT_BEAM_SIZE = 5
DEFAULT_VAD_FILTER = True

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 5
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 5

INPUT_AUDIO_EXTENSION = ".wav"
OUTPUT_TEXT_EXTENSION = ".txt"
OUTPUT_JSON_EXTENSION = ".json"

EXIT_SUCCESS = 0
EXIT_PARTIAL_FAILURE = 1
EXIT_CONFIGURATION_ERROR = 2
EXIT_INTERRUPTED = 130


class ConfigurationError(Exception):
    """Raised when command-line arguments or runtime configuration are invalid."""


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime.

    Returns:
        Current UTC datetime.

    I/O:
        This function performs no file or process I/O.

    Raises:
        No expected exceptions.
    """
    return datetime.now(UTC)


def utc_timestamp() -> str:
    """Return the current UTC timestamp in manifest-friendly format.

    Returns:
        Timestamp string formatted as YYYY-MM-DDTHH:MM:SSZ.

    I/O:
        This function performs no file or process I/O.

    Raises:
        No expected exceptions.
    """
    return utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def make_run_id() -> str:
    """Return a compact UTC run identifier.

    Returns:
        Run ID formatted as YYYYMMDDTHHMMSSZ.

    I/O:
        This function performs no file or process I/O.

    Raises:
        No expected exceptions.
    """
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def stringify_field(value: Any) -> str:
    """Convert a metadata field to a clean string.

    Args:
        value: Metadata value from a JSON record.

    Returns:
        A stripped string, or an empty string for None.

    I/O:
        This function performs no file or process I/O.

    Raises:
        No expected exceptions.
    """
    if value is None:
        return ""
    return str(value).strip()


def is_download_success(value: Any) -> bool:
    """Interpret the metadata Download Success field robustly.

    Args:
        value: Raw value of the "Download Success" field.

    Returns:
        True for boolean true, numeric 1, or true-like strings. False otherwise.

    I/O:
        This function performs no file or process I/O.

    Raises:
        No expected exceptions.
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, int | float):
        return value == 1

    if isinstance(value, str):
        return value.strip().lower() in {"true", "1"}

    return False


def shorten_error(text: str, max_chars: int = 1000) -> str:
    """Shorten an error message for logging and manifest storage.

    Args:
        text: Raw error text.
        max_chars: Maximum number of characters to return.

    Returns:
        A compact single-line error message.

    I/O:
        This function performs no file or process I/O.

    Raises:
        No expected exceptions.
    """
    clean_text = " ".join(str(text).strip().split())
    if len(clean_text) <= max_chars:
        return clean_text
    return clean_text[: max_chars - 3] + "..."


def clean_transcript_text(segment_texts: list[str]) -> str:
    """Create a clean transcript text from ordered segment texts.

    Args:
        segment_texts: Segment text strings returned by Whisper.

    Returns:
        Transcript text with repeated whitespace collapsed.

    I/O:
        This function performs no file or process I/O.

    Raises:
        No expected exceptions.
    """
    non_empty_segments = [text.strip() for text in segment_texts if text and text.strip()]
    return " ".join(" ".join(non_empty_segments).split())


def commercial_metadata(record: dict[str, Any]) -> dict[str, Any]:
    """Extract traceability metadata for manifest and transcript JSON outputs.

    Args:
        record: Eligible commercial metadata dictionary.

    Returns:
        Simplified metadata dictionary.

    I/O:
        This function performs no file or process I/O.

    Raises:
        No expected exceptions.
    """
    return {
        "title": record.get("title"),
        "decade": record.get("decade"),
        "sequence": record.get("sequence"),
        "category": record.get("category"),
        "video_id": record.get("video_id"),
        "url": record.get("url"),
        "source_start": record.get("source_start"),
        "source_end": record.get("source_end"),
    }


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the Whisper transcription programme.

    Returns:
        Parsed command-line arguments.

    I/O:
        Reads command-line arguments from sys.argv.

    Raises:
        SystemExit: Raised by argparse for invalid CLI syntax.
    """
    parser = argparse.ArgumentParser(
        description="Transcribe Whisper-ready commercial audio files with faster-whisper."
    )

    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path(DEFAULT_METADATA_PATH),
        help=f"Path to metadata NDJSON file. Default: {DEFAULT_METADATA_PATH}",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path(DEFAULT_INPUT_DIR),
        help=f"Directory containing source .wav audio files. Default: {DEFAULT_INPUT_DIR}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(DEFAULT_OUTPUT_DIR),
        help=f"Directory for transcript outputs. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--model-name",
        default=DEFAULT_MODEL_NAME,
        help=f"Whisper model name. Default: {DEFAULT_MODEL_NAME}",
    )
    parser.add_argument(
        "--device",
        default=DEFAULT_DEVICE,
        choices=["cuda", "cpu", "auto"],
        help=f"Device for transcription. Default: {DEFAULT_DEVICE}",
    )
    parser.add_argument(
        "--compute-type",
        default=DEFAULT_COMPUTE_TYPE,
        help=f"faster-whisper compute type. Default: {DEFAULT_COMPUTE_TYPE}",
    )
    parser.add_argument(
        "--language",
        default=DEFAULT_LANGUAGE,
        help=f"Language code, or 'auto' for detection. Default: {DEFAULT_LANGUAGE}",
    )
    parser.add_argument(
        "--task",
        default=DEFAULT_TASK,
        choices=["transcribe", "translate"],
        help=f"Whisper task. Default: {DEFAULT_TASK}",
    )
    parser.add_argument(
        "--beam-size",
        type=int,
        default=DEFAULT_BEAM_SIZE,
        help=f"Beam size for decoding. Default: {DEFAULT_BEAM_SIZE}",
    )
    parser.add_argument(
        "--vad-filter",
        dest="vad_filter",
        action="store_true",
        help="Enable voice activity detection filtering.",
    )
    parser.add_argument(
        "--no-vad-filter",
        dest="vad_filter",
        action="store_false",
        help="Disable voice activity detection filtering.",
    )
    parser.set_defaults(vad_filter=DEFAULT_VAD_FILTER)

    parser.add_argument(
        "--test-mode",
        dest="test_mode",
        action="store_true",
        help="Enable test mode.",
    )
    parser.add_argument(
        "--no-test-mode",
        dest="test_mode",
        action="store_false",
        help="Disable test mode and process all planned transcriptions.",
    )
    parser.set_defaults(test_mode=DEFAULT_TEST_MODE)

    parser.add_argument(
        "--test-limit",
        type=int,
        default=DEFAULT_TEST_LIMIT,
        help=f"Maximum planned items to attempt in test mode. Default: {DEFAULT_TEST_LIMIT}",
    )
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="Re-transcribe even when complete transcript outputs already exist.",
    )
    parser.add_argument(
        "--start-commercial-id",
        default=None,
        help="Optional Commercial ID from which to start planning.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path(DEFAULT_LOG_FILE),
        help=f"Append-only log file path. Default: {DEFAULT_LOG_FILE}",
    )
    parser.add_argument(
        "--manifest-file",
        type=Path,
        default=Path(DEFAULT_MANIFEST_FILE),
        help=f"Latest manifest JSON path. Default: {DEFAULT_MANIFEST_FILE}",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Number of workers. Current implementation requires 1. Default: {DEFAULT_WORKERS}",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Recorded timeout in seconds for each transcription. Default: {DEFAULT_TIMEOUT_SECONDS}",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help=f"Retry attempts after a failed transcription. Default: {DEFAULT_MAX_RETRIES}",
    )

    return parser.parse_args()


def setup_logging(log_file: Path) -> None:
    """Configure append-only file logging and console logging.

    Args:
        log_file: Path to the append-only log file.

    Returns:
        None.

    I/O:
        Creates the log file parent directory if needed and opens the log file
        in append mode through the logging module.

    Raises:
        ConfigurationError: If the log directory cannot be created or logging
        cannot be configured.
    """
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(f"Could not create log directory {log_file.parent}: {exc}") from exc

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-5s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"Could not open log file {log_file}: {exc}") from exc

    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments and transcription environment before processing.

    Args:
        args: Parsed command-line arguments.

    Returns:
        None.

    I/O:
        Checks filesystem paths, creates output/manifest/log parent directories,
        and checks Python dependency availability.

    Raises:
        ConfigurationError: If any argument, path, or dependency is invalid.
    """
    if not args.metadata.exists():
        raise ConfigurationError(f"Metadata file does not exist: {args.metadata}")

    if not args.metadata.is_file():
        raise ConfigurationError(f"Metadata path is not a file: {args.metadata}")

    if not args.input_dir.exists():
        raise ConfigurationError(f"Input directory does not exist: {args.input_dir}")

    if not args.input_dir.is_dir():
        raise ConfigurationError(f"Input path is not a directory: {args.input_dir}")

    if not stringify_field(args.model_name):
        raise ConfigurationError("--model-name must not be empty.")

    if not stringify_field(args.device):
        raise ConfigurationError("--device must not be empty.")

    if not stringify_field(args.compute_type):
        raise ConfigurationError("--compute-type must not be empty.")

    if not stringify_field(args.language):
        raise ConfigurationError("--language must not be empty.")

    if args.task not in {"transcribe", "translate"}:
        raise ConfigurationError("--task must be either 'transcribe' or 'translate'.")

    if args.beam_size <= 0:
        raise ConfigurationError("--beam-size must be greater than zero.")

    if args.test_limit <= 0:
        raise ConfigurationError("--test-limit must be greater than zero.")

    if args.workers <= 0:
        raise ConfigurationError("--workers must be greater than zero.")

    if args.workers != 1:
        raise ConfigurationError("Current sequential implementation requires --workers 1.")

    if args.timeout <= 0:
        raise ConfigurationError("--timeout must be greater than zero.")

    if args.max_retries < 0:
        raise ConfigurationError("--max-retries must be zero or greater.")

    if args.start_commercial_id is not None and not args.start_commercial_id.strip():
        raise ConfigurationError("--start-commercial-id must not be empty when provided.")

    if importlib.util.find_spec("faster_whisper") is None:
        raise ConfigurationError(
            "The faster_whisper package is not installed. Install it in the Whisper environment."
        )

    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(f"Could not create required output directories: {exc}") from exc


def load_commercial_metadata(metadata_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int]:
    """Load and validate eligible commercial metadata from an NDJSON file.

    Args:
        metadata_path: Path to the NDJSON metadata file.

    Returns:
        A tuple containing:
        - eligible commercial records where Download Success is true;
        - invalid eligible metadata records;
        - total number of non-empty metadata records read;
        - number of rows ignored because Download Success was not true.

    I/O:
        Reads the metadata file from disk.

    Raises:
        ConfigurationError: If the file cannot be read or contains invalid JSON.
    """
    eligible_commercials: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    total_records = 0
    ignored_download_failures = 0

    try:
        with metadata_path.open("r", encoding="utf-8") as file_obj:
            for line_number, line in enumerate(file_obj, start=1):
                raw_line = line.strip()
                if not raw_line:
                    continue

                total_records += 1

                try:
                    record = json.loads(raw_line)
                except json.JSONDecodeError as exc:
                    raise ConfigurationError(
                        f"Invalid JSON in metadata file at line {line_number}: {exc}"
                    ) from exc

                if not is_download_success(record.get("Download Success")):
                    ignored_download_failures += 1
                    continue

                commercial_id = stringify_field(record.get("Commercial ID"))

                if not commercial_id:
                    invalid_records.append(
                        {
                            "line_number": line_number,
                            "commercial_id": None,
                            "status": "failed_metadata",
                            "error": "Missing required field(s): Commercial ID",
                            "record": record,
                        }
                    )
                    continue

                eligible_commercials.append(
                    {
                        "line_number": line_number,
                        "commercial_id": commercial_id,
                        "title": record.get("Title"),
                        "decade": record.get("Decade"),
                        "sequence": record.get("Sequence"),
                        "category": record.get("Category"),
                        "video_id": record.get("Video ID"),
                        "url": record.get("URL"),
                        "source_start": record.get("Start"),
                        "source_end": record.get("End"),
                        "record": record,
                    }
                )
    except OSError as exc:
        raise ConfigurationError(f"Could not read metadata file {metadata_path}: {exc}") from exc

    return eligible_commercials, invalid_records, total_records, ignored_download_failures


def apply_start_commercial_filter(
        commercials: list[dict[str, Any]],
        start_commercial_id: str | None,
) -> list[dict[str, Any]]:
    """Apply optional start-commercial filtering while preserving metadata order.

    Args:
        commercials: Eligible commercial metadata records.
        start_commercial_id: Optional Commercial ID from which planning should start.

    Returns:
        Filtered commercial list.

    I/O:
        This function performs no file or process I/O.

    Raises:
        ConfigurationError: If start_commercial_id is provided but not found.
    """
    if start_commercial_id is None:
        return commercials

    clean_start_id = start_commercial_id.strip()

    for index, commercial in enumerate(commercials):
        if commercial["commercial_id"] == clean_start_id:
            return commercials[index:]

    raise ConfigurationError(
        f"--start-commercial-id {clean_start_id!r} was not found among eligible metadata rows."
    )


def make_planning_record(
        commercial: dict[str, Any],
        input_path: Path,
        text_output_path: Path,
        json_output_path: Path,
        status: str,
        error: str | None = None,
) -> dict[str, Any]:
    """Create a structured planning/result record for a commercial.

    Args:
        commercial: Commercial metadata dictionary.
        input_path: Expected source audio path.
        text_output_path: Expected plain-text transcript path.
        json_output_path: Expected JSON transcript path.
        status: Item status.
        error: Optional error message.

    Returns:
        Manifest-ready planning record.

    I/O:
        This function performs no file or process I/O.

    Raises:
        No expected exceptions.
    """
    return {
        "commercial_id": commercial["commercial_id"],
        "input_path": str(input_path),
        "text_output_path": str(text_output_path),
        "json_output_path": str(json_output_path),
        "status": status,
        "error": error,
        "return_code": None,
        "retries": 0,
        "duration_seconds": None,
        "start_time": None,
        "end_time": None,
        "transcript_characters": None,
        "segment_count": None,
        "detected_language": None,
        "language_probability": None,
        "metadata": commercial_metadata(commercial),
    }


def plan_transcriptions(
        commercials: list[dict[str, Any]],
        input_dir: Path,
        output_dir: Path,
        test_mode: bool,
        test_limit: int,
        reprocess: bool,
        start_commercial_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Create planned, skipped, and missing-input transcription records.

    Args:
        commercials: Eligible commercial metadata records.
        input_dir: Directory containing source audio files.
        output_dir: Directory where transcript files will be written.
        test_mode: Whether to limit planned transcription attempts.
        test_limit: Maximum number of attempted items in test mode.
        reprocess: Whether to overwrite existing transcript files.
        start_commercial_id: Optional Commercial ID from which to start planning.

    Returns:
        A tuple containing:
        - planned records to be attempted with Whisper;
        - records skipped because complete transcript outputs already exist;
        - records whose input audio is missing.

    I/O:
        Checks for input and output file existence.

    Raises:
        ConfigurationError: If start_commercial_id is provided but not found.
    """
    filtered_commercials = apply_start_commercial_filter(commercials, start_commercial_id)

    planned: list[dict[str, Any]] = []
    skipped_existing: list[dict[str, Any]] = []
    missing_input: list[dict[str, Any]] = []

    for commercial in filtered_commercials:
        commercial_id = commercial["commercial_id"]
        input_path = input_dir / f"{commercial_id}{INPUT_AUDIO_EXTENSION}"
        text_output_path = output_dir / f"{commercial_id}{OUTPUT_TEXT_EXTENSION}"
        json_output_path = output_dir / f"{commercial_id}{OUTPUT_JSON_EXTENSION}"

        if not input_path.exists():
            missing_input.append(
                make_planning_record(
                    commercial=commercial,
                    input_path=input_path,
                    text_output_path=text_output_path,
                    json_output_path=json_output_path,
                    status="missing_input",
                    error=f"Missing input audio: {input_path}",
                )
            )
            continue

        complete_outputs_exist = text_output_path.exists() and json_output_path.exists()
        if complete_outputs_exist and not reprocess:
            skipped_existing.append(
                make_planning_record(
                    commercial=commercial,
                    input_path=input_path,
                    text_output_path=text_output_path,
                    json_output_path=json_output_path,
                    status="skipped_existing",
                )
            )
            continue

        planned.append(
            make_planning_record(
                commercial=commercial,
                input_path=input_path,
                text_output_path=text_output_path,
                json_output_path=json_output_path,
                status="planned",
            )
        )

        if test_mode and len(planned) >= test_limit:
            break

    return planned, skipped_existing, missing_input


def load_whisper_model(model_name: str, device: str, compute_type: str) -> Any:
    """Load the faster-whisper model once for batch transcription.

    Args:
        model_name: Whisper model name.
        device: Device setting, such as "cuda", "cpu", or "auto".
        compute_type: faster-whisper compute type.

    Returns:
        Loaded WhisperModel instance.

    I/O:
        Imports faster_whisper and loads model files, potentially downloading
        model weights through the backend if not cached.

    Raises:
        ConfigurationError: If the backend cannot be imported or the model
        cannot be loaded.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ConfigurationError("Could not import faster_whisper.") from exc

    try:
        logging.info(
            "Loading Whisper model %s device=%s compute_type=%s",
            model_name,
            device,
            compute_type,
        )
        model = WhisperModel(model_name, device=device, compute_type=compute_type)
    except Exception as exc:
        raise ConfigurationError(f"Could not load Whisper model {model_name}: {exc}") from exc

    logging.info("Whisper model loaded successfully")
    return model


def write_transcript_outputs(
        text: str,
        transcript_json: dict[str, Any],
        text_output_path: Path,
        json_output_path: Path,
) -> None:
    """Write text and JSON transcript outputs for one commercial.

    Args:
        text: Clean transcript text.
        transcript_json: Detailed transcript dictionary.
        text_output_path: Destination `.txt` path.
        json_output_path: Destination `.json` path.

    Returns:
        None.

    I/O:
        Writes UTF-8 text and JSON files to disk.

    Raises:
        OSError: If output files cannot be written.
    """
    text_output_path.parent.mkdir(parents=True, exist_ok=True)
    json_output_path.parent.mkdir(parents=True, exist_ok=True)

    with text_output_path.open("w", encoding="utf-8") as file_obj:
        file_obj.write(text)
        file_obj.write("\n")

    with json_output_path.open("w", encoding="utf-8") as file_obj:
        json.dump(transcript_json, file_obj, ensure_ascii=False, indent=2)
        file_obj.write("\n")


def collect_segments(raw_segments: Any) -> list[dict[str, Any]]:
    """Convert faster-whisper segment objects into simple dictionaries.

    Args:
        raw_segments: Iterable of segment objects returned by model.transcribe.

    Returns:
        List of segment dictionaries with id, start, end, and text.

    I/O:
        Iterating over raw_segments may trigger backend transcription computation.

    Raises:
        Exceptions from the backend may propagate to the caller.
    """
    segments: list[dict[str, Any]] = []

    for index, segment in enumerate(raw_segments, start=1):
        segment_id = getattr(segment, "id", index)
        text = stringify_field(getattr(segment, "text", ""))

        segments.append(
            {
                "id": segment_id if segment_id is not None else index,
                "start": float(getattr(segment, "start", 0.0) or 0.0),
                "end": float(getattr(segment, "end", 0.0) or 0.0),
                "text": text,
            }
        )

    return segments


def build_transcription_kwargs(model_config: dict[str, Any]) -> dict[str, Any]:
    """Build keyword arguments for the faster-whisper transcribe call.

    Args:
        model_config: Model and decoding configuration.

    Returns:
        Keyword argument dictionary.

    I/O:
        This function performs no file or process I/O.

    Raises:
        No expected exceptions.
    """
    kwargs: dict[str, Any] = {
        "task": model_config["task"],
        "beam_size": model_config["beam_size"],
        "vad_filter": model_config["vad_filter"],
    }

    language = model_config.get("language")
    if language and language != "auto":
        kwargs["language"] = language

    return kwargs


def transcribe_one_commercial(
        model: Any,
        commercial: dict[str, Any],
        input_path: Path,
        text_output_path: Path,
        json_output_path: Path,
        model_config: dict[str, Any],
        max_retries: int,
        retry_delay: int,
) -> dict[str, Any]:
    """Transcribe one commercial audio file and return a structured result.

    Args:
        model: Loaded faster-whisper model.
        commercial: Commercial metadata dictionary.
        input_path: Source audio path.
        text_output_path: Destination plain-text transcript path.
        json_output_path: Destination detailed JSON transcript path.
        model_config: Model and transcription configuration.
        max_retries: Number of retries after the first failed attempt.
        retry_delay: Delay between retries in seconds.

    Returns:
        Manifest-ready result dictionary.

    I/O:
        Runs model transcription and writes transcript outputs.

    Raises:
        No expected exceptions are propagated for per-item failures. They are
        captured in the returned result.
    """
    commercial_id = commercial["commercial_id"]
    start_timestamp = utc_timestamp()
    start_monotonic = time.monotonic()

    result = make_planning_record(
        commercial=commercial,
        input_path=input_path,
        text_output_path=text_output_path,
        json_output_path=json_output_path,
        status="failed",
    )
    result["start_time"] = start_timestamp

    total_attempts = max_retries + 1
    traceback_text: str | None = None

    for attempt_number in range(1, total_attempts + 1):
        if attempt_number > 1:
            result["retries"] = attempt_number - 1
            logging.info(
                "RETRY %s attempt=%s/%s",
                commercial_id,
                attempt_number,
                total_attempts,
            )
            time.sleep(retry_delay)

        try:
            transcription_kwargs = build_transcription_kwargs(model_config)
            raw_segments, info = model.transcribe(str(input_path), **transcription_kwargs)

            segments = collect_segments(raw_segments)
            segment_texts = [segment["text"] for segment in segments]
            transcript_text = clean_transcript_text(segment_texts)

            detected_language = getattr(info, "language", None)
            language_probability = getattr(info, "language_probability", None)
            audio_duration = getattr(info, "duration", None)

            transcript_json = {
                "commercial_id": commercial_id,
                "input_path": str(input_path),
                "text_output_path": str(text_output_path),
                "json_output_path": str(json_output_path),
                "model": model_config,
                "transcription": {
                    "text": transcript_text,
                    "detected_language": detected_language,
                    "language_probability": language_probability,
                    "duration_seconds": audio_duration,
                    "segments": segments,
                },
                "metadata": commercial_metadata(commercial),
            }

            write_transcript_outputs(
                text=transcript_text,
                transcript_json=transcript_json,
                text_output_path=text_output_path,
                json_output_path=json_output_path,
            )

            result["status"] = "success"
            result["error"] = None
            result["transcript_characters"] = len(transcript_text)
            result["segment_count"] = len(segments)
            result["detected_language"] = detected_language
            result["language_probability"] = language_probability

            if not transcript_text:
                logging.warning("Empty transcript for %s", commercial_id)

            break

        except Exception as exc:
            traceback_text = traceback.format_exc()
            result["error"] = shorten_error(str(exc) or traceback_text)
            logging.error(
                "FAILED %s error=%s",
                commercial_id,
                result["error"],
            )

    result["end_time"] = utc_timestamp()
    result["duration_seconds"] = round(time.monotonic() - start_monotonic, 3)

    if result["status"] == "success":
        logging.info("SUCCESS %s -> %s", commercial_id, text_output_path)
    elif traceback_text:
        result["metadata"]["traceback"] = shorten_error(traceback_text, max_chars=3000)

    return result


def make_invalid_manifest_records(invalid_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert invalid metadata records into manifest item records.

    Args:
        invalid_records: Invalid metadata records from metadata loading.

    Returns:
        Manifest-ready invalid records.

    I/O:
        This function performs no file or process I/O.

    Raises:
        No expected exceptions.
    """
    manifest_records: list[dict[str, Any]] = []

    for record in invalid_records:
        manifest_records.append(
            {
                "commercial_id": record.get("commercial_id"),
                "input_path": None,
                "text_output_path": None,
                "json_output_path": None,
                "status": "failed_metadata",
                "error": record.get("error"),
                "return_code": None,
                "retries": 0,
                "duration_seconds": None,
                "start_time": None,
                "end_time": None,
                "transcript_characters": None,
                "segment_count": None,
                "detected_language": None,
                "language_probability": None,
                "metadata": {
                    "line_number": record.get("line_number"),
                    "record": record.get("record"),
                },
            }
        )

    return manifest_records


def build_manifest(
        args: argparse.Namespace,
        run_id: str,
        start_time: str,
        end_time: str,
        total_records: int,
        eligible_count: int,
        ignored_download_failures: int,
        invalid_records: list[dict[str, Any]],
        planned_count: int,
        attempted_results: list[dict[str, Any]],
        skipped_existing: list[dict[str, Any]],
        missing_input: list[dict[str, Any]],
        interrupted: bool,
) -> dict[str, Any]:
    """Build the complete run manifest.

    Args:
        args: Parsed command-line arguments.
        run_id: UTC run identifier.
        start_time: Run start timestamp.
        end_time: Run end timestamp.
        total_records: Total metadata records read.
        eligible_count: Number of valid eligible rows.
        ignored_download_failures: Rows ignored because Download Success was not true.
        invalid_records: Invalid eligible metadata rows.
        planned_count: Number of Whisper transcription records planned.
        attempted_results: Results for attempted transcriptions.
        skipped_existing: Records skipped because transcript outputs already existed.
        missing_input: Records whose input audio was missing.
        interrupted: Whether the run was interrupted.

    Returns:
        Complete manifest dictionary.

    I/O:
        This function performs no file or process I/O.

    Raises:
        No expected exceptions.
    """
    succeeded = sum(1 for item in attempted_results if item["status"] == "success")
    failed = sum(1 for item in attempted_results if item["status"] == "failed")

    commercials = (
            make_invalid_manifest_records(invalid_records)
            + missing_input
            + skipped_existing
            + attempted_results
    )

    return {
        "run_metadata": {
            "run_id": run_id,
            "tool_name": TOOL_NAME,
            "tool_version": TOOL_VERSION,
            "start_time": start_time,
            "end_time": end_time,
            "test_mode": args.test_mode,
            "test_limit": args.test_limit,
            "reprocess": args.reprocess,
            "workers": args.workers,
            "metadata_path": str(args.metadata),
            "input_dir": str(args.input_dir),
            "output_dir": str(args.output_dir),
            "log_file": str(args.log_file),
            "manifest_file": str(args.manifest_file),
            "config": {
                "backend": DEFAULT_BACKEND,
                "model_name": args.model_name,
                "device": args.device,
                "compute_type": args.compute_type,
                "language": args.language,
                "task": args.task,
                "beam_size": args.beam_size,
                "vad_filter": args.vad_filter,
                "timeout_seconds": args.timeout,
                "max_retries": args.max_retries,
                "retry_delay_seconds": DEFAULT_RETRY_DELAY_SECONDS,
                "start_commercial_id": args.start_commercial_id,
            },
            "summary": {
                "metadata_records": total_records,
                "eligible_download_success": eligible_count,
                "ignored_download_not_success": ignored_download_failures,
                "invalid_metadata": len(invalid_records),
                "planned": planned_count,
                "attempted": len(attempted_results),
                "succeeded": succeeded,
                "failed": failed,
                "missing_input": len(missing_input),
                "skipped_existing": len(skipped_existing),
            },
            "interrupted": interrupted,
        },
        "commercials": commercials,
        "invalid_records": invalid_records,
    }


def write_manifests(manifest: dict[str, Any], manifest_file: Path, run_id: str) -> tuple[Path, Path]:
    """Write latest and per-run manifest files.

    Args:
        manifest: Complete manifest dictionary.
        manifest_file: Path to the latest manifest file.
        run_id: Run identifier used in the timestamped manifest filename.

    Returns:
        A tuple containing:
        - latest manifest path;
        - timestamped per-run manifest path.

    I/O:
        Writes two JSON files to disk.

    Raises:
        ConfigurationError: If manifest files cannot be written.
    """
    per_run_manifest_file = manifest_file.with_name(
        f"{manifest_file.stem}_{run_id}{manifest_file.suffix}"
    )

    try:
        manifest_file.parent.mkdir(parents=True, exist_ok=True)

        with manifest_file.open("w", encoding="utf-8") as file_obj:
            json.dump(manifest, file_obj, ensure_ascii=False, indent=2)
            file_obj.write("\n")

        with per_run_manifest_file.open("w", encoding="utf-8") as file_obj:
            json.dump(manifest, file_obj, ensure_ascii=False, indent=2)
            file_obj.write("\n")
    except OSError as exc:
        raise ConfigurationError(f"Could not write manifest files: {exc}") from exc

    return manifest_file, per_run_manifest_file


def run_workflow(args: argparse.Namespace) -> int:
    """Run the main workflow after CLI parsing.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Process exit code.

    I/O:
        Reads metadata, checks input/output files, loads Whisper, transcribes
        audio, writes transcript files, writes logs, and writes manifest files.

    Raises:
        ConfigurationError: For validation and model-loading errors that should
        stop the run.
    """
    run_id = make_run_id()
    start_time = utc_timestamp()
    interrupted = False

    setup_logging(args.log_file)

    logging.info("Starting %s run_id=%s", TOOL_NAME, run_id)
    logging.info("Metadata path: %s", args.metadata)
    logging.info("Input directory: %s", args.input_dir)
    logging.info("Output directory: %s", args.output_dir)
    logging.info(
        "Model: backend=%s model=%s device=%s compute_type=%s",
        DEFAULT_BACKEND,
        args.model_name,
        args.device,
        args.compute_type,
    )
    logging.info(
        "Transcription: language=%s task=%s beam_size=%s vad_filter=%s",
        args.language,
        args.task,
        args.beam_size,
        str(args.vad_filter).lower(),
    )
    logging.info("Test mode: %s; test_limit=%s", str(args.test_mode).lower(), args.test_limit)
    logging.info("Reprocess: %s", str(args.reprocess).lower())
    logging.info("Start commercial ID: %s", args.start_commercial_id)

    validate_args(args)
    logging.info("Dependency available: faster_whisper")

    eligible_commercials: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    total_records = 0
    ignored_download_failures = 0
    planned: list[dict[str, Any]] = []
    skipped_existing: list[dict[str, Any]] = []
    missing_input: list[dict[str, Any]] = []
    attempted_results: list[dict[str, Any]] = []

    try:
        (
            eligible_commercials,
            invalid_records,
            total_records,
            ignored_download_failures,
        ) = load_commercial_metadata(args.metadata)

        logging.info(
            "Found %s metadata records; %s eligible for transcription; %s ignored; %s invalid",
            total_records,
            len(eligible_commercials),
            ignored_download_failures,
            len(invalid_records),
        )

        planned, skipped_existing, missing_input = plan_transcriptions(
            commercials=eligible_commercials,
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            test_mode=args.test_mode,
            test_limit=args.test_limit,
            reprocess=args.reprocess,
            start_commercial_id=args.start_commercial_id,
        )

        logging.info("Planned transcriptions: %s", len(planned))

        for item in skipped_existing:
            logging.info(
                "SKIPPED_EXISTING %s -> %s and %s",
                item["commercial_id"],
                item["text_output_path"],
                item["json_output_path"],
            )

        for item in missing_input:
            logging.error(
                "MISSING_INPUT %s expected=%s",
                item["commercial_id"],
                item["input_path"],
            )

        model = None
        if planned:
            model = load_whisper_model(
                model_name=args.model_name,
                device=args.device,
                compute_type=args.compute_type,
            )
        else:
            logging.info("No transcriptions planned; model loading skipped.")

        model_config = {
            "backend": DEFAULT_BACKEND,
            "model_name": args.model_name,
            "device": args.device,
            "compute_type": args.compute_type,
            "language": args.language,
            "task": args.task,
            "beam_size": args.beam_size,
            "vad_filter": args.vad_filter,
        }

        for item in planned:
            commercial_id = item["commercial_id"]
            commercial = next(
                record for record in eligible_commercials if record["commercial_id"] == commercial_id
            )

            result = transcribe_one_commercial(
                model=model,
                commercial=commercial,
                input_path=Path(item["input_path"]),
                text_output_path=Path(item["text_output_path"]),
                json_output_path=Path(item["json_output_path"]),
                model_config=model_config,
                max_retries=args.max_retries,
                retry_delay=DEFAULT_RETRY_DELAY_SECONDS,
            )
            attempted_results.append(result)

    except KeyboardInterrupt:
        interrupted = True
        logging.error("Interrupted by user.")
    finally:
        end_time = utc_timestamp()
        manifest = build_manifest(
            args=args,
            run_id=run_id,
            start_time=start_time,
            end_time=end_time,
            total_records=total_records,
            eligible_count=len(eligible_commercials),
            ignored_download_failures=ignored_download_failures,
            invalid_records=invalid_records,
            planned_count=len(planned),
            attempted_results=attempted_results,
            skipped_existing=skipped_existing,
            missing_input=missing_input,
            interrupted=interrupted,
        )

        latest_manifest, per_run_manifest = write_manifests(
            manifest=manifest,
            manifest_file=args.manifest_file,
            run_id=run_id,
        )

        logging.info("Wrote latest manifest: %s", latest_manifest)
        logging.info("Wrote per-run manifest: %s", per_run_manifest)

        summary = manifest["run_metadata"]["summary"]
        logging.info(
            "Finished run: succeeded=%s failed=%s skipped_existing=%s missing_input=%s invalid_metadata=%s",
            summary["succeeded"],
            summary["failed"],
            summary["skipped_existing"],
            summary["missing_input"],
            summary["invalid_metadata"],
        )

    if interrupted:
        return EXIT_INTERRUPTED

    failed_count = sum(1 for item in attempted_results if item["status"] == "failed")
    if failed_count or missing_input or invalid_records:
        return EXIT_PARTIAL_FAILURE

    return EXIT_SUCCESS


def main() -> int:
    """Run the batch Whisper transcription workflow and return an exit code.

    Returns:
        Exit code:
        - 0 for success;
        - 1 for per-item failures, missing inputs, or invalid eligible metadata;
        - 2 for configuration/validation errors;
        - 130 for keyboard interruption.

    I/O:
        Coordinates command-line parsing, validation, metadata reading, model
        loading, transcription, logging, transcript writing, and manifest writing.

    Raises:
        No exceptions are expected to propagate to the caller.
    """
    try:
        args = parse_args()
        return run_workflow(args)
    except ConfigurationError as exc:
        message = f"Configuration error: {exc}"
        print(message, file=sys.stderr)

        if logging.getLogger().handlers:
            logging.error(message)

        return EXIT_CONFIGURATION_ERROR
    except KeyboardInterrupt:
        print("Interrupted by user.", file=sys.stderr)
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    sys.exit(main())