#!/usr/bin/env bash
# End-to-end local test (no YouTube, no systemd, no root needed).
#   bash stream/tests/test_local.sh [WORKDIR]
# Needs: ffmpeg, ffprobe, python3. Takes ~2.5 minutes.
#
# A local FFmpeg RTMP listener stands in for YouTube. The streamer is pushed
# through: skip, graceful restart, new batch with a new loop video (graceful
# restart at a track boundary), FFmpeg crash (kill -9) and FFmpeg hang
# (SIGSTOP -> stall watchdog). Every received recording must have continuous
# audio/video timestamps, 2 s keyframes and silences only at track gaps.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
W="${1:-$(mktemp -d)}"
mkdir -p "$W"
W="$(cd "$W" && pwd)"
rm -rf "${W:?}/home" "${W:?}/run" "${W:?}/rx" "${W:?}/b1" "${W:?}/b2" "${W:?}/stop"
mkdir -p "$W/rx" "$W/b1/stream_tracks" "$W/b2/stream_tracks"
PORT=19350
GAP=1.5
FAIL=0
check() { if "$@"; then echo "PASS: $*"; else echo "FAIL: $*"; FAIL=1; fi; }

echo "== generating test media in $W"
enc=(-c:v libx264 -preset veryfast -profile:v high -pix_fmt yuv420p -b:v 4000k -maxrate 4500k
     -bufsize 9000k -g 60 -keyint_min 60 -sc_threshold 0 -an -movflags +faststart)
ffmpeg -v error -y -f lavfi -i "testsrc2=s=1920x1080:r=30" -t 20 "${enc[@]}" "$W/b1/stream_loop.mp4"
ffmpeg -v error -y -f lavfi -i "smptehdbars=s=1920x1080:r=30" -t 10 "${enc[@]}" "$W/b2/stream_loop.mp4"
ffmpeg -v error -y -f lavfi -i "testsrc2=s=1280x720:r=30" -t 12 -c:v libx264 -preset veryfast \
  -pix_fmt yuv420p -g 300 -an "$W/bad_gop.mp4"
for i in 1 2 3 4 5; do
  ffmpeg -v error -y -f lavfi -i "sine=f=$((200*i+100)):sample_rate=44100:d=$((5+i))" -ac 2 \
    -c:a aac -b:a 192k -metadata title="Tone $((200*i+100)) Hz" "$W/b1/stream_tracks/0${i}_tone.m4a"
done
for i in 1 2 3; do
  ffmpeg -v error -y -f lavfi -i "sine=f=$((150*i+1200)):sample_rate=44100:d=8" -ac 2 \
    -c:a aac -b:a 192k "$W/b2/stream_tracks/0${i}_new_week_song.m4a"
done
printf 'Study lofi test week\n' > "$W/b1/youtube.txt"
head -c 50000 "$W/b2/stream_tracks/01_new_week_song.m4a" > "$W/b2/stream_tracks/09_truncated.m4a"

export PYTHONPATH="$HERE" COC_HOME="$W/home" COC_RUN_DIR="$W/run" MIN_TRACK_SECONDS=5 \
  YOUTUBE_STREAM_KEY=testkey STREAM_URL="rtmp://127.0.0.1:$PORT/live2/testkey" \
  GAP_SECONDS=$GAP DAILY_RESTART_HOUR=-1 STALL_TIMEOUT=10

echo "== sync"
check python3 -m coc.sync --from-dir "$W/b1"
check python3 -c "import json,sys; d=json.load(open('$W/home/state/last_sync.json')); sys.exit(0 if d['tracks_added']==5 else 1)"
if python3 -m coc.sync --from-dir "$W/b1" | grep -q "already have"; then echo "PASS: duplicate output skipped"; else echo "FAIL: dedupe"; FAIL=1; fi
if python3 -m coc.status check-loop "$W/bad_gop.mp4" >/dev/null; then echo "FAIL: bad GOP accepted"; FAIL=1; else echo "PASS: bad GOP loop rejected"; fi

echo "== streaming to local RTMP listener (about 2 minutes)"
( n=0; while [ ! -f "$W/stop" ]; do n=$((n+1));
    ffmpeg -nostdin -v error -y -listen 1 -i "rtmp://127.0.0.1:$PORT/live2/testkey" -c copy -f flv "$W/rx/rx_$n.flv" || true
  done ) > "$W/rx.log" 2>&1 &
RX=$!
sleep 1
( time python3 -m coc.streamer ) > "$W/streamer.log" 2> "$W/time.txt" &
sleep 1
P="$(pgrep -f "python3 -m coc.streamer" | head -n1)"
ffpid() { pgrep -f "ffmpeg.*-progress pipe:1" | head -n1; }
sleep 18; echo "-- skip";             kill -USR2 "$P"
sleep 10; echo "-- graceful restart"; kill -USR1 "$P"
sleep 20; echo "-- new batch with new loop video"; python3 -m coc.sync --from-dir "$W/b2" | tail -n1
sleep 30; echo "-- kill -9 ffmpeg";   kill -9 "$(ffpid)"
sleep 15; echo "-- freeze ffmpeg (SIGSTOP)"; kill -STOP "$(ffpid)"
sleep 25
python3 -m coc.status --no-color || true
touch "$W/stop"; kill "$P"; wait "$P" 2>/dev/null || true
sleep 2; pkill -f "listen 1 -i rtmp://127.0.0.1:$PORT" || true; wait "$RX" 2>/dev/null || true

echo "== results"
cat "$W/time.txt" | grep -E 'real|user|sys' | tr '\n' ' '; echo
log="$W/streamer.log"
check grep -q "skipped:" "$log"
check grep -q "graceful restart at track boundary: requested" "$log"
check grep -q "graceful restart at track boundary: loop video changed" "$log"
check grep -q "ffmpeg exited (code -9)" "$log"
check grep -q "no progress for" "$log"
check grep -q "rejected track 09_truncated.m4a" <(python3 -m coc.sync --from-dir "$W/b2" --force 2>&1)
if grep -q testkey "$log"; then echo "FAIL: stream key leaked into log"; FAIL=1; else echo "PASS: stream key masked in logs"; fi
n=0
for f in "$W"/rx/rx_*.flv; do
  [ -s "$f" ] || continue
  n=$((n+1)); echo "-- $f"
  python3 "$HERE/tests/check_flv.py" "$f" --expect-gap "$GAP" || FAIL=1
done
check test "$n" -ge 4
grep "now playing" "$log" | tail -n 4
echo
if [ "$FAIL" -eq 0 ]; then echo "ALL TESTS PASSED"; else echo "SOME TESTS FAILED"; exit 1; fi
