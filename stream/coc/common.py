"""Shared config, paths and helpers for the Classic of Calm stream host.

Everything is configured through environment variables (systemd loads them from
/etc/classic-of-calm/env). Defaults below are what a fresh install uses.
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

ENV_FILE = Path("/etc/classic-of-calm/env")


def _load_env_file(path: Path = ENV_FILE) -> dict:
    """Parse a simple KEY=VALUE env file (only used when not already in env,
    e.g. when `coc status` is run by hand as root)."""
    out = {}
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]
        out[k.strip()] = v
    return out


def _env() -> dict:
    merged = _load_env_file()
    merged.update(os.environ)
    return merged


def _int(env, key, default):
    try:
        return int(str(env.get(key, default)).strip())
    except ValueError:
        return default


def _float(env, key, default):
    try:
        return float(str(env.get(key, default)).strip())
    except ValueError:
        return default


@dataclass
class Config:
    home: Path
    run_dir: Path
    stream_key: str
    protocol: str
    stream_url_override: str
    stream_format: str
    audio_bitrate: str
    audio_rate: int
    gap_seconds: float
    stall_timeout: int
    daily_restart_hour: int
    series: str
    new_track_weight: float
    loop_file_override: str
    kaggle_notebook: str
    kaggle_bin: str
    keep_batches: int
    library_max_gb: float
    min_free_gb: float
    ffmpeg: str
    ffprobe: str

    # ---- derived paths -------------------------------------------------
    @property
    def library(self) -> Path:
        return self.home / "library"

    @property
    def batches(self) -> Path:
        return self.library / "batches"

    @property
    def current_loop(self) -> Path:
        return self.library / "current_loop.mp4"

    @property
    def placeholder_loop(self) -> Path:
        return self.home / "placeholder_loop.mp4"

    @property
    def staging(self) -> Path:
        return self.home / "staging"

    @property
    def state_dir(self) -> Path:
        return self.home / "state"

    @property
    def last_sync_file(self) -> Path:
        return self.state_dir / "last_sync.json"

    @property
    def history_file(self) -> Path:
        return self.state_dir / "played.log"

    @property
    def now_playing_txt(self) -> Path:
        return self.home / "now_playing.txt"

    @property
    def now_playing_json(self) -> Path:
        return self.home / "now_playing.json"

    @property
    def streamer_state(self) -> Path:
        return self.run_dir / "streamer.json"

    def stream_url(self) -> str:
        if self.stream_url_override:
            return self.stream_url_override
        if not self.stream_key:
            return ""
        if self.protocol == "rtmps":
            return f"rtmps://a.rtmps.youtube.com:443/live2/{self.stream_key}"
        return f"rtmp://a.rtmp.youtube.com/live2/{self.stream_key}"


def load_config() -> Config:
    e = _env()
    return Config(
        home=Path(e.get("COC_HOME", "/var/lib/classic-of-calm")),
        run_dir=Path(e.get("COC_RUN_DIR", "/run/classic-of-calm")),
        stream_key=e.get("YOUTUBE_STREAM_KEY", "").strip(),
        protocol=e.get("STREAM_PROTOCOL", "rtmp").strip().lower(),
        stream_url_override=e.get("STREAM_URL", "").strip(),
        stream_format=e.get("STREAM_FORMAT", "flv").strip(),
        audio_bitrate=e.get("AUDIO_BITRATE", "160k").strip(),
        audio_rate=_int(e, "AUDIO_RATE", 44100),
        gap_seconds=_float(e, "GAP_SECONDS", 2.0),
        stall_timeout=_int(e, "STALL_TIMEOUT", 45),
        daily_restart_hour=_int(e, "DAILY_RESTART_HOUR", 4),
        series=e.get("STREAM_SERIES", "all").strip().lower() or "all",
        new_track_weight=_float(e, "NEW_TRACK_WEIGHT", 3.0),
        loop_file_override=e.get("LOOP_FILE", "").strip(),
        kaggle_notebook=e.get("KAGGLE_NOTEBOOK", "").strip(),
        kaggle_bin=e.get("KAGGLE_BIN", "/opt/classic-of-calm/venv/bin/kaggle"),
        keep_batches=_int(e, "KEEP_BATCHES", 8),
        library_max_gb=_float(e, "LIBRARY_MAX_GB", 15.0),
        min_free_gb=_float(e, "MIN_FREE_GB", 3.0),
        ffmpeg=e.get("FFMPEG", "ffmpeg"),
        ffprobe=e.get("FFPROBE", "ffprobe"),
    )


# ---- small helpers -------------------------------------------------------

def write_json_atomic(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def log(msg: str) -> None:
    # stdout goes to the systemd journal; keep it one line per event.
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


def sd_notify(state: str) -> None:
    """Minimal sd_notify(3) without external dependencies."""
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return
    if addr.startswith("@"):
        addr = "\0" + addr[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.connect(addr)
            s.sendall(state.encode())
    except OSError:
        pass


def slug_to_title(stem: str) -> str:
    """'03_misty_pine_study' -> 'Misty Pine Study'."""
    stem = re.sub(r"^\d+[_\-. ]*", "", stem)
    words = re.split(r"[_\-]+", stem)
    return " ".join(w[:1].upper() + w[1:] for w in words if w) or stem


def human_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"


def human_duration(seconds: float) -> str:
    seconds = int(max(0, seconds))
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    if d:
        return f"{d}d {h}h {m}m"
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


# ---- ffprobe ----------------------------------------------------------------

def ffprobe_json(cfg: Config, path: Path, *extra: str, timeout: int = 60):
    cmd = [cfg.ffprobe, "-v", "error", "-print_format", "json",
           "-show_format", "-show_streams", *extra, str(path)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=timeout, check=True).stdout
        return json.loads(out)
    except (subprocess.SubprocessError, ValueError, OSError):
        return None


def validate_loop(cfg: Config, path: Path) -> tuple[bool, list[str], dict]:
    """Check that a loop video can be streamed with `-c:v copy` to YouTube.

    Returns (ok, messages, info). Hard failures make ok False; soft issues are
    returned as 'WARN:' messages.
    """
    msgs: list[str] = []
    info: dict = {}
    meta = ffprobe_json(cfg, path)
    if not meta:
        return False, ["cannot read file with ffprobe"], info
    vids = [s for s in meta.get("streams", []) if s.get("codec_type") == "video"]
    if not vids:
        return False, ["no video stream"], info
    v = vids[0]
    info.update(codec=v.get("codec_name"), profile=v.get("profile"),
                pix_fmt=v.get("pix_fmt"), width=v.get("width"),
                height=v.get("height"), fps=v.get("avg_frame_rate"))
    try:
        info["duration"] = float(meta["format"].get("duration", 0))
    except (TypeError, ValueError):
        info["duration"] = 0.0
    try:
        info["bitrate_kbps"] = int(meta["format"].get("bit_rate", 0)) // 1000
    except (TypeError, ValueError):
        info["bitrate_kbps"] = 0
    ok = True
    if v.get("codec_name") != "h264":
        ok = False
        msgs.append(f"video codec is {v.get('codec_name')}, must be h264")
    if v.get("pix_fmt") not in ("yuv420p", "yuvj420p"):
        ok = False
        msgs.append(f"pix_fmt is {v.get('pix_fmt')}, must be yuv420p")
    if info["duration"] < 2:
        ok = False
        msgs.append("loop shorter than 2 s")
    if (v.get("width"), v.get("height")) not in ((1920, 1080), (1280, 720), (2560, 1440), (3840, 2160)):
        msgs.append(f"WARN: unusual resolution {v.get('width')}x{v.get('height')}")
    if info["bitrate_kbps"] and info["bitrate_kbps"] > 9000:
        msgs.append(f"WARN: bitrate {info['bitrate_kbps']} kbps is high for 1080p30 (aim 4000-4500)")

    # Keyframe spacing: YouTube wants <= 4 s, we require <= 2 s for clean loops.
    try:
        out = subprocess.run(
            [cfg.ffprobe, "-v", "error", "-select_streams", "v:0", "-skip_frame", "nokey",
             "-show_entries", "frame=pts_time,best_effort_timestamp_time", "-of", "csv=p=0",
             str(path)],
            capture_output=True, text=True, timeout=120, check=True).stdout
        kf = []
        for line in out.splitlines():
            for part in line.split(","):
                try:
                    kf.append(float(part))
                    break
                except ValueError:
                    continue
        kf = sorted(set(kf))
    except (subprocess.SubprocessError, OSError):
        kf = []
    if not kf:
        ok = False
        msgs.append("could not read keyframes")
    else:
        start = float(v.get("start_time") or 0)
        if kf[0] - start > 0.05:
            ok = False
            msgs.append("first frame is not a keyframe")
        gaps = [b - a for a, b in zip(kf, kf[1:])]
        gaps.append(info["duration"] - (kf[-1] - start))  # tail before loop restart
        max_gap = max(gaps) if gaps else 0
        info["max_keyframe_interval"] = round(max_gap, 3)
        if max_gap > 4.05:
            ok = False
            msgs.append(f"keyframe interval up to {max_gap:.2f} s (YouTube needs <= 4 s, use 2 s)")
        elif max_gap > 2.05:
            msgs.append(f"WARN: keyframe interval up to {max_gap:.2f} s (recommended exactly 2 s)")
    return ok, msgs, info
