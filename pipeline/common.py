"""Shared helpers: audio I/O, loudness / true peak, series specs, keys, ffmpeg."""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

log = logging.getLogger("pipeline")

MASTER_SR = 48000  # music bible 8.2 #15: master WAV 48 kHz / 24-bit

# ---------------------------------------------------------------------------
# Series specs (docs/05 "音訊規格", docs/03 sections 8.3, 9.3, 9.6, 8.1 #8/#14)
# ---------------------------------------------------------------------------
SERIES = {
    "study": dict(lufs=-14.0, tp=-1.0, xfade=(3.0, 5.0), bpm_step=6, tail_fade=6.0,
                  final_fade=10.0, dur=(110, 220), reverb_rt60=1.3, seal="讀", label="STUDY"),
    "work": dict(lufs=-14.0, tp=-1.0, xfade=(2.0, 4.0), bpm_step=6, tail_fade=5.0,
                 final_fade=8.0, dur=(110, 220), reverb_rt60=0.8, seal="作", label="WORK"),
    "sleep": dict(lufs=-16.0, tp=-1.5, xfade=(6.0, 10.0), bpm_step=4, tail_fade=12.0,
                  final_fade=20.0, dur=(150, 360), reverb_rt60=2.6, seal="眠", label="SLEEP"),
}
_SERIES_ALIASES = {"s": "study", "focus": "study", "study": "study",
                   "l": "sleep", "relax": "sleep", "sleep": "sleep",
                   "c": "work", "cafe": "work", "café": "work", "work": "work"}


def series_name(name: str | None) -> str:
    if not name:
        return "study"
    key = str(name).strip().lower().split("/")[0].strip()
    return _SERIES_ALIASES.get(key, "study")


def series_spec(name: str | None) -> dict:
    return SERIES[series_name(name)]


# ---------------------------------------------------------------------------
# ffmpeg
# ---------------------------------------------------------------------------
def ffmpeg_bin() -> str:
    exe = os.environ.get("FFMPEG_BIN") or shutil.which("ffmpeg")
    if exe:
        return exe
    try:  # optional fallback
        import imageio_ffmpeg  # type: ignore
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("ffmpeg not found: install it (apt-get install -y ffmpeg) "
                           "or `pip install imageio-ffmpeg`") from exc


def ffprobe_bin() -> str | None:
    return shutil.which("ffprobe")


def run_ffmpeg(args: list[str], quiet: bool = True) -> subprocess.CompletedProcess:
    cmd = [ffmpeg_bin(), "-hide_banner", "-nostdin", "-y"]
    if quiet:
        cmd += ["-loglevel", "error"]
    cmd += [str(a) for a in args]
    log.debug("ffmpeg %s", " ".join(cmd[1:]))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr[-3000:]}")
    return proc


