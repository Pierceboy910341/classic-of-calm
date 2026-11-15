"""Suno featured tracks: find the owner's downloaded files, match them to plan.json, convert.

Spec: docs/05-system-design.md ("Suno 曲目" and "Suno 輸入資料夾").

The owner downloads ~5 Suno tracks a week (browser, official Download button, MP3 or WAV) and
uploads them, filenames untouched, to ONE private Kaggle Dataset ``classic-of-calm-suno``.
Notebook 02 sees it at ``/kaggle/input/classic-of-calm-suno/`` (Kaggle sometimes nests it one
level deeper, e.g. ``/kaggle/input/datasets/<user>/classic-of-calm-suno/``; we search recursively).

Matching (no renaming required from the owner):
1. Title: the Suno "Song Title" is written into ``plan.json`` as ``suno.title`` (= ``title_en``).
   We compare it case/punctuation/accent-insensitively with the file name AND the embedded
   ID3/RIFF title tag (Suno writes the song title there; UNVERIFIED for every Suno version).
   Exact match > title contained in the name ("Under the Migu Tree (1).mp3") > fuzzy (difflib).
2. Files whose name matches a Suno title of ANOTHER week are ignored (the dataset may keep
   older weeks' files when the owner uploads a new version).
3. Order fallback: still-unmatched files (sorted by name) fill the still-unmatched Suno tracks
   in plan order. Logged as ``how: "order"`` so QA can double-check by ear.

Output: ``<out_dir>/<track_id>__suno__1.wav`` (44.1 kHz stereo PCM16, same as notebook-01
candidates) so QA / layer / master / compile treat them like any other candidate.
"""
from __future__ import annotations

import argparse
import difflib
import json
import logging
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

from .common import AUDIO_EXTS, ffmpeg_bin, ffprobe_bin, load_json, run_ffmpeg, save_json

log = logging.getLogger("pipeline.suno")

SOURCE_SUNO = "suno"
SOURCE_ACE = "ace-step"
MODEL_TAG = "suno"                    # middle part of <track_id>__suno__1.wav
DATASET_SLUG = "classic-of-calm-suno"
FUZZY_MIN = 0.80
TARGET_SR = 44100


# ---------------------------------------------------------------------------
# plan helpers
# ---------------------------------------------------------------------------
def track_source(track: dict) -> str:
    return SOURCE_SUNO if str(track.get("source") or "").strip().lower() == SOURCE_SUNO else SOURCE_ACE


def suno_tracks(plan: dict | None) -> list[dict]:
    return [t for t in (plan or {}).get("tracks", []) if isinstance(t, dict) and track_source(t) == SOURCE_SUNO]


def suno_title(track: dict) -> str:
    return str((track.get("suno") or {}).get("title") or track.get("title_en") or track.get("id") or "")


def is_suno_file(name: str) -> bool:
    parts = Path(name).stem.split("__")
    return len(parts) >= 2 and parts[1] == MODEL_TAG


def other_week_titles(repo_root: str | Path, week: str) -> list[str]:
    """Suno titles used in every other weekly/*/plan.json (to ignore stale files in the dataset)."""
    out = []
    for p in sorted(Path(repo_root, "weekly").glob("*/plan.json")):
        if p.parent.name == week:
            continue
        try:
            out += [suno_title(t) for t in suno_tracks(load_json(p))]
        except Exception:  # a broken old plan must not stop this week
            continue
    return [t for t in out if t]


# ---------------------------------------------------------------------------
# finding files
# ---------------------------------------------------------------------------
def _audio_under(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() in AUDIO_EXTS else []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTS
                  and not p.name.startswith("."))


def detect_sources(input_root: str | Path = "/kaggle/input", exclude: list[str | Path] = ()) -> list[Path]:
    """Folders under ``input_root`` that hold Suno downloads.

    * any folder named ``classic-of-calm-suno`` (preferred), else
    * any attached input that has audio files which are NOT notebook-01 candidates
      (``<id>__<model>__<take>.wav``), NOT under a ``candidates``/``samples``/``stream_tracks``
      folder, and NOT inside ``exclude`` (the candidates dir).
    """
    root = Path(input_root)
    if not root.exists():
        return []
    named = sorted({p for p in root.rglob(DATASET_SLUG) if p.is_dir()})
    if named:
        return named
    excl = [Path(e).resolve() for e in exclude if e]
    skip_parts = {"candidates", "samples", "stream_tracks"}
    tops: set[Path] = set()
    for p in _audio_under(root):
        rp = p.resolve()
        if any(rp == e or e in rp.parents for e in excl):
            continue
        if skip_parts & set(p.relative_to(root).parts[:-1]) or p.stem.count("__") >= 2:
            continue
        rel = p.relative_to(root).parts
        tops.add(root / rel[0] if len(rel) > 1 else p)
    return sorted(tops)


# ---------------------------------------------------------------------------
# title matching
# ---------------------------------------------------------------------------
_JUNK = re.compile(r"(\(\d+\)|\[\d+\]|\bv\d+\b|\bcopy\b|\bfinal\b|\bsuno\b|\bremaster(ed)?\b|"
                   r"\b[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}\b)")


def norm_title(s: str | None) -> str:
    """'Jade Slips at Midnight!' / 'jade_slips-at-midnight (1)' -> 'jade slips at midnight'."""
    s = unicodedata.normalize("NFKD", str(s or "")).casefold()
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("&", " and ").replace("'", "").replace("’", "")
    s = _JUNK.sub(" ", s)
    return " ".join(re.findall(r"[^\W_]+", s))


