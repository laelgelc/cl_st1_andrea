#!/usr/bin/env python3
"""
split4git.py

Safely split large files into ordered binary part files for Git-friendly storage,
then reassemble them later exactly at binary level.

The programme operates on a working directory used as both input and output. In
`disband` mode, it recursively scans the directory, finds regular files larger
than a configurable threshold, splits them into deterministic part files, and
records metadata in a JSON register. In `squad-up` mode, it reads the register,
verifies all part files, and reassembles missing or inconsistent original files.

Typical usage:

    python split4git.py disband . --threshold-mib 45 --dry-run
    python split4git.py disband . --threshold-mib 45
    python split4git.py squad-up . --dry-run
    python split4git.py squad-up .

Generated files by default:

    .split4git.register.json
    .split4git.log

Safety assumptions and limitations:

- File contents are processed in binary streaming mode.
- Symlinks are not followed by default.
- Part files are preserved during `squad-up`.
- Reassembly depends on a valid JSON register.
- The programme does not automatically edit `.gitignore`; it prints a managed
  section and stores it in the register.
- Parallel workers are accepted as an argument for future compatibility, but the
  current implementation processes files sequentially.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import stat
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOOL_NAME = "split4git.py"
TOOL_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"

DEFAULT_THRESHOLD_MIB = 45.0
MIB = 1024 * 1024
BUFFER_SIZE = 4 * MIB

DEFAULT_REGISTER_NAME = ".split4git.register.json"
DEFAULT_LOG_NAME = ".split4git.log"

GITIGNORE_BEGIN = "# BEGIN split4git managed originals"
GITIGNORE_END = "# END split4git managed originals"

EXIT_SUCCESS = 0
EXIT_PER_FILE_FAILURE = 1
EXIT_CONFIG_ERROR = 2
EXIT_REGISTER_ERROR = 3
EXIT_INTERRUPTED = 130


@dataclass
class Config:
    """Runtime configuration derived from CLI arguments.

    Attributes:
        command: Selected command, either `disband` or `squad-up`.
        working_directory: Absolute resolved working directory.
        threshold_mib: File-size threshold in MiB.
        threshold_bytes: File-size threshold in bytes.
        part_size_mib: Maximum part-file size in MiB.
        part_size_bytes: Maximum part-file size in bytes.
        dry_run: Whether to avoid filesystem modifications.
        register_file: Absolute path to the register file.
        log_file: Absolute path to the log file.
        force: Whether to allow replacing stale/conflicting generated outputs.
        keep_original: Whether to keep original files after splitting.
        workers: Number of requested workers. Current implementation is sequential.
        verbose: Whether to print detailed console output.
        quiet: Whether to reduce console output.
    """

    command: str
    working_directory: Path
    threshold_mib: float
    threshold_bytes: int
    part_size_mib: float
    part_size_bytes: int
    dry_run: bool
    register_file: Path
    log_file: Path
    force: bool
    keep_original: bool
    workers: int
    verbose: bool
    quiet: bool


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime.

    Performs no filesystem I/O.
    """

    return datetime.now(timezone.utc)


