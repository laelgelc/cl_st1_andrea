# `download_videos.py` — Programme Specification for Development

## 1. High-level Functionality Specification

### Programme Summary

`download_videos.py` is a batch-processing programme that downloads source YouTube videos for a television commercials corpus.

The programme reads the metadata file:

```text
corpus/00_sources/tv_commercials.ndjson
```

Each record in this NDJSON file contains metadata for one commercial. Because multiple commercials may come from the same YouTube source video, the programme must identify unique videos using the `Video ID` column and download each unique video only once.

For each unique video, the programme uses:

- the `Video ID` field to determine the output filename;
- the `URL` field as the YouTube source URL.

The base download command is:

```bash
yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" "https://youtu.be/G-zZFNf4PqQ" -o "video_0001.mp4"
```

The programme must generalise this command so that each video is downloaded as:

```bash
yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" "<URL>" -o "<output_dir>/<Video ID>.mp4"
```

For example:

```bash
yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" "https://youtu.be/G-zZFNf4PqQ" -o "corpus/01_videos/video_0001.mp4"
```

If YouTube blocks automated downloads with authentication or bot-confirmation checks, the programme must optionally support a Netscape-format cookies file passed to `yt-dlp` with `--cookies`.

For example:

```bash
yt-dlp --cookies env/youtube_cookies.txt -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" "https://youtu.be/G-zZFNf4PqQ" -o "corpus/01_videos/video_0001.mp4"
```

---

## 2. Key Behaviours

The programme must implement the following behaviours:

- Read video metadata from an NDJSON file.
- Extract the required fields:
  - `Video ID`
  - `URL`
- Download each unique `Video ID` only once.
- Save each video as an `.mp4` file named after its `Video ID`.
- Use `yt-dlp` as the external download engine.
- Optionally pass a Netscape-format cookies file to `yt-dlp` when `--cookies PATH` is provided.
- Use test mode by default, limiting processing to 5 unique videos.
- Skip already-downloaded videos by default, supporting safe re-runs.
- Allow reprocessing with an explicit command-line option.
- Continue processing remaining videos if one URL fails.
- Record progress and errors in an append-only log file.
- Produce a JSON manifest with run-level metadata and item-level results.
- Write both:
  - a timestamped per-run manifest;
  - a latest manifest that is overwritten on each run.
- Exit with status code `0` only when all attempted downloads succeed or are skipped.
- Exit with a non-zero status code if one or more attempted downloads fail, or if there is a configuration/validation error.

---

## 4.3 Optional arguments

### Metadata path

```bash
--metadata PATH
```

Default:

```text
corpus/00_sources/tv_commercials.ndjson
```

Description:

Path to the NDJSON metadata file.

---

### Output directory

```bash
--output-dir PATH
```

Default:

```text
corpus/01_videos/
```

Description:

Directory where downloaded `.mp4` files will be saved.

---

### Test mode

```bash
--test-mode
--no-test-mode
```

Default:

```text
--test-mode
```

Description:

When test mode is enabled, the programme processes only a limited number of planned videos.

---

### Test limit

```bash
--test-limit N
```

Default:

```text
5
```

Description:

Maximum number of videos to attempt when test mode is enabled.

Must be a positive integer.

Example:

```bash
python download_videos.py --test-limit 10
```

---

### Reprocess existing videos

```bash
--reprocess
```

Default:

```text
False
```

Description:

When omitted, the programme skips any video whose output `.mp4` file already exists.

When provided, the programme downloads the video again and overwrites the existing output file.

Example:

```bash
python download_videos.py --reprocess
```

---

### Cookies file

```bash
--cookies PATH
```

Default:

```text
None
```

Description:

Optional path to a Netscape-format `cookies.txt` file to pass to `yt-dlp`.

This is useful when YouTube blocks automated downloads from environments such as EC2 with authentication or bot-confirmation checks.

Example:

```bash
python download_videos.py --cookies env/youtube_cookies.txt
```

Recommended location:

```text
env/youtube_cookies.txt
```

Security note:

Treat the cookies file like a password. Do not commit it to Git, upload it publicly, or share it.

