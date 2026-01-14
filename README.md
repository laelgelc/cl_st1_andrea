# Corpus Linguistics - Study 1 - Andrea

## Phase 0 - Data Collection Testing

### Download (`yt-dlp`) and slice (`ffmpeg`) videos
The following commands were used to test downloading and slicing videos from YouTube.

```
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

. The script should accept a list of video URLs and a list of time ranges for slicing, and output the sliced videos with appropriate naming conventions.

## Phase 1 - Data Collection