def utc_iso(dt: datetime | None = None) -> str:
    """Return an ISO-8601 UTC timestamp with a `Z` suffix.

    Args:
        dt: Optional datetime. If omitted, the current UTC time is used.

    Returns:
        UTC timestamp string.
    """

    if dt is None:
        dt = utc_now()
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def run_id_now() -> str:
    """Return a filename-safe UTC run identifier.

    Returns:
        Timestamp in `YYYYMMDDTHHMMSSZ` format.
    """

    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def print_console(message: str, config: Config | None = None, *, verbose_only: bool = False) -> None:
    """Print a console message respecting quiet and verbose flags.

    Args:
        message: Message to print.
        config: Optional runtime configuration.
        verbose_only: If true, print only when verbose mode is enabled.

    Performs console output but no filesystem writes.
    """

    if config is not None:
        if config.quiet and not verbose_only:
            return
        if verbose_only and not config.verbose:
            return
    print(message)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list. If omitted, argparse uses `sys.argv`.

    Returns:
        Parsed argparse namespace.

    Raises:
        SystemExit: Raised by argparse for invalid CLI syntax.
    """

    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Split large files into Git-friendly parts and reassemble them later.",
    )
    parser.add_argument(
        "command",
        choices=["disband", "squad-up"],
        help="Operation to perform: split files or reassemble files.",
    )
    parser.add_argument(
        "working_directory",
        help="Working directory used as both input and output.",
    )
    parser.add_argument(
        "--threshold-mib",
        type=float,
        default=DEFAULT_THRESHOLD_MIB,
        help="Split files strictly larger than this size in MiB. Default: 45.",
    )
    parser.add_argument(
        "--part-size-mib",
        type=float,
        default=None,
        help="Maximum size of each part in MiB. Default: same as --threshold-mib.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report planned actions without modifying the filesystem.",
    )
    parser.add_argument(
        "--register-file",
        default=DEFAULT_REGISTER_NAME,
        help="Register JSON path. Relative paths are resolved against the working directory.",
    )
    parser.add_argument(
        "--log-file",
        default=DEFAULT_LOG_NAME,
        help="Append-only log path. Relative paths are resolved against the working directory.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace stale generated files where safe. Does not bypass hash verification.",
    )
    parser.add_argument(
        "--keep-original",
        dest="keep_original",
        action="store_true",
        default=True,
        help="Keep original files after splitting. This is the default.",
    )
    parser.add_argument(
        "--remove-original",
        dest="keep_original",
        action="store_false",
        help="Remove original files after verified splitting and successful register write.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of workers. Current implementation processes sequentially.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed progress information.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce console output.",
    )
    return parser.parse_args(argv)


def resolve_inside_working_directory(working_directory: Path, path_value: str | Path) -> Path:
    """Resolve a path and ensure it remains inside the working directory.

    Args:
        working_directory: Absolute resolved working directory.
        path_value: Path to resolve. Relative paths are interpreted relative to
            the working directory.

    Returns:
        Absolute resolved path.

    Raises:
        ValueError: If the resolved path escapes the working directory.
    """

    path = Path(path_value)
    if not path.is_absolute():
        path = working_directory / path
    resolved = path.resolve()
    try:
        resolved.relative_to(working_directory)
    except ValueError as exc:
        raise ValueError(f"path escapes working directory: {path_value}") from exc
    return resolved


def validate_config(args: argparse.Namespace) -> Config:
    """Validate CLI arguments and construct a Config object.

    Args:
        args: Parsed argparse namespace.

    Returns:
        Validated Config object.

    Raises:
        ValueError: If any configuration value is invalid.
    """

    working_directory = Path(args.working_directory).expanduser().resolve()

    if not working_directory.exists():
        raise ValueError(f"working directory does not exist: {working_directory}")
    if not working_directory.is_dir():
        raise ValueError(f"working directory is not a directory: {working_directory}")
    if not os.access(working_directory, os.R_OK):
        raise ValueError(f"working directory is not readable: {working_directory}")
    if not args.dry_run and not os.access(working_directory, os.W_OK):
        raise ValueError(f"working directory is not writable: {working_directory}")

    if args.threshold_mib <= 0:
        raise ValueError("--threshold-mib must be greater than 0")

    part_size_mib = args.part_size_mib if args.part_size_mib is not None else args.threshold_mib
    if part_size_mib <= 0:
        raise ValueError("--part-size-mib must be greater than 0")
    if part_size_mib > args.threshold_mib:
        raise ValueError("--part-size-mib must be less than or equal to --threshold-mib")

    if args.workers < 1:
        raise ValueError("--workers must be greater than or equal to 1")

    if args.verbose and args.quiet:
        raise ValueError("--verbose and --quiet cannot be used together")

    register_file = resolve_inside_working_directory(working_directory, args.register_file)
    log_file = resolve_inside_working_directory(working_directory, args.log_file)

    return Config(
        command=args.command,
        working_directory=working_directory,
        threshold_mib=args.threshold_mib,
        threshold_bytes=int(args.threshold_mib * MIB),
        part_size_mib=part_size_mib,
        part_size_bytes=int(part_size_mib * MIB),
        dry_run=args.dry_run,
        register_file=register_file,
        log_file=log_file,
        force=args.force,
        keep_original=args.keep_original,
        workers=args.workers,
        verbose=args.verbose,
        quiet=args.quiet,
    )


def setup_logging(config: Config) -> logging.Logger:
    """Configure and return the programme logger.

    Args:
        config: Runtime configuration.

    Returns:
        Configured logger.

    Filesystem writes:
        Creates/appends the log file unless dry-run mode is enabled.
    """

    logger = logging.getLogger("split4git")
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG if config.verbose else logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not config.dry_run:
        config.log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(config.log_file, mode="a", encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)

    if not config.quiet:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG if config.verbose else logging.INFO)
        logger.addHandler(console_handler)

    if not logger.handlers:
        logger.addHandler(logging.NullHandler())

    return logger


def safe_relative_path(working_directory: Path, path: Path) -> str:
    """Return a safe POSIX-style relative path from the working directory.

    Args:
        working_directory: Absolute resolved working directory.
        path: Absolute path inside the working directory.

    Returns:
        POSIX-style relative path.

    Raises:
        ValueError: If the path is outside the working directory.
    """

    resolved = path.resolve()
    rel = resolved.relative_to(working_directory)
    return rel.as_posix()


def validate_register_relative_path(relative_path: str) -> None:
    """Validate that a register path is safe and relative.

    Args:
        relative_path: POSIX-style relative path from the register.

    Raises:
        ValueError: If the path is absolute, empty, contains traversal, or is unsafe.
    """

    if not relative_path:
        raise ValueError("empty relative path")
    path = Path(relative_path)
    if path.is_absolute():
        raise ValueError(f"absolute paths are not allowed: {relative_path}")
    parts = path.parts
    if ".." in parts:
        raise ValueError(f"path traversal is not allowed: {relative_path}")


def path_from_register(working_directory: Path, relative_path: str) -> Path:
    """Resolve a safe register-relative path inside the working directory.

    Args:
        working_directory: Absolute resolved working directory.
        relative_path: Register path using `/` separators.

    Returns:
        Absolute path inside the working directory.

    Raises:
        ValueError: If the path is unsafe or escapes the working directory.
    """

    validate_register_relative_path(relative_path)
    resolved = (working_directory / Path(relative_path)).resolve()
    try:
        resolved.relative_to(working_directory)
    except ValueError as exc:
        raise ValueError(f"registered path escapes working directory: {relative_path}") from exc
    return resolved


def is_part_file(path: Path) -> bool:
    """Return whether a path appears to be a split4git part file.

    Args:
        path: Path to inspect.

    Returns:
        True if the filename contains the managed part marker.
    """

    return ".split4git.part" in path.name


def is_managed_temp_or_backup(path: Path) -> bool:
    """Return whether a path is a split4git temporary or backup file.

    Args:
        path: Path to inspect.

    Returns:
        True for known temporary, reassembly, register-temp, or backup files.
    """

    name = path.name
    return (
            name.endswith(".tmp")
            or ".split4git.reassemble.tmp" in name
            or ".split4git.inconsistent." in name
            or name == f"{DEFAULT_REGISTER_NAME}.tmp"
    )


def is_excluded_path(path: Path, config: Config) -> bool:
    """Return whether a path should be excluded from discovery.

    Args:
        path: Candidate filesystem path.
        config: Runtime configuration.

    Returns:
        True if the path is programme-managed or unsafe to process.
    """

    if ".git" in path.parts:
        return True

    resolved = path.resolve()
    if resolved == config.register_file:
        return True
    if resolved == config.log_file:
        return True

    if is_part_file(path):
        return True
    if is_managed_temp_or_backup(path):
        return True

    return False


def discover_files(config: Config) -> list[Path]:
    """Recursively discover regular candidate files.

    Args:
        config: Runtime configuration.

    Returns:
        Sorted list of absolute file paths.

    Filesystem writes:
        None.
    """

    discovered: list[Path] = []

    for root, dirs, files in os.walk(config.working_directory, followlinks=False):
        root_path = Path(root)

        dirs[:] = [
            d for d in dirs
            if d != ".git" and not (root_path / d).is_symlink()
        ]

        for filename in files:
            path = root_path / filename

            if path.is_symlink():
                continue
            if is_excluded_path(path, config):
                continue

            try:
                mode = path.lstat().st_mode
            except OSError:
                continue

            if not stat.S_ISREG(mode):
                continue

            discovered.append(path.resolve())

    return sorted(discovered, key=lambda item: safe_relative_path(config.working_directory, item))


def hash_file(path: Path, buffer_size: int = BUFFER_SIZE) -> str:
    """Compute a file's SHA-256 digest in streaming mode.

    Args:
        path: File to hash.
        buffer_size: Number of bytes to read per chunk.

    Returns:
        Lowercase hexadecimal SHA-256 digest.

    Filesystem writes:
        None.

    Raises:
        OSError: If the file cannot be read.
    """

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(buffer_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def load_register(config: Config, *, required: bool) -> dict[str, Any]:
    """Load and minimally validate the JSON register.

    Args:
        config: Runtime configuration.
        required: Whether absence of the register is an error.

    Returns:
        Register dictionary. If not required and missing, returns a new register.

    Filesystem writes:
        None.

    Raises:
        FileNotFoundError: If required and missing.
        ValueError: If JSON is malformed or incompatible.
    """

    if not config.register_file.exists():
        if required:
            raise FileNotFoundError(f"register file not found: {config.register_file}")
        return new_register(config)

    try:
        with config.register_file.open("r", encoding="utf-8") as handle:
            register = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed register JSON: {exc}") from exc

    if not isinstance(register, dict):
        raise ValueError("register root must be a JSON object")

    schema_version = register.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ValueError(f"unsupported register schema version: {schema_version!r}")

    files = register.get("files", [])
    if not isinstance(files, list):
        raise ValueError("register field 'files' must be a list")

    for entry in files:
        if not isinstance(entry, dict):
            raise ValueError("each register file entry must be an object")
        original_relative_path = entry.get("original_relative_path")
        if not isinstance(original_relative_path, str):
            raise ValueError("register file entry missing original_relative_path")
        path_from_register(config.working_directory, original_relative_path)

        parts = entry.get("parts", [])
        if not isinstance(parts, list):
            raise ValueError(f"parts must be a list for {original_relative_path}")
        for part in parts:
            if not isinstance(part, dict):
                raise ValueError(f"part entry must be an object for {original_relative_path}")
            part_relative_path = part.get("relative_path")
            if not isinstance(part_relative_path, str):
                raise ValueError(f"part missing relative_path for {original_relative_path}")
            path_from_register(config.working_directory, part_relative_path)

    register.setdefault("runs", [])
    register.setdefault("files", [])
    return register


def new_register(config: Config) -> dict[str, Any]:
    """Create a new empty register object.

    Args:
        config: Runtime configuration.

    Returns:
        Register dictionary.

    Filesystem writes:
        None.
    """

    now = utc_iso()
    return {
        "schema_version": SCHEMA_VERSION,
        "tool_name": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "working_directory": str(config.working_directory),
        "created_at": now,
        "updated_at": now,
        "config": {
            "threshold_mib": config.threshold_mib,
            "threshold_bytes": config.threshold_bytes,
            "part_size_mib": config.part_size_mib,
            "part_size_bytes": config.part_size_bytes,
        },
        "gitignore_section": None,
        "files": [],
        "runs": [],
    }


def write_register_atomic(config: Config, register: dict[str, Any]) -> None:
    """Atomically write the register JSON.

    Args:
        config: Runtime configuration.
        register: Register object to persist.

    Filesystem writes:
        Writes a temporary JSON file and atomically replaces the register.

    Raises:
        OSError: If writing or replacing fails.
    """

    register["updated_at"] = utc_iso()
    register["working_directory"] = str(config.working_directory)
    register["tool_name"] = TOOL_NAME
    register["tool_version"] = TOOL_VERSION
    register["schema_version"] = SCHEMA_VERSION
    register["config"] = {
        "threshold_mib": config.threshold_mib,
        "threshold_bytes": config.threshold_bytes,
        "part_size_mib": config.part_size_mib,
        "part_size_bytes": config.part_size_bytes,
    }

    config.register_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = config.register_file.with_name(config.register_file.name + ".tmp")

    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(register, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())

    os.replace(tmp_path, config.register_file)


def find_git_root(start: Path) -> Path | None:
    """Find the nearest Git repository root above a path.

    Args:
        start: Directory from which to search upwards.

    Returns:
        Repository root path, or None if not found.

    Filesystem writes:
        None.
    """

    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def gitignore_path_for_original(config: Config, original_path: Path, git_root: Path | None) -> str:
    """Return a `.gitignore` entry for an original file.

    Args:
        config: Runtime configuration.
        original_path: Absolute original-file path.
        git_root: Git repository root if detected.

    Returns:
        Slash-prefixed POSIX-style ignore path.
    """

    base = git_root if git_root is not None else config.working_directory
    try:
        rel = original_path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        rel = original_path.resolve().relative_to(config.working_directory).as_posix()
    return f"/{rel}"


def generate_gitignore_section(config: Config, register: dict[str, Any]) -> tuple[list[str], Path | None]:
    """Generate deterministic `.gitignore` guidance.

    Args:
        config: Runtime configuration.
        register: Register containing original file entries.

    Returns:
        Tuple of section lines and detected Git root, if any.

    Filesystem writes:
        None.
    """

    git_root = find_git_root(config.working_directory)
    entries: list[str] = []

    for entry in register.get("files", []):
        if entry.get("status") != "split":
            continue
        relative_path = entry.get("original_relative_path")
        if not isinstance(relative_path, str):
            continue
        original_path = path_from_register(config.working_directory, relative_path)
        entries.append(gitignore_path_for_original(config, original_path, git_root))

    unique_entries = sorted(set(entries))
    return [GITIGNORE_BEGIN, *unique_entries, GITIGNORE_END], git_root


def part_count_for_size(file_size: int, part_size: int) -> int:
    """Calculate the number of parts needed for a file.

    Args:
        file_size: Original file size in bytes.
        part_size: Part size in bytes.

    Returns:
        Number of required parts.
    """

    return (file_size + part_size - 1) // part_size


def part_paths_for(original: Path, file_size: int, part_size: int) -> list[Path]:
    """Generate deterministic part paths for an original file.

    Args:
        original: Original file path.
        file_size: Original file size in bytes.
        part_size: Maximum part size in bytes.

    Returns:
        Ordered list of part paths.

    Filesystem writes:
        None.
    """

    count = part_count_for_size(file_size, part_size)
    width = max(4, len(str(count)))
    return [
        original.with_name(f"{original.name}.split4git.part{index:0{width}d}")
        for index in range(1, count + 1)
    ]


def find_register_entry(register: dict[str, Any], original_relative_path: str) -> dict[str, Any] | None:
    """Find a register entry by original relative path.

    Args:
        register: Register object.
        original_relative_path: POSIX-style original path.

    Returns:
        Matching entry or None.
    """

    for entry in register.get("files", []):
        if entry.get("original_relative_path") == original_relative_path:
            return entry
    return None


def verify_registered_parts(config: Config, entry: dict[str, Any]) -> tuple[bool, str | None]:
    """Verify registered part existence, ordering, sizes, and hashes.

    Args:
        config: Runtime configuration.
        entry: Register entry for one original file.

    Returns:
        `(True, None)` if all checks pass, otherwise `(False, reason)`.

    Filesystem writes:
        None.
    """

    original_relative_path = entry.get("original_relative_path", "<unknown>")
    parts = entry.get("parts")

    if not isinstance(parts, list) or not parts:
        return False, f"{original_relative_path}: missing or empty parts list"

    expected_indexes = list(range(1, len(parts) + 1))
    actual_indexes = [part.get("index") for part in parts]
    if actual_indexes != expected_indexes:
        return False, f"{original_relative_path}: part indexes are not complete and ordered"

    total_size = 0

    for part in parts:
        relative_path = part.get("relative_path")
        expected_size = part.get("size_bytes")
        expected_hash = part.get("sha256")

        if not isinstance(relative_path, str):
            return False, f"{original_relative_path}: part has invalid relative_path"
        if not isinstance(expected_size, int) or expected_size < 0:
            return False, f"{original_relative_path}: part has invalid size_bytes"
        if not isinstance(expected_hash, str):
            return False, f"{original_relative_path}: part has invalid sha256"

        try:
            part_path = path_from_register(config.working_directory, relative_path)
        except ValueError as exc:
            return False, str(exc)

        if part_path.is_symlink():
            return False, f"{relative_path}: symlink part files are not allowed"
        if not part_path.exists():
            return False, f"{relative_path}: part file is missing"
        if not part_path.is_file():
            return False, f"{relative_path}: part path is not a regular file"

        actual_size = part_path.stat().st_size
        if actual_size != expected_size:
            return False, f"{relative_path}: size mismatch"

        actual_hash = hash_file(part_path)
        if actual_hash != expected_hash:
            return False, f"{relative_path}: SHA-256 mismatch"

        total_size += actual_size

    expected_total = entry.get("original_size_bytes")
    if total_size != expected_total:
        return False, f"{original_relative_path}: sum of part sizes does not match original size"

    return True, None


def registered_entry_is_consistent(config: Config, entry: dict[str, Any], original_path: Path) -> bool:
    """Check whether an existing register entry still matches the original and parts.

    Args:
        config: Runtime configuration.
        entry: Register entry.
        original_path: Original path on disk.

    Returns:
        True if original metadata and part metadata are consistent.

    Filesystem writes:
        None.
    """

    if not original_path.exists() or not original_path.is_file() or original_path.is_symlink():
        return False

    try:
        original_size = original_path.stat().st_size
        original_sha256 = hash_file(original_path)
    except OSError:
        return False

    if original_size != entry.get("original_size_bytes"):
        return False
    if original_sha256 != entry.get("original_sha256"):
        return False

    ok, _ = verify_registered_parts(config, entry)
    return ok


def plan_disband(config: Config, register: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Create a non-mutating split plan.

    Args:
        config: Runtime configuration.
        register: Existing or new register.

    Returns:
        Tuple of plan entries and discovery summary.

    Filesystem writes:
        None.
    """

    discovered = discover_files(config)
    plan: list[dict[str, Any]] = []
    eligible = 0
    skipped_below_threshold = 0
    skipped_already_split = 0
    conflicts = 0

    for path in discovered:
        try:
            size = path.stat().st_size
        except OSError as exc:
            plan.append({"action": "failed", "path": path, "status": "failed_io", "error": str(exc)})
            conflicts += 1
            continue

        if size <= config.threshold_bytes:
            skipped_below_threshold += 1
            continue

        eligible += 1
        original_relative_path = safe_relative_path(config.working_directory, path)
        existing_entry = find_register_entry(register, original_relative_path)

        if existing_entry is not None and registered_entry_is_consistent(config, existing_entry, path):
            plan.append({
                "action": "skip",
                "path": path,
                "relative_path": original_relative_path,
                "status": "skipped_already_split",
                "reason": "existing register entry and parts are consistent",
            })
            skipped_already_split += 1
            continue

        parts = part_paths_for(path, size, config.part_size_bytes)
        planned_conflicts: list[str] = []

        for part_path in parts:
            if part_path.exists() and not config.force:
                planned_conflicts.append(safe_relative_path(config.working_directory, part_path))

        if existing_entry is not None and not config.force:
            planned_conflicts.append("stale or inconsistent register entry exists; use --force to replace")

        if planned_conflicts:
            plan.append({
                "action": "failed",
                "path": path,
                "relative_path": original_relative_path,
                "status": "failed_conflict",
                "error": "; ".join(planned_conflicts),
            })
            conflicts += 1
            continue

        part_details = []
        for index, part_path in enumerate(parts, start=1):
            remaining = size - ((index - 1) * config.part_size_bytes)
            planned_size = min(config.part_size_bytes, remaining)
            part_details.append({
                "index": index,
                "path": part_path,
                "relative_path": safe_relative_path(config.working_directory, part_path),
                "planned_size_bytes": planned_size,
            })

        plan.append({
            "action": "split",
            "path": path,
            "relative_path": original_relative_path,
            "size_bytes": size,
            "parts": part_details,
            "status": "planned_split",
        })

    summary = {
        "discovered": len(discovered),
        "eligible": eligible,
        "skipped_below_threshold": skipped_below_threshold,
        "skipped_already_split": skipped_already_split,
        "conflicts": conflicts,
    }
    return plan, summary


