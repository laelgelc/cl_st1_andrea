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

## Phase 1 - Data Collection and Sampling

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
corpus/00_sources/tv_commercials.tsv
corpus/00_sources/tv_commercials_selected_1.ndjson
corpus/00_sources/tv_commercials_selected_1.xlsx
corpus/00_sources/tv_commercials_selected_1.tsv
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
### Sample commercial frames

The `sample_commercials_frames.py` programme samples representative frames from
commercial clips in `corpus/02_commercials/` and writes ordered frame sequences to
`corpus/05_frames/`.

The sampler uses a scene-change strategy with safeguards:

- first frame;
- scene-change frames;
- final frame near the end;
- maximum frame cap with chronological even downsampling.

Default test run:

```bash
python sample_commercials_frames.py
```

Full run:

```bash
python sample_commercials_frames.py --no-test-mode
```

Use a lower frame cap to reduce later LLM image-token cost:

```bash
python sample_commercials_frames.py --no-test-mode --max-frames 20
```

Use a more conservative scene-change threshold:

```bash
python sample_commercials_frames.py --no-test-mode --scene-threshold 0.30
```

Outputs are written to:

```text
corpus/05_frames/<Commercial ID>/
```

Each commercial directory contains selected JPEG frames and a `frames_manifest.json`
file recording timestamps, selection reasons, frame counts, and sampling parameters.

### Describe commercial visuals

The `describe_commercials_visual.py` programme describes the visual content of
sampled commercial frames using a multimodal OpenAI model.

It is Stage 2 of the visual analysis pipeline:

1. `sample_commercials_frames.py` samples representative frames from each commercial.
2. `describe_commercials_visual.py` submits those frames to a multimodal model and
   writes a visual description.

Default input:

```text
corpus/05_frames/
```

Default output:

```text
corpus/06_visual_descriptions/
```

Default prompt:

```text
describe_commercials_visual_prompts/visual_commercial_description_v1.txt
```

Default test run:

```bash
python describe_commercials_visual.py
```

Test run from a specific commercial ID:

```bash
python describe_commercials_visual.py \
  --test-limit 10 \
  --start-commercial-id tv_com_1960_54
```

Full run:

```bash
python describe_commercials_visual.py --no-test-mode
```

Use a different prompt:

```bash
python describe_commercials_visual.py \
  --prompt-file describe_commercials_visual_prompts/visual_commercial_description_v2_lightly_structured.txt
```

Use a lower frame cap for cost control:

```bash
python describe_commercials_visual.py \
  --no-test-mode \
  --max-frames-per-request 20
```

The programme writes one `.txt` and one `.json` output per commercial:

```text
corpus/06_visual_descriptions/<Commercial ID>.txt
corpus/06_visual_descriptions/<Commercial ID>.json
```

The `.txt` file contains the visual description. The `.json` file records model,
prompt, frame, response, and reproducibility metadata.

Requires `OPENAI_API_KEY` in `env/.env` or the system environment.

### Data Sampling

The sampling procedure was carried out after the transcript files had been generated and linked to the metadata table.

First, a `Transcript Word Count` column was added to `tv_commercials_df`. For each row where `Download Success` was `True`, the corresponding transcript file was located in:

```text
corpus/04_transcripts/
```

Each transcript filename was matched using the value in the `Commercial ID` column plus the `.txt` extension. The number of words in each transcript was counted and stored in `Transcript Word Count`. Rows associated with unsuccessful downloads were not counted.

Next, transcript word counts were examined separately by decade. The decade was inferred from the `Commercial ID` pattern, for example:

```text
tv_com_1950_1
tv_com_1960_1
tv_com_1970_1
```

For each decade from 1950 to 2020, descriptive statistics were calculated for `Transcript Word Count`, excluding rows where `Download Success` was `False`. Outliers were identified independently within each decade using the interquartile range rule:

```text
lower limit = Q1 - 1.5 × IQR
upper limit = Q3 + 1.5 × IQR
```

Commercials with transcript word counts below the lower limit or above the upper limit were treated as outliers for that decade.

An `Outlier` column was then added to `tv_commercials_df`. It was initially set to `False` for all rows, and then updated to `True` for all commercials identified as outliers in their respective decades.

After outlier identification, the number of eligible non-outlier commercials was counted per decade. Eligible commercials were those where:

- `Download Success` was `True`;
- `Outlier` was `False`;
- `Transcript Word Count` was greater than `20`

The resulting counts were:

| Decade | Non-Outlier Commercials, Longer than 20 Words |
|-------:|----------------------------------------------:|
|   1950 |                                           111 |
|   1960 |                                           119 |
|   1970 |                                           103 |
|   1980 |                                           105 |
|   1990 |                                           115 |
|   2000 |                                           114 |
|   2010 |                                           112 |
|   2020 |                                           115 |

The smallest number of eligible non-outlier commercials was `103`, found in the 1970 decade. This value was used as the balanced sample size for all decades.

A `Selected` column was then added to `tv_commercials_df` and initially set to `False`. From each decade, `103` eligible non-outlier commercials were randomly selected and marked as `Selected = True`.

The random selection used a fixed seed value:

```text
42
```

This makes the sampling reproducible, provided that the input data, filtering conditions, row order, and software behaviour remain unchanged.

The final balanced sample contains:

| Decade |   Selected Commercials |
|-------:|-----------------------:|
|   1950 |                    103 |
|   1960 |                    103 |
|   1970 |                    103 |
|   1980 |                    103 |
|   1990 |                    103 |
|   2000 |                    103 |
|   2010 |                    103 |
|   2020 |                    103 |

This produces a balanced dataset of `824` selected commercials across eight decades.

The updated metadata, including the `Transcript Word Count`, `Outlier`, and `Selected` columns, was saved back to:

```text
corpus/00_sources/tv_commercials.ndjson
corpus/00_sources/tv_commercials.xlsx
corpus/00_sources/tv_commercials.tsv
```

### Category label standardisation

After the sampling metadata had been prepared, the `Category` column was reviewed and standardised to correct spelling, punctuation, and naming inconsistencies.

The following category labels were updated:

| Original label                                                            | Standardised label                                                        |
|---------------------------------------------------------------------------|---------------------------------------------------------------------------|
| `Food, Beverage & Nutrition`                                              | `Food, Beverages & Nutrition`                                             |
| `Retail (Fashion/ Consumer Goods) &  Services`                            | `Retail (Fashion & Consumer Goods) & Services`                            |
| `Retail (Fashion/ Consumer Goods) &  Services `                           | `Retail (Fashion & Consumer Goods) & Services`                            |
| `Retail (Fashion/ Consumer Goods) &  Services, Consumer Goods & Services` | `Retail (Fashion & Consumer Goods) & Services, Consumer Goods & Services` |
| `Retail (Fashion/ Consumer Goods) &  Services, Fashion & Consumer Goods`  | `Retail (Fashion & Consumer Goods) & Services, Fashion & Consumer Goods`  |
| `Technology, Communication & Eletronics`                                  | `Technology, Communication & Electronics`                                 |
| `Transport (Personal/ Public), Travel & Energy`                           | `Transport (Personal & Public), Travel & Energy`                          |

The updated metadata, including the `Transcript Word Count`, `Outlier`, and `Selected` columns, was saved back to:

```text
corpus/00_sources/tv_commercials.ndjson
corpus/00_sources/tv_commercials.xlsx
corpus/00_sources/tv_commercials.tsv
```

A reduced metadata table containing only the selected commercials was also created. This table includes the following columns:

- `Decade`
- `Category`
- `Commercial ID`

Only rows where `Selected` is `True` are included. This selected-sample metadata table was saved as:

```text
corpus/00_sources/tv_commercials_selected_1.ndjson
corpus/00_sources/tv_commercials_selected_1.xlsx
corpus/00_sources/tv_commercials_selected_1.tsv
```

These files provide a compact reference list for the balanced sample of `824` selected commercials.

## Phase 2 - Lexical Multi-dimensional Analysis of the commercial verbal subcorpus to identify dimensions of underlying discourses

### Commercial verbal subcorpus organisation

The selected commercial transcripts were copied from the Phase 1 transcript directory:

```text
../cl_st1_ph1_andrea/corpus/04_transcripts/
```

to the Phase 2 commercial verbal subcorpus directory:

```text
corpus/commercial_verbal/
```

Only commercials marked as `Selected = True` in `tv_commercials_df` were included.

The copied transcript files were organised into decade-specific subdirectories using the value in the `Decade` column:

```text
corpus/commercial_verbal/1950/
corpus/commercial_verbal/1960/
corpus/commercial_verbal/1970/
corpus/commercial_verbal/1980/
corpus/commercial_verbal/1990/
corpus/commercial_verbal/2000/
corpus/commercial_verbal/2010/
corpus/commercial_verbal/2020/
```

Each copied transcript file keeps the filename derived from its `Commercial ID`:

```text
corpus/commercial_verbal/<Decade>/<Commercial ID>.txt
```

For example:

```text
corpus/commercial_verbal/1950/tv_com_1950_1.txt
```

The resulting verbal subcorpus contains the balanced sample of selected commercials, with `103` transcript files per decade and `824` transcript files in total.

## Phase 3 - Lexical Multi-dimensional Analysis of the commercial visual subcorpus to identify dimensions of underlying discourses

### Commercial visual subcorpus organisation

The selected commercial visual descriptions were copied from the Phase 1 visual description directory:

```text
../cl_st1_ph1_andrea/corpus/06_visual_descriptions/
```

to the Phase 2 commercial visual subcorpus directory:

```text
corpus/commercial_visual/
```

Only commercials marked as `Selected = True` in `tv_commercials_df` were included.

The copied visual description files were organised into decade-specific subdirectories using the value in the `Decade` column:

```text
corpus/commercial_visual/1950/
corpus/commercial_visual/1960/
corpus/commercial_visual/1970/
corpus/commercial_visual/1980/
corpus/commercial_visual/1990/
corpus/commercial_visual/2000/
corpus/commercial_visual/2010/
corpus/commercial_visual/2020/
```

Each copied visual description file keeps the filename derived from its `Commercial ID`:

```text
corpus/commercial_visual/<Decade>/<Commercial ID>.txt
```

For example:

```text
corpus/commercial_visual/1950/tv_com_1950_1.txt
```

The resulting visual subcorpus mirrors the verbal subcorpus, containing the same balanced sample of selected commercials, with `103` visual description files per decade and `824` visual description files in total.

## Phase 4 - Canonical Correlation Analysis of the commercial verbal and visual subcorpora to identify cross-modal discursive patterns



## Phase 5 - ANOVA Analysis of the commercial verbal, visual, and cross-modal discourses to detect diachronic variation in discourses

