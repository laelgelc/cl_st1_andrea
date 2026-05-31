#!/usr/bin/env python3
"""
generate_interpretation_gpt.py

Reads files from interpretation/input, sends each full file text as a single
user prompt to GPT, and saves the response to interpretation/output with the
same filename.

Default project usage:
    python generate_interpretation_gpt.py

Equivalent explicit usage:
    python generate_interpretation_gpt.py \
        --input interpretation/input \
        --output interpretation/output \
        --model gpt-5.5 \
        --workers 4 \
        --max-output-tokens 9000 \
        --skip-existing \
        --retries 5 \
        --retry-base-sleep 2.0

The script loads OPENAI_API_KEY from either:
    1. the system environment; or
    2. env/.env in the current project directory.

Expected input:
    interpretation/input/f<n>_<pole>.txt

Output:
    interpretation/output/f<n>_<pole>.txt
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv


# ------------------------------------------------------------
# Project defaults
# ------------------------------------------------------------

DEFAULT_PROJECT = Path.cwd().name
DEFAULT_INPUT_DIR = Path("interpretation/input")
DEFAULT_OUTPUT_DIR = Path("interpretation/output")
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_WORKERS = 4
DEFAULT_MAX_OUTPUT_TOKENS = 9000
DEFAULT_RETRIES = 5
DEFAULT_RETRY_BASE_SLEEP = 2.0


# ------------------------------------------------------------
# Environment loading
# ------------------------------------------------------------

load_dotenv(dotenv_path=Path("env/.env"), override=False)


# ------------------------------------------------------------
# API
# ------------------------------------------------------------

try:
    from openai import OpenAI
except ImportError:
    print(
        "Error: the `openai` package is not available in the active environment.\n"
        "Activate the correct project environment and ensure the OpenAI SDK is installed there."
    )
    sys.exit(1)


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Send LMDA interpretation prompts to GPT."
    )

    parser.add_argument(
        "--input",
        "-i",
        default=str(DEFAULT_INPUT_DIR),
        help="Directory containing prompt files. Default: interpretation/input.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for GPT responses. Default: interpretation/output.",
    )
    parser.add_argument(
        "--model",
        "-m",
        default=DEFAULT_MODEL,
        help=f"Model to use. Default: {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--max-output-tokens",
        "-t",
        type=int,
        default=DEFAULT_MAX_OUTPUT_TOKENS,
        help=f"Maximum output tokens. Default: {DEFAULT_MAX_OUTPUT_TOKENS}.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Number of parallel workers. Default: {DEFAULT_WORKERS}.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip prompts whose output file already exists. Default: enabled.",
    )
    parser.add_argument(
        "--no-skip-existing",
        dest="skip_existing",
        action="store_false",
        help="Reprocess prompts even if output files already exist.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"Number of retries for transient API/network failures. Default: {DEFAULT_RETRIES}.",
    )
    parser.add_argument(
        "--retry-base-sleep",
        type=float,
        default=DEFAULT_RETRY_BASE_SLEEP,
        help=f"Base sleep in seconds for exponential backoff. Default: {DEFAULT_RETRY_BASE_SLEEP}.",
    )

    return parser.parse_args()


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def read_text(path: Path) -> str:
    """Read a UTF-8 text file."""
    return path.read_text(encoding="utf-8", errors="ignore")


def write_text(path: Path, content: str) -> None:
    """Write a UTF-8 text file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def model_supports_temperature(model: str) -> bool:
    """
    Return whether the selected model should receive the temperature parameter.

    In this project, gpt-5.5 rejected the Responses API temperature parameter,
    so GPT-5-family models are treated as not supporting temperature here.
    """
    normalized = model.strip().lower()

    if normalized.startswith("gpt-5"):
        return False

    return True


def is_transient_error(exc: Exception) -> bool:
    """Return True if the exception looks like a transient API/network error."""
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


def call_api(
        *,
        client: OpenAI,
        model: str,
        full_prompt: str,
        max_output_tokens: int,
) -> str:
    """Send the full prompt file as a single user message."""
    kwargs = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": full_prompt,
            }
        ],
        "max_output_tokens": max_output_tokens,
    }

    if model_supports_temperature(model):
        kwargs["temperature"] = 0.0

    response = client.responses.create(**kwargs)

    output_text = getattr(response, "output_text", None)

    if not isinstance(output_text, str) or not output_text.strip():
        raise RuntimeError("API returned empty output.")

    return output_text.strip()


