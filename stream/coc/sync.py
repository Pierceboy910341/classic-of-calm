"""Daily library sync: pull the latest "02 Assemble" output from Kaggle.

    coc-sync                 # download from Kaggle (KAGGLE_NOTEBOOK)
    coc-sync --from-dir DIR  # import a folder you uploaded yourself
                             # (same layout: stream_tracks/*.m4a, stream_loop.mp4)

Steps: download into staging -> skip if identical to a batch we already have ->
validate every track (probe + full decode) and the loop video (h264, yuv420p,
keyframes <= 2-4 s) -> move into library/batches/<id>/ atomically -> point
library/current_loop.mp4 at the newest valid loop -> prune old batches
(KEEP_BATCHES, LIBRARY_MAX_GB, MIN_FREE_GB). The streamer notices new tracks
on its own at the next track boundary.
"""
from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .common import (Config, ffprobe_json, load_config, log, read_json,
                     slug_to_title, validate_loop, write_json_atomic)
from .library import Batch, dir_size, list_batches, series_matches

FILE_PATTERN = r"(^|/)(stream_tracks/[^/]+\.m4a|stream_loop\.mp4|youtube\.txt)$"
MIN_TRACK_S = float(os.environ.get("MIN_TRACK_SECONDS", "20"))
MAX_TRACK_S = 1800


def normalize_slug(s: str) -> str:
    """Accept 'user/slug', a full kaggle.com/code/user/slug URL, etc."""
    s = s.strip().rstrip("/")
    m = re.search(r"kaggle\.com/(?:code/)?([^/?#]+)/([^/?#]+)", s)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return s


def kaggle_env(cfg: Config) -> dict:
    # Empty KAGGLE_* variables confuse the CLI's auth detection.
    env = {k: v for k, v in os.environ.items() if not (k.startswith("KAGGLE_") and not v.strip())}
    kdir = cfg.home / ".kaggle"
    kdir.mkdir(parents=True, exist_ok=True)
    env.setdefault("HOME", str(cfg.home))
    env["KAGGLE_CONFIG_DIR"] = str(kdir)
    return env


def download(cfg: Config, dest: Path) -> tuple[bool, str]:
    slug = normalize_slug(cfg.kaggle_notebook)
    if "/" not in slug:
        return False, "KAGGLE_NOTEBOOK must look like 'username/notebook-slug'"
    base = [cfg.kaggle_bin, "kernels", "output", slug, "-p", str(dest), "-o"]
    attempts = [base + ["--file-pattern", FILE_PATTERN, "--page-size", "200"], base]
    last = ""
    for cmd in attempts:
        log("running: " + " ".join(cmd[:4]) + " ...")
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=3 * 3600,
                               env=kaggle_env(cfg))
        except subprocess.TimeoutExpired:
            return False, "kaggle download timed out"
        except OSError as e:
            return False, f"cannot run kaggle CLI: {e}"
        out = (p.stdout + p.stderr).strip()
        if p.returncode == 0:
            return True, out[-300:]
        last = out[-500:]
        if "unrecognized arguments" not in out:
            break  # real error, don't retry without the filter
    return False, f"kaggle CLI failed: {last}"


def remote_last_run(cfg: Config) -> str | None:
    """lastRunTime of the notebook according to Kaggle, or None if unknown.
    Lets the daily sync skip a ~200 MB download when nothing new ran."""
    slug = normalize_slug(cfg.kaggle_notebook)
    try:
        p = subprocess.run([cfg.kaggle_bin, "kernels", "list", "--mine", "--csv",
                            "--sort-by", "dateRun", "--page-size", "100"],
                           capture_output=True, text=True, timeout=120, env=kaggle_env(cfg))
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    for row in csv.DictReader(io.StringIO(p.stdout)):
        if (row.get("ref") or "").strip().lower() == slug.lower():
            return (row.get("lastRunTime") or "").strip() or None
    return None


