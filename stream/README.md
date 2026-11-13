# stream/ — 24/7 YouTube Live host

Technical reference for the VPS that runs the Classic of Calm live stream
(OVHcloud VPS-1, 2 vCPU / 4 GB, Ubuntu 24.04; also works on Oracle ARM).
For the owner, the only commands that matter are the install line and `coc`.

## Install

On a fresh Ubuntu 24.04 server, logged in as the default `ubuntu` user:

```bash
curl -fsSL https://raw.githubusercontent.com/OWNER/classic-of-calm/main/stream/install.sh | sudo bash
```

- **Before first use, replace `OWNER`** in that line *and* in `COC_REPO=` at the
  top of `install.sh` with the real GitHub owner. For a private repo, do
  `export GITHUB_TOKEN=<read-only token>` and then `curl ... | sudo -E bash`. Or copy
  the `stream/` folder to the server and run `sudo bash stream/install.sh`.
- The script asks 4 questions in English and Traditional Chinese: the YouTube
  stream key, the Kaggle username, the Kaggle API token (`KGAT_...`) or legacy
  key, and the "02 Assemble" notebook (a URL or `owner/slug`). Secrets are
  read with hidden input from `/dev/tty`, so `curl | bash` still works.
- Without a TTY, or with `--yes`, it takes `YOUTUBE_STREAM_KEY`,
  `KAGGLE_USERNAME`, `KAGGLE_KEY`/`KAGGLE_API_TOKEN` and `KAGGLE_NOTEBOOK` from
  the environment.
- You can run it again safely. It upgrades the code and keeps your settings and
  library. To change only the answers, run `sudo coc setup` (the same as
  `install.sh --configure`).

What it does:

1. Installs `ffmpeg python3 python3-venv unattended-upgrades logrotate acl`
   with apt, and the Kaggle CLI in `/opt/classic-of-calm/venv`. It installs
   `six` explicitly because kaggle 2.2.x imports it without declaring it.
2. Adds a 2 GB `/swapfile`, but only if RAM is below 2 GB and there is no swap.
3. Creates the system user `stream` (no login shell). Data goes in
   `/var/lib/classic-of-calm`, code in `/opt/classic-of-calm`, and the CLI is
   linked at `/usr/local/bin/coc`.
4. Writes `/etc/classic-of-calm/env` (`root:root 600`; systemd reads it through
   `EnvironmentFile=`). See `config/env.example` for every setting. Comments
   must go on their own lines because systemd does not strip trailing comments.
5. Generates `placeholder_loop.mp4`, a plain ink-green picture. The stream can
   go live before the first sync finishes.
6. Installs `coc-streamer.service`, `coc-sync.service` and `coc-sync.timer`,
   plus a journald size cap (300 MB / 1 month) and a logrotate rule for
   `played.log`.
7. Turns on unattended-upgrades for security updates. When a reboot is
   required, the server reboots at 04:20.
8. Checks the Kaggle login with `kaggle kernels status`, then starts the first
   sync in the background and starts the stream.

## Architecture

```
            ┌──────────── coc-streamer.service (python3 -m coc.streamer, user stream) ────────────┐
 library/   │  feeder loop: pick track → ffmpeg -i track.m4a -f s16le pipe:1 → write into pipe ──┐ │
 batches/*/ │                                                                                     │ │
 tracks/*.m4a                                                                    os.pipe (PCM) │ │
            │  main ffmpeg:  -re -stream_loop -1 -i stream_loop.mp4   (video, -c:v copy)   ◄────┘ │
 current_   │                -f s16le -i pipe:N                       (audio → AAC 160k)          │
 loop.mp4 ──┤                -f flv rtmp://a.rtmp.youtube.com/live2/<key>                         │
            │  watchdog thread: -progress → stall check, sd_notify WATCHDOG, state json, now-playing│
            └──────────────────────────────────────────────────────────────────────────────────────┘
 coc-sync.timer (daily 06:00 ± 45 min) → coc-sync.service → kaggle kernels output → validate → library/
```

### Why a PCM pipe and not the concat demuxer

The main FFmpeg reads a single, endless raw-PCM input. Track changes happen
entirely in the feeder, so the RTMP session never breaks between songs.
Timestamps are derived from the sample count, which keeps them continuous with
no drift. The feeder rescans the library at every track boundary, so new tracks
from `coc sync` start playing **without a restart**. A concat playlist would be
fixed when it starts, and would need an FFmpeg restart (an RTMP reconnect) to
pick up new files.

- Backpressure paces the feeder. The pipe is 512 KB (about 3 s) plus
  `-thread_queue_size 128` (about 3 s). The feeder therefore runs about 6 s ahead
  of what viewers hear. "Now playing" is published only when FFmpeg's
  `out_time` reaches the first sample of the track, so it is accurate to
  about 1 s.
