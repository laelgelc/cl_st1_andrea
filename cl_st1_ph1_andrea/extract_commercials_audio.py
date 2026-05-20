#!/usr/bin/env python3
"""
Extract Whisper-ready audio from television commercial video files.

This script reads commercial metadata from an NDJSON file, selects records where
"Download Success" is true, and extracts one WAV audio file per eligible
commercial using ffmpeg.

Source commercial videos are expected in the input directory as
"<Commercial ID>.mp4". Extracted audio files are written to the output directory
as "<Commercial ID>.wav".

The output audio format is designed for transcription with Whisper:
mono, 16 kHz, signed 16-bit PCM WAV.

By default, the script runs in test mode and attempts only the first 5 planned
commercials. Existing output audio files are skipped unless --reprocess is
provided, making the script safe to re-run.

Use --start-commercial-id to start planning extraction from a specific
Commercial ID onward.

Example:
    python extract_commercials_audio.py

Full run:
    python extract_commercials_audio.py --no-test-mode

Full run from a specific commercial:
    python extract_commercials_audio.py --no-test-mode --start-commercial-id tv_com_1950_25

The script writes an append-only log file and JSON manifests describing
run-level metadata and per-commercial audio extraction status.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


TOOL_NAME = "extract_commercials_audio.py"
TOOL_VERSION = "v1"

DEFAULT_METADATA_PATH = "corpus/00_sources/tv_commercials.ndjson"
DEFAULT_INPUT_DIR = "corpus/02_commercials"
DEFAULT_OUTPUT_DIR = "corpus/03_audio"
DEFAULT_LOG_FILE = "corpus/03_audio/extract_commercials_audio.log"
DEFAULT_MANIFEST_FILE = "corpus/03_audio/extract_commercials_audio_manifest.json"

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 5
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 5

OUTPUT_AUDIO_EXTENSION = ".wav"
INPUT_VIDEO_EXTENSION = ".mp4"

FFMPEG_AUDIO_CHANNELS = "1"
FFMPEG_AUDIO_SAMPLE_RATE = "16000"
FFMPEG_AUDIO_SAMPLE_FORMAT = "s16"

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
        A compact single-string error message.

    I/O:
        This function performs no file or process I/O.

    Raises:
        No expected exceptions.
    """
    clean_text = " ".join(text.strip().split())
    if len(clean_text) <= max_chars:
        return clean_text
    return clean_text[: max_chars - 3] + "..."


def build_ffmpeg_command(input_path: Path, output_path: Path) -> list[str]:
    """Build the ffmpeg command for one audio extraction.

    Args:
        input_path: Source commercial video path.
        output_path: Destination WAV audio path.

    Returns:
        Command as a list of arguments suitable for subprocess.

    I/O:
        This function performs no file or process I/O.

    Raises:
        No expected exceptions.
    """
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        FFMPEG_AUDIO_CHANNELS,
        "-ar",
        FFMPEG_AUDIO_SAMPLE_RATE,
        "-sample_fmt",
        FFMPEG_AUDIO_SAMPLE_FORMAT,
        str(output_path),
    ]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the commercial audio extraction programme.

    Returns:
        Parsed command-line arguments.

    I/O:
        Reads command-line arguments from sys.argv.

    Raises:
        SystemExit: Raised by argparse for invalid CLI syntax.
    """
    parser = argparse.ArgumentParser(
        description="Extract Whisper-ready WAV audio from commercial video files."
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
        help=f"Directory containing source commercial .mp4 files. Default: {DEFAULT_INPUT_DIR}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(DEFAULT_OUTPUT_DIR),
        help=f"Directory for extracted .wav files. Default: {DEFAULT_OUTPUT_DIR}",
    )
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
        help="Disable test mode and process all planned audio extractions.",
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
        help="Re-extract audio even when output .wav files already exist.",
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
        help=f"Timeout in seconds for each ffmpeg process. Default: {DEFAULT_TIMEOUT_SECONDS}",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help=f"Retry attempts after a failed ffmpeg command. Default: {DEFAULT_MAX_RETRIES}",
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


def check_ffmpeg_available() -> str:
    """Check that ffmpeg is available on the system path.

    Returns:
        A short ffmpeg version line if available.

    I/O:
        Runs `ffmpeg -version` as a subprocess.

    Raises:
        ConfigurationError: If ffmpeg is missing or cannot be executed.
    """
    if shutil.which("ffmpeg") is None:
        raise ConfigurationError("ffmpeg is not available on the system path.")

    try:
        completed = subprocess.run(
            ["ffmpeg", "-version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConfigurationError(f"Could not execute ffmpeg -version: {exc}") from exc

    if completed.returncode != 0:
        error = shorten_error(completed.stderr or completed.stdout or "Unknown ffmpeg error")
        raise ConfigurationError(f"ffmpeg -version failed: {error}")

    first_line = completed.stdout.splitlines()[0] if completed.stdout.splitlines() else "ffmpeg available"
    return first_line


def validate_args(args: argparse.Namespace) -> None:
    """Validate command-line arguments and external dependencies before processing.

    Args:
        args: Parsed command-line arguments.

    Returns:
        None.

    I/O:
        Checks filesystem paths, creates output/manifest/log parent directories,
        and runs an ffmpeg availability check.

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

    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(f"Could not create required output directories: {exc}") from exc

    check_ffmpeg_available()


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
        output_path: Path,
        status: str,
        error: str | None = None,
) -> dict[str, Any]:
    """Create a structured planning/result record for a commercial.

    Args:
        commercial: Commercial metadata dictionary.
        input_path: Expected source video path.
        output_path: Expected output audio path.
        status: Item status.
        error: Optional error message.

    Returns:
        Manifest-ready planning record.

    I/O:
        This function performs no file or process I/O.

    Raises:
        No expected exceptions.
    """
    command = build_ffmpeg_command(input_path, output_path)

    return {
        "commercial_id": commercial["commercial_id"],
        "input_path": str(input_path),
        "output_path": str(output_path),
        "status": status,
        "error": error,
        "return_code": None,
        "retries": 0,
        "duration_seconds": None,
        "start_time": None,
        "end_time": None,
        "metadata": {
            "title": commercial.get("title"),
            "decade": commercial.get("decade"),
            "sequence": commercial.get("sequence"),
            "category": commercial.get("category"),
            "video_id": commercial.get("video_id"),
            "url": commercial.get("url"),
            "source_start": commercial.get("source_start"),
            "source_end": commercial.get("source_end"),
            "command": command,
        },
    }


