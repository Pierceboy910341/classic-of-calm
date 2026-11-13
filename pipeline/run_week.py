"""Notebook-02 job in one command.

    python -m pipeline.run_week --week 2026-W47 --candidates <dir> --repo-root . [--out <dir>]

Reads   weekly/<WEEK>/plan.json, weekly/<WEEK>/selection.json (optional), weekly/<WEEK>/art/scene.png
        (+ art/thumbnail.png), samples/<instrument>/*.wav, candidate wavs (searched recursively).
Writes  <out>/compilation.mp4, thumbnail.png, youtube.txt, stream_tracks/<n>_<slug>.m4a,
        stream_loop.mp4 (docs/05 "notebook 02 輸出"), plus metadata.json, chapters.json,
        qa_report.json, run_report.json.
Without selection.json the best QA-passing take of each track is used and ordered automatically.
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import tempfile
import time
from pathlib import Path

from . import compile as comp
from . import layer as lay
from . import master as mas
from . import metadata as meta
from . import qa
from . import visuals as vis
from .common import (ffmpeg_loudness, find_audio_files, load_json, media_duration, parse_candidate_name,
                     read_audio, save_json, series_name, series_spec, slugify, write_wav)

log = logging.getLogger("pipeline.run_week")

INSTRUMENTS = ["guzheng", "pipa", "xiao", "dizi", "yangqin", "guqin", "erhu", "bianzhong", "bell", "zither",
               "dulcimer", "flute"]
_INST_CANON = {"zither": "guzheng", "dulcimer": "yangqin", "flute": "xiao"}


def lead_instrument(track: dict) -> str | None:
    tags = (track.get("tags") or "").lower()
    hits = [(tags.find(i), i) for i in INSTRUMENTS if i in tags]
    if hits:
        return _INST_CANON.get(min(hits)[1], min(hits)[1])
    return (track.get("layer") or {}).get("instrument")


def _step(msg: str) -> None:
    log.info("\n== %s ==", msg)


def resolve_picks(args, plan: dict, sel: dict | None, cand_index: dict[str, Path], series: str,
                  qa_report: dict) -> list[dict]:
    tracks = {t.get("id"): t for t in plan.get("tracks", [])}
    picks = []
    if sel and sel.get("picks"):
        for p in sel["picks"]:
            f = Path(p["file"]).name
            if f not in cand_index:
                log.warning("selection file not found in candidates: %s (skipped)", f)
                continue
            picks.append(dict(p, file=f))
        use_order = all(p.get("order") is not None for p in picks)
    else:
        log.warning("no selection.json — auto-picking the best QA take per track")
        seen = set()
        for r in sorted(qa_report["files"], key=lambda r: -r["score"]):
            if r["status"] == "fail" or r["track_id"] in seen:
                continue
            seen.add(r["track_id"])
            picks.append({"file": r["file"], "order": None, "fade_out": None, "notes": "auto"})
        use_order = False
    if args.max_tracks:
        picks = picks[: args.max_tracks]
    items = []
    for p in picks:
        parts = parse_candidate_name(p["file"])
        t = tracks.get(parts["track_id"], {})
        items.append({
            "file": p["file"], "src": str(cand_index[p["file"]]), "order": p.get("order"),
            "fade_out": p.get("fade_out"), "track_id": parts["track_id"], "model": parts["model"],
            "title_en": t.get("title_en") or parts["track_id"], "title_zh": t.get("title_zh"),
            "lore_note": t.get("lore_note"), "bpm": t.get("bpm"), "key": t.get("key"),
            "layer": t.get("layer"), "seed": t.get("seed"), "instrument": lead_instrument(t),
        })
    return comp.order_items(items, series, use_order)


def run(args) -> dict:
    t0 = time.time()
    repo = Path(args.repo_root).resolve()
    wdir = repo / "weekly" / args.week
    out = Path(args.out or (repo / "output" / args.week)).resolve()
    work = Path(args.work or tempfile.mkdtemp(prefix=f"coc_{args.week}_")).resolve()
    out.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    report: dict = {"week": args.week, "out": str(out), "work": str(work), "steps": {}}

    plan = load_json(wdir / "plan.json")
    if plan is None:
        raise SystemExit(f"plan.json not found: {wdir / 'plan.json'}")
    series = series_name(plan.get("series"))
    spec = series_spec(series)
    sel = load_json(wdir / "selection.json")
    log.info("week %s · series %s · selection.json %s", args.week, series, "found" if sel else "MISSING")

    cand_index = {p.name: p for p in find_audio_files(args.candidates) if p.suffix.lower() == ".wav"}
    if not cand_index:
        raise SystemExit(f"no candidate wavs under {args.candidates}")
    log.info("%d candidate wavs", len(cand_index))

    # 1. QA (all candidates when auto-picking, else only the picks)
    _step("QA")
    dr = tuple(args.qa_dur) if args.qa_dur else None
    if sel and sel.get("picks"):
        files = [cand_index[Path(p["file"]).name] for p in sel["picks"] if Path(p["file"]).name in cand_index]
    else:
        files = list(cand_index.values())
    qa_report = qa.run_qa(args.candidates, plan, series, dr, files=files)
    save_json(out / "qa_report.json", qa_report)
    report["steps"]["qa"] = qa_report["summary"]

    items = resolve_picks(args, plan, sel, cand_index, series, qa_report)
    if not items:
        raise SystemExit("nothing to assemble (no usable picks)")
    log.info("order: %s", " → ".join(it["track_id"] for it in items))

    # 2. layer + master each pick
    _step("layer + master")
    mdir = work / "mastered"
    per_track = []
    for n, it in enumerate(items, 1):
        x, sr = read_audio(it["src"])
        x, linfo = lay.layer_track(x, sr, it.get("layer"), args.samples or (repo / "samples"), series,
                                   seed=int(it.get("seed") or n))
        y, msr, minfo = mas.master_track(x, sr, series, it.get("fade_out"))
        path = write_wav(mdir / f"{n:02d}_{slugify(it['title_en'])}.wav", y, msr)
        it["path"] = str(path)
        per_track.append({"n": n, "file": it["file"], "layer": linfo, "master": minfo})
        log.info("[%d/%d] %s  %.1f LUFS  %.1f dBTP  %s", n, len(items), it["file"], minfo["lufs"],
                 minfo["true_peak"], "layered" if linfo.get("applied") else "-")
    report["tracks"] = per_track

    _step("stream_tracks")
    st = comp.export_stream_tracks(items, out / "stream_tracks")
    report["steps"]["stream_tracks"] = len(st)

    # 3. compilation audio + chapters
    _step("compile")
    comp_wav = work / "compilation.wav"
    cinfo = comp.compile_audio(items, comp_wav, series, args.xfade)
    chapters = cinfo["chapters"]
    save_json(out / "chapters.json", chapters)
    report["steps"]["compile"] = {k: v for k, v in cinfo.items() if k != "chapters"}
    log.info("compilation %.1f s · %s", cinfo["duration_s"], cinfo["measured"])

    # 4. metadata
    _step("youtube.txt")
    m = meta.write_youtube_txt(plan, chapters, cinfo["duration_s"], out)
    report["steps"]["metadata"] = {"title": m["title"], "checks": m["checks"]}

    # 5. visuals
    art = wdir / "art"
    scene = art / "scene.png"
    if not scene.exists():
        log.warning("art/scene.png missing — using a generated placeholder scene")
        scene = vis.placeholder_scene(work / "placeholder_scene.png", seed=hash(args.week) % 1000)
        report["placeholder_scene"] = True
    thumb_src = art / "thumbnail.png" if (art / "thumbnail.png").exists() else scene
    _step("thumbnail")
    mood = (plan.get("art") or {}).get("thumbnail_text") or (plan.get("youtube") or {}).get("thumbnail_text")
    vis.make_thumbnail(thumb_src, out / "thumbnail.png", series, mood, plan.get("creature"))
    if not args.no_video:
        size = tuple(int(v) for v in args.size.lower().split("x"))
        _step(f"loop video ({args.loop_seconds}s)")
        loop = vis.make_loop(scene, out / "stream_loop.mp4", args.loop_seconds, args.fps, size, series,
                             args.particles, seed=args.seed, preset=args.preset)
        _step("compilation.mp4")
        comp_audio = work / "compilation_audio.wav"
        shutil.move(str(comp_wav), comp_audio)
        vinfo = vis.render_compilation(loop, comp_audio, out / "compilation.mp4", chapters, series,
                                       args.loop_seconds, args.fps, captions=not args.no_captions, size=size,
                                       work_dir=work / "video")
        vinfo["mp4_duration_s"] = round(media_duration(out / "compilation.mp4"), 2)
        vinfo["mp4_loudness"] = ffmpeg_loudness(out / "compilation.mp4", spec["lufs"], spec["tp"])
        report["steps"]["video"] = vinfo
    else:
        shutil.copy2(comp_wav, out / "compilation.wav")
    report["elapsed_s"] = round(time.time() - t0, 1)
    save_json(out / "run_report.json", report)
    if not args.keep_work:
        shutil.rmtree(work, ignore_errors=True)
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.run_week", description="Assemble one week (notebook 02)")
    ap.add_argument("--week", required=True)
    ap.add_argument("--candidates", required=True, help="dir with notebook-01 candidate wavs (searched recursively)")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--out", help="output dir (default <repo>/output/<week>)")
    ap.add_argument("--work", help="scratch dir for big intermediates (default: system temp)")
    ap.add_argument("--samples", help="samples root (default <repo>/samples)")
    ap.add_argument("--loop-seconds", type=int, default=40)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--particles", choices=["petals", "rain", "none"], help="override series default")
    ap.add_argument("--preset", default="medium", help="x264 preset for the loop")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--xfade", type=float, help="crossfade seconds (default: series midpoint)")
    ap.add_argument("--qa-dur", type=float, nargs=2, metavar=("MIN", "MAX"), help="override QA duration range")
    ap.add_argument("--max-tracks", type=int)
    ap.add_argument("--no-video", action="store_true")
    ap.add_argument("--no-captions", action="store_true")
    ap.add_argument("--keep-work", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")
    rep = run(args)
    print(json.dumps({"out": rep["out"], "elapsed_s": rep["elapsed_s"], "steps": rep["steps"]},
                     ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
