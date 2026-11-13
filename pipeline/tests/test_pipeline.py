"""Tests for the notebook-02 pipeline. Run:  python -m pytest pipeline/tests -q
The end-to-end test renders real 1920x1080 video (~1-2 min on 4 CPUs); skip it with -m "not slow".
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from pipeline import compile as comp
from pipeline import layer as lay
from pipeline import master as mas
from pipeline import metadata as meta
from pipeline import qa
from pipeline import visuals as vis
from pipeline.common import (camelot_distance, ffmpeg_loudness, integrated_lufs, media_duration, parse_key,
                             true_peak_db, write_wav)
from pipeline.tests import synth

os.environ.setdefault("COC_FONT_DOWNLOAD", "0")
REPO = Path(__file__).resolve().parents[2]
SR = synth.SR


@pytest.fixture(scope="module")
def tmp(tmp_path_factory):
    return tmp_path_factory.mktemp("coc")


# ---------------------------------------------------------------- common
@pytest.mark.parametrize("key,cam", [("C major", "8B"), ("A minor", "8A"), ("D dorian", "8A"), ("G mixolydian", "8B"),
                                     ("E yu", "9A"), ("A zhi", "10B"), ("F# minor", "11A"), ("Bb major", "6B"),
                                     ("8A", "8A")])
def test_camelot(key, cam):
    assert parse_key(key)["camelot"] == cam


def test_camelot_distance():
    assert camelot_distance("8A", "8A") == 0
    assert camelot_distance("8A", "8B") == 0.5
    assert camelot_distance("12A", "1A") == 1
    assert camelot_distance("8A", None) == 3


# ---------------------------------------------------------------- qa
def _qa(tmp, name, x):
    p = synth.write(tmp / f"{name}__test__1.wav", x)
    return qa.analyze_file(p, "study", (10, 600))


def test_qa_clean_music_passes(tmp):
    r = _qa(tmp, "music", synth.lofi_track(40))
    assert r["status"] == "pass", r["flags"]
    assert r["track_id"] == "music" and r["model"] == "test"


def test_qa_noise_fails(tmp):
    r = _qa(tmp, "noise", synth.noise_track(30))
    assert r["status"] == "fail" and any(f["code"] == "noise" for f in r["flags"])


def test_qa_clipping_fails(tmp):
    r = _qa(tmp, "clip", np.clip(synth.lofi_track(30) * 3, -1, 1))
    assert any(f["code"] == "clipping" and f["level"] == "fail" for f in r["flags"])


def test_qa_abrupt_end_and_gap(tmp):
    r = _qa(tmp, "abrupt", synth.lofi_track(40, fade=False))
    assert r["metrics"]["abrupt"]
    x = synth.lofi_track(40)
    x[15 * SR:19 * SR] = 0
    r = _qa(tmp, "gap", x)
    assert r["metrics"]["silent_gaps"] and r["metrics"]["silent_gaps"][0]["length"] >= 3.5


def test_qa_silence_bounds(tmp):
    x = np.concatenate([np.zeros((SR, 2), np.float32), synth.lofi_track(20), np.zeros((3 * SR, 2), np.float32)])
    r = _qa(tmp, "pad", x)
    assert 0.9 <= r["metrics"]["lead_silence_s"] <= 1.1
    assert r["metrics"]["tail_silence_s"] >= 2.9


def test_qa_static_loop_flagged(tmp):
    r = _qa(tmp, "loop", synth.static_loop_track(90))
    assert any(f["code"] == "static_loop" for f in r["flags"])


def test_qa_vocal_heuristic_orders(tmp):
    music = _qa(tmp, "m2", synth.lofi_track(30))["metrics"]["vocal_score"]
    voc = _qa(tmp, "v2", synth.lofi_track(30) * 0.6 + synth.vocal_like(30) * 0.5)["metrics"]["vocal_score"]
    assert voc > 0.55 > music


def test_qa_cli_previews_select(tmp):
    d = tmp / "cands"
    synth.write(d / "s01__ace__1.wav", synth.lofi_track(20, seed=1))
    synth.write(d / "s02__ace__1.wav", synth.lofi_track(20, seed=2))
    synth.write(d / "s03__sa3__1.wav", synth.noise_track(20))
    rep = tmp / "report.json"
    assert qa.main([str(d), "--out", str(rep), "--min-dur", "10", "--max-dur", "60",
                    "--previews", str(tmp / "prev"), "--top", "5"]) == 0
    items = json.loads((tmp / "prev" / "shortlist.json").read_text())
    assert len(items) == 2 and all(Path(tmp / "prev" / i["preview"]).exists() for i in items)
    assert "shortlist" not in items[0]["file"]
    assert qa.main(["select", "--shortlist", str(tmp / "prev" / "shortlist.json"), "--keep", "留 2, 1",
                    "--week", "2026-W47", "--out", str(tmp / "sel.json")]) == 0
    sel = json.loads((tmp / "sel.json").read_text())
    assert [p["order"] for p in sel["picks"]] == [1, 2] and sel["picks"][0]["file"] == items[1]["file"]


# ---------------------------------------------------------------- layer
def test_layer_noop_without_samples(tmp):
    x = synth.lofi_track(30)
    y, info = lay.layer_track(x, SR, {"instrument": "guzheng"}, tmp / "nosamples")
    assert y is x and not info["applied"]
    (tmp / "empty" / "guzheng").mkdir(parents=True)
    y, info = lay.layer_track(x, SR, {"instrument": "guzheng"}, tmp / "empty")
    assert not info["applied"]


def test_layer_applies_with_samples(tmp):
    root = tmp / "samples"
    synth.write(root / "bell" / "b.wav", synth.bell_sample())
    x = synth.lofi_track(60, seed=3)
    y, info = lay.layer_track(x, SR, {"instrument": "bell", "role": "ornament", "gain_db": -20}, root, seed=1)
    assert info["applied"] and info["count"] >= 2 and info["gain_db"] == -12.0  # clamped to -6..-12
    assert y.shape == x.shape and np.max(np.abs(y)) <= 0.99 + 1e-6
    assert abs(integrated_lufs(y, SR) - integrated_lufs(x, SR)) < 2.0  # ornaments stay underneath


# ---------------------------------------------------------------- master
@pytest.mark.parametrize("series,lufs,tp", [("study", -14, -1.0), ("sleep", -16, -1.5)])
def test_master_targets(series, lufs, tp):
    x = synth.lofi_track(45, fade=False) * 1.3
    y, sr, info = mas.master_track(x, SR, series)
    assert sr == 48000
    assert abs(integrated_lufs(y, sr) - lufs) <= 0.5
    assert true_peak_db(y, sr) <= tp - mas.AAC_HEADROOM_DB + 0.05
    assert info["fade_reason"] == "abrupt ending"


def test_master_trims_silence_and_selection_fade():
    x = np.concatenate([np.zeros((2 * SR, 2), np.float32), synth.lofi_track(30),
                        np.zeros((4 * SR, 2), np.float32)])
    y, sr, info = mas.master_track(x, SR, "work", fade_out={"at": 28, "length": 3})
    assert info["trimmed_lead_s"] > 1.5 and info["fade_out_s"] == 3
    assert len(y) / sr < 28.5


# ---------------------------------------------------------------- compile
def test_auto_order_rules():
    items = [{"track_id": "a", "bpm": 90, "key": "A minor", "instrument": "guzheng"},
             {"track_id": "b", "bpm": 76, "key": "D dorian", "instrument": "guzheng"},
             {"track_id": "c", "bpm": 80, "key": "C major", "instrument": "xiao"},
             {"track_id": "d", "bpm": 84, "key": "E minor", "instrument": "pipa"}]
    order = [it["track_id"] for it in comp.auto_order(items, "study")]
    assert order[0] == "b"  # calm start
    assert order == ["b", "c", "d", "a"]
    sleep = [it["track_id"] for it in comp.auto_order(items, "sleep")]
    assert sleep[0] == "a"


def test_compile_crossfade_and_chapters(tmp):
    items = []
    for i in range(3):
        y, sr, _ = mas.master_track(synth.lofi_track(20, seed=i), SR, "sleep")
        p = write_wav(tmp / f"m{i}.wav", y, sr)
        items.append({"path": str(p), "title_en": f"T{i}", "order": i + 1})
    lens = [media_duration(it["path"]) for it in items]
    info = comp.compile_audio(items, tmp / "comp.wav", "sleep")
    xf = 8.0 * 0 + min(8.0, 0.25 * min(lens))
    assert abs(info["duration_s"] - (sum(lens) - 2 * xf)) < 0.05
    ch = info["chapters"]
    assert ch[0]["start_s"] == 0 and ch[1]["start_s"] > 10 and ch[2]["start_s"] > ch[1]["start_s"]
    assert abs(info["measured"]["lufs"] - (-16)) <= 0.5
    outs = comp.export_stream_tracks(items, tmp / "st")
    assert outs[0].name == "01_t0.m4a" and all(o.exists() for o in outs)


# ---------------------------------------------------------------- metadata
def test_metadata(tmp):
    plan = json.loads((REPO / "weekly" / "_example" / "plan.json").read_text(encoding="utf-8")) \
        if (REPO / "weekly" / "_example" / "plan.json").exists() else {"series": "study"}
    plan.setdefault("creature", {"no": 1, "zh": "狌狌", "en": "Xingxing", "quote_zh": "狌狌知人名。",
                                 "quote_en": "The xingxing knows people's names.", "source": "海內南經"})
    chapters = [{"start_s": 0, "title_en": "A", "title_zh": "甲"}, {"start_s": 185.2, "title_en": "B"},
                {"start_s": 3700, "title_en": "C"}]
    m = meta.write_youtube_txt(plan, chapters, 3900, tmp / "yt")
    txt = (tmp / "yt" / "youtube.txt").read_text(encoding="utf-8")
    assert "0:00 A · 甲" in txt and "3:05 B" in txt and "1:01:40 C" in txt
    assert "[1 hour]" in m["title"] or "[1 hour]" not in (plan.get("youtube") or {}).get("title", "[1 hour]")
    assert "AI" in m["description"] and len(m["title"]) <= 100
    assert sum(len(t) for t in m["tags"]) <= 500


# ---------------------------------------------------------------- visuals
def test_loop_is_seamless(tmp):
    scene = synth.test_scene(tmp / "scene.png", (640, 360))
    for series in ("study", "sleep"):
        r = vis.LoopRenderer(scene, seconds=4, fps=10, size=(640, 360), series=series)
        a = np.asarray(r.frame(0), dtype=float)
        assert np.array_equal(a, np.asarray(r.frame(r.N), dtype=float))
        step = np.abs(np.asarray(r.frame(1), dtype=float) - a).mean()
        wrap = np.abs(np.asarray(r.frame(r.N - 1), dtype=float) - a).mean()
        assert wrap < 3 * step + 0.5


def test_concat_list_keeps_phase():
    segs = [(Path("/a.mp4"), 0, 23), (Path("/b.mp4"), 23, 50)]
    lines = vis.build_concat_list(segs, 20)
    assert lines[1:4] == ["file '/a.mp4'", "inpoint 0.000", "outpoint 20.000"]
    assert "inpoint 3.000" in lines and lines[-1] == "outpoint 10.000"


def test_thumbnail(tmp):
    scene = synth.test_scene(tmp / "scene2.png", (1920, 1080))
    p = vis.make_thumbnail(scene, tmp / "thumb.png", "sleep", creature={"no": 3, "en": "Xuangui", "zh": "旋龜"})
    from PIL import Image
    assert Image.open(p).size == (1280, 720)


# ---------------------------------------------------------------- end to end
@pytest.mark.slow
def test_run_week_end_to_end(tmp):
    root = tmp / "repo"
    wdir = root / "weekly" / "2099-W01"
    (wdir / "art").mkdir(parents=True)
    tracks = [{"id": f"s0{i}", "series": "study", "title_en": t, "title_zh": z, "bpm": b, "key": k,
               "tags": tg, "layer": {"instrument": "guzheng", "role": "ornament"}, "seed": i}
              for i, (t, z, b, k, tg) in enumerate([("Under the Migu Tree", "迷穀之下", 80, "D dorian", "guzheng lofi"),
                                                    ("Jade Slips", "夜讀玉簡", 76, "A minor", "xiao lofi"),
                                                    ("Kunlun Library", "崑崙書閣", 84, "E dorian", "pipa lofi")], 1)]
    plan = {"week": "2099-W01", "series": "study", "creature": {"no": 1, "zh": "狌狌", "en": "Xingxing",
            "quote_zh": "狌狌知人名。", "quote_en": "The xingxing knows people's names.", "source": "海內南經"},
            "tracks": tracks, "youtube": {"title": "Study lofi with Xingxing 🏔 guzheng beats [1 hour] | Classic of Calm No.01",
                                          "description": "Test.", "tags": ["study lofi"]}}
    (wdir / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    cand = tmp / "input" / "nb01" / "candidates"
    for i, t in enumerate(tracks):
        synth.write(cand / f"{t['id']}__ace-step-1.5__1.wav", synth.lofi_track(22, bpm=t["bpm"], seed=i))
    synth.write(cand / "s01__stable-audio-3__1.wav", synth.noise_track(22))  # QA must reject this one
    synth.test_scene(wdir / "art" / "scene.png")
    synth.write(root / "samples" / "guzheng" / "p.wav", synth.bell_sample(f=587, dur=1.5))
    out = tmp / "out"
    cmd = [sys.executable, "-m", "pipeline.run_week", "--week", "2099-W01", "--candidates", str(tmp / "input"),
           "--repo-root", str(root), "--out", str(out), "--loop-seconds", "20", "--qa-dur", "10", "400",
           "--preset", "veryfast"]
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, env=dict(os.environ, COC_FONT_DOWNLOAD="0"))
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    for f in ("compilation.mp4", "thumbnail.png", "youtube.txt", "stream_loop.mp4", "chapters.json"):
        assert (out / f).exists(), f
    assert len(list((out / "stream_tracks").glob("*.m4a"))) == 3  # auto-pick: noise take rejected
    probe = shutil.which("ffprobe")
    if probe:
        s = subprocess.run([probe, "-v", "error", "-show_entries", "stream=codec_name,width,height,r_frame_rate",
                            "-of", "json", str(out / "compilation.mp4")], capture_output=True, text=True)
        streams = json.loads(s.stdout)["streams"]
        v = next(x for x in streams if x["codec_name"] == "h264")
        assert (v["width"], v["height"], v["r_frame_rate"]) == (1920, 1080, "30/1")
        assert any(x["codec_name"] == "aac" for x in streams)
    chapters = json.loads((out / "chapters.json").read_text())
    dur = media_duration(out / "compilation.mp4")
    assert abs(dur - (3 * 22 - 2 * 4)) < 2.5
    loud = ffmpeg_loudness(out / "compilation.mp4")
    assert abs(loud["lufs"] + 14) <= 0.5 and loud["true_peak"] <= -0.9
    assert len(chapters) == 3
    assert subprocess.run([shutil.which("ffmpeg") or "ffmpeg", "-v", "error", "-i", str(out / "compilation.mp4"),
                           "-f", "null", "-"], capture_output=True).returncode == 0
