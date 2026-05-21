# Corpus Linguistics - Study 1 - Andrea

## Phase 0 - Data Collection Testing

### Download (`yt-dlp`) and slice (`ffmpeg`) videos
The following commands were used to test downloading and slicing videos from YouTube.

```bash
# Test 1
## 1. Download the whole video first
yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" "https://youtu.be/WMIMxj0PGGY" -o "full_video_1.mp4"

## 2. Slice the commercial out of the local file
ffmpeg -ss 00:00:17 -to 00:01:42 -i "full_video_1.mp4" -c:v libx264 -c:a aac -avoid_negative_ts make_zero "Betty_Crocker_Cake.mp4"

# Test 2
## 1. Download the whole video first
yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" "https://youtu.be/54-wVD9Vq-w" -o "full_video_2.mp4"

## 2. Slice the commercial out of the local file
ffmpeg -ss 00:00:05 -to 00:00:19.5 -i "full_video_2.mp4" -c:v libx264 -c:a aac -avoid_negative_ts make_zero "Royal_Caribbean.mp4"
ffmpeg -ss 00:00:19.5 -to 00:00:29.5 -i "full_video_2.mp4" -c:v libx264 -c:a aac -avoid_negative_ts make_zero "Full_Monty.mp4"
ffmpeg -ss 00:00:29.5 -to 00:00:44.5 -i "full_video_2.mp4" -c:v libx264 -c:a aac -avoid_negative_ts make_zero "Bud_Light.mp4"
ffmpeg -ss 00:00:44.5 -to 00:01:14 -i "full_video_2.mp4" -c:v libx264 -c:a aac -avoid_negative_ts make_zero "Jeep.mp4"
ffmpeg -ss 00:01:14 -to 00:01:29 -i "full_video_2.mp4" -c:v libx264 -c:a aac -avoid_negative_ts make_zero "Wingstop.mp4"
ffmpeg -ss 00:01:29 -to 00:01:39 -i "full_video_2.mp4" -c:v libx264 -c:a aac -avoid_negative_ts make_zero "Tubi.mp4"
```

### Design a Python script to automate the video slicing process

Tasks:

1. Import `corpus/00_sources/TV_commercials_1950_2025_test.xlsx` into a Pandas DataFrame named `df_tv_commercials`.
2. `df_tv_commercials` has the following columns:
   - `Decade`: The decade of the TV commercial
   - `Sequence`: The sequence number of the TV commercial in the decade
   - `Title`: The title of the TV commercial
   - `Category`: The category of the TV commercial
   - `URL`: The YouTube URL of the video containing the TV commercial
   - `Start`: The start time of the TV commercial in the video
   - `End`: The end time of the TV commercial in the video
3. There may be incomplete rows in `df_tv_commercials`. For a row to be eligible to be processed, all columns except `Category`, which is optional, must be filled.
4. Create the column `File_ID` by concatenating the `Decade` and `Sequence` columns separated by an underscore for each eligible row. Use `tv_commercial_` as the prefix. Code `Sequence` as 3-digit integer. Example: `tv_commercial_1950_001`.
5. The script should accept a list of video URLs and a list of time ranges for slicing, and output the sliced videos with appropriate naming conventions.

## Phase 1 - Data Collection

### Source metadata

The source metadata for the television commercials is stored in:

```text
corpus/00_sources/
```

Current metadata files:

```text
corpus/00_sources/TV_commercials_1950_2025.xlsx
corpus/00_sources/tv_commercials.ndjson
corpus/00_sources/tv_commercials.xlsx
```

The original spreadsheet, `TV_commercials_1950_2025.xlsx`, is processed into a structured metadata table. The processed metadata includes:

- `Decade`
- `Sequence`
- `Title`
- `Category`
- `Commercial ID`
- `Video ID`
- `URL`
- `Start`
- `End`
- `Download Success`
- `Reason`

The processed metadata is saved in two formats:

- `tv_commercials.ndjson`: newline-delimited JSON, used by the download pipeline
- `tv_commercials.xlsx`: Excel version for inspection, sharing, and manual review

`Commercial ID` identifies each individual commercial, while `Video ID` identifies each unique source YouTube video. Multiple commercials may come from the same source video.

The `Download Success` column records whether the source video was successfully downloaded. The `Reason` column records either `Success` or the corresponding error message for failed downloads.

Known failed source videos:

| Video ID | Download Success | Reason |
|---|---:|---|
| `video_0300` | `False` | `Error: Unsupported URL: https://www.youtube.com/watch?v=_pHfv_HVSr&feature=youtu.be` |
| `video_0739` | `False` | `Error: [youtube] WX1wgKCVJzc: Private video.` |

### Download source videos

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
### Extract commercial clips

The `extract_commercials.py` programme extracts individual commercial clips from the downloaded source videos listed in:

```text
corpus/00_sources/tv_commercials.ndjson
```

Only rows where `Download Success` is `True` are processed.

Source videos are read from:

```text
corpus/01_videos/
```

Each source video is identified by the `Video ID` field and expected to exist as:

```text
corpus/01_videos/<Video ID>.mp4
```

Commercial clips are written to:

```text
corpus/02_commercials/
```