def embedded_title(path: str | Path) -> str | None:
    """ID3 / RIFF INFO title tag via ffprobe (or ffmpeg -i). None if absent/unreadable."""
    try:
        probe = ffprobe_bin()
        if probe:
            r = subprocess.run([probe, "-v", "error", "-show_entries", "format_tags=title", "-of",
                                "default=nw=1:nk=1", str(path)], capture_output=True, text=True, timeout=60)
            t = r.stdout.strip()
            return t or None
        r = subprocess.run([ffmpeg_bin(), "-hide_banner", "-i", str(path)], capture_output=True, text=True,
                           timeout=60)
        m = re.search(r"^\s*title\s*:\s*(.+)$", r.stderr, re.M | re.I)
        return m.group(1).strip() if m else None
    except Exception:
        return None


def title_score(title: str, names: list[str]) -> float:
    t = norm_title(title)
    if not t:
        return 0.0
    best = 0.0
    for n in names:
        c = norm_title(n)
        if not c:
            continue
        if c == t:
            return 1.0
        if re.search(rf"(^| ){re.escape(t)}( |$)", c):
            best = max(best, 0.95)
            continue
        r = difflib.SequenceMatcher(None, t.replace(" ", ""), c.replace(" ", "")).ratio()
        if r >= FUZZY_MIN:
            best = max(best, 0.9 * r)
    return best


def match_files(tracks: list[dict], files: list[Path], other_titles: list[str] = (),
                tag_reader=embedded_title) -> tuple[list[dict], list[dict]]:
    """Return (matches, ignored). matches: [{track_id, title, src, how, score}] in plan order."""
    names = {f: [f.stem] + ([tag_reader(f)] if tag_reader else []) for f in files}
    names = {f: [n for n in v if n] for f, v in names.items()}
    pairs = []
    for f in files:
        for i, t in enumerate(tracks):
            s = title_score(suno_title(t), names[f])
            if s > 0:
                pairs.append((s, i, f))
    pairs.sort(key=lambda x: (-x[0], x[1], str(x[2])))
    by_track: dict[int, dict] = {}
    used: set[Path] = set()
    for s, i, f in pairs:
        if i in by_track or f in used:
            continue
        by_track[i] = {"track_id": tracks[i]["id"], "title": suno_title(tracks[i]), "src": str(f),
                       "how": "title", "score": round(s, 3)}
        used.add(f)
    ignored = []
    rest = []
    for f in files:
        if f in used:
            continue
        other = max((title_score(o, names[f]) for o in other_titles), default=0.0)
        if other >= 0.9:
            ignored.append({"src": str(f), "reason": "title of another week"})
        else:
            rest.append(f)
    rest.sort(key=lambda p: (p.name.casefold(), str(p)))
    for i, t in enumerate(tracks):
        if i in by_track or not rest:
            continue
        f = rest.pop(0)
        by_track[i] = {"track_id": t["id"], "title": suno_title(t), "src": str(f), "how": "order", "score": 0.0}
    ignored += [{"src": str(f), "reason": "more files than Suno tracks in plan.json"} for f in rest]
    return [by_track[i] for i in sorted(by_track)], ignored


# ---------------------------------------------------------------------------
# conversion
# ---------------------------------------------------------------------------
def candidate_name(track_id: str, take: int = 1) -> str:
    return f"{track_id}__{MODEL_TAG}__{take}.wav"


def convert(src: str | Path, dst: str | Path) -> Path:
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(["-i", src, "-vn", "-map_metadata", "-1", "-ar", TARGET_SR, "-ac", 2, "-c:a", "pcm_s16le", dst])
    return dst


def ingest(sources: list[str | Path], plan: dict, out_dir: str | Path, other_titles: list[str] = (),
           tag_reader=embedded_title) -> dict:
    """Find + match + convert. Returns a report dict (also useful as suno_map.json)."""
    out_dir = Path(out_dir)
    tracks = suno_tracks(plan)
    files: list[Path] = []
    for s in sources or []:
        for p in _audio_under(Path(s)):
            if p not in files and not (out_dir in p.parents):
                files.append(p)
    rep = {"week": plan.get("week"), "expected": [t["id"] for t in tracks], "files_found": len(files),
           "matches": [], "ignored": [], "missing": []}
    if not tracks:
        rep["ignored"] = [{"src": str(f), "reason": "plan.json has no Suno tracks"} for f in files]
        return rep
    matches, ignored = match_files(tracks, files, other_titles, tag_reader)
    for m in matches:
        dst = out_dir / candidate_name(m["track_id"])
        try:
            convert(m["src"], dst)
            m["file"] = dst.name
            m["path"] = str(dst)
            log.info("Suno %-4s <- %s (%s%s)", m["track_id"], Path(m["src"]).name, m["how"],
                     f" {m['score']}" if m["how"] == "title" else "")
            rep["matches"].append(m)
        except Exception as exc:  # unreadable upload: report, do not stop the week
            ignored.append({"src": m["src"], "reason": f"cannot decode: {str(exc)[-300:]}"})
    rep["ignored"] = ignored
    got = {m["track_id"] for m in rep["matches"]}
    rep["missing"] = [t["id"] for t in tracks if t["id"] not in got]
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.suno", description="Match + convert Suno downloads")
    ap.add_argument("sources", nargs="+", help="folders/files with the owner's Suno downloads")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True, help="dir for <track_id>__suno__1.wav")
    ap.add_argument("--repo-root", help="to ignore other weeks' titles (default: plan's repo)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    plan = load_json(a.plan)
    root = Path(a.repo_root) if a.repo_root else Path(a.plan).resolve().parents[2]
    rep = ingest(a.sources, plan, a.out, other_week_titles(root, plan.get("week", "")))
    save_json(Path(a.out) / "suno_map.json", rep)
    print(json.dumps({k: rep[k] for k in ("expected", "files_found", "missing")}, ensure_ascii=False),
          f"{len(rep['matches'])} matched ->", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