---

### Log file

```bash
--log-file PATH
```

Default:

```text
corpus/01_videos/download_videos.log
```

Description:

Path to the append-only log file.

---

### Manifest file

```bash
--manifest-file PATH
```

Default:

```text
corpus/01_videos/download_videos_manifest.json
```

Description:

Path to the latest manifest file. The per-run timestamped manifest should be written next to this file.

---

### Workers

```bash
--workers N
```

Default:

```text
1
```

Description:

Number of worker processes.

For initial implementation, sequential execution with `--workers 1` is sufficient and preferred for simplicity. The architecture should still allow parallel execution later.

Must be a positive integer.

---

### Timeout

```bash
--timeout SECONDS
```

Default suggestion:

```text
3600
```

Description:

Maximum allowed time for a single `yt-dlp` download process.

If the timeout is reached:

- terminate the process;
- mark the item as failed;
- log the timeout;
- continue with the next video.

---

### Maximum retries

```bash
--max-retries N
```

Default suggestion:

```text
1
```

Description:

Number of retry attempts after a failed download.

For example, with `--max-retries 1`, each failed item may be attempted twice in total:

1. initial attempt;
2. one retry.

Must be zero or a positive integer.

---

## 4.4 Example commands

### Small default test run

```bash
python download_videos.py
```

### Test run with 10 videos

```bash
python download_videos.py --test-limit 10
```

### Test run with cookies

```bash
python download_videos.py \
  --test-limit 3 \
  --cookies env/youtube_cookies.txt
```

### Full production run

```bash
python download_videos.py --no-test-mode
```

### Full production run with cookies

```bash
python download_videos.py \
  --no-test-mode \
  --cookies env/youtube_cookies.txt
```

### Full production run with explicit paths and cookies

```bash
python download_videos.py \
  --metadata corpus/00_sources/tv_commercials.ndjson \
  --output-dir corpus/01_videos \
  --no-test-mode \
  --cookies env/youtube_cookies.txt
```

### Re-download videos even if files already exist

```bash
python download_videos.py --no-test-mode --reprocess
```

### Re-download videos with cookies

```bash
python download_videos.py \
  --no-test-mode \
  --reprocess \
  --cookies env/youtube_cookies.txt
```

---

## 5. Argument Validation

The programme must fail fast with a clear message if:

- the metadata file does not exist;
- the metadata file is unreadable;
- the metadata file contains invalid JSON lines;
- the output directory cannot be created;
- `--test-limit` is less than or equal to zero;
- `--workers` is less than or equal to zero;
- `--timeout` is less than or equal to zero;
- `--max-retries` is negative;
- `--cookies` is provided but the cookies file does not exist;
- `--cookies` is provided but the cookies path is not a file;
- `yt-dlp` is not available on the system path.

The programme should check for `yt-dlp` availability before processing begins.

A validation error should:

- be printed clearly to the console;
- be written to the log if logging has already been configured;
- cause the programme to exit with a non-zero status code.

---

## 6. Environment and Configuration

This programme does not require API keys or secret environment variables.

The programme depends on the external command-line tool:

```text
yt-dlp
```

The implementation must verify that `yt-dlp` is available before starting downloads.

Suggested check:

```bash
yt-dlp --version
```

The programme may optionally use a Netscape-format cookies file when YouTube requires authentication or bot confirmation. This file is passed with:

```bash
--cookies PATH
```

Recommended project-local location:

```text
env/youtube_cookies.txt
```

One-line note:

```text
cookies.txt is needed when YouTube blocks automated downloads with authentication or bot-confirmation checks; it can be obtained by signing in to YouTube in Firefox and exporting browser cookies in Netscape cookies.txt format using a cookies export extension.
```

Security requirements for cookies files:

- Treat the cookies file like a password.
- Do not commit it to Git.
- Do not upload it publicly.
- Do not share it.
- Prefer restrictive permissions on servers, for example:

```bash
chmod 600 env/youtube_cookies.txt
```

Recommended `.gitignore` entries:

```text
cookies.txt
youtube_cookies.txt
*cookies*.txt
env/youtube_cookies.txt
```

