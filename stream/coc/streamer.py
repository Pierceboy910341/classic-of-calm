"""24/7 YouTube Live streamer for Classic of Calm.

One long-running FFmpeg pushes to YouTube:
    video  = stream_loop.mp4 looped forever (-stream_loop -1 -re, -c:v copy)
    audio  = raw PCM read from a pipe (fd), encoded once to AAC

This process is the *feeder*: it decodes one .m4a after another (a small
ffmpeg per track) and writes the PCM into that pipe. Because the main FFmpeg
only ever sees one endless PCM stream, track changes never touch the RTMP
session. New tracks that `coc sync` adds are picked up at the next track
boundary with no restart.

The RTMP session is only restarted (gracefully, at a track boundary) when:
  * the loop video changed (new week's stream_loop.mp4),
  * the daily maintenance hour is reached (DAILY_RESTART_HOUR, -1 = never),
  * someone asks for it: SIGUSR1 / `coc restart` .
FFmpeg crashes or stalls (no progress for STALL_TIMEOUT s) restart it with
backoff. systemd restarts *this* process if it dies or stops pinging the
watchdog.

Signals: SIGTERM/SIGINT stop, SIGUSR1 graceful restart at next track
boundary, SIGUSR2 skip current track.
"""
from __future__ import annotations

import collections
import fcntl
import os
import random
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .common import (Config, load_config, log, sd_notify, write_json_atomic,
                     write_text_atomic)
from .library import list_batches, list_tracks, library_signature, resolve_loop

CHUNK = 64 * 1024
F_SETPIPE_SZ = 1031


def iso(ts: float | None = None) -> str:
    return datetime.fromtimestamp(ts or time.time(), timezone.utc).isoformat(timespec="seconds")


