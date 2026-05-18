"""
Download source YouTube videos for the television commercials corpus.

This script reads video metadata from an NDJSON file, extracts unique videos
using the "Video ID" and "URL" fields, and downloads each source video with
yt-dlp. Downloaded files are saved as "<Video ID>.mp4" in the output directory.

By default, the script runs in test mode and attempts only the first 5 planned
videos. Existing output files are skipped unless --reprocess is provided,
making the script safe to re-run.

Example:
    python download_videos.py

Full run:
    python download_videos.py --no-test-mode

The script writes an append-only log file and JSON manifests describing
run-level metadata and per-video status.
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


TOOL_NAME = "download_videos.py"
TOOL_VERSION = "v1"

DEFAULT_METADATA_PATH = "corpus/00_sources/tv_commercials.ndjson"
DEFAULT_OUTPUT_DIR = "corpus/01_videos"
DEFAULT_LOG_FILE = "corpus/01_videos/download_videos.log"
DEFAULT_MANIFEST_FILE = "corpus/01_videos/download_videos_manifest.json"

DEFAULT_TEST_MODE = True
DEFAULT_TEST_LIMIT = 5
DEFAULT_WORKERS = 1
DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_MAX_RETRIES = 1
DEFAULT_RETRY_DELAY_SECONDS = 5

YT_DLP_FORMAT = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"

EXIT_SUCCESS = 0
EXIT_DOWNLOAD_FAILURE = 1
EXIT_CONFIGURATION_ERROR = 2
EXIT_INTERRUPTED = 130


class ConfigurationError(Exception):
    """Raised when command-line arguments or runtime configuration are invalid."""


def utc_now() -> datetime:
    """Return the current UTC datetime.

    Returns:
        A timezone-aware UTC datetime.
    """
    return datetime.now(UTC)


def utc_timestamp() -> str:
    """Return the current UTC timestamp in ISO-8601 format.

    Returns:
        A string such as "2026-05-18T14:30:12Z".
    """
    return utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def make_run_id() -> str:
    """Create a UTC run identifier safe for filenames.

    Returns:
        A string such as "20260518T143012Z".
    """
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the video download programme.

    Returns:
        An argparse namespace containing validated or default command-line
        values. Detailed semantic validation is performed separately by
        validate_args().
    """
    parser = argparse.ArgumentParser(
        description="Download source YouTube videos listed in an NDJSON metadata file."
    )

    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path(DEFAULT_METADATA_PATH),
        help=f"Path to the NDJSON metadata file. Default: {DEFAULT_METADATA_PATH}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(DEFAULT_OUTPUT_DIR),
        help=f"Directory where downloaded videos are saved. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--test-mode",
        dest="test_mode",
        action="store_true",
        default=DEFAULT_TEST_MODE,
        help="Enable test mode. This is the default.",
    )
    parser.add_argument(
        "--no-test-mode",
        dest="test_mode",
        action="store_false",
        help="Disable test mode and process all planned videos.",
    )
    parser.add_argument(
        "--test-limit",
        type=int,
        default=DEFAULT_TEST_LIMIT,
        help=f"Maximum videos to attempt in test mode. Default: {DEFAULT_TEST_LIMIT}",
    )
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="Re-download videos even when output files already exist.",
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
        help=f"Latest manifest file path. Default: {DEFAULT_MANIFEST_FILE}",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Number of workers. Initial implementation runs sequentially. Default: {DEFAULT_WORKERS}",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Timeout in seconds for one yt-dlp process. Default: {DEFAULT_TIMEOUT_SECONDS}",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help=f"Retries after a failed download. Default: {DEFAULT_MAX_RETRIES}",
    )
    parser.add_argument(
        "--retry-delay",
        type=int,
        default=DEFAULT_RETRY_DELAY_SECONDS,
        help=f"Delay in seconds between retries. Default: {DEFAULT_RETRY_DELAY_SECONDS}",
    )

    return parser.parse_args()