- Every track is decoded to 44.1 kHz s16le stereo, so no resampling is needed
  for 44.1 kHz masters. A 50 ms fade-in removes clicks. Between tracks the
  feeder inserts `GAP_SECONDS` of silence (default 2 s).
- The audio is encoded to AAC once, in the main FFmpeg (`AUDIO_BITRATE`,
  default 160k). The video is never re-encoded.
- If the library is empty, the feeder writes silence. The stream stays up and
  plays the loop or placeholder picture.

### Restarts (RTMP reconnects)

| Cause | Behaviour |
|---|---|
| New loop video (`current_loop.mp4` target changed) | Graceful: at the next track boundary, the feeder closes the pipe and waits until FFmpeg has played the buffered audio (`out_time ≥ fed audio`, so the cut falls inside the inter-track gap). It then sends SIGTERM and starts a new session at once. Measured gap: under 1 s locally |
| `DAILY_RESTART_HOUR` (default 4, server time; `-1` = off) | Same graceful path, once a day. This avoids long-run timestamp drift and the FLV 32-bit ms wrap after about 49 days |
| `sudo coc restart` / `systemctl reload coc-streamer` (SIGUSR1) | Same graceful path |
| FFmpeg exits (network error, YouTube dropped the connection) | Reconnect with backoff of 2, 4, 8 … up to 60 s. The backoff resets after 5 healthy minutes |
| FFmpeg makes no progress for `STALL_TIMEOUT` s (default 45) | The watchdog thread sends SIGKILL to FFmpeg, then the reconnect path runs. `-rw_timeout 20 s` also fails a blocked RTMP write |
| Python supervisor hangs or dies | systemd `WatchdogSec=180` (it is pinged only while healthy) together with `Restart=always`, `StartLimitIntervalSec=0` |

Signals for the main PID: TERM/INT stop, USR1/HUP do a graceful restart, USR2
skips the current track (`sudo coc skip`).

Turn **off "Auto-stop"** in YouTube Studio's stream settings. A reconnect then
continues the same broadcast instead of ending it. Use the default
(persistent) stream key, not a one-time key.

### rtmps

`STREAM_PROTOCOL=rtmps` uses `rtmps://a.rtmps.youtube.com:443/live2/<key>`.
Ubuntu's FFmpeg supports it. It encrypts the stream key in transit, at almost no
CPU cost. `STREAM_URL=` overrides the whole URL, for example to use YouTube's
backup ingest or a local test server. The stream key is masked as `****` in
everything the streamer logs, and that includes FFmpeg's own error lines. The
key is still visible in the FFmpeg command line (`ps`) to local root and to the
`stream` user.

## Loop video requirements (for `pipeline/visuals.py`)

The video is sent with `-c:v copy`, so the file must already meet YouTube's
ingest spec. `sync` refuses a loop that fails the hard checks (you can run
`coc check-loop FILE` to test one):

| Requirement | Hard / soft |
|---|---|
| H.264 (High profile), `yuv420p` | hard |
| First frame is a keyframe; keyframe interval **exactly 2 s** (warn if > 2 s, reject if > 4 s, including the tail before the loop restarts) | hard |
| Duration ≥ 2 s. Use 20–60 s, and a whole multiple of 2 s so the GOP grid survives the loop point | hard / recommended |
| 1920x1080, 30 fps constant frame rate | soft (warning on unusual sizes) |
| About 4000–4500 kbps capped VBR/CBR (warning above 9 Mbps) | soft |
| No audio track (it is ignored anyway), `+faststart` | recommended |

Suggested encode:

```bash
ffmpeg -i frames_or_render -t 30 -r 30 -c:v libx264 -preset slow -profile:v high -pix_fmt yuv420p \
  -b:v 4000k -maxrate 4500k -bufsize 9000k -g 60 -keyint_min 60 -sc_threshold 0 \
  -force_key_frames "expr:gte(t,n_forced*2)" -an -movflags +faststart stream_loop.mp4
```

B-frames are fine. Make the first and last frames visually continuous; the
streamer does not crossfade at the loop point.

## Library and sync

```
/var/lib/classic-of-calm/
  library/batches/<YYYY-MM-DD_HHMMSS_fp>/manifest.json  tracks/*.m4a  stream_loop.mp4  youtube.txt
  library/current_loop.mp4 -> batches/<newest batch with a valid loop>/stream_loop.mp4
  placeholder_loop.mp4          used until the first valid loop exists
  staging/                      temporary downloads (removed after each sync)
  state/last_sync.json          result of the last sync (read by `coc status`)
  state/played.log              play history (TSV, logrotated weekly)
  now_playing.txt / .json       current title, ready for a future overlay
/run/classic-of-calm/streamer.json   live state, rewritten every 2 s
```

`python3 -m coc.sync` (the daily timer, or `sudo coc sync`):

