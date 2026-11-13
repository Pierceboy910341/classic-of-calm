"""Automated QA for candidate tracks (docs/03-music-bible.md section 8).

CLI
---
    python -m pipeline.qa <dir> --out report.json [--plan weekly/W/plan.json] [--series study]
                          [--previews previews/ --top 30]
    python -m pipeline.qa previews report.json --out previews/ --top 30   # 128k mp3 + shortlist
    python -m pipeline.qa select --shortlist previews/shortlist.json --keep 1,3,5 \
                          --week 2026-W47 --out weekly/2026-W47/selection.json

What is measured (per file)
---------------------------
duration, integrated LUFS (BS.1770 via pyloudnorm), true peak (4x oversampled), clipping
(runs of >=3 samples at full scale), leading / trailing silence (-50 dBFS), abrupt ending
(level of the last 0.25 s / 2 s of audible material relative to the track median), long silent
gaps inside the track (>= 2 s under -45 dBFS), spectral flatness + >8 kHz energy share
("noise / shimmer" heuristic), loop repetition (self-similarity of band-energy frames at the
best lag), rough vocal-presence score, approximate loudness range.

Limits (read before trusting a number)
--------------------------------------
* Everything here is a *heuristic screen* to save listening time; it never replaces the
  listening checklist in music bible 8.1 (AI artefacts, stereotype riffs, key clashes,
  similarity to known works cannot be measured here).
* Noise heuristic: spectral flatness is high for white/pink noise, rain beds and heavy tape
  hiss. A track that is mostly rain + quiet pad (sleep series) may be flagged as "warn".
* Repetition: lofi is loop-based by design; only near-identical repetition (2 s-median cosine > 0.97 of
  1 s band-energy frames at a fixed lag) over long stretches is flagged. Melodic variation
  over an identical drum loop usually passes. Exact digital loops always get caught.
* Vocal presence: computed on a harmonic-only (median-filtered) spectrogram as syllable-rate
  (3-8 Hz) modulation + vibrato-like pitch wobble in the 250-3500 Hz band. Breathy xiao/dizi
  lines, erhu vibrato and pipa tremolo can trigger it (false positives); hummed or very quiet
  "ooh/ahh" pads usually do NOT (false negatives). It only ever produces a "warn", never a fail.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter

from .common import (find_audio_files, integrated_lufs, load_json, parse_candidate_name, read_audio,
                     run_ffmpeg, save_json, series_name, series_spec, true_peak_db, frame_rms_db)

log = logging.getLogger("pipeline.qa")

SILENCE_DB = -50.0
GAP_DB = -45.0
FRAME_S = 0.05


# ---------------------------------------------------------------------------
# individual measurements (reused by master.py)
# ---------------------------------------------------------------------------
def silence_bounds(mono: np.ndarray, sr: int, thr_db: float = SILENCE_DB) -> tuple[float, float]:
    """Return (leading_silence_s, trailing_silence_s)."""
    fr = frame_rms_db(mono, sr, FRAME_S)
    active = np.where(fr > thr_db)[0]
    dur = len(mono) / sr
    if len(active) == 0:
        return dur, dur
    lead = active[0] * FRAME_S
    tail = max(0.0, dur - (active[-1] + 1) * FRAME_S)
    return float(lead), float(tail)


def ending_energy(mono: np.ndarray, sr: int) -> dict:
    """Energy of the end of the audible part relative to the track's median level."""
    fr = frame_rms_db(mono, sr, FRAME_S)
    active = np.where(fr > SILENCE_DB)[0]
    if len(active) < 10:
        return {"last2s_rel_db": -60.0, "final_rel_db": -60.0, "abrupt": False}
    end = active[-1] + 1
    ref = float(np.median(fr[active[0]:end]))
    n2 = max(1, int(2.0 / FRAME_S))
    nf = max(1, int(0.25 / FRAME_S))
    lin = lambda a: 10 * np.log10(np.mean(10 ** (a / 10)) + 1e-12)  # noqa: E731
    last2 = float(lin(fr[max(0, end - n2):end]) - ref)
    final = float(lin(fr[max(0, end - nf):end]) - ref)
    return {"last2s_rel_db": round(last2, 2), "final_rel_db": round(final, 2),
            "abrupt": bool(final > -9.0 and last2 > -6.0)}


