#!/usr/bin/env bash
# Build the final video:  intro -> your live demo -> real terminal run -> architecture walkthrough
#   bash video/stitch.sh path/to/your-demo-recording.mov   ->  video/shepherd-demo.mp4
# Without an argument it builds a preview with a placeholder card where the demo goes.
set -euo pipefail
cd "$(dirname "$0")"
DEMO="${1:-}"
T=$(mktemp -d)
norm() {  # $1 in, $2 out: 1920x1080, 30 fps, H.264 + AAC (adds silence if the input has no audio)
  if ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$1" | grep -q .; then
    ffmpeg -v error -y -i "$1" -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x0d1510,fps=30" \
      -c:v libx264 -pix_fmt yuv420p -crf 20 -c:a aac -ar 48000 -ac 2 "$2"
  else
    ffmpeg -v error -y -i "$1" -f lavfi -i anullsrc=r=48000:cl=stereo -shortest \
      -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x0d1510,fps=30" \
      -c:v libx264 -pix_fmt yuv420p -crf 20 -c:a aac -ar 48000 -ac 2 "$2"
  fi
}
norm intro.mp4 "$T/1.mp4"
if [ -n "$DEMO" ]; then
  norm "$DEMO" "$T/2.mp4"; OUT=shepherd-demo.mp4
else
  ffmpeg -v error -y -f lavfi -i color=c=0x0d1510:s=1920x1080:d=4:r=30 -f lavfi -i anullsrc=r=48000:cl=stereo -shortest \
    -vf "drawtext=text='[ your live demo goes here ]':fontcolor=0xe2b448:fontsize=64:x=(w-tw)/2:y=(h-th)/2" \
    -c:v libx264 -pix_fmt yuv420p -c:a aac "$T/2.mp4"; OUT=shepherd-preview.mp4
fi
norm terminal.mp4 "$T/3.mp4"
norm architecture.mp4 "$T/4.mp4"
printf "file '%s'\n" "$T/1.mp4" "$T/2.mp4" "$T/3.mp4" "$T/4.mp4" > "$T/list.txt"
ffmpeg -v error -y -f concat -safe 0 -i "$T/list.txt" -c copy "$OUT"
echo "wrote video/$OUT ($(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT" | cut -d. -f1)s)"
