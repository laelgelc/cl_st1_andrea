# By default, the script runs in test mode and attempts only the first 5 planned videos
python download_videos.py

# Full run
python download_videos.py --no-test-mode

# Full run on an EC2 instance
nohup bash run_python_ec2.sh \
   download_videos.py \
       --no-test-mode \
> process_output.log 2>&1 &
