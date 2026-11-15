set -e
D=29
# chord pad: Am -> F -> C -> G -> Am, each chord rendered separately and crossfaded (0.6 s) so changes are smooth
X=0.6
seg() { f=$1; d=$2; o=$3
  P="0.06*(sin(2*PI*$f*t)+0.6*sin(2*PI*$f*1.2599*t)+0.5*sin(2*PI*$f*1.4983*t)+0.25*sin(2*PI*$f*2*t))*(0.75+0.25*sin(2*PI*0.25*t))"
  ffmpeg -loglevel error -y -f lavfi -i "aevalsrc=exprs='$P|$P':s=44100:d=$d" $o; }
seg 220    6.2 c1.wav   # 0-5.6 (+X)
seg 174.61 9.0 c2.wav   # 5.6-14
seg 130.81 8.4 c3.wav   # 14-21.8
seg 196    3.6 c4.wav   # 21.8-24.8
seg 220    4.8 c5.wav   # 24.8-29
ffmpeg -loglevel error -y -i c1.wav -i c2.wav -i c3.wav -i c4.wav -i c5.wav -filter_complex "[0][1]acrossfade=d=$X[a];[a][2]acrossfade=d=$X[b];[b][3]acrossfade=d=$X[c];[c][4]acrossfade=d=$X,atrim=0:$D,lowpass=f=1800,aecho=0.8:0.7:120|240:0.25|0.15" pad.wav
# rain: filtered pink noise, slowly breathing
ffmpeg -loglevel error -y -f lavfi -i "anoisesrc=color=pink:amplitude=0.12:d=$D:r=44100" -af "highpass=f=500,lowpass=f=5000,volume='0.6+0.4*sin(2*PI*0.08*t)':eval=frame,pan=stereo|c0=c0|c1=c0" rain.wav
# radar pings at the four pass frames (5.6, 6.9, 8.2, 9.5 s) and a final one on the end card (24.9 s)
G='exp(-8*(t-T))*sin(2*PI*1320*t)*gte(t,T)'
PINGS=""; for T in 5.65 6.95 8.25 9.55 24.9; do PINGS="$PINGS+0.12*${G//T/$T}"; done
ffmpeg -loglevel error -y -f lavfi -i "aevalsrc=exprs='0${PINGS}':s=44100:d=$D" -af "aecho=0.8:0.5:180:0.35,pan=stereo|c0=c0|c1=c0" pings.wav
ffmpeg -loglevel error -y -i pad.wav -i rain.wav -i pings.wav -filter_complex "[0][1][2]amix=inputs=3:normalize=0,afade=t=in:st=0:d=1.2,afade=t=out:st=27.3:d=1.7,loudnorm=I=-20:TP=-2:LRA=9" -ar 44100 -c:a pcm_s16le mix.wav
ffmpeg -loglevel error -y -i tanaw-demo-30s.mp4 -i mix.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 160k -shortest -movflags +faststart \
  -metadata title="TANAW - NASA Space Apps 2026 (SI-generated video and audio, made with AI tools)" \
  -metadata comment="Screen captures of the real Tanaw app on real NASA-ISRO NISAR data, assembled with AI-written code (Playwright + ffmpeg). The music is original and was synthesized by AI-written code (ffmpeg); it contains no samples or copyrighted material." \
  tanaw-demo-30s-audio.mp4
