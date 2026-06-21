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

| Video ID     | Download Success | Reason                                                                                |
|--------------|-----------------:|---------------------------------------------------------------------------------------|
| `video_0300` |          `False` | `Error: Unsupported URL: https://www.youtube.com/watch?v=_pHfv_HVSr&feature=youtu.be` |
| `video_0739` |          `False` | `Error: [youtube] WX1wgKCVJzc: Private video.`                                        |

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

The `sample_commercials_frames.py` programme samples frames from commercial clips in
`corpus/02_commercials/` and writes ordered frame sequences to `corpus/05_frames/`.

The sampler uses a fixed-interval strategy with safeguards:

- first frame;
- one frame every 0.25 seconds by default;
- final frame 1.0 second before the end;
- resize width of 768 px;
- optional maximum frame cap with chronological even downsampling.

By default, `--max-frames 0` means no cap, so all deduplicated sampled frames are saved.

Default test run:

```bash
python sample_commercials_frames.py
```

Full run:

```bash
python sample_commercials_frames.py --no-test-mode
```

Use a different interval:

```bash
python sample_commercials_frames.py --no-test-mode --frame-interval-seconds 0.50
```

Apply a frame cap:

```bash
python sample_commercials_frames.py --no-test-mode --max-frames 30
```

Explicitly disable the cap:

```bash
python sample_commercials_frames.py --no-test-mode --max-frames 0
```

Outputs are written to:

```text
corpus/05_frames/<Commercial ID>/
```

Each commercial directory contains selected JPEG frames and a `frames_manifest.json`
file recording timestamps, selection reasons, frame counts, and sampling parameters.

### Select commercial frames

The `select_commercials_frames.py` programme filters the dense sampled-frame output
from `corpus/05_frames/` and writes cleaner selected frame sequences to
`corpus/05_frames_selected/`.

It removes:

- dark or near-black frames, including dark sequences at the beginning, middle, or end;
- visually duplicate or near-duplicate frames caused by dense 0.25-second sampling.

Default test run:

```bash
python select_commercials_frames.py
```

Full run:

```bash
python select_commercials_frames.py --no-test-mode
```

Force regeneration:

```bash
python select_commercials_frames.py --no-test-mode --reprocess
```

Use more aggressive duplicate removal:

```bash
python select_commercials_frames.py \
  --no-test-mode \
  --duplicate-distance-threshold 0.06
```

Outputs are written to:

```text
corpus/05_frames_selected/<Commercial ID>/
```

Each commercial directory contains selected JPEG frames and a
`selected_frames_manifest.json` file recording source frames, rejected frames,
darkness metrics, duplicate metrics, and selection settings.

### Describe commercial visuals

The visual-description stage generates commercial-specific prompts and submits
selected frame sequences, together with the corresponding commercial audio, to a
multimodal OpenAI model. The output is a prose visual description designed to
describe what is visible while using the audio only as supporting context.

It uses the selected-commercial metadata file:

```text
corpus/00_sources/tv_commercials_selected_2.tsv
```

This file contains the selected commercials and their brief `Description` values.

It also uses the prompt template:

```text
describe_commercials_visual_prompts/visual_commercial_description_v4.md
```

For each row in `tv_commercials_selected_2.tsv`, the programme creates a
commercial-specific Markdown prompt by replacing the product-context placeholder
in the template with the row's `Description` value.

Generated prompt files are written to:

```text
corpus/06_visual_descriptions_prompts/
```

Each prompt file is named after the commercial ID:

```text
corpus/06_visual_descriptions_prompts/<Commercial ID>.md
```

For example:

```text
corpus/06_visual_descriptions_prompts/tv_com_1950_1.md
```

For each commercial, the programme submits:

- the generated commercial-specific prompt;
- the corresponding selected frames from:

```text
corpus/05_frames_selected/<Commercial ID>/
```

- the corresponding audio file from:

```text
corpus/03_audio/<Commercial ID>.wav
```

For example:

```text
corpus/03_audio/tv_com_1950_1.wav
```