1. Prunes first, to make room.
2. Asks `kaggle kernels list --mine` for the notebook's `lastRunTime`. If it is
   unchanged since the last good sync, the run is skipped with no download.
3. Runs `kaggle kernels output <KAGGLE_NOTEBOOK> -p staging/... --file-pattern
   '(stream_tracks/*.m4a|stream_loop.mp4|youtube.txt)' --page-size 200`. The
   filter skips the large `compilation.mp4`; on CLIs without the flag, the
   download is retried without it.
4. Skips the import if the output's fingerprint (names, sizes and the first
   64 KB of each file) matches a batch it already has.
5. Validates every `.m4a`: ffprobe audio stream, duration 20 s–30 min, and a
   **full decode with no errors**, which catches truncated downloads. Bad files
   are rejected and listed in the manifest. The loop goes through the checks in
   the table above.
6. Builds the batch in `batches/.tmp-*` and renames it into place, so readers
   never see a half-written batch. The title comes from the m4a `title` tag,
   or else from the file name (`03_misty_pine.m4a` → "Misty Pine"). The series
   (study/sleep/work) is read from the first lines of `youtube.txt`.
7. Points `current_loop.mp4` at the newest valid loop. The streamer notices and
   reconnects gracefully at the next track boundary.
8. Retention: it keeps `KEEP_BATCHES` (8 weeks), `LIBRARY_MAX_GB` (15) and
   `MIN_FREE_GB` (3). The newest batch and the batch holding the current loop
   are never deleted.

`sudo coc import DIR` imports a folder with the same layout, which is useful
when Kaggle is unavailable. The source files are copied, never moved.

Track choice is a weighted shuffle. There are no repeats within the last
`len(tracks)/2` plays, and tracks in the newest batch are `NEW_TRACK_WEIGHT`
(3×) as likely to be picked, so each new week is heard often while older weeks
stay in the mix. `STREAM_SERIES=study|sleep|work` limits the stream to one
series (batches with an unknown series are always included).

## Operations

```
coc                     status screen (stream up?, uptime, now playing, library, last/next sync, disk, last error)
coc now                 current title
sudo coc logs [-f]      journalctl -u coc-streamer -u coc-sync
sudo coc sync           run the sync now and show the result
sudo coc import DIR     import a local folder
sudo coc restart        graceful reconnect at the end of the current song; --now = systemctl restart
sudo coc skip           next song
sudo coc stop|start
sudo coc setup          re-ask stream key / Kaggle answers, then restart
coc check-loop FILE     validate a loop video
```

## Resource use (measured)

On the dev box, a 150 s run with a 1080p30 4 Mbps loop, 256k AAC sources
pushed over RTMP took **6.9 CPU-seconds in total: about 4.6 % of one core**
for the supervisor, main FFmpeg and per-track decoders together. Expect about
5–10 % of one vCPU on VPS-1. The sync runs with `Nice=15`, `IOSchedulingClass=idle`
and `CPUWeight=20`, and the streamer runs with `Nice=-5` and `OOMScoreAdjust=-500`.
RAM use is under 100 MB. Bandwidth is about 4.3 Mbps, or about 1.4 TB a month,
so the plan needs unmetered traffic.

## Tests

```bash
bash stream/tests/test_local.sh /tmp/some-scratch-dir
```

The test needs only ffmpeg and python3, with no root, systemd or network. It
generates a 1080p loop with 2 s GOPs, a second loop, a loop with a bad GOP,
tone tracks and a truncated m4a. It runs `sync`, then streams to a **local
FFmpeg RTMP listener** that stands in for YouTube for about 2 minutes, while
doing a skip, a graceful restart, a new batch with a new loop, `kill -9` of
FFmpeg and a SIGSTOP freeze to trigger the stall watchdog. It then checks every
received recording with `tests/check_flv.py`:

- video and audio DTS strictly continuous
- keyframes every 2.00 s across loop wraps
- silences only at the expected inter-track gaps
- dedupe works, the bad loop and the truncated track are rejected, and the key
  does not appear in the logs

`shellcheck` passes on `install.sh`, `bin/coc` and `tests/test_local.sh`.

Not tested here: the real YouTube ingest and the real Kaggle download (no
credentials or network in the dev sandbox), and running `install.sh` on a real
Ubuntu 24.04 VM. The installer's configure step was tested both
non-interactively and through a pseudo-TTY.

## Uninstall

```bash
sudo systemctl disable --now coc-streamer coc-sync.timer
sudo rm -f /etc/systemd/system/coc-* /usr/local/bin/coc /etc/logrotate.d/classic-of-calm \
  /etc/systemd/journald.conf.d/classic-of-calm.conf /etc/apt/apt.conf.d/52classic-of-calm
sudo rm -rf /opt/classic-of-calm /etc/classic-of-calm /var/lib/classic-of-calm /run/classic-of-calm
sudo userdel stream
```
