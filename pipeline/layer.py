"""Optional instrument layering (music bible 6.1): sparse CC0 sample ornaments + shared reverb.

plan.json track field::

    "layer": {"instrument": "guzheng", "role": "ornament",   # ornament | texture | bell
              "gain_db": -9, "density": 1.0}                   # optional

Samples are read from ``samples/<instrument>/*.wav`` (only CC0 / cleared material, see
samples/LICENSES.md). If the folder is missing or empty the track is returned unchanged.

Placement is tempo-agnostic: candidate times are the track's own detected onsets (so a pluck
lands on an existing transient and never fights the groove), restricted to quieter mid-band
moments ("leave space", bible 1.2 #6), with a minimum spacing per role. The layer bus is set
6-12 dB under the track's level, softened at 2-5 kHz (bible 1.4) and sent with a little of the
track into one shared generated reverb so both sit in the same room.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

from .common import as_stereo, from_db, read_audio, resample, series_spec

log = logging.getLogger("pipeline.layer")

ROLE_DEFAULTS = {
    #            spacing (s)  max len (s)  gain dB  pan
    "ornament": dict(spacing=(8.0, 18.0), max_len=6.0, gain_db=-9.0, pan=0.3),
    "texture": dict(spacing=(12.0, 24.0), max_len=12.0, gain_db=-12.0, pan=0.5),
    "bell": dict(spacing=(30.0, 60.0), max_len=10.0, gain_db=-10.0, pan=0.2),
}


def list_samples(samples_root: str | Path | None, instrument: str | None) -> list[Path]:
    if not samples_root or not instrument:
        return []
    d = Path(samples_root) / str(instrument)
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.suffix.lower() in (".wav", ".flac", ".ogg", ".aif", ".aiff"))


def generate_ir(sr: int, rt60: float = 1.3, predelay_ms: float = 15.0, seed: int = 7) -> np.ndarray:
    """Stereo decorrelated exponentially-decaying noise IR, darkened over time."""
    rng = np.random.default_rng(seed)
    n = int(sr * min(6.0, rt60 * 1.2))
    t = np.arange(n) / sr
    env = np.exp(-6.91 * t / rt60)  # -60 dB at rt60
    noise = rng.standard_normal((n, 2))
    # darker tail: blend a low-passed copy in as time goes on
    sos = butter(2, 3500, fs=sr, output="sos")
    dark = sosfilt(sos, noise, axis=0)
    mix = np.clip(t / max(rt60, 1e-3), 0, 1)[:, None]
    ir = ((1 - mix) * noise + mix * dark * 1.6) * env[:, None]
    ir[: int(0.004 * sr)] *= np.linspace(0, 1, int(0.004 * sr))[:, None]
    ir = np.concatenate([np.zeros((int(predelay_ms / 1000 * sr), 2)), ir])
    ir /= np.sqrt(np.sum(ir ** 2, axis=0, keepdims=True)) + 1e-12
    return ir.astype(np.float32)


def apply_reverb(x: np.ndarray, ir: np.ndarray) -> np.ndarray:
    y = np.stack([fftconvolve(x[:, c], ir[:, c], mode="full")[: len(x)] for c in range(2)], 1)
    return y.astype(np.float32)


def _peaking(sr, f0, gain_db, q=0.9):
    a = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * f0 / sr
    alpha = np.sin(w0) / (2 * q)
    b = np.array([1 + alpha * a, -2 * np.cos(w0), 1 - alpha * a])
    aa = np.array([1 + alpha / a, -2 * np.cos(w0), 1 - alpha / a])
    return np.concatenate([b / aa[0], aa / aa[0]])[None, :]


def detect_onsets(mono: np.ndarray, sr: int, hop_s: float = 0.01) -> tuple[np.ndarray, np.ndarray]:
    """Onset times (s) and a local mid-band 'busyness' level (dB) at each onset."""
    hop = int(sr * hop_s)
    nfft = 1024
    n = 1 + max(0, len(mono) - nfft) // hop
    if n < 8:
        return np.array([]), np.array([])
    idx = np.arange(nfft)[None, :] + hop * np.arange(n)[:, None]
    mag = np.abs(np.fft.rfft(mono[idx] * np.hanning(nfft), axis=1))
    flux = np.maximum(0, np.diff(np.log1p(mag * 10), axis=0)).sum(axis=1)
    flux = np.concatenate([[0], flux])
    from scipy.ndimage import maximum_filter1d, uniform_filter1d
    thr = uniform_filter1d(flux, int(1.0 / hop_s)) * 1.5 + 1e-9
    peaks = (flux == maximum_filter1d(flux, int(0.1 / hop_s))) & (flux > thr)
    freqs = np.fft.rfftfreq(nfft, 1 / sr)
    mid = mag[:, (freqs > 400) & (freqs < 4000)].sum(axis=1)
    busy = 20 * np.log10(uniform_filter1d(mid, int(1.5 / hop_s)) + 1e-9)
    t = np.where(peaks)[0]
    return t * hop_s, busy[t]


def _choose_times(onsets, busy, dur, spacing, rng, avoid_start=4.0, avoid_end=8.0, density=1.0):
    lo, hi = spacing[0] / density, spacing[1] / density
    ok = (onsets > avoid_start) & (onsets < dur - avoid_end)
    onsets, busy = onsets[ok], busy[ok]
    times = []
    if len(onsets) == 0:  # no transients (ambient): fall back to a free-time grid
        t = avoid_start + rng.uniform(0, lo)
        while t < dur - avoid_end:
            times.append(float(t))
            t += rng.uniform(lo, hi)
        return times
    quiet_cut = np.percentile(busy, 60)
    t = avoid_start + rng.uniform(0, lo)
    while t < dur - avoid_end:
        win = (onsets >= t) & (onsets <= t + (hi - lo) + 1.0)
        cand = np.where(win & (busy <= quiet_cut))[0]
        if len(cand) == 0:
            cand = np.where(win)[0]
        if len(cand) == 0:
            t += lo
            continue
        pick = onsets[cand[rng.integers(0, len(cand))]]
        times.append(float(pick))
        t = pick + rng.uniform(lo, hi)
    return times


def _active_rms(x: np.ndarray, sr: int) -> float:
    mono = x.mean(axis=1) if x.ndim == 2 else x
    hop = max(1, int(0.05 * sr))
    n = len(mono) // hop
    if n == 0:
        return float(np.sqrt(np.mean(mono ** 2)) + 1e-9)
    r = np.sqrt(np.mean(mono[: n * hop].reshape(n, hop) ** 2, axis=1))
    act = r[r > np.max(r) * 0.05]
    return float(np.sqrt(np.mean(act ** 2))) if len(act) else 1e-9


def layer_track(x: np.ndarray, sr: int, layer: dict | None, samples_root: str | Path | None,
                series: str = "study", seed: int = 0) -> tuple[np.ndarray, dict]:
    """Return (mixed_audio, info). No-op (info['applied']=False) when nothing to layer."""
    info = {"applied": False}
    if not layer or not layer.get("instrument"):
        info["reason"] = "no layer in plan"
        return x, info
    inst = layer["instrument"]
    files = list_samples(samples_root, inst)
    if not files:
        info["reason"] = f"no samples in {Path(samples_root or 'samples') / inst}"
        log.info("layer: %s", info["reason"])
        return x, info
    role = layer.get("role", "ornament")
    rd = ROLE_DEFAULTS.get(role, ROLE_DEFAULTS["ornament"])
    gain_db = float(np.clip(layer.get("gain_db", rd["gain_db"]), -12.0, -6.0))
    rng = np.random.default_rng(seed)
    dur = len(x) / sr
    onsets, busy = detect_onsets(x.mean(axis=1), sr)
    times = _choose_times(onsets, busy, dur, rd["spacing"], rng, density=float(layer.get("density", 1.0)))
    if not times:
        info["reason"] = "track too short for ornaments"
        return x, info

    sos_soft = _peaking(sr, 3200, -3.0, q=0.7)
    sos_hp = butter(2, 120, btype="high", fs=sr, output="sos")
    sos_lp = butter(2, 9000, fs=sr, output="sos")
    cache: dict[Path, np.ndarray] = {}
    bus = np.zeros_like(x)
    used = []
    for t in times:
        f = files[rng.integers(0, len(files))]
        if f not in cache:
            s, ssr = read_audio(f)
            s = resample(s, ssr, sr)
            s = s[: int(rd["max_len"] * sr)]
            fo = min(len(s), int(0.25 * sr))
            if fo > 0:
                s[-fo:] *= np.linspace(1, 0, fo)[:, None]
            fi = min(len(s), int(0.005 * sr))
            s[:fi] *= np.linspace(0, 1, fi)[:, None]
            s = sosfilt(sos_soft, s, axis=0)
            s = sosfilt(sos_hp, s, axis=0)
            s = sosfilt(sos_lp, s, axis=0).astype(np.float32)
            s /= _active_rms(s, sr) + 1e-9
            cache[f] = as_stereo(s)
        s = cache[f]
        pan = rng.uniform(-rd["pan"], rd["pan"])
        g = from_db(rng.uniform(-1.5, 1.5))
        lr = np.array([np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)]) * np.sqrt(2)
        a = int(t * sr)
        b = min(len(x), a + len(s))
        bus[a:b] += s[: b - a] * lr[None, :] * g
        used.append({"t": round(t, 2), "sample": f.name})

    track_rms = _active_rms(x, sr)
    bus *= track_rms * from_db(gain_db)
    ir = generate_ir(sr, series_spec(series)["reverb_rt60"], seed=seed + 11)
    send = bus * 0.7 + x * 0.06  # shared reverb: mostly layer, a touch of the bed to glue
    wet = apply_reverb(send, ir)
    wet_gain = from_db(-8.0)
    y = x + bus * 0.8 + wet * wet_gain
    peak = float(np.max(np.abs(y)))
    if peak > 0.99:
        y *= 0.99 / peak
    info.update(applied=True, instrument=inst, role=role, gain_db=gain_db, count=len(used),
                placements=used, samples=sorted({u["sample"] for u in used}))
    return y.astype(np.float32), info
