"""Mastering: gentle EQ, compression-lite, silence trim, tail-fade fixing, loudness normalisation
with a true-peak limiter. Targets (docs/05): study/work -14 LUFS / -1 dBTP, sleep -16 / -1.5.

CLI: ``python -m pipeline.master in.wav out.wav --series sleep [--fade-out 12]``
"""
from __future__ import annotations

import argparse
import logging
import sys

import numpy as np
from scipy.ndimage import minimum_filter1d, uniform_filter1d
from scipy.signal import butter, lfilter, resample_poly, sosfilt

from .common import (MASTER_SR, db, from_db, integrated_lufs, read_audio, resample, series_name,
                     series_spec, true_peak_db, write_wav)
from .qa import ending_energy, silence_bounds

log = logging.getLogger("pipeline.master")


def _biquad(kind: str, sr: int, f0: float, gain_db: float = 0.0, q: float = 0.707) -> np.ndarray:
    """RBJ cookbook biquad as an SOS row."""
    a = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * f0 / sr
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2 * q)
    if kind == "peak":
        b = [1 + alpha * a, -2 * cw, 1 - alpha * a]
        aa = [1 + alpha / a, -2 * cw, 1 - alpha / a]
    elif kind in ("lowshelf", "highshelf"):
        sa = 2 * np.sqrt(a) * alpha
        if kind == "lowshelf":
            b = [a * ((a + 1) - (a - 1) * cw + sa), 2 * a * ((a - 1) - (a + 1) * cw), a * ((a + 1) - (a - 1) * cw - sa)]
            aa = [(a + 1) + (a - 1) * cw + sa, -2 * ((a - 1) + (a + 1) * cw), (a + 1) + (a - 1) * cw - sa]
        else:
            b = [a * ((a + 1) + (a - 1) * cw + sa), -2 * a * ((a - 1) + (a + 1) * cw), a * ((a + 1) + (a - 1) * cw - sa)]
            aa = [(a + 1) - (a - 1) * cw + sa, 2 * ((a - 1) - (a + 1) * cw), (a + 1) - (a - 1) * cw - sa]
    else:
        raise ValueError(kind)
    b, aa = np.array(b), np.array(aa)
    return np.concatenate([b / aa[0], aa / aa[0]])


EQ = {  # gentle, "warm & a bit dark" (bible 2/3/4 mix notes); 2-5 kHz pluck softening (1.4)
    "study": [("peak", 3500, -1.5, 0.8), ("highshelf", 10000, -1.5, 0.7), ("lowshelf", 90, 0.5, 0.7)],
    "work": [("peak", 3500, -1.0, 0.8), ("highshelf", 12000, -0.5, 0.7)],
    "sleep": [("peak", 3000, -2.0, 0.7), ("highshelf", 8000, -3.0, 0.7), ("lowshelf", 120, 0.5, 0.7)],
}
COMP = {"study": (1.6, -6.0), "work": (1.6, -6.0), "sleep": (1.3, -8.0)}  # ratio, thr rel. to RMS


def eq(x: np.ndarray, sr: int, series: str) -> np.ndarray:
    sos = [butter(2, 28, btype="high", fs=sr, output="sos")[0]]
    sos += [_biquad(k, sr, f, g, q) for k, f, g, q in EQ[series]]
    return sosfilt(np.array(sos), x, axis=0).astype(np.float32)


def compress_lite(x: np.ndarray, sr: int, ratio: float, thr_rel_db: float) -> tuple[np.ndarray, float]:
    """Slow broadband RMS compressor (feed-forward, smoothed gain). Returns (y, max_gr_db)."""
    p = np.mean(x.astype(np.float64) ** 2, axis=1)
    a = np.exp(-1.0 / (0.08 * sr))
    env = lfilter([1 - a], [1, -a], p)
    env_db = 10 * np.log10(np.maximum(env, 1e-12))
    loud = env_db[env_db > np.max(env_db) - 40]
    ref = float(np.mean(loud)) if len(loud) else -30.0
    thr = ref + thr_rel_db
    gr = -np.maximum(0.0, env_db - thr) * (1 - 1 / ratio)
    r = np.exp(-1.0 / (0.25 * sr))
    gr = lfilter([1 - r], [1, -r], gr)
    return (x * (10 ** (gr / 20))[:, None]).astype(np.float32), float(-np.min(gr))


def tp_limit(x: np.ndarray, sr: int, ceiling_db: float, lookahead_ms: float = 2.0, os: int = 4) -> tuple[np.ndarray, float]:
    """Look-ahead true-peak limiter. Gain is min-filtered then box-smoothed within the same
    window, which guarantees g(t) <= required gain at every sample."""
    ceil = from_db(ceiling_db)
    n = len(x)
    peak = np.zeros(n, dtype=np.float32)
    chunk = sr * 20
    for s in range(0, n, chunk):
        a, b = max(0, s - 32), min(n, s + chunk + 32)
        up = np.abs(resample_poly(x[a:b], os, 1, axis=0)).max(axis=1)
        m = len(up) // os
        pk = up[: m * os].reshape(m, os).max(axis=1)
        pk = np.maximum(pk, np.abs(x[a:a + m]).max(axis=1))
        peak[s:min(n, s + chunk)] = pk[s - a: s - a + min(n, s + chunk) - s]
    req = np.minimum(1.0, ceil / np.maximum(peak, 1e-9))
    if np.all(req >= 1.0):
        return x, 0.0
    la = max(1, int(lookahead_ms / 1000 * sr))
    g = minimum_filter1d(req, 2 * la + 1, mode="nearest")
    g = uniform_filter1d(g, 2 * la + 1, mode="nearest")
    # slow release on top (only ever lowers the gain further -> still safe)
    rel = np.exp(-1.0 / (0.08 * sr))
    g_rel = lfilter([1 - rel], [1, -rel], g - 1.0) + 1.0
    g = np.minimum(g, g_rel).astype(np.float32)
    return (x * g[:, None]).astype(np.float32), float(-db(np.min(g)))