def split_file(config: Config, original_path: Path, planned_parts: list[dict[str, Any]]) -> dict[str, Any]:
    """Split one file into verified binary part files.

    Args:
        config: Runtime configuration.
        original_path: File to split.
        planned_parts: Ordered planned part metadata from `plan_disband`.

    Returns:
        Register entry for the split file.

    Filesystem writes:
        Writes temporary part files and atomically renames them to final paths.

    Raises:
        OSError: For read/write/rename errors.
        ValueError: If post-write verification fails.
    """

    original_stat = original_path.stat()
    original_size = original_stat.st_size
    original_hash = hashlib.sha256()
    written_parts: list[dict[str, Any]] = []
    temp_paths: list[Path] = []

    try:
        with original_path.open("rb") as source:
            for part in planned_parts:
                index = part["index"]
                final_path = part["path"]
                temp_path = final_path.with_name(final_path.name + ".tmp")

                if final_path.exists() and config.force:
                    final_path.unlink()
                elif final_path.exists():
                    raise FileExistsError(f"part already exists: {final_path}")

                temp_paths.append(temp_path)
                bytes_remaining = part["planned_size_bytes"]
                part_hash = hashlib.sha256()
                part_size = 0

                with temp_path.open("wb") as target:
                    while bytes_remaining > 0:
                        chunk = source.read(min(BUFFER_SIZE, bytes_remaining))
                        if not chunk:
                            break
                        target.write(chunk)
                        original_hash.update(chunk)
                        part_hash.update(chunk)
                        part_size += len(chunk)
                        bytes_remaining -= len(chunk)

                    target.flush()
                    os.fsync(target.fileno())

                if part_size != part["planned_size_bytes"]:
                    raise ValueError(f"part size mismatch while writing {final_path}")

                actual_temp_hash = hash_file(temp_path)
                if actual_temp_hash != part_hash.hexdigest():
                    raise ValueError(f"part hash mismatch after writing {temp_path}")

                os.replace(temp_path, final_path)
                temp_paths.remove(temp_path)

                written_parts.append({
                    "index": index,
                    "relative_path": safe_relative_path(config.working_directory, final_path),
                    "size_bytes": part_size,
                    "sha256": part_hash.hexdigest(),
                })

        original_sha256 = original_hash.hexdigest()

        if sum(part["size_bytes"] for part in written_parts) != original_size:
            raise ValueError("sum of written part sizes does not equal original size")

        for part in written_parts:
            part_path = path_from_register(config.working_directory, part["relative_path"])
            if hash_file(part_path) != part["sha256"]:
                raise ValueError(f"final part hash verification failed: {part['relative_path']}")

        return {
            "original_relative_path": safe_relative_path(config.working_directory, original_path),
            "original_size_bytes": original_size,
            "original_sha256": original_sha256,
            "status": "split",
            "split_at": utc_iso(),
            "part_size_bytes": config.part_size_bytes,
            "parts": written_parts,
            "metadata": {
                "part_count": len(written_parts),
                "original_mtime_ns": original_stat.st_mtime_ns,
                "original_mode": f"{stat.S_IMODE(original_stat.st_mode):04o}",
            },
        }

    except Exception:
        for temp_path in temp_paths:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
        raise