The selected frames remain the primary evidence for what is visible. The audio is
included only as supporting context, for example to help clarify product names,
brand names, slogans, speakers, or ambiguous visual references. Audio-only
information should not be described as visible.

The dense sampled frames in `corpus/05_frames/` are not used for this stage.
Only the filtered selected frames from `corpus/05_frames_selected/` are submitted
to the model.

Responses are saved in:

```text
corpus/06_visual_descriptions/
```

Each successful commercial produces:

```text
corpus/06_visual_descriptions/<Commercial ID>.txt
corpus/06_visual_descriptions/<Commercial ID>.json
```

The `.txt` file contains the clean visual description returned by the model. The
`.json` file records reproducibility metadata, including the metadata source,
prompt template, generated prompt file, prompt hashes, submitted frames,
submitted audio file, model configuration, response metadata, and any error
information.

Default test run:

```bash
python describe_commercials_visual.py
```

Full run:

```bash
python describe_commercials_visual.py --no-test-mode
```

Reprocess existing prompts and visual descriptions:

```bash
python describe_commercials_visual.py --no-test-mode --reprocess
```

Resume from a specific commercial ID:

```bash
python describe_commercials_visual.py \
  --no-test-mode \
  --start-commercial-id tv_com_1960_54
```

Use a Stage 2 frame cap for cost control:

```bash
python describe_commercials_visual.py \
  --no-test-mode \
  --max-frames-per-request 40
```

Use a non-default audio directory:

```bash
python describe_commercials_visual.py \
  --no-test-mode \
  --audio-dir corpus/03_audio
```

The visual-description stage requires `OPENAI_API_KEY` in `env/.env` or in the
system environment. The API key must not be logged or written to output files.

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

The Lexical Multi-dimensional Analysis (LMDA) was processed according to the corresponding procedures.

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

The Lexical Multi-dimensional Analysis (LMDA) was processed according to the corresponding procedures.

## Phase 4 - Canonical Correlation Analysis of the commercial verbal and visual subcorpora to identify cross-modal discursive patterns

Phase 4 prepares the verbal and visual LMDA factor-score outputs for Canonical Correlation Analysis (CCA). The goal is to create a paired cross-modal dataset in which each row represents the same commercial in both modalities.

The Phase 2 verbal factor scores and Phase 3 visual factor scores were loaded from their respective SAS output files and linked to their `file_ids.txt` mappings. The factor-score columns were renamed to make the modality explicit:

- verbal dimensions: `ver1` to `ver8`;
- visual dimensions: `vis1` to `vis8`.

Only the metadata and factor-score columns required for CCA were retained:

- `file_id`;
- `group_filename`;
- `decade`;
- verbal factor-score columns;
- visual factor-score columns.

Before merging, the verbal and visual score tables were compared by `file_id`. The comparison showed that the verbal score table contained `820` commercials and the visual score table contained `824` commercials. There were no verbal-only rows, but four visual-only rows were identified:

```text
t000455
t000474
t000481
t000538
```

Because CCA requires paired observations, the CCA dataset was created using only commercials present in both modalities. The verbal and visual score tables were therefore inner-merged by `file_id`, producing a CCA-ready table with `820` matched rows.

The shared metadata fields were checked after merging. Both `group_filename` and `decade` agreed across the matched verbal and visual records, so duplicate metadata columns were reduced to a single clean copy.

The resulting CCA dataset contains the following columns:

```text
file_id
group_filename
decade
ver1
ver2
ver3
ver4
ver5
ver6
ver7
ver8
vis1
vis2
vis3
vis4
vis5
vis6
vis7
vis8
```

The CCA-ready dataset was exported to the Phase 1 source metadata directory in three formats:

```text
cl_st1_ph1_andrea/corpus/00_sources/tv_commercials_cca.ndjson
cl_st1_ph1_andrea/corpus/00_sources/tv_commercials_cca.xlsx
cl_st1_ph1_andrea/corpus/00_sources/tv_commercials_cca.tsv
```

These files provide the aligned verbal–visual factor-score matrix for the subsequent Canonical Correlation Analysis.

