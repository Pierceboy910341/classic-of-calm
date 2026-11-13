"""Compilation: ordering, equal-power crossfades, chapters, stream_tracks export.

Ordering: selection.json ``order`` if present, otherwise automatic (music bible 9.2-9.5):
greedy chain minimising Camelot distance, BPM jumps beyond the series step (+-6, sleep +-4),
same lead-instrument neighbours; study/work start from the calmest (lowest BPM) track, sleep
starts high and descends. Every start is tried and the cheapest chain wins.

Audio is streamed to disk track by track (only one track + one crossfade tail in memory), so
2-hour compilations fit easily in Kaggle RAM.
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

from .master import AAC_HEADROOM_DB, tp_limit
from .common import (MASTER_SR, camelot_distance, ffmpeg_loudness, from_db, parse_key, read_audio,
                     resample, run_ffmpeg, series_name, series_spec, slugify)

log = logging.getLogger("pipeline.compile")


# ---------------------------------------------------------------------------
# ordering
# ---------------------------------------------------------------------------
def transition_cost(a: dict, b: dict, series: str) -> float:
    step = series_spec(series)["bpm_step"]
    ca = a.get("camelot") or (parse_key(a.get("key")) or {}).get("camelot")
    cb = b.get("camelot") or (parse_key(b.get("key")) or {}).get("camelot")
    cost = 2.0 * min(camelot_distance(ca, cb), 3.0)
    ba, bb = a.get("bpm"), b.get("bpm")
    if ba and bb:
        d = abs(float(ba) - float(bb))
        cost += 1.5 * max(0.0, d - step) + 0.05 * d
        if series_name(series) == "sleep" and bb > ba:
            cost += 0.3 * (bb - ba)
    ia, ib = a.get("instrument"), b.get("instrument")
    if ia and ib and ia == ib:
        cost += 3.0
    return cost


def auto_order(items: list[dict], series: str) -> list[dict]:
    n = len(items)
    if n <= 2:
        return sorted(items, key=lambda it: it.get("bpm") or 0, reverse=series_name(series) == "sleep")
    bpms = [float(it.get("bpm") or 0) for it in items]
    rank = np.argsort(np.argsort(bpms))  # 0 = slowest
    best, best_cost = None, float("inf")
    for start in range(n):
        order, used, total = [start], {start}, 0.0
        while len(order) < n:
            cur = items[order[-1]]
            nxt = min((j for j in range(n) if j not in used), key=lambda j: transition_cost(cur, items[j], series))
            total += transition_cost(cur, items[nxt], series)
            order.append(nxt)
            used.add(nxt)
        start_pen = (n - 1 - rank[start]) if series_name(series) == "sleep" else rank[start]
        total += 0.5 * float(start_pen)
        if total < best_cost:
            best, best_cost = order, total
    return [items[i] for i in best]


def order_items(items: list[dict], series: str, use_selection_order: bool) -> list[dict]:
    if use_selection_order and all(it.get("order") is not None for it in items):
        return sorted(items, key=lambda it: float(it["order"]))
    return auto_order(items, series)


# ---------------------------------------------------------------------------
# crossfaded render
# ---------------------------------------------------------------------------
def _load(path: str | Path) -> np.ndarray:
    x, sr = read_audio(path)
    return resample(x, sr, MASTER_SR)


def compile_audio(items: list[dict], out_wav: str | Path, series: str = "study",
                  xfade_s: float | None = None, final_fade_s: float | None = None,
                  first_fade_s: float = 2.0, correct_loudness: bool = True) -> dict:
    """items: ordered dicts with at least 'path' (mastered 48 kHz wav) and 'title_en'."""
    series = series_name(series)
    spec = series_spec(series)
    sr = MASTER_SR
    xf = float(xfade_s if xfade_s is not None else sum(spec["xfade"]) / 2)
    final_fade = float(final_fade_s if final_fade_s is not None else spec["final_fade"])
    lens = [int(sf.info(str(it["path"])).frames * MASTER_SR / sf.info(str(it["path"])).samplerate) for it in items]
    xfs = [0] + [int(min(xf, 0.25 * min(lens[i - 1], lens[i]) / sr) * sr) for i in range(1, len(items))] + [0]
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    chapters = []
    pos = 0
    carry = None
    with sf.SoundFile(str(out_wav), "w", samplerate=sr, channels=2, subtype="PCM_24") as fh:
        for i, it in enumerate(items):
            y = _load(it["path"])
            if i == 0 and first_fade_s:
                n = min(len(y), int(first_fade_s * sr))
                y[:n] *= (np.sin(np.linspace(0, 1, n) * np.pi / 2) ** 2)[:, None]
            if i == len(items) - 1 and final_fade:
                n = min(len(y) // 3, int(final_fade * sr))
                y[len(y) - n:] *= (np.sin(np.linspace(1, 0, n) * np.pi / 2) ** 2)[:, None]
            lin, lout = xfs[i], xfs[i + 1]
            start = pos
            if carry is not None and lin > 0:
                th = np.linspace(0, np.pi / 2, lin)[:, None]
                mixed = carry * np.cos(th) + y[:lin] * np.sin(th)
                # equal-power sums of correlated material can exceed the ceiling: limit locally
                mixed, _ = tp_limit(mixed.astype(np.float32), sr, spec["tp"] - AAC_HEADROOM_DB - 0.1)
                fh.write(np.clip(mixed, -1, 1))
                pos += lin
            body = y[lin: len(y) - lout] if lout else y[lin:]
            fh.write(np.clip(body, -1, 1))
            pos += len(body)
            carry = y[len(y) - lout:] if lout else None
            mark = 0.0 if i == 0 else (start + lin / 2) / sr
            chapters.append({"n": i + 1, "start_s": round(mark, 3), "xfade_start_s": round(start / sr, 3),
                             "title_en": it.get("title_en") or it.get("track_id") or f"Track {i + 1}",
                             "title_zh": it.get("title_zh"), "file": Path(it["path"]).name,
                             "track_id": it.get("track_id"), "lore_note": it.get("lore_note")})
    total = pos / sr
    info = {"series": series, "duration_s": round(total, 2), "xfade_s": xf, "tracks": len(items),
            "chapters": chapters}
    # whole-compilation loudness check (bible 8.3: +-0.5 after export)
    meas = ffmpeg_loudness(out_wav, spec["lufs"], spec["tp"])
    info["measured"] = meas
    if correct_loudness:
        gain = spec["lufs"] - meas["lufs"]
        gain = min(gain, spec["tp"] - AAC_HEADROOM_DB - meas["true_peak"])
        if abs(gain) > 0.3:
            _apply_gain_stream(out_wav, gain)
            info["gain_correction_db"] = round(gain, 2)
            info["measured"] = ffmpeg_loudness(out_wav, spec["lufs"], spec["tp"])
    return info


def _apply_gain_stream(path: Path, gain_db: float, block: int = MASTER_SR * 30) -> None:
    tmp = path.with_suffix(".gain.wav")
    g = from_db(gain_db)
    with sf.SoundFile(str(path)) as src, sf.SoundFile(str(tmp), "w", samplerate=src.samplerate,
                                                      channels=src.channels, subtype="PCM_24") as dst:
        for blk in src.blocks(blocksize=block, dtype="float32", always_2d=True):
            dst.write(np.clip(blk * g, -1, 1))
    shutil.move(str(tmp), str(path))


def export_stream_tracks(items: list[dict], out_dir: str | Path, bitrate: str = "320k") -> list[Path]:
    """stream_tracks/<n>_<slug>.m4a (already loudness-normalised masters, AAC)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    outs = []
    for i, it in enumerate(items, 1):
        dst = out_dir / f"{i:02d}_{slugify(it.get('title_en') or it.get('track_id') or 'track')}.m4a"
        meta = ["-metadata", f"title={it.get('title_en') or ''}", "-metadata", "artist=Classic of Calm"]
        run_ffmpeg(["-i", it["path"], "-vn", "-c:a", "aac", "-b:a", bitrate, *meta, "-movflags", "+faststart", dst])
        outs.append(dst)
    return outs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.compile")
    ap.add_argument("wavs", nargs="+", help="mastered wavs in order")
    ap.add_argument("--out", required=True)
    ap.add_argument("--series", default="study")
    ap.add_argument("--xfade", type=float)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    items = [{"path": p, "title_en": Path(p).stem} for p in a.wavs]
    info = compile_audio(items, a.out, a.series, a.xfade)
    for c in info["chapters"]:
        print(c["start_s"], c["title_en"])
    print(info["measured"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
