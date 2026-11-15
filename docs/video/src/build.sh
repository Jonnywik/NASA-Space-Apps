set -e
mk() { # name seconds zoom(1/0)
  n=$1; d=$2; z=$3; f=$(python3 -c "print(round($d*30))")
  if [ "$z" = 1 ]; then
    ffmpeg -loglevel error -y -loop 1 -i scenes/$n.png -vf "scale=3840:2160,zoompan=z='1+0.035*on/$f':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=$f:s=1920x1080:fps=30,format=yuv420p" -frames:v $f -c:v libx264 -crf 18 -preset medium seg/$n.mp4
  else
    ffmpeg -loglevel error -y -loop 1 -i scenes/$n.png -vf "fps=30,format=yuv420p" -frames:v $f -c:v libx264 -crf 18 -preset medium seg/$n.mp4
  fi
}
mk s01_title 2.6 1
mk s02_question 3.0 1
mk s03_p1 1.3 0
mk s03_p2 1.3 0
mk s03_p3 1.3 0
mk s03_p4 1.3 0
mk s04_sees 3.2 1
mk s05_valid 4.0 1
mk s06_cant 3.8 1
mk s07_spot 3.0 1
mk s08_end 4.2 1
for n in s01_title s02_question s03_p1 s03_p2 s03_p3 s03_p4 s04_sees s05_valid s06_cant s07_spot s08_end; do echo "file 'seg/$n.mp4'"; done > list.txt
ffmpeg -loglevel error -y -f concat -safe 0 -i list.txt -c copy joined.mp4
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 joined.mp4)
ffmpeg -loglevel error -y -i joined.mp4 -vf "fade=t=in:st=0:d=0.4,fade=t=out:st=$(python3 -c "print($D-0.5)"):d=0.5" -c:v libx264 -crf 20 -preset slow -pix_fmt yuv420p -movflags +faststart -metadata title="TANAW - NASA Space Apps 2026 (SI-generated video, made with AI tools)" -metadata comment="Screen captures of the real Tanaw app on real NASA-ISRO NISAR data; assembled with AI-written code (Playwright + ffmpeg)." tanaw-demo-30s.mp4
