"""Synthetic fixtures: lofi-ish test tracks, noise, vocal-like tones, test scene image."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100
_PENTA = [0, 2, 4, 7, 9]


def _note(f, dur, sr=SR, harm=(1.0, 0.4, 0.2), decay=3.0):
    t = np.arange(int(dur * sr)) / sr
    y = sum(a * np.sin(2 * np.pi * f * (k + 1) * t) for k, a in enumerate(harm))
    return y * np.exp(-decay * t)


def lofi_track(dur=20.0, bpm=80, root_hz=146.83, seed=0, sr=SR, fade=True, end_abrupt=False):
    """Chords + bass + kick/hat + varied pentatonic melody + light crackle. Stereo float32."""
    rng = np.random.default_rng(seed)
    n = int(dur * sr)
    y = np.zeros(n)
    beat = 60.0 / bpm
    prog = [0, 5, 3, 7]  # semitone offsets of chord roots
    bar = 4 * beat
    for b in range(int(dur / bar) + 1):
        r = root_hz * 2 ** (prog[b % 4] / 12)
        s = int(b * bar * sr)
        for iv in (0, 3, 7, 10, 14):
            seg = _note(r * 2 ** (iv / 12), bar, sr, decay=0.6) * 0.06
            e = min(n, s + len(seg))
            if e > s:
                y[s:e] += seg[: e - s]
        bass = _note(r / 2, bar, sr, harm=(1.0, 0.2), decay=1.0) * 0.18
        e = min(n, s + len(bass))
        if e > s:
            y[s:e] += bass[: e - s]
    for k in range(int(dur / beat)):
        s = int(k * beat * sr)
        if k % 2 == 0:  # kick
            t = np.arange(int(0.25 * sr)) / sr
            kick = np.sin(2 * np.pi * (50 + 80 * np.exp(-25 * t)) * t) * np.exp(-12 * t) * 0.5
            e = min(n, s + len(kick)); y[s:e] += kick[: e - s]
        hat = rng.standard_normal(int(0.04 * sr)) * np.exp(-np.arange(int(0.04 * sr)) / (0.008 * sr)) * 0.03
        hat = np.diff(hat, prepend=0)
        for off in (0, beat / 2):
            s2 = int((k * beat + off) * sr)
            e = min(n, s2 + len(hat)); y[s2:e] += hat[: e - s2] if e > s2 else 0
    t_mel = 0.0
    while t_mel < dur:  # melody: random pentatonic notes, varied rhythm
        deg = _PENTA[rng.integers(0, 5)] + 12 * rng.integers(1, 3)
        f = root_hz * 2 ** (deg / 12)
        d = beat * rng.choice([0.5, 1, 1.5, 2])
        seg = _note(f, d * 1.5, sr, harm=(1.0, 0.5, 0.25, 0.1), decay=4.0) * 0.12
        s = int(t_mel * sr); e = min(n, s + len(seg))
        y[s:e] += seg[: e - s]
        t_mel += d + (beat if rng.random() < 0.2 else 0)
    crack = (rng.random(n) < 0.0008) * rng.standard_normal(n) * 0.05
    y += crack + rng.standard_normal(n) * 0.002
    if fade:
        fl = int(3 * sr)
        y[-fl:] *= np.linspace(1, 0, fl) ** 2
        y[: int(0.05 * sr)] *= np.linspace(0, 1, int(0.05 * sr))
    if end_abrupt:
        y[-int(0.01 * sr):] *= 1.0
    y = y / (np.max(np.abs(y)) + 1e-9) * 0.7
    st = np.stack([y, np.roll(y, 7)], axis=1).astype(np.float32)
    return st


def noise_track(dur=20.0, sr=SR, seed=1):
    rng = np.random.default_rng(seed)
    y = rng.standard_normal(int(dur * sr)) * 0.2
    return np.stack([y, y], 1).astype(np.float32)


def static_loop_track(dur=90.0, sr=SR):
    one = lofi_track(dur=4 * 60 / 80, seed=3, fade=False)
    reps = int(np.ceil(dur * sr / len(one)))
    return np.tile(one, (reps, 1))[: int(dur * sr)]


def vocal_like(dur=20.0, sr=SR, seed=2):
    """Sawtooth-ish voice: 5.5 Hz vibrato, glides, syllabic 4 Hz AM, formant emphasis."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(dur * sr)) / sr
    base = 220 * 2 ** (np.repeat(rng.choice([0, 2, 4, 7, 9], int(dur * 2) + 1), sr // 2)[: len(t)] / 12)
    from scipy.ndimage import uniform_filter1d
    base = uniform_filter1d(base, int(0.08 * sr))
    f = base * (1 + 0.012 * np.sin(2 * np.pi * 5.5 * t))
    ph = 2 * np.pi * np.cumsum(f) / sr
    y = sum(np.sin(k * ph) / k for k in range(1, 14))
    am = 0.55 + 0.45 * np.sin(2 * np.pi * 4.2 * t + 2 * np.sin(2 * np.pi * 0.7 * t))
    from scipy.signal import butter, sosfilt
    sos = butter(2, [500, 3000], btype="band", fs=sr, output="sos")
    y = sosfilt(sos, y) * am
    y = y / np.max(np.abs(y)) * 0.6
    return np.stack([y, y], 1).astype(np.float32)


def write(path, x, sr=SR):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), x, sr, subtype="PCM_16")
    return Path(path)


def bell_sample(sr=SR, dur=2.5, f=660.0):
    t = np.arange(int(dur * sr)) / sr
    y = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-d * t)
            for a, r, d in [(1, 1, 1.5), (0.5, 2.76, 2.5), (0.3, 5.4, 4), (0.2, 8.9, 6)])
    return (y / np.max(np.abs(y)) * 0.8).astype(np.float32)


def test_scene(path, size=(1920, 1080)):
    """A crude blue-green 'landscape' with warm glowing dots (for the Migu-glow mask)."""
    from PIL import Image, ImageDraw, ImageFilter
    w, h = size
    img = Image.new("RGB", size, (239, 228, 204))
    d = ImageDraw.Draw(img)
    for i in range(h):
        c = int(40 + 60 * i / h)
        d.line([(0, i), (w, i)], fill=(47 - c // 4, 93 - c // 6, 138 - c // 3))
    rng = np.random.default_rng(5)
    for k, col in enumerate([(62, 142, 126), (47, 93, 138), (36, 33, 30)]):
        pts = [(0, h)]
        for x in range(0, w + 80, 80):
            pts.append((x, int(h * (0.45 + 0.15 * k) + 120 * np.sin(x / (200 + 90 * k) + k) + rng.integers(-20, 20))))
        pts.append((w, h))
        d.polygon(pts, fill=col)
    for _ in range(40):
        x, y = int(rng.integers(0, w)), int(rng.integers(h // 3, h - 50))
        d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(232, 182, 81))
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    img.save(path)
    return Path(path)