def update_register_file_entry(register: dict[str, Any], entry: dict[str, Any]) -> None:
    """Insert or replace a file entry in the register.

    Args:
        register: Register object.
        entry: File entry to insert.

    Filesystem writes:
        None.
    """

    original_relative_path = entry["original_relative_path"]
    files = register.setdefault("files", [])
    for index, existing in enumerate(files):
        if existing.get("original_relative_path") == original_relative_path:
            files[index] = entry
            return
    files.append(entry)


def remove_originals_after_register_write(config: Config, successful_entries: list[dict[str, Any]], logger: logging.Logger) -> None:
    """Remove originals after split verification and register persistence.

    Args:
        config: Runtime configuration.
        successful_entries: Entries whose originals may be removed.
        logger: Logger for recording removals and failures.

    Filesystem writes:
        Deletes original files only when `--remove-original` was requested.
    """

    if config.keep_original:
        return

    for entry in successful_entries:
        relative_path = entry["original_relative_path"]
        original_path = path_from_register(config.working_directory, relative_path)
        try:
            if original_path.exists():
                if hash_file(original_path) != entry["original_sha256"]:
                    logger.error("Refusing to remove modified original: %s", relative_path)
                    continue
                original_path.unlink()
                logger.info("Removed original after verified split: %s", relative_path)
        except OSError as exc:
            logger.error("Failed to remove original %s: %s", relative_path, exc)