def call_api_with_retries(
        *,
        model: str,
        full_prompt: str,
        max_output_tokens: int,
        retries: int,
        base_sleep: float,
) -> str:
    """
    Retry wrapper with exponential backoff and jitter for transient failures.

    Creates a fresh client per call to avoid thread-safety assumptions.
    """
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    last_error: Exception | None = None

    for attempt in range(retries + 1):
        try:
            return call_api(
                client=client,
                model=model,
                full_prompt=full_prompt,
                max_output_tokens=max_output_tokens,
            )

        except Exception as exc:
            last_error = exc

            if attempt >= retries or not is_transient_error(exc):
                break

            sleep_seconds = base_sleep * (2 ** attempt)
            sleep_seconds = sleep_seconds * (0.8 + 0.4 * random.random())

            print(
                f"[WARN] Attempt {attempt + 1}/{retries} failed: {exc} "
                f"— retrying in {sleep_seconds:.1f}s"
            )

            time.sleep(sleep_seconds)

    raise RuntimeError(
        f"API call failed after {retries + 1} attempts: {last_error}"
    ) from last_error


# ------------------------------------------------------------
# Worker
# ------------------------------------------------------------

def process_prompt(
        *,
        path: Path,
        outpath: Path,
        model: str,
        max_tokens: int,
        retries: int,
        base_sleep: float,
) -> bool:
    """Process one prompt file."""
    try:
        print(f"[WORKER] Reading {path.name}")

        full_prompt = read_text(path).strip()

        if not full_prompt:
            raise ValueError("Prompt file is empty after stripping.")

        print(f"[WORKER] Sending to GPT: {path.name}")

        result = call_api_with_retries(
            model=model,
            full_prompt=full_prompt,
            max_output_tokens=max_tokens,
            retries=retries,
            base_sleep=base_sleep,
        )

        write_text(outpath, result)

        print(f"[WORKER] Saved → {outpath}")

        return True

    except Exception as exc:
        print(f"[ERROR] {path.name}: {exc}")
        return False


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main() -> None:
    """Main entry point."""
    args = parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(
            f"ERROR: input directory does not exist or is not a directory: {input_dir}"
        )

    if args.workers <= 0:
        raise SystemExit("ERROR: --workers must be greater than 0.")

    if args.max_output_tokens <= 0:
        raise SystemExit("ERROR: --max-output-tokens must be greater than 0.")

    if args.retries < 0:
        raise SystemExit("ERROR: --retries must be non-negative.")

    if args.retry_base_sleep < 0:
        raise SystemExit("ERROR: --retry-base-sleep must be non-negative.")

    api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        raise SystemExit(
            "ERROR: OPENAI_API_KEY is not set in the environment or env/.env."
        )

    files = sorted(input_dir.glob("*.txt"))

    if not files:
        print("No prompt files found.")
        sys.exit(0)

    tasks: list[tuple[Path, Path]] = []

    for prompt_file in files:
        outpath = output_dir / prompt_file.name

        if args.skip_existing and outpath.exists():
            continue

        tasks.append((prompt_file, outpath))

    if not tasks:
        print("Nothing to do: all outputs already exist.")
        sys.exit(0)

    print(f"Project: {DEFAULT_PROJECT}")
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Model: {args.model}")
    print(f"Temperature sent: {model_supports_temperature(args.model)}")
    print(f"Submitting {len(tasks)} prompts using {args.workers} workers…")

    succeeded = 0
    failed: list[str] = []

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        future_map = {
            pool.submit(
                process_prompt,
                path=input_path,
                outpath=output_path,
                model=args.model,
                max_tokens=args.max_output_tokens,
                retries=args.retries,
                base_sleep=args.retry_base_sleep,
            ): input_path
            for input_path, output_path in tasks
        }

        for future in as_completed(future_map):
            prompt_path = future_map[future]

            if future.result():
                succeeded += 1
            else:
                failed.append(prompt_path.name)

    print(f"\nDone. Succeeded: {succeeded}/{len(tasks)}")

    if failed:
        print("Failed prompts:")

        for name in failed:
            print(f"  - {name}")

        raise SystemExit("ERROR: some prompts failed. See log above.")


if __name__ == "__main__":
    main()