class TrackPicker:
    """Shuffled, no-recent-repeat picker that favours the newest batch."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.sig = None
        self.tracks = []
        self.newest_ts = 0.0
        self.multi_batch = False
        self.recent: collections.deque = collections.deque()

    def refresh(self) -> None:
        sig = library_signature(self.cfg)
        if sig == self.sig:
            return
        self.sig = sig
        batches = list_batches(self.cfg)
        self.tracks = list_tracks(self.cfg, batches)
        self.newest_ts = max((t.imported_ts for t in self.tracks), default=0.0)
        self.multi_batch = len({t.batch_id for t in self.tracks}) > 1
        log(f"library: {len(self.tracks)} tracks in {len(batches)} batches")

    def next(self):
        self.refresh()
        if not self.tracks:
            return None
        hist = max(0, min(len(self.tracks) // 2, 200))
        while len(self.recent) > hist:
            self.recent.popleft()
        recent = set(self.recent)
        avail = [t for t in self.tracks if t.path not in recent and t.path.exists()]
        if not avail:
            self.recent.clear()
            avail = [t for t in self.tracks if t.path.exists()]
            if not avail:
                return None
        w = self.cfg.new_track_weight if self.multi_batch else 1.0
        weights = [w if t.imported_ts == self.newest_ts else 1.0 for t in avail]
        t = random.choices(avail, weights=weights, k=1)[0]
        if hist:
            self.recent.append(t.path)
        return t


class Session:
    """One FFmpeg process == one RTMP connection."""

    def __init__(self, cfg: Config, loop: Path, url: str):
        self.cfg = cfg
        self.loop = loop
        self.started = time.time()
        self.last_advance = time.monotonic()
        self.out_time = 0.0
        self.speed = ""
        self.bitrate = ""
        self.audio_pos = 0  # bytes of PCM written into the pipe
        self.stderr_tail: collections.deque = collections.deque(maxlen=15)
        self.pending: collections.deque = collections.deque()  # (start_sec, track)
        self.bytes_per_sec = cfg.audio_rate * 2 * 2  # s16le stereo

        r, w = os.pipe()
        try:
            fcntl.fcntl(w, F_SETPIPE_SZ, 1 << 20)  # ~6 s cushion between tracks
        except OSError:
            pass
        self.wfd = w
        cmd = [cfg.ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "warning",
               "-nostats", "-progress", "pipe:1", "-stats_period", "1",
               "-re", "-stream_loop", "-1", "-i", str(loop),
               "-thread_queue_size", "1024",
               "-f", "s16le", "-ar", str(cfg.audio_rate), "-ac", "2", "-i", f"pipe:{r}",
               "-map", "0:v:0", "-map", "1:a:0",
               "-c:v", "copy",
               "-c:a", "aac", "-b:a", cfg.audio_bitrate, "-ar", str(cfg.audio_rate), "-ac", "2",
               "-shortest", "-max_muxing_queue_size", "2048",
               "-f", cfg.stream_format]
        if cfg.stream_format == "flv":
            cmd += ["-flvflags", "no_duration_filesize"]
        if url.startswith("rtmp"):
            cmd += ["-rw_timeout", "20000000"]  # fail a blocked socket write after 20 s
        cmd.append(url)
        self.secret = cfg.stream_key
        log(f"starting ffmpeg session: loop={loop.name} url={self.mask(url)}")
        self.proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, pass_fds=(r,), bufsize=0)
        os.close(r)
        self.t_progress = threading.Thread(target=self._read_progress, daemon=True)
        self.t_stderr = threading.Thread(target=self._read_stderr, daemon=True)
        self.t_progress.start()
        self.t_stderr.start()

    def mask(self, s: str) -> str:
        return s.replace(self.secret, "****") if self.secret else s

    def alive(self) -> bool:
        return self.proc.poll() is None

    def _read_progress(self):
        for raw in self.proc.stdout:
            line = raw.decode(errors="replace").strip()
            k, _, v = line.partition("=")
            if k == "out_time_us":
                try:
                    t = int(v) / 1e6
                except ValueError:
                    continue
                if t > self.out_time:
                    self.out_time = t
                    self.last_advance = time.monotonic()
            elif k == "speed":
                self.speed = v
            elif k == "bitrate":
                self.bitrate = v

    def _read_stderr(self):
        for raw in self.proc.stderr:
            line = self.mask(raw.decode(errors="replace").rstrip())
            if line:
                self.stderr_tail.append(line)
                log(f"ffmpeg: {line}")

    def write(self, data: bytes) -> None:
        mv = memoryview(data)
        while mv:
            n = os.write(self.wfd, mv)
            mv = mv[n:]
            self.audio_pos += n

    def close_input(self):
        if self.wfd is not None:
            try:
                os.close(self.wfd)
            except OSError:
                pass
            self.wfd = None

    def stop(self, graceful: bool):
        self.close_input()
        if graceful:
            # -shortest: ffmpeg drains the remaining audio and exits on its own.
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                pass
        if self.alive():
            self.proc.terminate()
            try:
                self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self.t_progress.join(timeout=2)
        self.t_stderr.join(timeout=2)


class Streamer:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.picker = TrackPicker(cfg)
        self.session: Session | None = None
        self.stop_flag = threading.Event()
        self.restart_flag = threading.Event()
        self.skip_flag = threading.Event()
        self.status = "starting"
        self.started = time.time()
        self.sessions = 0
        self.failures = 0
        self.tracks_played = 0
        self.last_error = ""
        self.now_playing: dict | None = None
        self.heartbeat = time.monotonic()
        self.lock = threading.Lock()

    # ---- signals ---------------------------------------------------------
    def install_signals(self):
        def stop(signum, _frame):
            log(f"signal {signum}: stopping")
            self.stop_flag.set()
            s = self.session
            if s:
                s.close_input()
                if s.alive():
                    s.proc.terminate()

        def restart(_s, _f):
            log("graceful restart requested (will happen at next track boundary)")
            self.restart_flag.set()

        def skip(_s, _f):
            log("skip requested")
            self.skip_flag.set()

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGUSR1, restart)
        signal.signal(signal.SIGHUP, restart)
        signal.signal(signal.SIGUSR2, skip)

    # ---- watchdog / state thread -------------------------------------------
    def watchdog_loop(self):
        last_state = 0.0
        while not self.stop_flag.is_set():
            s = self.session
            healthy = True
            if s is not None and s.alive():
                stalled_for = time.monotonic() - s.last_advance
                if stalled_for > self.cfg.stall_timeout:
                    healthy = False
                    self.last_error = f"no progress for {int(stalled_for)} s, restarting ffmpeg"
                    log(self.last_error)
                    s.close_input()
                    s.proc.kill()
                self._announce(s)
            elif time.monotonic() - self.heartbeat > 120:
                healthy = False  # main loop wedged -> let systemd restart us
            if healthy:
                sd_notify("WATCHDOG=1")
            if time.time() - last_state >= 2:
                last_state = time.time()
                self.write_state()
            time.sleep(1)

    def _announce(self, s: Session):
        """Publish 'now playing' when FFmpeg actually reaches a track's first
        sample (the feeder runs a few seconds ahead because of buffering)."""
        while s.pending and s.pending[0][0] <= s.out_time + 0.5:
            _, t = s.pending.popleft()
            self.now_playing = {"title": t.title, "file": str(t.path), "batch": t.batch_id,
                                "series": t.series, "duration": t.duration,
                                "started_at": iso()}
            self.tracks_played += 1
            try:
                write_text_atomic(self.cfg.now_playing_txt, t.title + "\n")
                write_json_atomic(self.cfg.now_playing_json, self.now_playing)
                with open(self.cfg.history_file, "a") as f:
                    f.write(f"{iso()}\t{t.batch_id}\t{t.path.name}\t{t.title}\n")
            except OSError as e:
                log(f"cannot write now-playing files: {e}")
            log(f"now playing: {t.title} [{t.batch_id}]")

    def write_state(self):
        s = self.session
        state = {
            "pid": os.getpid(),
            "status": self.status,
            "service_started_at": iso(self.started),
            "sessions": self.sessions,
            "unexpected_restarts": self.failures,
            "tracks_played": self.tracks_played,
            "last_error": self.last_error,
            "now_playing": self.now_playing,
            "updated_at": iso(),
        }
        if s is not None:
            state.update({
                "session_started_at": iso(s.started),
                "loop": str(s.loop),
                "out_time": round(s.out_time, 1),
                "speed": s.speed,
                "bitrate": s.bitrate,
                "seconds_since_progress": round(time.monotonic() - s.last_advance, 1),
                "ffmpeg_alive": s.alive(),
            })
        try:
            write_json_atomic(self.cfg.streamer_state, state)
        except OSError:
            pass

    # ---- feeding -------------------------------------------------------------
    def _silence(self, s: Session, seconds: float) -> str:
        n = int(seconds * s.bytes_per_sec) // 4 * 4
        zero = bytes(min(CHUNK, n) or 4)
        while n > 0:
            if self.stop_flag.is_set():
                return "stop"
            k = min(n, len(zero))
            try:
                s.write(zero[:k])
            except (BrokenPipeError, OSError, TypeError):
                return "died"
            n -= k
            self.heartbeat = time.monotonic()
        return "ok"

    def _play(self, s: Session, track) -> str:
        cfg = self.cfg
        cmd = [cfg.ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error",
               "-i", str(track.path), "-vn", "-sn", "-dn",
               "-af", "afade=t=in:d=0.05",
               "-f", "s16le", "-ar", str(cfg.audio_rate), "-ac", "2", "pipe:1"]
        try:
            dec = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   bufsize=0)
        except OSError as e:
            log(f"cannot start decoder: {e}")
            return "ok"
        s.pending.append((s.audio_pos / s.bytes_per_sec, track))
        result = "ok"
        carry = b""
        written = 0
        try:
            while True:
                if self.stop_flag.is_set():
                    result = "stop"
                    break
                if self.skip_flag.is_set():
                    self.skip_flag.clear()
                    log(f"skipped: {track.title}")
                    break
                chunk = dec.stdout.read(CHUNK)
                if not chunk:
                    break
                data = carry + chunk
                cut = len(data) - (len(data) % 4)  # keep whole stereo frames
                carry = data[cut:]
                if cut:
                    s.write(data[:cut])
                    written += cut
                self.heartbeat = time.monotonic()
        except (BrokenPipeError, OSError, TypeError):
            result = "died"
        finally:
            if dec.poll() is None:
                dec.kill()
            dec.wait()
            dec.stdout.close()
        if result == "ok" and written == 0:
            log(f"WARNING: track produced no audio, skipping: {track.path}")
            if s.pending and s.pending[-1][1] is track:
                s.pending.pop()
        return result

    def _restart_due(self, s: Session) -> str | None:
        if self.restart_flag.is_set():
            return "requested"
        loop = resolve_loop(self.cfg)
        if loop is not None and loop != s.loop:
            return f"loop video changed -> {loop.name}"
        h = self.cfg.daily_restart_hour
        if 0 <= h <= 23 and time.localtime().tm_hour == h and time.time() - s.started > 7200:
            return "daily maintenance restart"
        return None

    def feed(self, s: Session) -> str:
        while True:
            self.heartbeat = time.monotonic()
            if self.stop_flag.is_set():
                return "stop"
            if not s.alive():
                return "died"
            why = self._restart_due(s)
            if why:
                log(f"graceful restart at track boundary: {why}")
                return "restart"
            track = self.picker.next()
            if track is None:
                self.status = "streaming (library empty: silence)"
                r = self._silence(s, 5)
            else:
                self.status = "streaming"
                r = self._play(s, track)
                if r == "ok":
                    r = self._silence(s, self.cfg.gap_seconds)
            if r != "ok":
                return r

    # ---- main loop -----------------------------------------------------------
    def _wait(self, seconds: float):
        end = time.monotonic() + seconds
        while time.monotonic() < end and not self.stop_flag.is_set():
            self.heartbeat = time.monotonic()
            time.sleep(0.5)

    def run(self) -> int:
        self.install_signals()
        for d in (self.cfg.state_dir, self.cfg.run_dir):
            d.mkdir(parents=True, exist_ok=True)
        threading.Thread(target=self.watchdog_loop, daemon=True).start()
        sd_notify("READY=1")
        backoff = 2.0
        while not self.stop_flag.is_set():
            url = self.cfg.stream_url()
            if not url:
                self.status = "waiting: no YouTube stream key configured"
                log(self.status)
                self._wait(60)
                continue
            loop = resolve_loop(self.cfg)
            if loop is None:
                self.status = "waiting: no loop video yet (run `coc sync`)"
                log(self.status)
                self._wait(60)
                continue
            self.restart_flag.clear()
            self.status = "connecting"
            s = Session(self.cfg, loop, url)
            self.session = s
            self.sessions += 1
            result = self.feed(s)
            graceful = result == "restart"
            s.stop(graceful=graceful)
            rc = s.proc.returncode
            if result == "stop" or self.stop_flag.is_set():
                break
            if graceful:
                backoff = 2.0
                continue
            self.failures += 1
            healthy_for = time.time() - s.started
            if healthy_for > 300:
                backoff = 2.0
            tail = " | ".join(list(s.stderr_tail)[-3:])
            self.last_error = f"ffmpeg exited (code {rc}) after {int(healthy_for)} s: {tail}"[:500]
            log(self.last_error)
            self.status = f"reconnecting in {int(backoff)} s"
            self._wait(backoff)
            backoff = min(backoff * 2, 60.0)
        self.status = "stopped"
        self.write_state()
        sd_notify("STOPPING=1")
        log("streamer stopped")
        return 0


def main() -> int:
    cfg = load_config()
    if cfg.gap_seconds < 0:
        cfg.gap_seconds = 0
    return Streamer(cfg).run()


if __name__ == "__main__":
    sys.exit(main())