def silent_gaps(mono: np.ndarray, sr: int, min_gap_s: float = 2.0) -> list[dict]:
    fr = frame_rms_db(mono, sr, FRAME_S)
    active = np.where(fr > SILENCE_DB)[0]
    if len(active) == 0:
        return []
    seg = fr[active[0]:active[-1] + 1] <= GAP_DB
    gaps, start = [], None
    for i, q in enumerate(np.append(seg, False)):
        if q and start is None:
            start = i
        elif not q and start is not None:
            if (i - start) * FRAME_S >= min_gap_s:
                gaps.append({"start": round((active[0] + start) * FRAME_S, 2),
                             "length": round((i - start) * FRAME_S, 2)})
            start = None
    return gaps


def clipping(x: np.ndarray, level: float = 0.999, min_run: int = 3) -> dict:
    hot = np.abs(x) >= level
    hot_any = hot.any(axis=1)
    n_hot = int(hot_any.sum())
    events = 0
    if n_hot:
        d = np.diff(np.concatenate([[0], hot_any.astype(np.int8), [0]]))
        starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
        events = int(np.sum((ends - starts) >= min_run))
    return {"clip_events": events, "clipped_ratio": round(n_hot / max(1, len(x)), 6)}


def _spectrogram(mono: np.ndarray, sr: int, nfft: int = 2048, hop: int = 1024):
    if len(mono) < nfft:
        mono = np.pad(mono, (0, nfft - len(mono)))
    n = 1 + (len(mono) - nfft) // hop
    idx = np.arange(nfft)[None, :] + hop * np.arange(n)[:, None]
    frames = mono[idx] * np.hanning(nfft)[None, :].astype(np.float32)
    mag = np.abs(np.fft.rfft(frames, axis=1)).astype(np.float32)
    freqs = np.fft.rfftfreq(nfft, 1 / sr)
    return mag, freqs, hop / sr


def spectral_stats(mag: np.ndarray, freqs: np.ndarray) -> dict:
    band = (freqs >= 150) & (freqs <= 10000)
    p = mag[:, band] ** 2 + 1e-12
    energy = p.sum(axis=1)
    loud = energy > np.percentile(energy, 30)
    if loud.sum() < 3:
        loud = np.ones_like(loud)
    flat = np.exp(np.mean(np.log(p[loud]), axis=1)) / np.mean(p[loud], axis=1)
    pall = mag ** 2
    hf = pall[:, freqs > 8000].sum() / (pall[:, freqs > 30].sum() + 1e-12)
    centroid = float(np.sum(pall.sum(0) * freqs) / (pall.sum() + 1e-12))
    return {"spectral_flatness": round(float(np.median(flat)), 4),
            "hf_ratio_8k": round(float(hf), 4), "spectral_centroid_hz": round(centroid, 1)}


def _band_features(mag: np.ndarray, freqs: np.ndarray, frame_dt: float, win_s: float = 0.5,
                   step_s: float = 0.1, nb: int = 24):
    """Log band energies smoothed over ``win_s`` and sampled every ~``step_s``."""
    from scipy.ndimage import uniform_filter1d
    edges = np.geomspace(60, min(12000, freqs[-1]), nb + 1)
    bands = np.stack([mag[:, (freqs >= lo) & (freqs < hi)].mean(axis=1) for lo, hi in zip(edges[:-1], edges[1:])], 1)
    win = max(1, int(round(win_s / frame_dt)))
    sm = uniform_filter1d(bands, win, axis=0, mode="nearest")
    step = max(1, int(round(step_s / frame_dt)))
    return np.log(sm[::step] + 1e-6), step * frame_dt