def append_run(register: dict[str, Any], run_record: dict[str, Any]) -> None:
    """Append a non-dry-run execution record to the register.

    Args:
        register: Register object.
        run_record: Run metadata to append.

    Filesystem writes:
        None.
    """

    register.setdefault("runs", []).append(run_record)


def command_disband(config: Config, logger: logging.Logger) -> int:
    """Execute the `disband` command.

    Args:
        config: Runtime configuration.
        logger: Configured logger.

    Returns:
        Process exit code.

    Filesystem writes:
        In non-dry-run mode, writes part files, register, and log entries.
    """

    try:
        register = load_register(config, required=False)
    except Exception as exc:
        print_console(f"Register error: {exc}", config)
        logger.error("Register error: %s", exc)
        return EXIT_REGISTER_ERROR

    plan, summary = plan_disband(config, register)

    print_console(f"Working directory: {config.working_directory}", config)
    print_console(f"Threshold: {config.threshold_mib} MiB ({config.threshold_bytes} bytes)", config)
    print_console(f"Part size: {config.part_size_mib} MiB ({config.part_size_bytes} bytes)", config)
    print_console(f"Discovered files: {summary['discovered']}", config)
    print_console(f"Eligible files: {summary['eligible']}", config)

    for item in plan:
        rel = item.get("relative_path") or safe_relative_path(config.working_directory, item["path"])
        if item["action"] == "split":
            print_console(f"PLAN split: {rel}", config)
            print_console(f"  parts: {len(item['parts'])}", config, verbose_only=True)
            for part in item["parts"]:
                print_console(
                    f"    {part['relative_path']} ({part['planned_size_bytes']} bytes)",
                    config,
                    verbose_only=True,
                )
        elif item["action"] == "skip":
            print_console(f"SKIP {rel}: {item.get('reason')}", config)
        elif item["action"] == "failed":
            print_console(f"CONFLICT/FAIL {rel}: {item.get('error')}", config)

    if config.dry_run:
        dry_register = json.loads(json.dumps(register))
        for item in plan:
            if item["action"] == "split":
                placeholder_entry = {
                    "original_relative_path": item["relative_path"],
                    "status": "split",
                    "parts": [
                        {"relative_path": part["relative_path"]}
                        for part in item["parts"]
                    ],
                }
                update_register_file_entry(dry_register, placeholder_entry)

        section, git_root = generate_gitignore_section(config, dry_register)
        print_gitignore_section(config, section, git_root)
        print_console("Dry run complete: no files were modified.", config)
        return EXIT_PER_FILE_FAILURE if summary["conflicts"] else EXIT_SUCCESS

    run_id = run_id_now()
    start_time = utc_iso()
    file_results: list[dict[str, Any]] = []
    successful_entries: list[dict[str, Any]] = []
    failed = 0
    processed = 0
    skipped = 0

    for item in plan:
        relative_path = item.get("relative_path") or safe_relative_path(config.working_directory, item["path"])
        started = time.monotonic()

        if item["action"] == "skip":
            skipped += 1
            logger.info("SKIPPED_ALREADY_SPLIT %s", relative_path)
            file_results.append({
                "relative_path": relative_path,
                "status": item["status"],
                "error": None,
                "duration_seconds": round(time.monotonic() - started, 3),
                "metadata": {},
            })
            continue

        if item["action"] == "failed":
            failed += 1
            logger.error("FAILED %s: %s", relative_path, item.get("error"))
            file_results.append({
                "relative_path": relative_path,
                "status": item["status"],
                "error": item.get("error"),
                "duration_seconds": round(time.monotonic() - started, 3),
                "metadata": {},
            })
            continue

        try:
            logger.info("SPLITTING %s", relative_path)
            entry = split_file(config, item["path"], item["parts"])
            update_register_file_entry(register, entry)
            successful_entries.append(entry)
            processed += 1
            logger.info("SUCCESS %s parts=%d", relative_path, len(entry["parts"]))
            file_results.append({
                "relative_path": relative_path,
                "status": "success",
                "error": None,
                "duration_seconds": round(time.monotonic() - started, 3),
                "metadata": {
                    "parts_written": len(entry["parts"]),
                },
            })
        except Exception as exc:
            failed += 1
            logger.error("FAILED %s: %s", relative_path, exc)
            file_results.append({
                "relative_path": relative_path,
                "status": "failed_io",
                "error": str(exc),
                "duration_seconds": round(time.monotonic() - started, 3),
                "metadata": {},
            })

    section, git_root = generate_gitignore_section(config, register)
    register["gitignore_section"] = {
        "begin_marker": GITIGNORE_BEGIN,
        "end_marker": GITIGNORE_END,
        "content": section,
        "generated_at": utc_iso(),
    }

    status = "success" if failed == 0 else ("partial_success" if processed or skipped else "failed")
    run_record = {
        "run_id": run_id,
        "command": "disband",
        "dry_run": False,
        "start_time": start_time,
        "end_time": utc_iso(),
        "status": status,
        "summary": {
            "discovered": summary["discovered"],
            "eligible": summary["eligible"],
            "processed": processed,
            "skipped": skipped,
            "failed": failed,
        },
        "files": file_results,
    }
    append_run(register, run_record)

    try:
        write_register_atomic(config, register)
        logger.info("Register written: %s", config.register_file)
    except Exception as exc:
        logger.error("Failed to write register: %s", exc)
        print_console(f"Failed to write register: {exc}", config)
        return EXIT_REGISTER_ERROR

    remove_originals_after_register_write(config, successful_entries, logger)

    print_gitignore_section(config, section, git_root)
    print_console(
        f"Summary: processed={processed}, skipped={skipped}, failed={failed}",
        config,
    )

    return EXIT_PER_FILE_FAILURE if failed else EXIT_SUCCESS