def setup_logging(log_file: Path) -> logging.Logger:
    """Configure append-only file logging and console logging.

    Args:
        log_file: Path where log messages should be appended.

    Returns:
        A configured logger for this programme.

    Raises:
        ConfigurationError: If the log directory cannot be created.
    """
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(f"Could not create log directory {log_file.parent}: {exc}") from exc

    logger = logging.getLogger(TOOL_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-5s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def validate_args(args: argparse.Namespace) -> str:
    """Validate command-line arguments and external dependencies before processing.

    Args:
        args: Parsed command-line arguments.

    Returns:
        The detected yt-dlp version string.

    Raises:
        ConfigurationError: If an argument, path, or dependency is invalid.
    """
    if not args.metadata.exists():
        raise ConfigurationError(f"Metadata file does not exist: {args.metadata}")

    if not args.metadata.is_file():
        raise ConfigurationError(f"Metadata path is not a file: {args.metadata}")

    if args.test_limit <= 0:
        raise ConfigurationError("--test-limit must be greater than 0")

    if args.workers <= 0:
        raise ConfigurationError("--workers must be greater than 0")

    if args.timeout <= 0:
        raise ConfigurationError("--timeout must be greater than 0")

    if args.max_retries < 0:
        raise ConfigurationError("--max-retries must be 0 or greater")

    if args.retry_delay < 0:
        raise ConfigurationError("--retry-delay must be 0 or greater")

    yt_dlp_path = shutil.which("yt-dlp")
    if yt_dlp_path is None:
        raise ConfigurationError("yt-dlp is not available on the system PATH")

    try:
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.SubprocessError as exc:
        raise ConfigurationError(f"Could not check yt-dlp version: {exc}") from exc

    if result.returncode != 0:
        error = summarise_error(result.stderr or result.stdout)
        raise ConfigurationError(f"yt-dlp --version failed: {error}")

    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        args.manifest_file.parent.mkdir(parents=True, exist_ok=True)
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(f"Could not create required output directories: {exc}") from exc

    if args.workers != 1:
        raise ConfigurationError(
            "Parallel execution is not implemented in this version; please use --workers 1"
        )

    return result.stdout.strip()


def summarise_error(text: str | None, max_length: int = 500) -> str:
    """Create a short one-line error summary.

    Args:
        text: Raw error text, often stderr from yt-dlp.
        max_length: Maximum length of the returned string.

    Returns:
        A compact error message suitable for logs and manifests.
    """
    if not text:
        return "Unknown error"

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    summary = lines[-1] if lines else text.strip()
    if len(summary) > max_length:
        summary = summary[: max_length - 3] + "..."
    return summary


def load_video_metadata(metadata_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Load and validate video metadata from an NDJSON file.

    This function performs file I/O. It reads one JSON object per line,
    extracts "Video ID" and "URL", records invalid metadata rows, and
    deduplicates valid videos by first-seen "Video ID".

    Args:
        metadata_path: Path to the NDJSON metadata file.

    Returns:
        A tuple containing:
        - valid unique video records;
        - invalid metadata records;
        - total number of metadata records read.

    Raises:
        ConfigurationError: If a line contains invalid JSON or the file
        cannot be read.
    """
    videos: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    seen_video_ids: set[str] = set()
    metadata_records = 0

    try:
        with metadata_path.open("r", encoding="utf-8") as input_file:
            for line_number, line in enumerate(input_file, start=1):
                stripped_line = line.strip()
                if not stripped_line:
                    continue

                metadata_records += 1

                try:
                    record = json.loads(stripped_line)
                except json.JSONDecodeError as exc:
                    raise ConfigurationError(
                        f"Invalid JSON in metadata file at line {line_number}: {exc}"
                    ) from exc

                video_id = record.get("Video ID")
                url = record.get("URL")

                if not isinstance(video_id, str) or not video_id.strip():
                    invalid_records.append(
                        {
                            "line_number": line_number,
                            "status": "failed_metadata",
                            "error": "Missing or empty Video ID",
                            "record": record,
                        }
                    )
                    continue

                if not isinstance(url, str) or not url.strip():
                    invalid_records.append(
                        {
                            "line_number": line_number,
                            "video_id": video_id,
                            "status": "failed_metadata",
                            "error": "Missing or empty URL",
                            "record": record,
                        }
                    )
                    continue

                clean_video_id = video_id.strip()
                clean_url = url.strip()

                if clean_video_id in seen_video_ids:
                    continue

                seen_video_ids.add(clean_video_id)
                videos.append(
                    {
                        "video_id": clean_video_id,
                        "url": clean_url,
                        "source_line_number": line_number,
                    }
                )

    except OSError as exc:
        raise ConfigurationError(f"Could not read metadata file {metadata_path}: {exc}") from exc

    return videos, invalid_records, metadata_records


def make_skipped_existing_result(video: dict[str, Any], output_path: Path) -> dict[str, Any]:
    """Create a manifest result for a video skipped because output already exists.

    Args:
        video: Video metadata containing video_id and URL.
        output_path: Expected output path for the video.

    Returns:
        A structured item-level manifest dictionary.
    """
    timestamp = utc_timestamp()
    return {
        "video_id": video["video_id"],
        "url": video["url"],
        "output_path": str(output_path),
        "status": "skipped_existing",
        "error": None,
        "return_code": None,
        "retries": 0,
        "duration_seconds": 0.0,
        "start_time": timestamp,
        "end_time": timestamp,
        "metadata": {
            "reason": "Output file already exists and --reprocess was not provided",
        },
    }


def plan_downloads(
        videos: list[dict[str, Any]],
        output_dir: Path,
        test_mode: bool,
        test_limit: int,
        reprocess: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Create skipped and planned download records.

    This function performs filesystem checks but does not download videos.

    Args:
        videos: Unique valid video records.
        output_dir: Directory where video files should be saved.
        test_mode: Whether to limit planned attempts.
        test_limit: Maximum planned attempts when test mode is active.
        reprocess: Whether existing files should be downloaded again.

    Returns:
        A tuple containing:
        - planned download records;
        - skipped-existing result records.
    """
    planned: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for video in videos:
        output_path = output_dir / f"{video['video_id']}.mp4"

        if output_path.exists() and not reprocess:
            skipped.append(make_skipped_existing_result(video, output_path))
            continue

        planned.append(
            {
                "video_id": video["video_id"],
                "url": video["url"],
                "output_path": output_path,
                "source_line_number": video.get("source_line_number"),
            }
        )

    if test_mode:
        planned = planned[:test_limit]

    return planned, skipped


def build_yt_dlp_command(url: str, output_path: Path) -> list[str]:
    """Build the yt-dlp command for one video.

    Args:
        url: YouTube video URL.
        output_path: Output path for the downloaded .mp4 file.

    Returns:
        A subprocess-safe argument list.
    """
    return [
        "yt-dlp",
        "-f",
        YT_DLP_FORMAT,
        url,
        "-o",
        str(output_path),
    ]


def download_one_video(
        video_id: str,
        url: str,
        output_path: Path,
        timeout: int,
        max_retries: int,
        retry_delay: int = DEFAULT_RETRY_DELAY_SECONDS,
) -> dict[str, Any]:
    """Download one video with yt-dlp and return a structured result.

    This function performs external process I/O using subprocess. It catches
    per-item failures and returns a manifest-ready dictionary instead of
    raising for ordinary yt-dlp failures.

    Args:
        video_id: Unique video identifier used for reporting.
        url: YouTube URL to download.
        output_path: Destination .mp4 filepath.
        timeout: Maximum seconds allowed per yt-dlp attempt.
        max_retries: Number of retries after the first failed attempt.
        retry_delay: Seconds to wait between failed attempts.

    Returns:
        A structured result dictionary containing status, error, return code,
        timing, retry count, and command metadata.
    """
    command = build_yt_dlp_command(url, output_path)
    start_time = utc_timestamp()
    start_monotonic = time.monotonic()
    attempts_allowed = max_retries + 1
    last_error: str | None = None
    last_return_code: int | None = None
    retries_used = 0

    for attempt_number in range(1, attempts_allowed + 1):
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            last_return_code = result.returncode

            if result.returncode == 0:
                end_time = utc_timestamp()
                return {
                    "video_id": video_id,
                    "url": url,
                    "output_path": str(output_path),
                    "status": "success",
                    "error": None,
                    "return_code": result.returncode,
                    "retries": retries_used,
                    "duration_seconds": round(time.monotonic() - start_monotonic, 3),
                    "start_time": start_time,
                    "end_time": end_time,
                    "metadata": {
                        "command": command,
                        "stdout_summary": summarise_error(result.stdout) if result.stdout else None,
                    },
                }

            last_error = summarise_error(result.stderr or result.stdout)

        except subprocess.TimeoutExpired:
            last_return_code = None
            last_error = f"Download timed out after {timeout} seconds"
        except OSError as exc:
            last_return_code = None
            last_error = f"Could not run yt-dlp: {exc}"

        if attempt_number < attempts_allowed:
            retries_used += 1
            if retry_delay > 0:
                time.sleep(retry_delay)

    end_time = utc_timestamp()
    return {
        "video_id": video_id,
        "url": url,
        "output_path": str(output_path),
        "status": "failed",
        "error": last_error,
        "return_code": last_return_code,
        "retries": retries_used,
        "duration_seconds": round(time.monotonic() - start_monotonic, 3),
        "start_time": start_time,
        "end_time": end_time,
        "metadata": {
            "command": command,
        },
    }


def create_manifest(
        args: argparse.Namespace,
        run_id: str,
        start_time: str,
        end_time: str | None,
        metadata_records: int,
        unique_videos: int,
        planned_count: int,
        results: list[dict[str, Any]],
        invalid_records: list[dict[str, Any]],
        interrupted: bool = False,
) -> dict[str, Any]:
    """Create the JSON manifest object.

    Args:
        args: Parsed command-line arguments.
        run_id: Run identifier.
        start_time: Run start timestamp.
        end_time: Run end timestamp, or None while interrupted/unfinished.
        metadata_records: Count of NDJSON records read.
        unique_videos: Count of unique valid videos found.
        planned_count: Count of videos selected for attempted downloading.
        results: Per-video result dictionaries.
        invalid_records: Invalid metadata result dictionaries.
        interrupted: Whether the run was interrupted.

    Returns:
        A manifest dictionary ready to be written as JSON.
    """
    succeeded = sum(1 for item in results if item["status"] == "success")
    failed = sum(1 for item in results if item["status"] == "failed")
    skipped_existing = sum(1 for item in results if item["status"] == "skipped_existing")

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
            "output_dir": str(args.output_dir),
            "log_file": str(args.log_file),
            "manifest_file": str(args.manifest_file),
            "interrupted": interrupted,
            "config": {
                "yt_dlp_format": YT_DLP_FORMAT,
                "timeout_seconds": args.timeout,
                "max_retries": args.max_retries,
                "retry_delay_seconds": args.retry_delay,
            },
            "summary": {
                "metadata_records": metadata_records,
                "unique_videos": unique_videos,
                "planned": planned_count,
                "attempted": succeeded + failed,
                "succeeded": succeeded,
                "failed": failed,
                "skipped_existing": skipped_existing,
                "invalid_metadata": len(invalid_records),
            },
        },
        "videos": results,
        "invalid_records": invalid_records,
    }