def plan_audio_extractions(
        commercials: list[dict[str, Any]],
        input_dir: Path,
        output_dir: Path,
        test_mode: bool,
        test_limit: int,
        reprocess: bool,
        start_commercial_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Create planned, skipped, and missing-input commercial audio extraction records.

    Args:
        commercials: Eligible commercial metadata records.
        input_dir: Directory containing source commercial videos.
        output_dir: Directory where WAV files will be written.
        test_mode: Whether to limit planned extraction attempts.
        test_limit: Maximum number of attempted items in test mode.
        reprocess: Whether to overwrite existing output audio files.
        start_commercial_id: Optional Commercial ID from which to start planning.

    Returns:
        A tuple containing:
        - planned records to be attempted with ffmpeg;
        - records skipped because output already exists;
        - records whose input video is missing.

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
        input_path = input_dir / f"{commercial_id}{INPUT_VIDEO_EXTENSION}"
        output_path = output_dir / f"{commercial_id}{OUTPUT_AUDIO_EXTENSION}"

        if not input_path.exists():
            missing_input.append(
                make_planning_record(
                    commercial=commercial,
                    input_path=input_path,
                    output_path=output_path,
                    status="missing_input",
                    error=f"Missing input video: {input_path}",
                )
            )
            continue

        if output_path.exists() and not reprocess:
            skipped_existing.append(
                make_planning_record(
                    commercial=commercial,
                    input_path=input_path,
                    output_path=output_path,
                    status="skipped_existing",
                )
            )
            continue

        planned.append(
            make_planning_record(
                commercial=commercial,
                input_path=input_path,
                output_path=output_path,
                status="planned",
            )
        )

        if test_mode and len(planned) >= test_limit:
            break

    return planned, skipped_existing, missing_input


def extract_one_audio(
        commercial_id: str,
        input_path: Path,
        output_path: Path,
        timeout: int,
        max_retries: int,
        retry_delay: int,
) -> dict[str, Any]:
    """Extract one Whisper-ready WAV audio file with ffmpeg and return a structured result.

    Args:
        commercial_id: Commercial identifier.
        input_path: Source commercial video path.
        output_path: Destination WAV audio path.
        timeout: Maximum seconds allowed for each ffmpeg attempt.
        max_retries: Number of retries after the first failed attempt.
        retry_delay: Delay between retries in seconds.

    Returns:
        A dictionary containing status, timing, return code, retries, error,
        and the ffmpeg command.

    I/O:
        Runs ffmpeg as a subprocess and writes the output audio file.

    Raises:
        No expected exceptions are propagated for per-item failures. They are
        captured in the returned result.
    """
    command = build_ffmpeg_command(input_path, output_path)
    start_timestamp = utc_timestamp()
    start_monotonic = time.monotonic()

    result: dict[str, Any] = {
        "commercial_id": commercial_id,
        "input_path": str(input_path),
        "output_path": str(output_path),
        "status": "failed",
        "error": None,
        "return_code": None,
        "retries": 0,
        "duration_seconds": None,
        "start_time": start_timestamp,
        "end_time": None,
        "metadata": {
            "command": command,
        },
    }

    total_attempts = max_retries + 1

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
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            result["return_code"] = None
            result["error"] = f"ffmpeg timed out after {timeout} seconds"
            logging.error("FAILED %s timeout after %s seconds", commercial_id, timeout)

            if exc.stderr:
                result["error"] = f"{result['error']}: {shorten_error(str(exc.stderr))}"

            continue
        except OSError as exc:
            result["return_code"] = None
            result["error"] = f"Could not execute ffmpeg: {exc}"
            logging.error("FAILED %s could not execute ffmpeg: %s", commercial_id, exc)
            continue

        result["return_code"] = completed.returncode

        if completed.returncode == 0:
            result["status"] = "success"
            result["error"] = None
            break

        error_text = completed.stderr or completed.stdout or f"ffmpeg exited with {completed.returncode}"
        result["error"] = shorten_error(error_text)
        logging.error(
            "FAILED %s return_code=%s error=%s",
            commercial_id,
            completed.returncode,
            result["error"],
        )

    result["end_time"] = utc_timestamp()
    result["duration_seconds"] = round(time.monotonic() - start_monotonic, 3)

    if result["status"] == "success":
        logging.info("SUCCESS %s -> %s", commercial_id, output_path)

    return result


def merge_execution_result(
        planned_record: dict[str, Any],
        execution_result: dict[str, Any],
) -> dict[str, Any]:
    """Merge execution fields into a planned manifest record.

    Args:
        planned_record: Original planned record with metadata.
        execution_result: Result returned by extract_one_audio.

    Returns:
        Manifest-ready item record.

    I/O:
        This function performs no file or process I/O.

    Raises:
        No expected exceptions.
    """
    merged = dict(planned_record)
    merged.update(
        {
            "status": execution_result["status"],
            "error": execution_result["error"],
            "return_code": execution_result["return_code"],
            "retries": execution_result["retries"],
            "duration_seconds": execution_result["duration_seconds"],
            "start_time": execution_result["start_time"],
            "end_time": execution_result["end_time"],
        }
    )

    metadata = dict(planned_record.get("metadata", {}))
    metadata["command"] = execution_result["metadata"]["command"]
    merged["metadata"] = metadata

    return merged


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
                "output_path": None,
                "status": "failed_metadata",
                "error": record.get("error"),
                "return_code": None,
                "retries": 0,
                "duration_seconds": None,
                "start_time": None,
                "end_time": None,
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
        planned_count: Number of ffmpeg extraction records planned.
        attempted_results: Results for attempted ffmpeg extractions.
        skipped_existing: Records skipped because output already existed.
        missing_input: Records whose input video was missing.
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
                "output_format": OUTPUT_AUDIO_EXTENSION.lstrip("."),
                "audio_channels": int(FFMPEG_AUDIO_CHANNELS),
                "audio_sample_rate": int(FFMPEG_AUDIO_SAMPLE_RATE),
                "audio_sample_format": FFMPEG_AUDIO_SAMPLE_FORMAT,
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
    """Run the main workflow after CLI parsing and initial validation.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Process exit code.

    I/O:
        Reads metadata, checks input/output files, executes ffmpeg, writes logs,
        and writes manifest files.

    Raises:
        ConfigurationError: For validation errors that should stop the run.
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
        "Audio format: wav; channels=%s; sample_rate=%s; sample_fmt=%s",
        FFMPEG_AUDIO_CHANNELS,
        FFMPEG_AUDIO_SAMPLE_RATE,
        FFMPEG_AUDIO_SAMPLE_FORMAT,
    )
    logging.info("Test mode: %s; test_limit=%s", str(args.test_mode).lower(), args.test_limit)
    logging.info("Reprocess: %s", str(args.reprocess).lower())
    logging.info("Start commercial ID: %s", args.start_commercial_id)

    validate_args(args)
    ffmpeg_version = check_ffmpeg_available()
    logging.info("ffmpeg available: %s", ffmpeg_version)

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
            "Found %s metadata records; %s eligible for audio extraction; %s ignored; %s invalid",
            total_records,
            len(eligible_commercials),
            ignored_download_failures,
            len(invalid_records),
        )

        planned, skipped_existing, missing_input = plan_audio_extractions(
            commercials=eligible_commercials,
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            test_mode=args.test_mode,
            test_limit=args.test_limit,
            reprocess=args.reprocess,
            start_commercial_id=args.start_commercial_id,
        )

        logging.info("Planned audio extractions: %s", len(planned))

        for item in skipped_existing:
            logging.info(
                "SKIPPED_EXISTING %s -> %s",
                item["commercial_id"],
                item["output_path"],
            )

        for item in missing_input:
            logging.error(
                "MISSING_INPUT %s expected=%s",
                item["commercial_id"],
                item["input_path"],
            )

        for item in planned:
            commercial_id = item["commercial_id"]
            result = extract_one_audio(
                commercial_id=commercial_id,
                input_path=Path(item["input_path"]),
                output_path=Path(item["output_path"]),
                timeout=args.timeout,
                max_retries=args.max_retries,
                retry_delay=DEFAULT_RETRY_DELAY_SECONDS,
            )
            attempted_results.append(merge_execution_result(item, result))

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
    """Run the batch commercial audio extraction workflow and return an exit code.

    Returns:
        Exit code:
        - 0 for success;
        - 1 for per-item failures, missing inputs, or invalid eligible metadata;
        - 2 for configuration/validation errors;
        - 130 for keyboard interruption.

    I/O:
        Coordinates command-line parsing, validation, metadata reading, ffmpeg
        execution, logging, and manifest writing.

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