def probe_track(cfg: Config, path: Path) -> tuple[dict | None, str]:
    meta = ffprobe_json(cfg, path)
    if not meta:
        return None, "unreadable"
    if not any(s.get("codec_type") == "audio" for s in meta.get("streams", [])):
        return None, "no audio stream"
    try:
        dur = float(meta["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        return None, "unknown duration"
    if not MIN_TRACK_S <= dur <= MAX_TRACK_S:
        return None, f"duration {dur:.0f} s out of range"
    # Full decode catches truncated downloads.
    p = subprocess.run(["nice", "-n", "15", cfg.ffmpeg, "-v", "error", "-nostdin",
                        "-i", str(path), "-vn", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=600)
    if p.returncode != 0 or p.stderr.strip():
        return None, "decode errors: " + p.stderr.strip()[:120]
    tags = {k.lower(): v for k, v in (meta["format"].get("tags") or {}).items()}
    title = (tags.get("title") or "").strip() or slug_to_title(path.stem)
    return {"title": title, "duration": round(dur, 2), "bytes": path.stat().st_size}, ""


def detect_series(youtube_txt: Path | None) -> str:
    if not youtube_txt or not youtube_txt.is_file():
        return "unknown"
    try:
        head = "\n".join(youtube_txt.read_text(errors="replace").splitlines()[:5]).lower()
    except OSError:
        return "unknown"
    m = re.search(r"\b(study|sleep|work)\b", head)
    return m.group(1) if m else "unknown"


def fingerprint(tracks: list[Path], loop: Path | None) -> str:
    h = hashlib.sha256()
    for p in sorted(tracks + ([loop] if loop else []), key=lambda x: x.name):
        h.update(f"{p.name}:{p.stat().st_size};".encode())
        with open(p, "rb") as f:
            h.update(f.read(1 << 16))
    return h.hexdigest()


def update_current_loop(cfg: Config, batches: list[Batch]) -> str | None:
    for b in reversed(batches):
        if series_matches(cfg, b.series) and b.loop_path and b.manifest.get("loop_ok"):
            target = b.loop_path.relative_to(cfg.library)
            tmp = cfg.library / ".current_loop.tmp"
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass
            if cfg.current_loop.is_symlink() and os.readlink(cfg.current_loop) == str(target):
                return str(target)
            tmp.symlink_to(target)
            os.replace(tmp, cfg.current_loop)
            log(f"current loop video -> {target}")
            return str(target)
    return None


def prune(cfg: Config) -> list[str]:
    removed = []
    batches = list_batches(cfg)
    protected = {batches[-1].batch_id} if batches else set()
    if cfg.current_loop.exists():
        cur = cfg.current_loop.resolve()
        for b in batches:
            if b.path.resolve() in cur.parents:
                protected.add(b.batch_id)
    sizes = {b.batch_id: dir_size(b.path) for b in batches}

    def total():
        return sum(sizes[b.batch_id] for b in batches)

    def free_gb():
        return shutil.disk_usage(cfg.home).free / 1e9

    def drop_oldest() -> bool:
        for b in batches:
            if b.batch_id not in protected:
                shutil.rmtree(b.path, ignore_errors=True)
                batches.remove(b)
                removed.append(b.batch_id)
                log(f"pruned old batch {b.batch_id}")
                return True
        return False

    while len(batches) > max(1, cfg.keep_batches) and drop_oldest():
        pass
    while total() > cfg.library_max_gb * 1e9 and drop_oldest():
        pass
    while free_gb() < cfg.min_free_gb and drop_oldest():
        pass
    return removed


def import_dir(cfg: Config, src: Path, source_label: str, force: bool) -> dict:
    tracks_dir = next((p for p in src.rglob("stream_tracks") if p.is_dir()), None)
    tracks = sorted(tracks_dir.glob("*.m4a")) if tracks_dir else []
    loop = next(iter(sorted(src.rglob("stream_loop.mp4"))), None)
    ytxt = next(iter(sorted(src.rglob("youtube.txt"))), None)
    if not tracks and not loop:
        return {"ok": False, "message": "output has no stream_tracks/*.m4a and no stream_loop.mp4"}

    fp = fingerprint(tracks, loop)
    existing = list_batches(cfg)
    if not force:
        for b in existing:
            if b.manifest.get("fingerprint") == fp:
                return {"ok": True, "message": f"already have this output (batch {b.batch_id})",
                        "batch_id": b.batch_id, "new": False}

    good, rejected = [], []
    for t in tracks:
        info, why = probe_track(cfg, t)
        if info:
            good.append((t, info))
        else:
            rejected.append(f"{t.name}: {why}")
            log(f"rejected track {t.name}: {why}")
    loop_ok, loop_msgs, loop_info = (False, [], {})
    if loop:
        loop_ok, loop_msgs, loop_info = validate_loop(cfg, loop)
        for m in loop_msgs:
            log(f"loop video: {m}")
        if not loop_ok:
            rejected.append("stream_loop.mp4: " + "; ".join(loop_msgs))
    if not good and not loop_ok:
        return {"ok": False, "message": "nothing valid to import", "rejected": rejected}

    now = time.time()
    batch_id = time.strftime("%Y-%m-%d_%H%M%S", time.localtime(now)) + "_" + fp[:6]
    cfg.batches.mkdir(parents=True, exist_ok=True)
    tmp = cfg.batches / f".tmp-{batch_id}"
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "tracks").mkdir(parents=True)
    manifest = {
        "batch_id": batch_id, "imported_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)),
        "imported_ts": now, "source": source_label, "series": detect_series(ytxt),
        "fingerprint": fp, "tracks": [], "loop": None, "loop_ok": False,
        "loop_info": loop_info, "loop_messages": loop_msgs, "rejected": rejected,
    }
    for t, info in good:
        shutil.move(str(t), tmp / "tracks" / t.name)
        manifest["tracks"].append({"file": f"tracks/{t.name}", **info})
    if loop and loop_ok:
        shutil.move(str(loop), tmp / "stream_loop.mp4")
        manifest["loop"], manifest["loop_ok"] = "stream_loop.mp4", True
    if ytxt:
        shutil.copy2(ytxt, tmp / "youtube.txt")
        first = ytxt.read_text(errors="replace").strip().splitlines()
        manifest["title"] = first[0][:200] if first else ""
    write_json_atomic(tmp / "manifest.json", manifest)
    for p in [tmp, *tmp.rglob("*")]:
        os.chmod(p, 0o755 if p.is_dir() else 0o644)
    os.replace(tmp, cfg.batches / batch_id)
    log(f"imported batch {batch_id}: {len(good)} tracks, loop={'yes' if manifest['loop'] else 'no'}, "
        f"series={manifest['series']}, rejected={len(rejected)}")
    return {"ok": True, "message": f"imported {len(good)} tracks", "batch_id": batch_id,
            "new": True, "tracks_added": len(good), "rejected": rejected}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-dir", type=Path, help="import a local folder instead of Kaggle")
    ap.add_argument("--force", action="store_true", help="import even if identical to an existing batch")
    ap.add_argument("--keep-staging", action="store_true")
    args = ap.parse_args(argv)
    cfg = load_config()
    for d in (cfg.state_dir, cfg.staging, cfg.batches):
        d.mkdir(parents=True, exist_ok=True)

    lock = open(cfg.state_dir / "sync.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("another sync is already running")
        return 0

    started = time.time()
    prune(cfg)  # make room before downloading
    stage = cfg.staging / time.strftime("%Y%m%d-%H%M%S")
    try:
        if args.from_dir:
            src = args.from_dir
            if src.is_dir():
                # copy, never move the caller's files
                shutil.copytree(src, stage)
                result = import_dir(cfg, stage, f"dir:{src}", args.force)
            else:
                result = {"ok": False, "message": f"{src} is not a folder"}
        elif not cfg.kaggle_notebook:
            result = {"ok": False, "message": "KAGGLE_NOTEBOOK not configured (run: sudo coc setup)"}
        else:
            free = shutil.disk_usage(cfg.home).free / 1e9
            if free < cfg.min_free_gb:
                result = {"ok": False, "message": f"only {free:.1f} GB free disk, not downloading"}
            else:
                remote = remote_last_run(cfg)
                prev = read_json(cfg.last_sync_file, {}) or {}
                if (remote and not args.force and prev.get("ok") and list_batches(cfg)
                        and prev.get("remote_run_time") == remote):
                    result = {"ok": True, "new": False,
                              "message": f"no new notebook run on Kaggle (last run {remote})"}
                else:
                    stage.mkdir(parents=True)
                    ok, msg = download(cfg, stage)
                    if ok:
                        result = import_dir(cfg, stage,
                                            f"kaggle:{normalize_slug(cfg.kaggle_notebook)}", args.force)
                    else:
                        result = {"ok": False, "message": msg}
                result["remote_run_time"] = remote
    except Exception as e:  # keep a record for `coc status` no matter what
        result = {"ok": False, "message": f"unexpected error: {e!r}"}
    finally:
        if not args.keep_staging:
            shutil.rmtree(stage, ignore_errors=True)

    batches = list_batches(cfg)
    loop_target = update_current_loop(cfg, batches)
    result["pruned"] = prune(cfg)
    result["loop"] = loop_target
    result["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    result["took_s"] = round(time.time() - started, 1)
    prev = read_json(cfg.last_sync_file, {}) or {}
    if result["ok"]:
        result["last_success_at"] = result["finished_at"]
    elif prev.get("last_success_at"):
        result["last_success_at"] = prev["last_success_at"]
    write_json_atomic(cfg.last_sync_file, result)
    log(("sync OK: " if result["ok"] else "sync FAILED: ") + result["message"])
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
