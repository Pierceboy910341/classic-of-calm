"""Suno featured-track ingestion: title matching, order fallback, conversion, plan validation,
notebook-01 skipping and always-include in notebook 02. Run: python -m pytest pipeline/tests -q
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import soundfile as sf

from pipeline import kaggle_utils as ku
from pipeline import qa
from pipeline import run_week as rw
from pipeline import suno
from pipeline.common import run_ffmpeg
from pipeline.tests import synth

os.environ.setdefault("COC_FONT_DOWNLOAD", "0")
REPO = Path(__file__).resolve().parents[2]


def _ace(i, bpm=80, key="D dorian"):
    return {"id": f"s{i:02d}", "series": "study", "title_en": f"Ace Track {i}", "title_zh": "",
            "tags": "lofi, guzheng, instrumental", "negative": "vocals", "bpm": bpm, "key": key,
            "duration": 30, "seed": i, "layer": {"instrument": "guzheng", "role": "ornament"}}


def _suno(i, title, bpm=78, key="A minor"):
    t = _ace(i, bpm, key)
    t.update(title_en=title, source="suno",
             suno={"styles": f"{bpm} BPM, {key}, jazzy lofi hip hop, guzheng, instrumental, no vocals",
                   "exclude": "vocals, choir, rap", "title": title})
    return t


def _plan(week="2099-W02"):
    return {"week": week, "trial": False, "series": "study", "models": ["ace-step-1.5"],
            "creature": {"no": 1, "id": "x", "zh": "狌狌", "en": "Xingxing", "quote_zh": "", "quote_en": "",
                         "source": ""},
            "tracks": [_ace(1, 80, "D dorian"), _ace(2, 76, "A minor"), _ace(3, 84, "E dorian"),
                       _suno(4, "Under the Migu Tree", 78, "D minor"),
                       _suno(5, "Jade Slips at Midnight", 74, "A minor"),
                       _suno(6, "Lamplight Blossoms", 82, "G major")],
            "art": {}, "youtube": {"title": "t", "description": "AI", "tags": []}}


def _mp3(path, x, sr=synth.SR, title=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.wav")
    sf.write(str(tmp), x, sr, subtype="PCM_16")
    meta = ["-metadata", f"title={title}"] if title else []
    run_ffmpeg(["-i", tmp, "-c:a", "libmp3lame", "-b:a", "192k", *meta, path])
    tmp.unlink()
    return path


# ---------------------------------------------------------------- plan / notebook 01
def test_validate_plan_and_build_jobs_skip_suno():
    plan = _plan()
    errors, warnings, bad = ku.validate_plan(plan)
    assert not errors, errors
    jobs = ku.build_jobs(plan, ku.MODEL_ACE, 1, "/tmp/x")
    assert {j["track_id"] for j in jobs} == {"s01", "s02", "s03"}
    assert [t["id"] for t in ku.suno_tracks(plan)] == ["s04", "s05", "s06"]
    assert ku.plan_models({}) == [ku.MODEL_ACE]


def test_validate_plan_suno_errors():
    plan = _plan()
    plan["tracks"][3]["suno"] = {"styles": ""}
    plan["tracks"][4]["source"] = "udio"
    plan["tracks"][5]["suno"]["styles"] = "x" * 1001
    errors, _, bad = ku.validate_plan(plan)
    assert len(errors) == 3 and set(bad) == {"s04", "s05", "s06"}


# ---------------------------------------------------------------- matching
@pytest.mark.parametrize("a,b", [("Jade Slips at Midnight!", "jade_slips-at-midnight (1)"),
                                 ("Café Night", "cafe night"), ("Rock & Roll", "rock and roll")])
def test_norm_title(a, b):
    assert suno.norm_title(a) == suno.norm_title(b)


def test_match_title_order_and_other_week():
    tracks = _plan()["tracks"][3:]
    files = [Path("/in/lamplight blossoms (2).mp3"), Path("/in/UNDER THE MIGU TREE.wav"),
             Path("/in/Old Song From Last Week.mp3"), Path("/in/a1b2c3.mp3")]
    m, ign = suno.match_files(tracks, files, ["Old Song From Last Week"], tag_reader=None)
    got = {x["track_id"]: (Path(x["src"]).name, x["how"]) for x in m}
    assert got["s04"] == ("UNDER THE MIGU TREE.wav", "title")
    assert got["s06"] == ("lamplight blossoms (2).mp3", "title")
    assert got["s05"] == ("a1b2c3.mp3", "order")  # fallback by order
    assert [Path(i["src"]).name for i in ign] == ["Old Song From Last Week.mp3"]


def test_match_uses_embedded_title_and_fuzzy():
    tracks = _plan()["tracks"][3:]
    files = [Path("/in/song-77.mp3"), Path("/in/Jade Slip at Midnite.mp3")]
    tags = {"song-77.mp3": "Lamplight Blossoms"}
    m, _ = suno.match_files(tracks, files, tag_reader=lambda p: tags.get(p.name))
    got = {x["track_id"]: (Path(x["src"]).name, x["how"]) for x in m}
    assert got["s06"] == ("song-77.mp3", "title")
    assert got["s05"] == ("Jade Slip at Midnite.mp3", "title")
    assert "s04" not in got


def test_ingest_converts_mp3_and_wav(tmp_path):
    src = tmp_path / "input" / "classic-of-calm-suno"
    _mp3(src / "Under the Migu Tree.mp3", synth.lofi_track(12, seed=1))
    mono48 = synth.lofi_track(12, seed=2, sr=48000)[:, 0]
    (src / "x").mkdir(parents=True)
    sf.write(str(src / "x" / "jade slips at midnight.wav"), mono48, 48000)
    _mp3(src / "untitled.mp3", synth.lofi_track(12, seed=3), title="Lamplight Blossoms")
    found = suno.detect_sources(tmp_path / "input")
    assert found == [src]
    rep = suno.ingest(found, _plan(), tmp_path / "out")
    assert rep["missing"] == [] and len(rep["matches"]) == 3
    assert all(m["how"] == "title" for m in rep["matches"]), rep["matches"]
    for tid in ("s04", "s05", "s06"):
        info = sf.info(str(tmp_path / "out" / f"{tid}__suno__1.wav"))
        assert (info.samplerate, info.channels) == (44100, 2)


def test_detect_sources_generic_input(tmp_path):
    root = tmp_path / "input"
    synth.write(root / "nb01" / "candidates" / "s01__ace-step-1.5__1.wav", synth.lofi_track(3))
    synth.write(root / "my-music" / "Some Song.wav", synth.lofi_track(3))
    assert suno.detect_sources(root, exclude=[root / "nb01" / "candidates"]) == [root / "my-music"]


# ---------------------------------------------------------------- qa / selection
def test_qa_suno_and_select(tmp_path):
    root = tmp_path / "repo"
    wdir = root / "weekly" / "2099-W02"
    wdir.mkdir(parents=True)
    (wdir / "plan.json").write_text(json.dumps(_plan()), encoding="utf-8")
    dl = tmp_path / "dl"
    _mp3(dl / "Under the Migu Tree.mp3", synth.lofi_track(15, seed=1))
    out = tmp_path / "suno_wavs"
    assert qa.main(["suno", str(dl), "--plan", str(wdir / "plan.json"), "--out", str(out)]) == 0
    assert (out / "s04__suno__1.wav").exists() and (out / "qa_report.json").exists()
    sl = [{"n": 1, "file": "s01__ace-step-1.5__1.wav", "model": "ace-step-1.5"}]
    sel = qa.make_selection(sl, [1], "2099-W02", ["s04__suno__1.wav"])
    assert [p["file"] for p in sel["picks"]] == ["s01__ace-step-1.5__1.wav", "s04__suno__1.wav"]
    assert sel["model_vote"] == {"ace-step-1.5": 1}


# ---------------------------------------------------------------- notebook 02 always-include
def test_resolve_picks_always_includes_suno():
    plan = _plan()
    names = [f"s0{i}__ace-step-1.5__1.wav" for i in (1, 2, 3)] + [f"s0{i}__suno__1.wav" for i in (4, 5, 6)]
    idx = {n: Path("/x") / n for n in names}
    sel = {"picks": [{"file": names[i], "order": o} for i, o in ((2, 1), (0, 2), (1, 3))]}
    args = SimpleNamespace(max_tracks=None)
    items = rw.resolve_picks(args, plan, sel, idx, "study", {"files": []})
    order = [it["file"] for it in items]
    assert len(order) == 6 and set(order) == set(names)
    ace = [f for f in order if "__ace" in f]
    assert ace == [names[2], names[0], names[1]]  # owner's order kept
    assert order[0] == names[2] and order[-1] == names[1]  # first/last untouched
    # auto mode (no selection): suno kept even when QA fails it
    qa_rep = {"files": [{"file": n, "track_id": n.split("__")[0], "score": 50,
                         "status": "fail" if "suno" in n else "pass"} for n in names]}
    items = rw.resolve_picks(args, plan, None, idx, "study", qa_rep)
    assert {it["file"] for it in items} == set(names)


def test_run_week_with_suno_no_video(tmp_path):
    root = tmp_path / "repo"
    wdir = root / "weekly" / "2099-W02"
    wdir.mkdir(parents=True)
    plan = _plan()
    (wdir / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    cand = tmp_path / "input" / "nb01" / "candidates"
    for i in (1, 2, 3):
        synth.write(cand / f"s0{i}__ace-step-1.5__1.wav", synth.lofi_track(20, seed=i))
    dl = tmp_path / "input" / "classic-of-calm-suno"
    _mp3(dl / "Under the Migu Tree.mp3", synth.lofi_track(20, seed=7))
    _mp3(dl / "Jade Slips at Midnight (1).mp3", synth.lofi_track(20, seed=8))
    out = tmp_path / "out"
    rc = rw.main(["--week", "2099-W02", "--candidates", str(cand), "--repo-root", str(root), "--out", str(out),
                  "--suno", str(dl), "--no-video", "--qa-dur", "10", "400"])
    assert rc == 0
    rep = json.loads((out / "run_report.json").read_text())
    assert rep["steps"]["suno"]["matched"] == 2 and rep["steps"]["suno"]["missing"] == ["s06"]
    chapters = json.loads((out / "chapters.json").read_text())
    assert {c["track_id"] for c in chapters} == {"s01", "s02", "s03", "s04", "s05"}
    assert len(list((out / "stream_tracks").glob("*.m4a"))) == 5
