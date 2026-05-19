#!/usr/bin/env python3
"""
Extract television commercial clips from downloaded source videos.

This script reads commercial metadata from an NDJSON file, selects records where
"Download Success" is true, and extracts one commercial clip per eligible record
using ffmpeg.

Source videos are expected in the input directory as "<Video ID>.mp4".
Extracted clips are written to the output directory as "<Commercial ID>.mp4".

By default, the script runs in test mode and attempts only the first 5 planned
commercials. Existing output clips are skipped unless --reprocess is provided,
making the script safe to re-run.

Use --start-commercial-id to start planning extraction from a specific
Commercial ID onward.

Example:
    python extract_commercials.py

Full run:
    python extract_commercials.py --no-test-mode

Full run from a specific commercial:
    python extract_commercials.py --no-test-mode --start-commercial-id tv_com_1950_25

The script writes an append-only log file and JSON manifests describing
run-level metadata and per-commercial status.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


TOOL_NAME = "extract_commercials.py"
TOOL_VERSION = "v1"

DEFAULT_METADATA_PATH = "corpus/00_sources/tv_commercials.ndjson"
DEFAULT_INPUT_DIR = "corpus/01_videos"
DEFAULT_OUTPUT_DIR = "corpus/02_commercials"
DEFAULT_LOG_FILE = "corpus/02_commercials/extract_commercials.log"
DEFAULT_MANIFEST_FILE = "corpus/02_commercials/extract_commercials_manifest.json"

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 5
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 5

FFMPEG_VIDEO_CODEC = "libx264"
FFMPEG_AUDIO_CODEC = "aac"
FFMPEG_AVOID_NEGATIVE_TS = "make_zero"

EXIT_SUCCESS = 0
EXIT_RUN_FAILURE = 1
EXIT_CONFIGURATION_ERROR = 2
EXIT_INTERRUPTED = 130


class ConfigurationError(Exception):
    """Raised when command-line arguments or required runtime resources are invalid."""


def utc_now() -> datetime:
    """Return the current UTC datetime with timezone information."""
    return datetime.now(UTC)


def utc_timestamp() -> str:
    """Return the current UTC time as an ISO-like string suitable for JSON manifests."""
    return utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def make_run_id() -> str:
    """Return a compact UTC run identifier suitable for filenames."""
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for the commercial extraction programme.

    Returns:
        argparse.Namespace: Parsed command-line configuration.

    I/O:
        Reads command-line arguments from sys.argv through argparse.

    Error behaviour:
        argparse exits automatically with a non-zero status for invalid syntax.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Extract individual television commercial clips from downloaded "
            "source videos using ffmpeg."
        )
    )

    parser.add_argument(
        "--metadata",
        default=DEFAULT_METADATA_PATH,
        help=f"Path to NDJSON metadata file. Default: {DEFAULT_METADATA_PATH}",
    )
    parser.add_argument(
        "--input-dir",
        default=DEFAULT_INPUT_DIR,
        help=f"Directory containing source videos. Default: {DEFAULT_INPUT_DIR}",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for extracted commercials. Default: {DEFAULT_OUTPUT_DIR}",
    )

    test_mode_group = parser.add_mutually_exclusive_group()
    test_mode_group.add_argument(
        "--test-mode",
        dest="test_mode",
        action="store_true",
        help="Enable test mode.",
    )
    test_mode_group.add_argument(
        "--no-test-mode",
        dest="test_mode",
        action="store_false",
        help="Disable test mode and process all planned commercials.",
    )
    parser.set_defaults(test_mode=DEFAULT_TEST_MODE)

    parser.add_argument(
        "--test-limit",
        type=int,
        default=DEFAULT_TEST_LIMIT,
        help=f"Maximum commercials to attempt in test mode. Default: {DEFAULT_TEST_LIMIT}",
    )
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="Re-extract clips even when output files already exist.",
    )
    parser.add_argument(
        "--start-commercial-id",
        default=None,
        help="Start planning extraction from this Commercial ID onward.",
    )
    parser.add_argument(
        "--log-file",
        default=DEFAULT_LOG_FILE,
        help=f"Path to append-only log file. Default: {DEFAULT_LOG_FILE}",
    )
    parser.add_argument(
        "--manifest-file",
        default=DEFAULT_MANIFEST_FILE,
        help=f"Path to latest JSON manifest. Default: {DEFAULT_MANIFEST_FILE}",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help="Number of workers. Current implementation supports only 1.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Timeout in seconds for one ffmpeg process. Default: {DEFAULT_TIMEOUT_SECONDS}",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help=f"Retries after a failed ffmpeg command. Default: {DEFAULT_MAX_RETRIES}",
    )

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    """
    Validate command-line arguments and external dependencies before processing.

    Args:
        args: Parsed command-line arguments.

    Returns:
        None.

    I/O:
        Checks filesystem paths and verifies ffmpeg availability on PATH.

    Raises:
        ConfigurationError: If any argument, path, or external dependency is invalid.
    """
    metadata_path = Path(args.metadata)
    input_dir = Path(args.input_dir)

    if not metadata_path.exists():
        raise ConfigurationError(f"Metadata file does not exist: {metadata_path}")
    if not metadata_path.is_file():
        raise ConfigurationError(f"Metadata path is not a file: {metadata_path}")

    try:
        with metadata_path.open("r", encoding="utf-8"):
            pass
    except OSError as exc:
        raise ConfigurationError(f"Metadata file is not readable: {metadata_path}: {exc}") from exc

    if not input_dir.exists():
        raise ConfigurationError(f"Input directory does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise ConfigurationError(f"Input path is not a directory: {input_dir}")

    if args.test_limit <= 0:
        raise ConfigurationError("--test-limit must be greater than zero")
    if args.workers <= 0:
        raise ConfigurationError("--workers must be greater than zero")
    if args.workers != 1:
        raise ConfigurationError("Current implementation supports only --workers 1")
    if args.timeout <= 0:
        raise ConfigurationError("--timeout must be greater than zero")
    if args.max_retries < 0:
        raise ConfigurationError("--max-retries must be zero or greater")

    if args.start_commercial_id is not None and not str(args.start_commercial_id).strip():
        raise ConfigurationError("--start-commercial-id was provided but is empty")

    if shutil.which("ffmpeg") is None:
        raise ConfigurationError("ffmpeg is not available on the system PATH")


def setup_logging(log_file: Path) -> None:
    """
    Configure append-only file logging and console logging.

    Args:
        log_file: Path to the log file.

    Returns:
        None.

    I/O:
        Creates the log file parent directory if needed and opens the log file in append mode.

    Error behaviour:
        Raises OSError if the log directory or log file cannot be created/opened.
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-5s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def is_download_success(value: Any) -> bool:
    """
    Interpret metadata values for the Download Success field.

    Args:
        value: Raw metadata value.

    Returns:
        bool: True only for accepted truthy success values.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1"}
    return False


def stringify_field(value: Any) -> str:
    """
    Convert a metadata field to a stripped string.

    Args:
        value: Raw metadata field value.

    Returns:
        str: Empty string for None, otherwise stripped string representation.
    """
    if value is None:
        return ""
    return str(value).strip()


def load_commercial_metadata(metadata_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int]:
    """
    Load and validate eligible commercial metadata from an NDJSON file.

    Args:
        metadata_path: Path to the NDJSON metadata file.

    Returns:
        tuple:
            - eligible_commercials: Valid records where Download Success is true.
            - invalid_records: Eligible records that are missing required fields.
            - total_records: Total number of non-empty metadata records read.
            - ignored_download_failures: Records ignored because Download Success is not true.

    I/O:
        Reads the NDJSON metadata file from disk.

    Raises:
        ConfigurationError: If a line contains invalid JSON or the file cannot be read.
    """
    eligible_commercials: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    total_records = 0
    ignored_download_failures = 0

    required_fields = ["Commercial ID", "Video ID", "Start", "End"]

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

                missing_fields = [
                    field for field in required_fields if not stringify_field(record.get(field))
                ]

                if missing_fields:
                    invalid_records.append(
                        {
                            "line_number": line_number,
                            "commercial_id": stringify_field(record.get("Commercial ID")) or None,
                            "video_id": stringify_field(record.get("Video ID")) or None,
                            "status": "failed_metadata",
                            "error": f"Missing required field(s): {', '.join(missing_fields)}",
                            "record": record,
                        }
                    )
                    continue

                commercial = {
                    "line_number": line_number,
                    "commercial_id": stringify_field(record.get("Commercial ID")),
                    "video_id": stringify_field(record.get("Video ID")),
                    "start": stringify_field(record.get("Start")),
                    "end": stringify_field(record.get("End")),
                    "title": record.get("Title"),
                    "decade": record.get("Decade"),
                    "sequence": record.get("Sequence"),
                    "category": record.get("Category"),
                    "url": record.get("URL"),
                    "record": record,
                }
                eligible_commercials.append(commercial)
    except OSError as exc:
        raise ConfigurationError(f"Could not read metadata file {metadata_path}: {exc}") from exc

    return eligible_commercials, invalid_records, total_records, ignored_download_failures


def base_commercial_result(commercial: dict[str, Any], input_path: Path, output_path: Path) -> dict[str, Any]:
    """
    Build a standard manifest item skeleton for one commercial.

    Args:
        commercial: Normalised commercial metadata.
        input_path: Expected source video path.
        output_path: Commercial output clip path.

    Returns:
        dict: Manifest item with common fields populated.
    """
    return {
        "commercial_id": commercial["commercial_id"],
        "video_id": commercial["video_id"],
        "start": commercial["start"],
        "end": commercial["end"],
        "input_path": str(input_path),
        "output_path": str(output_path),
        "status": None,
        "error": None,
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
            "url": commercial.get("url"),
            "line_number": commercial.get("line_number"),
        },
    }


def plan_extractions(
        commercials: list[dict[str, Any]],
        input_dir: Path,
        output_dir: Path,
        test_mode: bool,
        test_limit: int,
        reprocess: bool,
        start_commercial_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Create planned, skipped, and missing-input commercial extraction records.

    Args:
        commercials: Valid eligible commercial records.
        input_dir: Directory containing source video files.
        output_dir: Directory for extracted commercial files.
        test_mode: Whether to limit planned extraction attempts.
        test_limit: Maximum number of attempts when test mode is active.
        reprocess: Whether to overwrite existing commercial clips.
        start_commercial_id: Optional Commercial ID from which to start planning.

    Returns:
        tuple:
            - planned: Items that should be extracted with ffmpeg.
            - skipped_existing: Items skipped because output already exists.
            - missing_input: Items that cannot be extracted because the source video is missing.

    I/O:
        Checks file existence for expected input and output paths.

    Raises:
        ConfigurationError: If start_commercial_id is provided but not found.
    """
    selected_commercials = commercials

    if start_commercial_id is not None:
        start_index = None
        for index, commercial in enumerate(commercials):
            if commercial["commercial_id"] == start_commercial_id:
                start_index = index
                break

        if start_index is None:
            raise ConfigurationError(
                f"--start-commercial-id not found among eligible records: {start_commercial_id}"
            )

        selected_commercials = commercials[start_index:]

    planned: list[dict[str, Any]] = []
    skipped_existing: list[dict[str, Any]] = []
    missing_input: list[dict[str, Any]] = []

    for commercial in selected_commercials:
        input_path = input_dir / f"{commercial['video_id']}.mp4"
        output_path = output_dir / f"{commercial['commercial_id']}.mp4"
        item = base_commercial_result(commercial, input_path, output_path)

        if not input_path.exists():
            item["status"] = "missing_input"
            item["error"] = f"Source video does not exist: {input_path}"
            missing_input.append(item)
            continue

        if output_path.exists() and not reprocess:
            item["status"] = "skipped_existing"
            skipped_existing.append(item)
            continue

        planned.append(item)

    if test_mode:
        planned = planned[:test_limit]

    return planned, skipped_existing, missing_input