def print_gitignore_section(config: Config, section: list[str], git_root: Path | None) -> None:
    """Print generated `.gitignore` guidance.

    Args:
        config: Runtime configuration.
        section: Lines of the generated section.
        git_root: Detected Git repository root, if any.

    Filesystem writes:
        None.
    """

    if config.quiet:
        return

    print()
    if git_root is not None:
        print(f"Repository root detected at: {git_root}")
        print("Add the following section to your repository root .gitignore:")
    else:
        print("No Git repository root was detected.")
        print("The following entries are relative to the working directory:")
    print()
    for line in section:
        print(line)
    print()


def original_is_consistent(original_path: Path, entry: dict[str, Any]) -> bool:
    """Check whether an original file exists and matches registered metadata.

    Args:
        original_path: Original path to check.
        entry: Register entry.

    Returns:
        True if the original's size and SHA-256 match the register.

    Filesystem writes:
        None.
    """

    if original_path.is_symlink():
        return False
    if not original_path.exists() or not original_path.is_file():
        return False
    if original_path.stat().st_size != entry.get("original_size_bytes"):
        return False
    return hash_file(original_path) == entry.get("original_sha256")


def backup_path_for_inconsistent_original(original_path: Path, run_id: str) -> Path:
    """Create a non-existing backup path for an inconsistent original.

    Args:
        original_path: Existing inconsistent original.
        run_id: Current run identifier.

    Returns:
        Backup path that does not currently exist.

    Filesystem writes:
        None.
    """

    base = original_path.with_name(f"{original_path.name}.split4git.inconsistent.{run_id}.bak")
    if not base.exists():
        return base

    counter = 1
    while True:
        candidate = original_path.with_name(
            f"{original_path.name}.split4git.inconsistent.{run_id}.{counter:03d}.bak"
        )
        if not candidate.exists():
            return candidate
        counter += 1