Each clip is named after its `Commercial ID`:

```text
corpus/02_commercials/<Commercial ID>.mp4
```

The clipping command generated for each eligible row is equivalent to:

```bash
ffmpeg -y -ss "<Start>" -to "<End>" -i "corpus/01_videos/<Video ID>.mp4" -c:v libx264 -c:a aac -avoid_negative_ts make_zero "corpus/02_commercials/<Commercial ID>.mp4"
```

Default test run:

```bash
python extract_commercials.py
```

This processes up to 5 eligible commercials.

Full run:

```bash
python extract_commercials.py --no-test-mode
```

To resume planning from a specific commercial ID onward, use:

```bash
python extract_commercials.py \
  --no-test-mode \
  --start-commercial-id tv_com_1950_25
```

The programme is safe to re-run: existing commercial clips are skipped by default. To force re-extraction, use:

```bash
python extract_commercials.py --no-test-mode --reprocess
```

The programme writes:

```text
corpus/02_commercials/extract_commercials.log
corpus/02_commercials/extract_commercials_manifest.json
```

A timestamped per-run manifest is also created for each execution.

### Extract commercial audio

The `extract_commercials_audio.py` programme extracts Whisper-ready audio from the individual commercial video files listed in:

```text
corpus/00_sources/tv_commercials.ndjson
```

Only rows where `Download Success` is `True` are processed.

Source commercial videos are read from:

```text
corpus/02_commercials/
```

Each source commercial video is identified by the `Commercial ID` field and expected to exist as:

```text
corpus/02_commercials/<Commercial ID>.mp4
```

Audio files are written to:

```text
corpus/03_audio/
```

Each audio file is named after its `Commercial ID`:

```text
corpus/03_audio/<Commercial ID>.wav
```

The audio extraction command generated for each eligible row is equivalent to:

```bash
ffmpeg -y -i "corpus/02_commercials/<Commercial ID>.mp4" -vn -ac 1 -ar 16000 -sample_fmt s16 "corpus/03_audio/<Commercial ID>.wav"
```

The resulting audio is suitable for Whisper transcription:

- WAV format;
- mono;
- 16 kHz;
- signed 16-bit PCM.

Default test run:

```bash
python extract_commercials_audio.py
```

This processes up to 5 eligible commercials.

Full run:

```bash
python extract_commercials_audio.py --no-test-mode
```

To resume planning from a specific commercial ID onward, use:

```bash
python extract_commercials_audio.py \
  --no-test-mode \
  --start-commercial-id tv_com_1950_25
```

The programme is safe to re-run: existing audio files are skipped by default. To force re-extraction, use:

```bash
python extract_commercials_audio.py --no-test-mode --reprocess
```

The programme writes:

```text
corpus/03_audio/extract_commercials_audio.log
corpus/03_audio/extract_commercials_audio_manifest.json
```

A timestamped per-run manifest is also created for each execution.

### Transcribe commercial audio with Whisper

The `transcribe_commercials_whisper.py` programme transcribes Whisper-ready audio files listed in:

```text
corpus/00_sources/tv_commercials.ndjson
```

Only rows where `Download Success` is `True` are processed.

Source audio files are read from:

```text
corpus/03_audio/
```

Each source audio file is identified by the `Commercial ID` field and expected to exist as:

```text
corpus/03_audio/<Commercial ID>.wav
```

Transcripts are written to:

```text
corpus/04_transcripts/
```

Each successful transcription writes both:

```text
corpus/04_transcripts/<Commercial ID>.txt
corpus/04_transcripts/<Commercial ID>.json
```

The `.txt` file contains clean transcript text for corpus analysis. The `.json` file preserves segment timestamps, model configuration, and source metadata.

The default transcription model is:

```text
Whisper Large v3
```

through the `faster-whisper` backend.

Recommended EC2 environment:

```text
x86_64 GPU instance
Python 3.11
faster-whisper
CUDA-capable NVIDIA GPU
```

Default test run:

```bash
python transcribe_commercials_whisper.py
```

This processes up to 5 eligible commercials.

Full run:

```bash
python transcribe_commercials_whisper.py --no-test-mode
```

To resume planning from a specific commercial ID onward, use:

```bash
python transcribe_commercials_whisper.py \
  --no-test-mode \
  --start-commercial-id tv_com_1950_25
```

The programme is safe to re-run: existing complete transcript outputs are skipped by default. To force re-transcription, use:

```bash
python transcribe_commercials_whisper.py --no-test-mode --reprocess
```

The programme writes:

```text
corpus/04_transcripts/transcribe_commercials_whisper.log
corpus/04_transcripts/transcribe_commercials_whisper_manifest.json
```

A timestamped per-run manifest is also created for each execution.

#### Reprocessing without VAD filtering

After inspecting the initial transcripts, the final transcription run was performed **without VAD filtering**. This produced better results for the commercial audio, likely because short slogans, jingles, brief voice-over segments, or speech over music can be affected by automatic voice activity detection.

Recommended EC2 full run:

```bash
nohup bash run_python_ec2.sh \
   transcribe_commercials_whisper.py \
       --no-test-mode \
       --no-vad-filter \
> whisper_transcription_output.log 2>&1 &
```