def build_ffmpeg_command(
        start: str,
        end: str,
        input_path: Path | str,
        output_path: Path | str,
) -> list[str]:
    """
    Build an ffmpeg command list for subprocess execution.

    Args:
        start: Start timestamp.
        end: End timestamp.
        input_path: Source video path.
        output_path: Output commercial clip path.

    Returns:
        list[str]: ffmpeg command as an argument list.
    """
    return [
        "ffmpeg",
        "-y",
        "-ss",
        start,
        "-to",
        end,
        "-i",
        str(input_path),
        "-c:v",
        FFMPEG_VIDEO_CODEC,
        "-c:a",
        FFMPEG_AUDIO_CODEC,
        "-avoid_negative_ts",
        FFMPEG_AVOID_NEGATIVE_TS,
        str(output_path),
    ]


def summarise_error(stderr: str, stdout: str = "", exception_message: str | None = None) -> str:
    """
    Produce a short error summary from ffmpeg stderr, stdout, or an exception.

    Args:
        stderr: Captured stderr text.
        stdout: Captured stdout text.
        exception_message: Optional exception string.

    Returns:
        str: Short error summary.
    """
    if exception_message:
        return exception_message

    candidate = stderr.strip() or stdout.strip()
    if not candidate:
        return "Unknown ffmpeg error"

    lines = [line.strip() for line in candidate.splitlines() if line.strip()]
    if not lines:
        return "Unknown ffmpeg error"

    return lines[-1][:1000]