def fade(x: np.ndarray, sr: int, fade_in: float = 0.0, fade_out: float = 0.0, curve: str = "sine") -> np.ndarray:
    y = x.copy()
    if fade_in > 0:
        n = min(len(y), int(fade_in * sr))
        r = np.linspace(0, 1, n)
        y[:n] *= (np.sin(r * np.pi / 2) ** 2 if curve == "sine" else r)[:, None]
    if fade_out > 0:
        n = min(len(y), int(fade_out * sr))
        r = np.linspace(1, 0, n)
        y[len(y) - n:] *= (np.sin(r * np.pi / 2) ** 2 if curve == "sine" else r)[:, None]
    return y


def trim_silence(x: np.ndarray, sr: int, max_lead: float = 0.2, keep_tail: float = 0.3) -> tuple[np.ndarray, float, float]:
    lead, tail = silence_bounds(x.mean(axis=1), sr)
    cut_a = int(max(0.0, lead - 0.05) * sr) if lead > max_lead else 0
    cut_b = int(max(0.0, tail - keep_tail) * sr) if tail > 1.0 else 0
    y = x[cut_a: len(x) - cut_b] if cut_b else x[cut_a:]
    return y, cut_a / sr, cut_b / sr


def _parse_fade_out(fade_out) -> tuple[float | None, float | None]:
    """selection.json fade_out: null | seconds | {"at": s, "length": s} | "at:length"."""
    if fade_out is None or fade_out == "":
        return None, None
    if isinstance(fade_out, dict):
        return fade_out.get("at"), fade_out.get("length")
    if isinstance(fade_out, str) and ":" in fade_out:
        a, b = fade_out.split(":", 1)
        return float(a), float(b)
    return None, float(fade_out)


def master_track(x: np.ndarray, sr: int, series: str = "study", fade_out=None,
                 target_sr: int = MASTER_SR) -> tuple[np.ndarray, int, dict]:
    series = series_name(series)
    spec = series_spec(series)
    info: dict = {"series": series, "lufs_in": round(integrated_lufs(x, sr), 2)}
    x = resample(x, sr, target_sr)
    sr = target_sr
    # 1. manual cut point from selection.json
    cut_at, fo_len = _parse_fade_out(fade_out)
    if cut_at:
        x = x[: int(float(cut_at) * sr)]
        info["cut_at"] = float(cut_at)
    # 2. silence trim (bible 8.2 #18: head <= 0.2 s, tail <= 1 s)
    x, trimmed_a, trimmed_b = trim_silence(x, sr)
    info["trimmed_lead_s"], info["trimmed_tail_s"] = round(trimmed_a, 2), round(trimmed_b, 2)
    # 3. EQ + compression-lite
    x = eq(x, sr, series)
    ratio, thr = COMP[series]
    x, gr = compress_lite(x, sr, ratio, thr)
    info["comp_max_gr_db"] = round(gr, 2)
    # 4. fades: hard start -> 1 s fade-in; abrupt end -> series tail fade (bible 8.1 #7/#8)
    mono = x.mean(axis=1)
    head = float(np.sqrt(np.mean(mono[: int(0.1 * sr)] ** 2)) + 1e-9)
    body = float(np.sqrt(np.mean(mono ** 2)) + 1e-9)
    fade_in = 1.0 if db(head) > db(body) - 12 else 0.02
    end = ending_energy(mono, sr)
    if fo_len:
        fade_out_s = float(fo_len)
        why = "selection"
    elif end["abrupt"] or cut_at:
        fade_out_s = spec["tail_fade"]
        why = "abrupt ending"
    else:
        fade_out_s = 1.0  # declick / smooth natural endings
        why = "natural ending"
    fade_out_s = min(fade_out_s, len(x) / sr / 4)
    x = fade(x, sr, fade_in, fade_out_s)
    info.update(fade_in_s=fade_in, fade_out_s=round(fade_out_s, 2), fade_reason=why)
    # 5. loudness normalisation + true-peak limiting (iterate: limiting lowers loudness)
    target, ceiling = spec["lufs"], spec["tp"]
    lim_total = 0.0
    for _ in range(3):
        cur = integrated_lufs(x, sr)
        if cur <= -69:
            break
        x = x * from_db(target - cur)
        x, lim = tp_limit(x, sr, ceiling - 0.15)
        lim_total = max(lim_total, lim)
        if abs(integrated_lufs(x, sr) - target) < 0.2:
            break
    tp = true_peak_db(x, sr)
    if tp > ceiling - 0.05:
        x = x * from_db(ceiling - 0.1 - tp)
    info.update(lufs=round(integrated_lufs(x, sr), 2), true_peak=round(true_peak_db(x, sr), 2),
                limiter_max_gr_db=round(lim_total, 2), target_lufs=target, ceiling_dbtp=ceiling,
                duration_s=round(len(x) / sr, 2), sample_rate=sr)
    return x.astype(np.float32), sr, info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.master")
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--series", default="study")
    ap.add_argument("--fade-out", default=None)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    x, sr = read_audio(a.inp)
    y, sr, info = master_track(x, sr, a.series, a.fade_out)
    write_wav(a.out, y, sr)
    print(info)
    return 0


if __name__ == "__main__":
    sys.exit(main())