The programme must not log the cookies file contents. It should only log whether a cookies file was provided.

---

## 7.1 High-level flow

The programme must follow this workflow:

1. **Startup**
   - Parse command-line arguments.
   - Validate arguments.
   - If `--cookies` is provided, validate that the cookies file exists and is a file.
   - Generate a UTC `run_id`.
   - Ensure the output directory exists.
   - Set up logging.
   - Check that `yt-dlp` is available.

2. **Metadata loading**
   - Open the NDJSON metadata file.
   - Read records line by line.
   - Parse each JSON object.
   - Validate required fields.
   - Extract `Video ID` and `URL`.

3. **Discovery**
   - Identify unique videos by `Video ID`.
   - Preserve first-seen order.
   - Record duplicates as metadata in the manifest if useful.

4. **Planning**
   - For each unique video:
     - compute output path as `<output_dir>/<Video ID>.mp4`;
     - decide whether to skip or download.
   - If the file exists and `--reprocess` is not enabled:
     - mark the item as `skipped_existing`.
   - If the file does not exist or `--reprocess` is enabled:
     - plan the item for download.
   - If test mode is enabled:
     - limit the planned list to `--test-limit`.

5. **Execution**
   - For each planned item:
     - build the `yt-dlp` command;
     - include `--cookies <cookies_path>` if `--cookies` was provided;
     - run `yt-dlp`;
     - capture stdout, stderr, return code, timing, and any exception;
     - retry according to `--max-retries`;
     - mark the item as `success` or `failed`.

6. **End-of-run summary**
   - Count:
     - total metadata records;
     - total unique videos;
     - skipped existing files;
     - attempted downloads;
     - successful downloads;
     - failed downloads;
     - invalid metadata rows, if any.
   - Write the latest manifest.
   - Write the per-run manifest.
   - Log the final summary.
   - Exit with an appropriate status code.

7. **Interrupt handling**
   - Catch `KeyboardInterrupt`.
   - Stop cleanly.
   - Write a partial manifest.
   - Log the interruption.
   - Exit non-zero.

---

## 8.1 Base command

For each video, the programme must run:

```bash
yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" "<URL>" -o "<output_path>"
```

Example:

```bash
yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" "https://youtu.be/G-zZFNf4PqQ" -o "corpus/01_videos/video_0001.mp4"
```

If a cookies file is provided, the programme must run a command equivalent to:

```bash
yt-dlp --cookies "<cookies_path>" -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" "<URL>" -o "<output_path>"
```

Example:

```bash
yt-dlp --cookies "env/youtube_cookies.txt" -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" "https://youtu.be/G-zZFNf4PqQ" -o "corpus/01_videos/video_0001.mp4"
```

---

## 8.6 YouTube authentication and bot-confirmation checks

When running on cloud infrastructure such as EC2, YouTube may reject unauthenticated automated downloads with an error such as:

```text
Sign in to confirm you’re not a bot. Use --cookies-from-browser or --cookies for the authentication.
```

This should be treated as a per-video `yt-dlp` failure unless a valid cookies file is provided.

The programme must support the `--cookies PATH` argument so that users can provide a Netscape-format cookies file exported from a browser where YouTube is signed in.

The cookies file should be obtained by:

1. signing in to YouTube in Firefox;
2. exporting cookies in Netscape `cookies.txt` format using a cookies export extension;
3. copying the cookies file to the execution environment, such as EC2;
4. passing it to the programme with `--cookies`.

Example:

```bash
python download_videos.py \
  --no-test-mode \
  --cookies env/youtube_cookies.txt
```

The programme must not print or log the contents of the cookies file.

---

## 9.1 Manifest structure

The manifest must use this general structure:

```json
{
  "run_metadata": {
    "run_id": "20260518T143012Z",
    "tool_name": "download_videos.py",
    "tool_version": "v1",
    "start_time": "2026-05-18T14:30:12Z",
    "end_time": "2026-05-18T14:35:42Z",
    "test_mode": true,
    "test_limit": 5,
    "reprocess": false,
    "workers": 1,
    "metadata_path": "corpus/00_sources/tv_commercials.ndjson",
    "output_dir": "corpus/01_videos",
    "log_file": "corpus/01_videos/download_videos.log",
    "manifest_file": "corpus/01_videos/download_videos_manifest.json",
    "config": {
      "yt_dlp_format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
      "timeout_seconds": 3600,
      "max_retries": 1,
      "retry_delay_seconds": 5,
      "cookies_provided": true
    },
    "summary": {
      "metadata_records": 960,
      "unique_videos": 739,
      "planned": 5,
      "attempted": 5,
      "succeeded": 5,
      "failed": 0,
      "skipped_existing": 0,
      "invalid_metadata": 0
    }
  },
  "videos": [
    {
      "video_id": "video_0001",
      "url": "https://youtu.be/G-zZFNf4PqQ",
      "output_path": "corpus/01_videos/video_0001.mp4",
      "status": "success",
      "error": null,
      "return_code": 0,
      "retries": 0,
      "duration_seconds": 42.8,
      "start_time": "2026-05-18T14:30:15Z",
      "end_time": "2026-05-18T14:30:58Z",
      "metadata": {
        "command": [
          "yt-dlp",
          "--cookies",
          "env/youtube_cookies.txt",
          "-f",
          "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
          "https://youtu.be/G-zZFNf4PqQ",
          "-o",
          "corpus/01_videos/video_0001.mp4"
        ]
      }
    }
  ],
  "invalid_records": []
}
```

The manifest may record whether cookies were provided using:

```json
"cookies_provided": true
```

The programme should avoid recording cookies file contents. If the command list records the cookies path, users must ensure the manifest is not published if the path itself is considered sensitive.

---

## 10. Logging Specification

The programme must write an append-only log file.

Default:

```text
corpus/01_videos/download_videos.log
```

### Log format

Each line should follow this format:

```text
[YYYY-MM-DD HH:MM:SS] LEVEL  message
```

Example:

```text
[2026-05-18 14:30:12] INFO  Starting download_videos.py run_id=20260518T143012Z
```

### Required log events

The programme must log:

- startup;
- parsed configuration summary;
- metadata file path;
- output directory;
- test mode status;
- test limit;
- reprocess setting;
- whether a cookies file was provided;
- `yt-dlp` availability and version if available;
- number of metadata records read;
- number of unique videos found;
- number of invalid metadata records;
- number of planned downloads;
- each skipped existing video;
- each successful download;
- each failed download;
- each retry attempt;
- manifest write paths;
- end-of-run summary;
- keyboard interrupts;
- validation/configuration errors.

The programme must not log cookies file contents.

### Example log lines

```text
[2026-05-18 14:30:12] INFO  Starting download_videos.py run_id=20260518T143012Z
[2026-05-18 14:30:12] INFO  Metadata path: corpus/00_sources/tv_commercials.ndjson
[2026-05-18 14:30:12] INFO  Output directory: corpus/01_videos
[2026-05-18 14:30:12] INFO  Test mode: true; test_limit=5
[2026-05-18 14:30:12] INFO  Cookies file provided: true
[2026-05-18 14:30:13] INFO  Found 960 metadata records and 739 unique videos
[2026-05-18 14:30:15] INFO  SUCCESS video_0001 https://youtu.be/G-zZFNf4PqQ -> corpus/01_videos/video_0001.mp4
[2026-05-18 14:31:02] ERROR FAILED video_0002 https://youtu.be/example error='Video unavailable'
[2026-05-18 14:35:42] INFO  Wrote latest manifest: corpus/01_videos/download_videos_manifest.json
[2026-05-18 14:35:42] INFO  Finished run: succeeded=4 failed=1 skipped_existing=0
```

---

## 12.1 Module-level docstring

At the top of `download_videos.py`, include a module-level docstring explaining:

- purpose of the programme;
- expected input metadata file;
- output video directory;
- use of `yt-dlp`;
- optional cookies support;
- default test mode;
- resumability behaviour;
- example commands.

Suggested module docstring:

```python
"""
Download source YouTube videos for the television commercials corpus.

This script reads video metadata from an NDJSON file, extracts unique videos
using the "Video ID" and "URL" fields, and downloads each source video with
yt-dlp. Downloaded files are saved as "<Video ID>.mp4" in the output directory.

By default, the script runs in test mode and attempts only the first 5 planned
videos. Existing output files are skipped unless --reprocess is provided,
making the script safe to re-run.

If YouTube requires authentication or bot confirmation, pass a Netscape-format
cookies file exported from a browser with --cookies.

Example:
    python download_videos.py

Example with cookies:
    python download_videos.py --cookies env/youtube_cookies.txt

Full run:
    python download_videos.py --no-test-mode --cookies env/youtube_cookies.txt

The script writes an append-only log file and JSON manifests describing
run-level metadata and per-video status.
"""
```

---

## 13. Suggested Constants

The implementation should define constants near the top of the file:

```python
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
```

---

## 15. Acceptance Criteria

The programme is considered complete when the following conditions are met:

1. Running:

   ```bash
   python download_videos.py
   ```

   performs a test run of up to 5 videos.

2. The programme reads:

   ```text
   corpus/00_sources/tv_commercials.ndjson
   ```

3. The programme creates the output directory if needed:

   ```text
   corpus/01_videos/
   ```

4. Each downloaded video is saved as:

   ```text
   corpus/01_videos/<Video ID>.mp4
   ```

5. Existing `.mp4` files are skipped unless `--reprocess` is used.

6. Duplicate `Video ID` values are downloaded only once.

7. Failed downloads do not stop the full batch.

8. Invalid or unavailable YouTube URLs are marked as `failed`.

9. The programme supports optional cookies with:

   ```bash
   --cookies PATH
   ```

10. When `--cookies PATH` is provided, the programme passes the cookies file to `yt-dlp`.

11. The programme validates that the cookies file exists when `--cookies` is provided.

12. The programme logs whether cookies were provided, but does not log cookies file contents.

13. A log file is written at:

   ```text
   corpus/01_videos/download_videos.log
   ```

14. A latest manifest is written at:

   ```text
   corpus/01_videos/download_videos_manifest.json
   ```

15. A timestamped per-run manifest is also written.

16. The manifest records:
   - run metadata;
   - configuration;
   - whether cookies were provided;
   - per-video status;
   - errors;
   - timings;
   - summary counts.

17. The programme exits with:
   - `0` if all attempted downloads succeed or are skipped;
   - non-zero if any attempted download fails;
   - non-zero for configuration errors;
   - `130` for keyboard interruption.

---

## 16. Short README Section

The following section can be added to project documentation.

## Download source videos

The `download_videos.py` programme downloads the source YouTube videos listed in
`corpus/00_sources/tv_commercials.ndjson`.

Each unique video is identified by the `Video ID` field and downloaded from the
corresponding `URL`. Videos are saved as `.mp4` files named after their video ID.

Default test run:

```bash
python download_videos.py
```

This processes up to 5 videos.

Full run:

```bash
python download_videos.py --no-test-mode
```

If YouTube blocks automated downloads with authentication or bot-confirmation checks,
provide a Netscape-format cookies file exported from a signed-in browser session:

```bash
python download_videos.py \
  --no-test-mode \
  --cookies env/youtube_cookies.txt
```

`cookies.txt` is needed when YouTube blocks automated downloads with authentication or bot-confirmation checks; it can be obtained by signing in to YouTube in Firefox and exporting browser cookies in Netscape `cookies.txt` format using a cookies export extension.

Outputs are written to:

```text
corpus/01_videos/
```

The programme is safe to re-run: existing videos are skipped by default. To
force re-downloading, use:

```bash
python download_videos.py --no-test-mode --reprocess
```

The programme writes:

```text
corpus/01_videos/download_videos.log
corpus/01_videos/download_videos_manifest.json
```

A timestamped per-run manifest is also created for each execution.

Security note: treat the cookies file like a password and do not commit it to Git.

Also add the cookies file to `.gitignore` if it is not already ignored:

```text
cookies.txt
youtube_cookies.txt
*cookies*.txt
env/youtube_cookies.txt
```