def extract_one_commercial(
        commercial_id: str,
        video_id: str,
        start: str,
        end: str,
        input_path: Path,
        output_path: Path,
        timeout: int,
        max_retries: int,
        retry_delay: int,
) -> dict[str, Any]:
    """
    Extract one commercial clip with ffmpeg and return a structured result.

    Args:
        commercial_id: Commercial ID used for logging and manifest output.
        video_id: Source video ID used for logging and manifest output.
        start: Start timestamp.
        end: End timestamp.
        input_path: Path to source video.
        output_path: Path to output clip.
        timeout: Maximum seconds allowed for each ffmpeg attempt.
        max_retries: Number of retry attempts after the first failed attempt.
        retry_delay: Seconds to wait between retries.

    Returns:
        dict: Structured result containing status, command, return code, timing, and errors.

    I/O:
        Runs ffmpeg as a subprocess and writes the output video clip.

    Error behaviour:
        Does not raise for ffmpeg failures. Returns status "failed" instead.
        KeyboardInterrupt is not swallowed.
    """
    command = build_ffmpeg_command(start, end, input_path, output_path)
    started_at = utc_timestamp()
    wall_start = time.monotonic()

    result: dict[str, Any] = {
        "commercial_id": commercial_id,
        "video_id": video_id,
        "start": start,
        "end": end,
        "input_path": str(input_path),
        "output_path": str(output_path),
        "status": "failed",
        "error": None,
        "return_code": None,
        "retries": 0,
        "duration_seconds": None,
        "start_time": started_at,
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
                "Retrying %s from %s; attempt %s of %s",
                commercial_id,
                video_id,
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
            logging.error(
                "FAILED %s %s %s-%s timeout after %s seconds",
                commercial_id,
                video_id,
                start,
                end,
                timeout,
            )

            if attempt_number == total_attempts:
                break
            continue
        except OSError as exc:
            result["return_code"] = None
            result["error"] = summarise_error("", exception_message=str(exc))
            logging.error("FAILED %s %s OSError: %s", commercial_id, video_id, exc)

            if attempt_number == total_attempts:
                break
            continue

        result["return_code"] = completed.returncode

        if completed.returncode == 0:
            result["status"] = "success"
            result["error"] = None
            break

        result["error"] = summarise_error(completed.stderr, completed.stdout)
        logging.error(
            "FAILED %s %s %s-%s return_code=%s error=%s",
            commercial_id,
            video_id,
            start,
            end,
            completed.returncode,
            result["error"],
        )

        if attempt_number == total_attempts:
            break

    result["end_time"] = utc_timestamp()
    result["duration_seconds"] = round(time.monotonic() - wall_start, 3)

    return result


def write_manifests(manifest: dict[str, Any], manifest_file: Path, run_id: str) -> tuple[Path, Path]:
    """
    Write latest and per-run manifest files.

    Args:
        manifest: Manifest dictionary to serialise as JSON.
        manifest_file: Path to the latest manifest file.
        run_id: Current run identifier used in the timestamped manifest filename.

    Returns:
        tuple[Path, Path]: Paths to latest manifest and per-run manifest.

    I/O:
        Creates the manifest parent directory and writes two JSON files.

    Error behaviour:
        Raises OSError if manifest files cannot be written.
    """
    manifest_file.parent.mkdir(parents=True, exist_ok=True)

    per_run_manifest = manifest_file.with_name(
        f"{manifest_file.stem}_{run_id}{manifest_file.suffix}"
    )

    with manifest_file.open("w", encoding="utf-8") as file_obj:
        json.dump(manifest, file_obj, ensure_ascii=False, indent=2)

    with per_run_manifest.open("w", encoding="utf-8") as file_obj:
        json.dump(manifest, file_obj, ensure_ascii=False, indent=2)

    return manifest_file, per_run_manifest


def get_ffmpeg_version() -> str | None:
    """
    Return the first line of `ffmpeg -version`, if available.

    Returns:
        str | None: ffmpeg version line, or None if unavailable.

    I/O:
        Runs ffmpeg as a subprocess.

    Error behaviour:
        Returns None if the version command fails.
    """
    try:
        completed = subprocess.run(
            ["ffmpeg", "-version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if completed.returncode != 0:
        return None

    first_line = completed.stdout.splitlines()[0] if completed.stdout.splitlines() else None
    return first_line


def build_manifest(
        args: argparse.Namespace,
        run_id: str,
        start_time: str,
        end_time: str | None,
        total_records: int,
        eligible_count: int,
        ignored_download_failures: int,
        invalid_records: list[dict[str, Any]],
        commercial_results: list[dict[str, Any]],
        interrupted: bool,
) -> dict[str, Any]:
    """
    Build the complete run manifest.

    Args:
        args: Parsed command-line arguments.
        run_id: Current run ID.
        start_time: Run start timestamp.
        end_time: Run end timestamp, or None during partial manifest creation.
        total_records: Total metadata records read.
        eligible_count: Valid eligible commercial count.
        ignored_download_failures: Rows ignored because Download Success was not true.
        invalid_records: Invalid eligible metadata rows.
        commercial_results: Per-commercial result records.
        interrupted: Whether the run was interrupted.

    Returns:
        dict: JSON-serialisable manifest.
    """
    succeeded = sum(1 for item in commercial_results if item.get("status") == "success")
    failed = sum(1 for item in commercial_results if item.get("status") == "failed")
    missing_input = sum(1 for item in commercial_results if item.get("status") == "missing_input")
    skipped_existing = sum(
        1 for item in commercial_results if item.get("status") == "skipped_existing"
    )
    attempted = sum(
        1 for item in commercial_results if item.get("status") in {"success", "failed"}
    )

    summary = {
        "metadata_records": total_records,
        "eligible_download_success": eligible_count + len(invalid_records),
        "ignored_download_not_success": ignored_download_failures,
        "invalid_metadata": len(invalid_records),
        "planned": attempted,
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": failed,
        "missing_input": missing_input,
        "skipped_existing": skipped_existing,
    }

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
            "metadata_path": str(Path(args.metadata)),
            "input_dir": str(Path(args.input_dir)),
            "output_dir": str(Path(args.output_dir)),
            "log_file": str(Path(args.log_file)),
            "manifest_file": str(Path(args.manifest_file)),
            "config": {
                "ffmpeg_codec_video": FFMPEG_VIDEO_CODEC,
                "ffmpeg_codec_audio": FFMPEG_AUDIO_CODEC,
                "avoid_negative_ts": FFMPEG_AVOID_NEGATIVE_TS,
                "timeout_seconds": args.timeout,
                "max_retries": args.max_retries,
                "retry_delay_seconds": DEFAULT_RETRY_DELAY_SECONDS,
                "start_commercial_id": args.start_commercial_id,
            },
            "summary": summary,
            "interrupted": interrupted,
        },
        "commercials": commercial_results,
        "invalid_records": invalid_records,
    }


def main() -> int:
    """
    Run the batch commercial extraction workflow and return an exit code.

    Returns:
        int: Process exit code.

    I/O:
        Reads metadata, checks video files, runs ffmpeg, writes logs and manifests.

    Error behaviour:
        Returns:
            0 for success;
            1 for per-commercial failures, missing inputs, or invalid eligible metadata;
            2 for configuration errors;
            130 for keyboard interruption.
    """
    args = parse_args()
    run_id = make_run_id()
    start_time = utc_timestamp()

    metadata_path = Path(args.metadata)
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    log_file = Path(args.log_file)
    manifest_file = Path(args.manifest_file)

    total_records = 0
    ignored_download_failures = 0
    eligible_commercials: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    commercial_results: list[dict[str, Any]] = []

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_file.parent.mkdir(parents=True, exist_ok=True)
        setup_logging(log_file)

        logging.info("Starting %s run_id=%s", TOOL_NAME, run_id)
        logging.info("Metadata path: %s", metadata_path)
        logging.info("Input directory: %s", input_dir)
        logging.info("Output directory: %s", output_dir)
        logging.info("Test mode: %s; test_limit=%s", str(args.test_mode).lower(), args.test_limit)
        logging.info("Reprocess existing clips: %s", str(args.reprocess).lower())
        logging.info("Start commercial ID: %s", args.start_commercial_id)

        validate_args(args)

        ffmpeg_version = get_ffmpeg_version()
        if ffmpeg_version:
            logging.info("ffmpeg available: %s", ffmpeg_version)
        else:
            logging.info("ffmpeg available")

        eligible_commercials, invalid_records, total_records, ignored_download_failures = (
            load_commercial_metadata(metadata_path)
        )

        for invalid_record in invalid_records:
            logging.error(
                "INVALID_METADATA line=%s commercial_id=%s video_id=%s error=%s",
                invalid_record.get("line_number"),
                invalid_record.get("commercial_id"),
                invalid_record.get("video_id"),
                invalid_record.get("error"),
            )

        logging.info(
            "Found %s metadata records; %s eligible valid records; %s ignored; %s invalid eligible records",
            total_records,
            len(eligible_commercials),
            ignored_download_failures,
            len(invalid_records),
        )

        planned, skipped_existing, missing_input = plan_extractions(
            commercials=eligible_commercials,
            input_dir=input_dir,
            output_dir=output_dir,
            test_mode=args.test_mode,
            test_limit=args.test_limit,
            reprocess=args.reprocess,
            start_commercial_id=args.start_commercial_id,
        )

        commercial_results.extend(skipped_existing)
        commercial_results.extend(missing_input)

        for item in skipped_existing:
            logging.info(
                "SKIPPED_EXISTING %s %s -> %s",
                item["commercial_id"],
                item["video_id"],
                item["output_path"],
            )

        for item in missing_input:
            logging.error(
                "MISSING_INPUT %s %s expected=%s",
                item["commercial_id"],
                item["video_id"],
                item["input_path"],
            )

        logging.info("Planned extractions: %s", len(planned))

        for item in planned:
            result = extract_one_commercial(
                commercial_id=item["commercial_id"],
                video_id=item["video_id"],
                start=item["start"],
                end=item["end"],
                input_path=Path(item["input_path"]),
                output_path=Path(item["output_path"]),
                timeout=args.timeout,
                max_retries=args.max_retries,
                retry_delay=DEFAULT_RETRY_DELAY_SECONDS,
            )

            merged_metadata = item.get("metadata", {}).copy()
            merged_metadata.update(result.get("metadata", {}))
            result["metadata"] = merged_metadata

            commercial_results.append(result)

            if result["status"] == "success":
                logging.info(
                    "SUCCESS %s %s %s-%s -> %s",
                    result["commercial_id"],
                    result["video_id"],
                    result["start"],
                    result["end"],
                    result["output_path"],
                )
            else:
                logging.error(
                    "FAILED %s %s %s-%s -> %s error=%s",
                    result["commercial_id"],
                    result["video_id"],
                    result["start"],
                    result["end"],
                    result["output_path"],
                    result["error"],
                )

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
            commercial_results=commercial_results,
            interrupted=False,
        )

        latest_manifest, per_run_manifest = write_manifests(manifest, manifest_file, run_id)

        summary = manifest["run_metadata"]["summary"]
        logging.info("Wrote latest manifest: %s", latest_manifest)
        logging.info("Wrote per-run manifest: %s", per_run_manifest)
        logging.info(
            "Finished run: succeeded=%s failed=%s skipped_existing=%s missing_input=%s invalid_metadata=%s",
            summary["succeeded"],
            summary["failed"],
            summary["skipped_existing"],
            summary["missing_input"],
            summary["invalid_metadata"],
        )

        if (
                summary["failed"] > 0
                or summary["missing_input"] > 0
                or summary["invalid_metadata"] > 0
        ):
            return EXIT_RUN_FAILURE

        return EXIT_SUCCESS

    except KeyboardInterrupt:
        end_time = utc_timestamp()

        try:
            logging.error("Interrupted by user")
        except Exception:
            pass

        try:
            manifest = build_manifest(
                args=args,
                run_id=run_id,
                start_time=start_time,
                end_time=end_time,
                total_records=total_records,
                eligible_count=len(eligible_commercials),
                ignored_download_failures=ignored_download_failures,
                invalid_records=invalid_records,
                commercial_results=commercial_results,
                interrupted=True,
            )
            latest_manifest, per_run_manifest = write_manifests(manifest, manifest_file, run_id)
            logging.info("Wrote partial latest manifest: %s", latest_manifest)
            logging.info("Wrote partial per-run manifest: %s", per_run_manifest)
        except Exception as exc:
            print(f"Could not write partial manifest after interruption: {exc}", file=sys.stderr)

        return EXIT_INTERRUPTED

    except ConfigurationError as exc:
        message = f"Configuration error: {exc}"
        print(message, file=sys.stderr)

        try:
            logging.error(message)
        except Exception:
            pass

        return EXIT_CONFIGURATION_ERROR

    except OSError as exc:
        message = f"I/O error: {exc}"
        print(message, file=sys.stderr)

        try:
            logging.error(message)
        except Exception:
            pass

        return EXIT_CONFIGURATION_ERROR


if __name__ == "__main__":
    sys.exit(main())