def repetition(mag: np.ndarray, freqs: np.ndarray, frame_dt: float, sim_thr: float = 0.97) -> dict:
    f, dt = _band_features(mag, freqs, frame_dt, win_s=1.0)
    n = len(f)
    out = {"loop_lag_s": None, "loop_similarity": 0.0, "repeat_run_s": 0.0, "repeat_ratio": 0.0}
    if n * dt < 12:
        return out
    f = f - f.mean(axis=0, keepdims=True)
    f = f / (np.linalg.norm(f, axis=1, keepdims=True) + 1e-9)
    best_l, best_s = None, -1.0
    max_lag = min(int(32 / dt), n // 3)
    for lag in range(int(4 / dt), max_lag + 1):
        s = float(np.mean(np.sum(f[:-lag] * f[lag:], axis=1)))
        if s > best_s:
            best_l, best_s = lag, s
    if best_l is None:
        return out
    sims = np.sum(f[:-best_l] * f[best_l:], axis=1)
    sims = median_filter(sims, size=int(2.0 / dt) | 1, mode="nearest") > sim_thr
    run = best = 0
    for q in sims:
        run = run + 1 if q else 0
        best = max(best, run)
    rep_s = (best + best_l) * dt if best else 0.0
    dur = n * dt
    return {"loop_lag_s": round(best_l * dt, 2), "loop_similarity": round(best_s, 4),
            "repeat_run_s": round(min(rep_s, dur), 1), "repeat_ratio": round(min(1.0, rep_s / dur), 3)}


def vocal_presence(mag: np.ndarray, freqs: np.ndarray, frame_dt: float) -> dict:
    """Rough singing detector (see module doc for limits). Returns score in [0, 1]."""
    if len(mag) < 64:
        return {"vocal_score": 0.0}
    harm = median_filter(mag, size=(9, 1))
    perc = median_filter(mag, size=(1, 17))
    hmask = harm > perc
    band = (freqs >= 250) & (freqs <= 3500)
    hb = (mag * hmask)[:, band]
    env = np.log(hb.sum(axis=1) + 1e-6)
    env = env - median_filter(env, size=int(1.5 / frame_dt) | 1)
    spec = np.abs(np.fft.rfft(env * np.hanning(len(env)))) ** 2
    mf = np.fft.rfftfreq(len(env), frame_dt)
    syl = spec[(mf >= 3) & (mf <= 8)].sum() / (spec[(mf >= 0.5) & (mf <= 20)].sum() + 1e-12)
    # pitch wobble: frame-to-frame movement of the dominant harmonic bin (vibrato/glide)
    fb = freqs[band]
    peak = fb[np.argmax(hb, axis=1)]
    strong = hb.max(axis=1) > np.percentile(hb.max(axis=1), 50)
    cents = np.abs(np.diff(1200 * np.log2(np.maximum(peak, 1.0))))
    small_moves = ((cents > 5) & (cents < 120))[strong[1:]] if strong[1:].any() else np.array([0.0])
    wobble = float(np.mean(small_moves)) if len(small_moves) else 0.0
    harm_share = float(hb.sum() / (mag[:, band].sum() + 1e-9))
    score = float(np.clip(1.6 * syl * harm_share + 0.9 * wobble * harm_share, 0, 1))
    return {"vocal_score": round(score, 3), "syllabic_mod": round(float(syl), 3),
            "pitch_wobble": round(wobble, 3), "harmonic_share_mid": round(harm_share, 3)}


def approx_lra(mono: np.ndarray, sr: int) -> float:
    hop = int(sr * 1.0)
    win = int(sr * 3.0)
    if len(mono) < win + hop:
        return 0.0
    vals = []
    for s in range(0, len(mono) - win, hop):
        r = np.sqrt(np.mean(mono[s:s + win].astype(np.float64) ** 2))
        vals.append(20 * np.log10(r + 1e-9))
    v = np.array(vals)
    v = v[v > -70]
    if len(v) < 3:
        return 0.0
    v = v[v > (10 * np.log10(np.mean(10 ** (v / 10))) - 20)]
    return float(np.percentile(v, 95) - np.percentile(v, 10))


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------
def analyze_file(path: str | Path, series: str = "study", dur_range: tuple[float, float] | None = None) -> dict:
    t0 = time.time()
    path = Path(path)
    spec = series_spec(series)
    res: dict = parse_candidate_name(path.name)
    res["path"] = str(path)
    res["series"] = series_name(series)
    try:
        x, sr = read_audio(path)
    except Exception as exc:
        res.update(status="fail", score=0, flags=[{"code": "unreadable", "level": "fail", "msg": str(exc)}])
        return res
    mono = x.mean(axis=1)
    dur = len(x) / sr
    lead, tail = silence_bounds(mono, sr)
    m = {
        "sample_rate": sr,
        "duration_s": round(dur, 2),
        "lufs": round(integrated_lufs(x, sr), 2),
        "true_peak_dbtp": round(true_peak_db(x, sr), 2),
        "lead_silence_s": round(lead, 2),
        "tail_silence_s": round(tail, 2),
        "lra_approx": round(approx_lra(mono, sr), 2),
    }
    m.update(clipping(x))
    m.update(ending_energy(mono, sr))
    m["silent_gaps"] = silent_gaps(mono, sr)
    # analysis spectrogram at <=22.05 kHz for speed
    if sr > 24000:
        from .common import resample
        ma, asr = resample(mono[:, None], sr, 22050)[:, 0], 22050
    else:
        ma, asr = mono, sr
    mag, freqs, fdt = _spectrogram(ma, asr)
    m.update(spectral_stats(mag, freqs))
    m.update(repetition(mag, freqs, fdt))
    m.update(vocal_presence(mag, freqs, fdt))
    res["metrics"] = m

    flags = []

    def flag(code, level, msg, penalty):
        flags.append({"code": code, "level": level, "msg": msg, "penalty": penalty})

    lo, hi = dur_range or spec["dur"]
    if m["lufs"] <= -60:
        flag("silent", "fail", "file is (almost) silent", 100)
    if dur < lo * 0.8 or dur > hi * 1.3:
        flag("duration", "fail", f"duration {dur:.0f}s far outside {lo:.0f}-{hi:.0f}s", 30)
    elif dur < lo or dur > hi:
        flag("duration", "warn", f"duration {dur:.0f}s outside {lo:.0f}-{hi:.0f}s", 10)
    if m["clipped_ratio"] > 0.001 or m["clip_events"] > 50:
        flag("clipping", "fail", f"{m['clip_events']} clip events ({m['clipped_ratio']:.3%} samples)", 35)
    elif m["clip_events"] > 0:
        flag("clipping", "warn", f"{m['clip_events']} clip events", min(20, 2 * m["clip_events"]))
    if m["true_peak_dbtp"] > 0.0:
        flag("true_peak", "info", f"true peak {m['true_peak_dbtp']} dBTP (limiter will fix)", 3)
    if -60 < m["lufs"] < -32:
        flag("too_quiet", "warn", f"very quiet ({m['lufs']} LUFS): noise floor will be raised", 10)
    if lead > 3.0:
        flag("lead_silence", "warn", f"{lead:.1f}s leading silence", 8)
    elif lead > 0.2:
        flag("lead_silence", "info", f"{lead:.1f}s leading silence (trimmed by master)", 2)
    if tail > 5.0:
        flag("tail_silence", "warn", f"{tail:.1f}s trailing silence", 6)
    elif tail > 1.0:
        flag("tail_silence", "info", f"{tail:.1f}s trailing silence (trimmed by master)", 2)
    if m["abrupt"]:
        flag("abrupt_end", "warn", f"ends at full energy (last 0.25s {m['final_rel_db']} dB vs median): "
             "master will add a fade; listen for a mid-phrase cut", 10)
    for g in m["silent_gaps"]:
        lvl = "fail" if g["length"] > 6 else "warn"
        flag("silent_gap", lvl, f"{g['length']}s silence at {g['start']}s", 25 if lvl == "fail" else 10)
    if m["spectral_flatness"] > 0.35:
        flag("noise", "fail", f"noise-like spectrum (flatness {m['spectral_flatness']})", 40)
    elif m["spectral_flatness"] > 0.22:
        flag("noise", "warn", f"noisy spectrum (flatness {m['spectral_flatness']})", 15)
    if m["hf_ratio_8k"] > 0.15:
        flag("hf_harsh", "warn", f"{m['hf_ratio_8k']:.0%} energy above 8 kHz (shimmer/harsh?)", 6)
    if m["repeat_ratio"] > 0.85 and dur > 30:
        flag("static_loop", "fail", f"near-identical loop for {m['repeat_ratio']:.0%} of the track", 30)
    elif m["repeat_run_s"] > 60:
        flag("repetitive", "warn", f"unchanged loop for {m['repeat_run_s']:.0f}s", 10)
    if m["vocal_score"] > 0.55:
        flag("vocals?", "warn", f"possible vocals (score {m['vocal_score']}) — listen", 15)

    score = max(0, 100 - sum(f["penalty"] for f in flags))
    levels = {f["level"] for f in flags}
    res["status"] = "fail" if "fail" in levels else ("warn" if "warn" in levels else "pass")
    res["score"] = int(score)
    res["flags"] = flags
    res["analysis_s"] = round(time.time() - t0, 2)
    return res


def _track_series(plan: dict | None, track_id: str, default: str) -> str:
    if plan:
        for t in plan.get("tracks", []):
            if t.get("id") == track_id:
                return series_name(t.get("series") or plan.get("series"))
        return series_name(plan.get("series") or default)
    return series_name(default)


def run_qa(cand_dir: str | Path, plan: dict | None = None, series: str | None = None,
           dur_range: tuple[float, float] | None = None, files: list[Path] | None = None) -> dict:
    cand_dir = Path(cand_dir)
    files = files if files is not None else [p for p in find_audio_files(cand_dir) if p.suffix.lower() == ".wav"]
    titles = {t.get("id"): t for t in (plan or {}).get("tracks", [])}
    results = []
    for i, p in enumerate(files, 1):
        s = series or _track_series(plan, parse_candidate_name(p.name)["track_id"], "study")
        r = analyze_file(p, s, dur_range)
        t = titles.get(r["track_id"])
        if t:
            r["title_en"] = t.get("title_en")
            r["title_zh"] = t.get("title_zh")
        log.info("[%d/%d] %s -> %s %s", i, len(files), p.name, r["status"], r["score"])
        results.append(r)
    results.sort(key=lambda r: (-r["score"], r["file"]))
    summary = {s: sum(1 for r in results if r["status"] == s) for s in ("pass", "warn", "fail")}
    return {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "dir": str(cand_dir),
            "count": len(results), "summary": summary, "files": results}


# ---------------------------------------------------------------------------
# previews + selection helpers (for the QA agent / owner listening loop)
# ---------------------------------------------------------------------------
def shortlist(report: dict, top: int = 30, one_per_track: bool = False) -> list[dict]:
    ok = [r for r in report["files"] if r.get("status") != "fail"]
    ok.sort(key=lambda r: (-r["score"], r["file"]))
    if one_per_track:
        seen, out = set(), []
        for r in ok:
            if r["track_id"] not in seen:
                seen.add(r["track_id"])
                out.append(r)
        ok = out
    return ok[:top]


def export_previews(report: dict | str | Path, out_dir: str | Path, top: int = 30,
                    bitrate: str = "128k", wav_dir: str | Path | None = None) -> list[dict]:
    """Export numbered 128k mp3 previews of the shortlist + shortlist.json/.txt."""
    if not isinstance(report, dict):
        report = load_json(report)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for n, r in enumerate(shortlist(report, top), 1):
        src = Path(wav_dir) / r["file"] if wav_dir else Path(r["path"])
        dst = out_dir / f"{n:02d}__{Path(r['file']).stem}.mp3"
        run_ffmpeg(["-i", src, "-vn", "-c:a", "libmp3lame", "-b:a", bitrate, dst])
        items.append({"n": n, "file": r["file"], "preview": dst.name, "track_id": r["track_id"],
                      "model": r.get("model"), "title_en": r.get("title_en"), "score": r["score"],
                      "status": r["status"], "notes": "; ".join(f["msg"] for f in r.get("flags", [])
                                                                  if f["level"] != "info")})
    save_json(out_dir / "shortlist.json", items)
    lines = ["# 試聽清單 Shortlist — 回覆要保留的編號，例如：留 1, 3, 5", ""]
    for it in items:
        t = f" — {it['title_en']}" if it.get("title_en") else ""
        lines.append(f"{it['n']:>2}. {it['preview']}{t}  [score {it['score']}, {it['status']}]"
                     + (f"  ⚠ {it['notes']}" if it["notes"] else ""))
    (out_dir / "shortlist.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return items


def make_selection(shortlist_items: list[dict], keep: list[int], week: str) -> dict:
    by_n = {it["n"]: it for it in shortlist_items}
    picks, vote = [], {}
    for order, n in enumerate(keep, 1):
        it = by_n.get(n)
        if not it:
            raise ValueError(f"shortlist has no item {n}")
        picks.append({"file": it["file"], "order": order, "fade_out": None, "notes": ""})
        if it.get("model"):
            vote[it["model"]] = vote.get(it["model"], 0) + 1
    return {"week": week, "picks": picks, "model_vote": vote}


def _parse_keep(s: str) -> list[int]:
    import re
    return [int(v) for v in re.findall(r"\d+", s)]


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if argv and argv[0] == "previews":
        ap = argparse.ArgumentParser(prog="pipeline.qa previews")
        ap.add_argument("report")
        ap.add_argument("--out", required=True)
        ap.add_argument("--top", type=int, default=30)
        ap.add_argument("--bitrate", default="128k")
        a = ap.parse_args(argv[1:])
        items = export_previews(a.report, a.out, a.top, a.bitrate)
        print(f"{len(items)} previews -> {a.out}")
        return 0
    if argv and argv[0] == "select":
        ap = argparse.ArgumentParser(prog="pipeline.qa select")
        ap.add_argument("--shortlist", required=True)
        ap.add_argument("--keep", required=True, help='e.g. "1,3,5" or "留 1, 3, 5"')
        ap.add_argument("--week", required=True)
        ap.add_argument("--out", required=True)
        a = ap.parse_args(argv[1:])
        sel = make_selection(load_json(a.shortlist), _parse_keep(a.keep), a.week)
        save_json(a.out, sel)
        print(f"{len(sel['picks'])} picks -> {a.out}")
        return 0
    ap = argparse.ArgumentParser(prog="pipeline.qa", description="QA candidate wavs")
    ap.add_argument("dir")
    ap.add_argument("--out", default="report.json")
    ap.add_argument("--plan", help="plan.json (titles + per-track series)")
    ap.add_argument("--series", help="force series (study|sleep|work)")
    ap.add_argument("--min-dur", type=float)
    ap.add_argument("--max-dur", type=float)
    ap.add_argument("--previews", help="also export mp3 previews of the shortlist to this dir")
    ap.add_argument("--top", type=int, default=30)
    a = ap.parse_args(argv)
    plan = load_json(a.plan) if a.plan else None
    dr = (a.min_dur or 0, a.max_dur or 1e9) if (a.min_dur or a.max_dur) else None
    rep = run_qa(a.dir, plan, a.series, dr)
    save_json(a.out, rep)
    print(json.dumps(rep["summary"]), "->", a.out)
    if a.previews:
        items = export_previews(rep, a.previews, a.top)
        print(f"{len(items)} previews -> {a.previews}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