### Canonical Correlation Analysis

The aligned CCA dataset was analysed in SAS using `PROC CANCORR`. The SAS input file was:

```text
cl_st1_ph4_andrea/output_cl_st1_ph4_andrea_CCA/tv_commercials_cca.tsv
```

The SAS output files were saved under:

```text
cl_st1_ph4_andrea/output_cl_st1_ph4_andrea_CCA/
```

The main outputs are:

```text
cl_st1_ph4_andrea/output_cl_st1_ph4_andrea_CCA/tv_commercials_cca-results.html
cl_st1_ph4_andrea/output_cl_st1_ph4_andrea_CCA/tv_commercials_cca_scores.tsv
```

A Markdown summary of the main CCA results was also prepared as:

```text
cl_st1_ph4_andrea/tv_commercials_cca-results.md
```

The CCA used the eight verbal LMDA factor-score dimensions as the `VAR` set:

```text
ver1
ver2
ver3
ver4
ver5
ver6
ver7
ver8
```

and the eight visual LMDA factor-score dimensions as the `WITH` set:

```text
vis1
vis2
vis3
vis4
vis5
vis6
vis7
vis8
```

The sequential significance tests indicated that the first four canonical functions were statistically significant at `α = .05`:

| Canonical function | Canonical correlation | Squared canonical correlation | p value | Interpretation status          |
|-------------------:|----------------------:|------------------------------:|--------:|--------------------------------|
|                  1 |              0.383981 |                      0.147441 | < .0001 | strongest and most robust      |
|                  2 |              0.335207 |                      0.112364 | < .0001 | robust                         |
|                  3 |              0.244872 |                      0.059962 | < .0001 | robust but weaker              |
|                  4 |              0.162135 |                      0.026288 |  0.0435 | marginal; interpret cautiously |

Canonical functions 5–8 were not statistically significant.

### Canonical structure interpretation

The CCA results were inspected using canonical structure loadings rather than raw canonical coefficients. Canonical structure loadings were preferred for interpretation because they show how strongly each original verbal or visual LMDA dimension correlates with its corresponding canonical variate.

A loading cutoff of:

```text
|loading| >= .30
```

was used to identify the main contributors to each canonical dimension. The original sign of each loading was preserved.

The first four canonical dimensions showed the following structure:

| Canonical dimension | Positive verbal pole   | Negative verbal pole | Positive visual pole | Negative visual pole                   |
|--------------------:|------------------------|----------------------|----------------------|----------------------------------------|
|                   1 | `ver1`, `ver7`         | —                    | `vis7`               | `vis1`, `vis4`, `vis2`, `vis3`, `vis6` |
|                   2 | `ver6`, `ver5`         | `ver3`               | `vis4`, `vis8`       | `vis1`                                 |
|                   3 | `ver2`, `ver5`, `ver8` | —                    | `vis3`, `vis2`       | `vis6`, `vis5`                         |
|                   4 | `ver8`                 | `ver5`               | `vis6`, `vis7`       | `vis5`                                 |

The first canonical dimension is dominated by `ver1` on the verbal side and contrasts `vis7` with a broader cluster of negative visual loadings. The second dimension opposes a cross-modal pattern combining `ver6`, `ver5`, `vis4`, and `vis8` against a contrasting pole defined by `ver3` and `vis1`. The third dimension is centred on `ver2`, supported by `ver5` and `ver8`, and visually aligns with `vis3` and `vis2` while contrasting with `vis6` and `vis5`. The fourth dimension contrasts `ver8` and `vis6`/`vis7` with `ver5` and `vis5`, but it should be interpreted cautiously because its canonical correlation is small and its significance is marginal.

At this stage, the interpretation remains statistical and structural. The substantive discourse interpretation requires replacing labels such as `ver1`, `ver2`, `vis1`, and `vis2` with the factor interpretations developed in Phase 2 and Phase 3.

## Phase 5 - ANOVA Analysis of the commercial verbal, visual, and cross-modal discourses to detect diachronic variation in discourses

