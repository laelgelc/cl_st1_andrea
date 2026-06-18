# ==============================================================================
# Corpus Linguistics - Study 1 - Andrea
# Phase 1 pipeline command reference
#
# This shell script is a command notebook for running the main data-processing
# stages in order. Commands are intentionally listed explicitly so that test runs,
# full runs, resumable runs, and EC2/background runs can be launched manually.
#
# Most Python programmes in this project run in test mode by default, usually
# processing only the first 5 eligible items. Use --no-test-mode for full runs.
# ==============================================================================


# ==============================================================================
# 1. Download source YouTube videos
#
# Programme:
#   download_videos.py
#
# Input:
#   corpus/00_sources/tv_commercials.ndjson
#
# Output:
#   corpus/01_videos/<Video ID>.mp4
#
# Notes:
#   - Default run is test mode.
#   - Existing videos are skipped unless --reprocess is used.
#   - Use --cookies when YouTube blocks automated downloads with authentication,
#     consent, or bot-confirmation checks.
# ==============================================================================

# Test run without browser cookies.
python download_videos.py

# Test run with a Netscape-format cookies file.
# The cookies file can be exported from a signed-in browser session, for example
# from Firefox using a cookies export extension. Treat this file like a password.
python download_videos.py --cookies env/cookies.txt

# Full/resumable run starting from a specific source video ID.
python download_videos.py --no-test-mode --start-video-id video_0504

# Full/resumable run with browser cookies.
python download_videos.py --no-test-mode --cookies env/cookies.txt --start-video-id video_0504


# ==============================================================================
# 2. Split large downloaded video files for Git storage, if needed
#
# Programme:
#   split4git.py
#
# Purpose:
#   Split files in the target directory that are larger than recommended by GitHub.
#
# Notes:
#   - Always inspect the dry run before executing the real split.
#   - This is a repository/storage maintenance step, not part of the analysis
#     pipeline itself.
# ==============================================================================

# Preview planned file-splitting actions.
python split4git.py disband corpus/01_videos --dry-run

# Execute file splitting.
python split4git.py disband corpus/01_videos


# ==============================================================================
# 3. Extract individual commercial clips
#
# Programme:
#   extract_commercials.py
#
# Input:
#   corpus/01_videos/<Video ID>.mp4
#   corpus/00_sources/tv_commercials.ndjson
#
# Output:
#   corpus/02_commercials/<Commercial ID>.mp4
#
# Notes:
#   - Default run is test mode.
#   - Existing clips are skipped unless --reprocess is used.
# ==============================================================================

# Test run.
python extract_commercials.py

# Full run.
python extract_commercials.py --no-test-mode


# ==============================================================================
# 4. Extract Whisper-ready audio from commercial clips
#
# Programme:
#   extract_commercials_audio.py
#
# Input:
#   corpus/02_commercials/<Commercial ID>.mp4
#
# Output:
#   corpus/03_audio/<Commercial ID>.wav
#
# Notes:
#   - Default run is test mode.
#   - Output audio is prepared for Whisper transcription.
# ==============================================================================

# Test run.
python extract_commercials_audio.py

# Full run.
python extract_commercials_audio.py --no-test-mode


# ==============================================================================
# 5. Transcribe commercial audio with Whisper
#
# Programme:
#   transcribe_commercials_whisper.py
#
# Input:
#   corpus/03_audio/<Commercial ID>.wav
#
# Output:
#   corpus/04_transcripts/<Commercial ID>.txt
#   corpus/04_transcripts/<Commercial ID>.json
#
# Notes:
#   - Default run is test mode.
#   - Full transcription is intended to run on an EC2 instance with the appropriate
#     Whisper/CUDA environment.
#   - Before running on EC2, check that run_python_ec2_transcription.sh points to the intended
#     Python environment, for example whisper_lg_v3 rather than my_env.
# ==============================================================================

# Local/default test run.
python transcribe_commercials_whisper.py

# Full EC2 run in the background.
# stdout and stderr are redirected to whisper_transcription_output.log.
nohup bash run_python_ec2_transcription.sh \
   transcribe_commercials_whisper.py \
       --no-test-mode \
> whisper_transcription_output.log 2>&1 &

# Full EC2 run without VAD filtering.
# This may preserve short slogans, jingles, brief voice-over segments, or speech
# over music that automatic voice activity detection could otherwise suppress.
nohup bash run_python_ec2_transcription.sh \
   transcribe_commercials_whisper.py \
       --no-test-mode \
       --no-vad-filter \
> whisper_transcription_output.log 2>&1 &


# ==============================================================================
# 6. Sample representative frames from commercial clips
#
# Programme:
#   sample_commercials_frames.py
#
# Input:
#   corpus/02_commercials/<Commercial ID>.mp4
#
# Output:
#   corpus/05_frames/<Commercial ID>/frame_0001.jpg
#   corpus/05_frames/<Commercial ID>/frames_manifest.json
#
# Notes:
#   - Default run is test mode.
#   - The sampler uses first-frame, scene-change, and last-frame extraction.
#   - The resulting frame directories are the input for visual LLM description.
# ==============================================================================

# Test run.
python sample_commercials_frames.py --test-mode --test-limit 10

# Full run.
python sample_commercials_frames.py --no-test-mode


# Test run.
python select_commercials_frames.py --test-mode --test-limit 10

# Full run.
python select_commercials_frames.py --no-test-mode

# ==============================================================================
# 8. Describe commercial visuals from sampled frames
#
# Programme:
#   describe_commercials_visual.py
#
# Input:
#   corpus/05_frames/<Commercial ID>/frames_manifest.json
#   corpus/05_frames/<Commercial ID>/frame_0001.jpg
#   corpus/05_frames/<Commercial ID>/frame_0002.jpg
#   ...
#
# Output:
#   corpus/06_visual_descriptions/<Commercial ID>.txt
#   corpus/06_visual_descriptions/<Commercial ID>.json
#
# Notes:
#   - This is Stage 2 of the visual analysis pipeline.
#   - It does not sample video frames; it uses the frames already produced by
#     sample_commercials_frames.py.
#   - Default run is test mode.
#   - The default prompt is:
#       describe_commercials_visual_prompts/visual_commercial_description_v1.txt
#   - The programme requires OPENAI_API_KEY in env/.env or in the system environment.
#   - Existing successful descriptions are skipped unless --reprocess is used.
# ==============================================================================

# Default test run using the default prompt, model, and image-detail settings.
python describe_commercials_visual.py

# Test run starting from a specific commercial ID and attempting up to 10 new items.
# Use the exact commercial ID format found under corpus/05_frames/.
python describe_commercials_visual.py \
  --test-limit 10 \
  --start-commercial-id tv_com_1960_54

# Full run with workers.
python describe_commercials_visual.py \
  --no-test-mode \
  --workers 4

# Full run with workers on an EC2 instance.
nohup bash run_python_ec2.sh \
   describe_commercials_visual.py \
       --no-test-mode \
       --workers 4 \
> describe_commercials_visual_output.log 2>&1 &

# Full run with the lightly structured prompt.
python describe_commercials_visual.py \
  --no-test-mode \
  --prompt-file describe_commercials_visual_prompts/visual_commercial_description_v2_lightly_structured.txt

# Full run with an additional Stage 2 frame cap for cost control.
python describe_commercials_visual.py \
  --no-test-mode \
  --max-frames-per-request 20

# Test run.
python describe_commercials_visual.py \
  --test-limit 10 \
  --start-commercial-id tv_com_1960_54