def write_manifests(
        manifest: dict[str, Any],
        manifest_file: Path,
        run_id: str,
) -> tuple[Path, Path]:
    """Write latest and per-run manifest files.

    This function performs JSON file output.

    Args:
        manifest: Manifest dictionary to write.
        manifest_file: Path to the latest manifest file.
        run_id: Run identifier used for the per-run manifest filename.

    Returns:
        A tuple of (latest_manifest_path, per_run_manifest_path).

    Raises:
        OSError: If writing either manifest fails.
    """
    manifest_file.parent.mkdir(parents=True, exist_ok=True)

    per_run_manifest_file = manifest_file.with_name(
        f"{manifest_file.stem}_{run_id}{manifest_file.suffix}"
    )

    with manifest_file.open("w", encoding="utf-8") as output_file:
        json.dump(manifest, output_file, ensure_ascii=False, indent=2)

    with per_run_manifest_file.open("w", encoding="utf-8") as output_file:
        json.dump(manifest, output_file, ensure_ascii=False, indent=2)

    return manifest_file, per_run_manifest_file


def log_configuration(
        logger: logging.Logger,
        args: argparse.Namespace,
        run_id: str,
        yt_dlp_version: str,
) -> None:
    """Log startup configuration details.

    Args:
        logger: Configured programme logger.
        args: Parsed command-line arguments.
        run_id: Current run identifier.
        yt_dlp_version: Version string reported by yt-dlp.
    """
    logger.info("Starting %s run_id=%s", TOOL_NAME, run_id)
    logger.info("Metadata path: %s", args.metadata)
    logger.info("Output directory: %s", args.output_dir)
    logger.info("Log file: %s", args.log_file)
    logger.info("Manifest file: %s", args.manifest_file)
    logger.info("Test mode: %s; test_limit=%s", args.test_mode, args.test_limit)
    logger.info("Reprocess: %s", args.reprocess)
    logger.info("Workers: %s", args.workers)
    logger.info("Timeout seconds: %s", args.timeout)
    logger.info("Max retries: %s", args.max_retries)
    logger.info("Retry delay seconds: %s", args.retry_delay)
    logger.info("yt-dlp version: %s", yt_dlp_version)