def plan_squad_up(config: Config, register: dict[str, Any], run_id: str) -> list[dict[str, Any]]:
    """Create a non-mutating reassembly plan.

    Args:
        config: Runtime configuration.
        register: Valid register.
        run_id: Current run identifier for backup path planning.

    Returns:
        Ordered plan entries.

    Filesystem writes:
        None.
    """

    entries = sorted(
        register.get("files", []),
        key=lambda item: item.get("original_relative_path", ""),
    )
    plan: list[dict[str, Any]] = []

    for entry in entries:
        relative_path = entry.get("original_relative_path")

        if not isinstance(relative_path, str):
            plan.append({
                "action": "failed",
                "entry": entry,
                "relative_path": "<invalid>",
                "status": "failed_register",
                "error": "missing original_relative_path",
            })
            continue

        try:
            original_path = path_from_register(config.working_directory, relative_path)
        except ValueError as exc:
            plan.append({
                "action": "failed",
                "entry": entry,
                "relative_path": relative_path,
                "status": "failed_register",
                "error": str(exc),
            })
            continue

        ok, reason = verify_registered_parts(config, entry)
        if not ok:
            status = "failed_missing_part" if reason and "missing" in reason.lower() else "failed_part_integrity"
            plan.append({
                "action": "failed",
                "entry": entry,
                "relative_path": relative_path,
                "status": status,
                "error": reason,
            })
            continue

        if original_path.exists():
            if original_is_consistent(original_path, entry):
                plan.append({
                    "action": "skip",
                    "entry": entry,
                    "relative_path": relative_path,
                    "status": "skipped_existing_consistent",
                    "reason": "original already exists and matches register",
                })
            else:
                backup_path = backup_path_for_inconsistent_original(original_path, run_id)
                plan.append({
                    "action": "reassemble",
                    "entry": entry,
                    "relative_path": relative_path,
                    "status": "planned_reassemble_with_backup",
                    "backup_path": backup_path,
                    "temp_path": original_path.with_name(f"{original_path.name}.split4git.reassemble.tmp"),
                })
        else:
            plan.append({
                "action": "reassemble",
                "entry": entry,
                "relative_path": relative_path,
                "status": "planned_reassemble",
                "backup_path": None,
                "temp_path": original_path.with_name(f"{original_path.name}.split4git.reassemble.tmp"),
            })

    return plan


def reassemble_file(config: Config, entry: dict[str, Any], backup_path: Path | None) -> None:
    """Reassemble one original file from verified part files.

    Args:
        config: Runtime configuration.
        entry: Register entry for one original.
        backup_path: Backup destination if an inconsistent original exists.

    Filesystem writes:
        May rename an inconsistent original, write a temporary reassembly file,
        and atomically move it into place. It never modifies part files.

    Raises:
        OSError: For file operation errors.
        ValueError: If final size or hash verification fails.
    """

    relative_path = entry["original_relative_path"]
    original_path = path_from_register(config.working_directory, relative_path)
    temp_path = original_path.with_name(f"{original_path.name}.split4git.reassemble.tmp")

    if temp_path.exists():
        if config.force:
            temp_path.unlink()
        else:
            raise FileExistsError(f"temporary reassembly file already exists: {temp_path}")

    original_path.parent.mkdir(parents=True, exist_ok=True)

    if original_path.exists():
        if backup_path is None:
            if original_is_consistent(original_path, entry):
                return
            raise ValueError(f"original exists but no backup path was provided: {relative_path}")
        os.replace(original_path, backup_path)

    digest = hashlib.sha256()
    total_size = 0

    try:
        with temp_path.open("wb") as target:
            for part in sorted(entry["parts"], key=lambda item: item["index"]):
                part_path = path_from_register(config.working_directory, part["relative_path"])
                with part_path.open("rb") as source:
                    while True:
                        chunk = source.read(BUFFER_SIZE)
                        if not chunk:
                            break
                        target.write(chunk)
                        digest.update(chunk)
                        total_size += len(chunk)

            target.flush()
            os.fsync(target.fileno())

        if total_size != entry["original_size_bytes"]:
            raise ValueError(f"reassembled size mismatch for {relative_path}")

        if digest.hexdigest() != entry["original_sha256"]:
            raise ValueError(f"reassembled SHA-256 mismatch for {relative_path}")

        if hash_file(temp_path) != entry["original_sha256"]:
            raise ValueError(f"final temporary-file hash verification failed for {relative_path}")

        metadata = entry.get("metadata", {})
        mode_text = metadata.get("original_mode")
        if isinstance(mode_text, str):
            try:
                os.chmod(temp_path, int(mode_text, 8))
            except OSError:
                pass

        mtime_ns = metadata.get("original_mtime_ns")
        if isinstance(mtime_ns, int):
            try:
                os.utime(temp_path, ns=(mtime_ns, mtime_ns))
            except OSError:
                pass

        os.replace(temp_path, original_path)

    except Exception:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass
        raise


