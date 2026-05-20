# Download source YouTube videos for a television commercials corpus
# By default, the script runs in test mode and attempts only the first 5 planned videos

python download_videos.py

python download_videos.py --cookies env/cookies.txt

# Note: is needed when YouTube blocks automated downloads with authentication or bot-confirmation checks;
# it can be obtained by signing in to YouTube in Firefox and exporting browser cookies in Netscape format
# using a cookies export extension.

# Full run

python download_videos.py --no-test-mode --start-video-id video_0504

python download_videos.py --no-test-mode --cookies env/cookies.txt --start-video-id video_0504

# Split files on the indicated directory that are larger than recommended by GitHub

python split4git.py disband corpus/01_videos --dry-run

python split4git.py disband corpus/01_videos

# Clip individual television commercials from previously downloaded source video files.
# By default, the script runs in test mode and attempts only the first 5 commercials

python extract_commercials.py

# Full run

python extract_commercials.py --no-test-mode

# Extract Whisper-ready audio from television commercial video files

python extract_commercials_audio.py

# Full run

python extract_commercials_audio.py --no-test-mode

# Transcribe Whisper-ready audio files extracted from individual television commercial video clips
# By default, the script runs in test mode and attempts only the first 5 commercial audio files

python transcribe_commercials_whisper.py

# Full run on an EC2 instance
# Note: Change the Python environment from 'my_env' to 'whisper_lg_v3' in 'run_python_ec2.sh'

nohup bash run_python_ec2.sh \
   transcribe_commercials_whisper.py \
       --no-test-mode \
> process_output.log 2>&1 &