def main() -> int:
    """Run the batch video download workflow and return an exit code.

    This function orchestrates argument parsing, validation, metadata loading,
    planning, sequential download execution, logging, manifest writing, and
    exit-code selection.

    Returns:
        Process exit code:
        - 0 for success;
        - 1 if downloads or metadata records failed;
        - 2 for configuration errors;
        - 130 for keyboard interruption.
    """
    args = parse_args()
    run_id = make_run_id()
    run_start_time = utc_timestamp()
    logger: logging.Logger | None = None

    metadata_records = 0
    unique_videos = 0
    planned_count = 0
    results: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []

    try:
        logger = setup_logging(args.log_file)
        yt_dlp_version = validate_args(args)
        log_configuration(logger, args, run_id, yt_dlp_version)

        videos, invalid_records, metadata_records = load_video_metadata(args.metadata)
        unique_videos = len(videos)

        logger.info(
            "Found %s metadata records and %s unique videos",
            metadata_records,
            unique_videos,
        )
        logger.info("Invalid metadata records: %s", len(invalid_records))

        planned, skipped_existing = plan_downloads(
            videos=videos,
            output_dir=args.output_dir,
            test_mode=args.test_mode,
            test_limit=args.test_limit,
            reprocess=args.reprocess,
        )
        planned_count = len(planned)
        results.extend(skipped_existing)

        for skipped in skipped_existing:
            logger.info(
                "SKIPPED_EXISTING %s -> %s",
                skipped["video_id"],
                skipped["output_path"],
            )

        logger.info("Planned downloads: %s", planned_count)

        for item in planned:
            logger.info(
                "Downloading %s %s -> %s",
                item["video_id"],
                item["url"],
                item["output_path"],
            )

            result = download_one_video(
                video_id=item["video_id"],
                url=item["url"],
                output_path=item["output_path"],
                timeout=args.timeout,
                max_retries=args.max_retries,
                retry_delay=args.retry_delay,
            )
            results.append(result)

            if result["status"] == "success":
                logger.info(
                    "SUCCESS %s %s -> %s",
                    result["video_id"],
                    result["url"],
                    result["output_path"],
                )
            else:
                logger.error(
                    "FAILED %s %s error=%r",
                    result["video_id"],
                    result["url"],
                    result["error"],
                )

        manifest = create_manifest(
            args=args,
            run_id=run_id,
            start_time=run_start_time,
            end_time=utc_timestamp(),
            metadata_records=metadata_records,
            unique_videos=unique_videos,
            planned_count=planned_count,
            results=results,
            invalid_records=invalid_records,
        )

        latest_manifest, per_run_manifest = write_manifests(
            manifest=manifest,
            manifest_file=args.manifest_file,
            run_id=run_id,
        )

        logger.info("Wrote latest manifest: %s", latest_manifest)
        logger.info("Wrote per-run manifest: %s", per_run_manifest)

        summary = manifest["run_metadata"]["summary"]
        logger.info(
            "Finished run: succeeded=%s failed=%s skipped_existing=%s invalid_metadata=%s",
            summary["succeeded"],
            summary["failed"],
            summary["skipped_existing"],
            summary["invalid_metadata"],
        )

        if summary["failed"] > 0 or summary["invalid_metadata"] > 0:
            return EXIT_DOWNLOAD_FAILURE

        return EXIT_SUCCESS

    except KeyboardInterrupt:
        if logger is not None:
            logger.warning("Run interrupted by user")

        manifest = create_manifest(
            args=args,
            run_id=run_id,
            start_time=run_start_time,
            end_time=utc_timestamp(),
            metadata_records=metadata_records,
            unique_videos=unique_videos,
            planned_count=planned_count,
            results=results,
            invalid_records=invalid_records,
            interrupted=True,
        )

        try:
            latest_manifest, per_run_manifest = write_manifests(
                manifest=manifest,
                manifest_file=args.manifest_file,
                run_id=run_id,
            )
            if logger is not None:
                logger.info("Wrote partial latest manifest: %s", latest_manifest)
                logger.info("Wrote partial per-run manifest: %s", per_run_manifest)
        except OSError as exc:
            if logger is not None:
                logger.error("Could not write partial manifest: %s", exc)

        return EXIT_INTERRUPTED

    except ConfigurationError as exc:
        message = f"Configuration error: {exc}"
        if logger is not None:
            logger.error(message)
        else:
            print(message, file=sys.stderr)
        return EXIT_CONFIGURATION_ERROR

    except OSError as exc:
        message = f"File-system error: {exc}"
        if logger is not None:
            logger.error(message)
        else:
            print(message, file=sys.stderr)
        return EXIT_CONFIGURATION_ERROR


if __name__ == "__main__":
    sys.exit(main())