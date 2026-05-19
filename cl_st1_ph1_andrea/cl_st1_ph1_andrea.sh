# By default, the script runs in test mode and attempts only the first 5 planned videos
python download_videos.py --cookies env/cookies.txt

#Note: is needed when YouTube blocks automated downloads with authentication or bot-confirmation checks;
# it can be obtained by signing in to YouTube in Firefox and exporting browser cookies in Netscape format
# using a cookies export extension.

# Full run
python download_videos.py --no-test-mode --cookies env/cookies.txt

# Full run on an EC2 instance
nohup bash run_python_ec2.sh \
   download_videos.py \
       --no-test-mode \
       --cookies env/cookies.txt \
> process_output.log 2>&1 &