def command_squad_up(config: Config, logger: logging.Logger) -> int:
    """Execute the `squad-up` command.

    Args:
        config: Runtime configuration.
        logger: Configured logger.

    Returns:
        Process exit code.

    Filesystem writes:
        In non-dry-run mode, may write originals, backup inconsistent originals,
        update the register, and append logs. Part files are preserved unchanged.
    """

    try:
        register = load_register(config, required=True)
    except FileNotFoundError as exc:
        print_console(str(exc), config)
        logger.error("%s", exc)
        return EXIT_REGISTER_ERROR
    except Exception as exc:
        print_console(f"Register error: {exc}", config)
        logger.error("Register error: %s", exc)
        return EXIT_REGISTER_ERROR

    run_id = run_id_now()
    plan = plan_squad_up(config, register, run_id)

    print_console(f"Register: {config.register_file}", config)
    print_console(f"Registered files: {len(register.get('files', []))}", config)

    for item in plan:
        rel = item["relative_path"]
        if item["action"] == "skip":
            print_console(f"SKIP {rel}: original already consistent; parts verified and preserved", config)
        elif item["action"] == "reassemble":
            backup_path = item.get("backup_path")
            if backup_path is not None:
                backup_rel = safe_relative_path(config.working_directory, backup_path)
                print_console(f"PLAN reassemble {rel}; inconsistent original would be backed up to {backup_rel}", config)
            else:
                print_console(f"PLAN reassemble {rel}", config)
            print_console(
                f"  temp: {safe_relative_path(config.working_directory, item['temp_path'])}",
                config,
                verbose_only=True,
            )
        elif item["action"] == "failed":
            print_console(f"FAIL {rel}: {item.get('error')}", config)

    if config.dry_run:
        print_console("Dry run complete: no files were modified.", config)
        return EXIT_PER_FILE_FAILURE if any(item["action"] == "failed" for item in plan) else EXIT_SUCCESS

    start_time = utc_iso()
    file_results: list[dict[str, Any]] = []
    processed = 0
    skipped = 0
    failed = 0

    for item in plan:
        started = time.monotonic()
        relative_path = item["relative_path"]

        if item["action"] == "failed":
            failed += 1
            logger.error("FAILED %s: %s", relative_path, item.get("error"))
            file_results.append({
                "relative_path": relative_path,
                "status": item["status"],
                "error": item.get("error"),
                "duration_seconds": round(time.monotonic() - started, 3),
                "metadata": {"part_files_preserved": True},
            })
            continue

        if item["action"] == "skip":
            skipped += 1
            logger.info("SKIPPED_EXISTING_CONSISTENT %s", relative_path)
            file_results.append({
                "relative_path": relative_path,
                "status": "skipped_existing_consistent",
                "error": None,
                "duration_seconds": round(time.monotonic() - started, 3),
                "metadata": {
                    "parts_verified": len(item["entry"].get("parts", [])),
                    "part_files_preserved": True,
                },
            })
            continue

        try:
            logger.info("REASSEMBLING %s", relative_path)
            reassemble_file(config, item["entry"], item.get("backup_path"))
            processed += 1
            logger.info("SUCCESS_REASSEMBLED %s", relative_path)
            file_results.append({
                "relative_path": relative_path,
                "status": "success_reassembled",
                "error": None,
                "duration_seconds": round(time.monotonic() - started, 3),
                "metadata": {
                    "parts_verified": len(item["entry"].get("parts", [])),
                    "part_files_preserved": True,
                    "backup_path": (
                        safe_relative_path(config.working_directory, item["backup_path"])
                        if item.get("backup_path") is not None
                        else None
                    ),
                },
            })
        except Exception as exc:
            failed += 1
            logger.error("FAILED_REASSEMBLY %s: %s", relative_path, exc)
            file_results.append({
                "relative_path": relative_path,
                "status": "failed_reassembly",
                "error": str(exc),
                "duration_seconds": round(time.monotonic() - started, 3),
                "metadata": {"part_files_preserved": True},
            })

    status = "success" if failed == 0 else ("partial_success" if processed or skipped else "failed")
    run_record = {
        "run_id": run_id,
        "command": "squad-up",
        "dry_run": False,
        "start_time": start_time,
        "end_time": utc_iso(),
        "status": status,
        "summary": {
            "registered": len(register.get("files", [])),
            "processed": processed,
            "skipped": skipped,
            "failed": failed,
        },
        "files": file_results,
    }
    append_run(register, run_record)

    try:
        write_register_atomic(config, register)
        logger.info("Register written: %s", config.register_file)
    except Exception as exc:
        logger.error("Failed to write register: %s", exc)
        print_console(f"Failed to write register: {exc}", config)
        return EXIT_REGISTER_ERROR

    print_console(
        f"Summary: reassembled={processed}, skipped={skipped}, failed={failed}; part files preserved",
        config,
    )

    return EXIT_PER_FILE_FAILURE if failed else EXIT_SUCCESS


def main(argv: list[str] | None = None) -> int:
    """Programme entry point.

    Args:
        argv: Optional argument list.

    Returns:
        Process exit code.

    Filesystem writes:
        Depends on selected command and dry-run setting.
    """

    try:
        args = parse_args(argv)
        config = validate_config(args)
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    logger = setup_logging(config)
    logger.info(
        "Startup command=%s working_directory=%s dry_run=%s threshold_mib=%s part_size_mib=%s",
        config.command,
        config.working_directory,
        config.dry_run,
        config.threshold_mib,
        config.part_size_mib,
    )

    if config.workers != 1:
        logger.warning("workers=%d requested, but current implementation processes sequentially", config.workers)

    try:
        if config.command == "disband":
            return command_disband(config, logger)
        if config.command == "squad-up":
            return command_squad_up(config, logger)

        print(f"Unknown command: {config.command}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        print("Interrupted by user.", file=sys.stderr)
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    sys.exit(main())