def media_duration(path: str | Path) -> float:
    """Container duration in seconds (ffprobe if present, else parse ffmpeg -i)."""
    probe = ffprobe_bin()
    if probe:
        out = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True)
        try:
            return float(out.stdout.strip())
        except ValueError:
            pass
    proc = subprocess.run([ffmpeg_bin(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", proc.stderr)
    if not m:
        raise RuntimeError(f"cannot read duration of {path}")
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def ffmpeg_loudness(path: str | Path, target_i: float = -14.0, target_tp: float = -1.0) -> dict:
    """Streamed EBU R128 measurement via ffmpeg loudnorm (low memory, for long files)."""
    proc = subprocess.run([ffmpeg_bin(), "-hide_banner", "-nostdin", "-i", str(path), "-af",
                           f"loudnorm=I={target_i}:TP={target_tp}:LRA=7:print_format=json",
                           "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", proc.stderr, re.S)
    if not m:
        raise RuntimeError(f"loudnorm measurement failed for {path}: {proc.stderr[-1000:]}")
    d = json.loads(m.group(0))
    return {"lufs": float(d["input_i"]), "true_peak": float(d["input_tp"]), "lra": float(d["input_lra"])}


# ---------------------------------------------------------------------------
# Audio I/O
# ---------------------------------------------------------------------------
def as_stereo(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 1:
        return np.stack([x, x], axis=1)
    if x.shape[1] == 1:
        return np.repeat(x, 2, axis=1)
    return x[:, :2]


def read_audio(path: str | Path) -> tuple[np.ndarray, int]:
    """Read audio as float32 stereo (n, 2). Falls back to ffmpeg decode for mp3/m4a."""
    path = Path(path)
    try:
        x, sr = sf.read(str(path), dtype="float32", always_2d=True)
    except Exception:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "decoded.wav"
            run_ffmpeg(["-i", path, "-vn", "-c:a", "pcm_f32le", tmp])
            x, sr = sf.read(str(tmp), dtype="float32", always_2d=True)
    return as_stereo(x), int(sr)


def write_wav(path: str | Path, x: np.ndarray, sr: int, subtype: str = "PCM_24") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.clip(x, -1.0, 1.0), sr, subtype=subtype)
    return path


def resample(x: np.ndarray, sr_from: int, sr_to: int) -> np.ndarray:
    if sr_from == sr_to:
        return x
    g = np.gcd(sr_from, sr_to)
    return resample_poly(x, sr_to // g, sr_from // g, axis=0).astype(np.float32)


def db(x: float, floor: float = -120.0) -> float:
    return float(20 * np.log10(max(float(x), 10 ** (floor / 20))))


def from_db(d: float) -> float:
    return float(10 ** (d / 20))


def frame_rms_db(mono: np.ndarray, sr: int, frame_s: float = 0.05) -> np.ndarray:
    hop = max(1, int(sr * frame_s))
    n = len(mono) // hop
    if n == 0:
        return np.array([db(np.sqrt(np.mean(mono ** 2)) if len(mono) else 0.0)])
    fr = mono[: n * hop].reshape(n, hop)
    rms = np.sqrt(np.mean(fr.astype(np.float64) ** 2, axis=1))
    return 20 * np.log10(np.maximum(rms, 1e-9))


# ---------------------------------------------------------------------------
# Loudness / true peak
# ---------------------------------------------------------------------------
def integrated_lufs(x: np.ndarray, sr: int) -> float:
    import pyloudnorm as pyln
    if len(x) < int(0.4 * sr) + 1:
        return -70.0
    meter = pyln.Meter(sr)
    with np.errstate(divide="ignore"):
        val = meter.integrated_loudness(np.asarray(x, dtype=np.float64))
    return float(val) if np.isfinite(val) else -70.0


def true_peak_db(x: np.ndarray, sr: int, oversample: int = 4, chunk_s: float = 20.0) -> float:
    """BS.1770-style true peak estimate via polyphase oversampling, chunked for memory."""
    if len(x) == 0:
        return -120.0
    chunk = int(chunk_s * sr)
    pad = 64
    peak = 0.0
    for start in range(0, len(x), chunk):
        a = max(0, start - pad)
        b = min(len(x), start + chunk + pad)
        up = resample_poly(x[a:b], oversample, 1, axis=0)
        peak = max(peak, float(np.max(np.abs(up))))
    peak = max(peak, float(np.max(np.abs(x))))
    return db(peak)


# ---------------------------------------------------------------------------
# Keys: "D dorian", "A minor", "G 徵", "Am", "8A" -> Camelot
# ---------------------------------------------------------------------------
_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
# offset (semitones) from mode tonic down to the parent major (ionian) tonic, and minor-ness
_MODES = {
    "major": (0, False), "ionian": (0, False), "maj": (0, False), "gong": (0, False), "宮": (0, False),
    "dorian": (2, True), "shang": (2, True), "商": (2, True),
    "phrygian": (4, True), "jue": (4, True), "角": (4, True),
    "lydian": (5, False), "yayue": (5, False),
    "mixolydian": (7, False), "zhi": (7, False), "徵": (7, False),
    "minor": (9, True), "min": (9, True), "m": (9, True), "aeolian": (9, True), "yu": (9, True), "羽": (9, True),
    "locrian": (11, True),
}


def parse_key(key: str | None) -> dict | None:
    """Return {'tonic': pc, 'mode': str, 'camelot': '8A'} or None."""
    if not key:
        return None
    s = str(key).strip()
    m = re.fullmatch(r"(\d{1,2})\s*([ABab])", s)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 12:
            return {"tonic": None, "mode": "camelot", "camelot": f"{n}{m.group(2).upper()}"}
        return None
    m = re.match(r"^([A-Ga-g])\s*([#♯b♭]?)\s*(.*)$", s)
    if not m:
        return None
    pc = _PC[m.group(1).upper()]
    acc = m.group(2)
    if acc in ("#", "♯"):
        pc += 1
    elif acc in ("b", "♭"):
        pc -= 1
    mode_txt = m.group(3).strip().lower().replace("-", " ")
    mode_word = mode_txt.split()[0] if mode_txt else "major"
    if mode_word not in _MODES:
        mode_word = "major" if not mode_txt else ("minor" if "min" in mode_txt else "major")
    off, minor = _MODES[mode_word]
    parent = (pc - off) % 12
    num = ((parent * 7) % 12 + 7) % 12 + 1  # C major = 8B
    return {"tonic": pc % 12, "mode": mode_word, "camelot": f"{num}{'A' if minor else 'B'}"}


def camelot_distance(a: str | None, b: str | None) -> float:
    """0 = same key, 0.5 = relative major/minor, 1 = adjacent (+-1), larger = clash. 3 if unknown."""
    if not a or not b:
        return 3.0
    na, la = int(a[:-1]), a[-1]
    nb, lb = int(b[:-1]), b[-1]
    d = min((na - nb) % 12, (nb - na) % 12)
    if d == 0:
        return 0.0 if la == lb else 0.5
    return float(d + (0 if la == lb else 0.5))


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------
def slugify(text: str, maxlen: int = 48) -> str:
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return (t[:maxlen].rstrip("-")) or "track"


def parse_candidate_name(name: str) -> dict:
    """`<track_id>__<model>__<take>.wav` -> parts (spec docs/05)."""
    stem = Path(name).stem
    parts = stem.split("__")
    out = {"file": Path(name).name, "track_id": parts[0], "model": None, "take": None}
    if len(parts) >= 2:
        out["model"] = parts[1]
    if len(parts) >= 3:
        out["take"] = parts[2]
    return out


def load_json(path: str | Path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: str | Path, obj) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
    return p


def fmt_ts(seconds: float, force_hours: bool = False) -> str:
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    if h or force_hours:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


AUDIO_EXTS = (".wav", ".flac", ".ogg", ".aif", ".aiff", ".mp3", ".m4a")


def find_audio_files(root: str | Path, recursive: bool = True) -> list[Path]:
    root = Path(root)
    it = root.rglob("*") if recursive else root.glob("*")
    return sorted(p for p in it if p.is_file() and p.suffix.lower() in AUDIO_EXTS)
