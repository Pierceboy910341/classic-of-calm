"""`coc status`: one friendly screen about the stream (English + 繁中)."""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from .common import (human_bytes, human_duration, load_config, read_json,
                     validate_loop)
from .library import dir_size, list_batches, list_tracks

GREEN, RED, YELLOW, DIM, BOLD, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"


def color(on: bool):
    def c(code, text):
        return f"{code}{text}{RESET}" if on else text
    return c


def systemctl(*args) -> str:
    try:
        return subprocess.run(["systemctl", *args], capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def parse_iso(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        try:
            return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z").timestamp()
        except ValueError:
            return None


def ago(ts: float | None) -> str:
    if ts is None:
        return "?"
    return human_duration(time.time() - ts) + " ago"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cfg = load_config()
    c = color(sys.stdout.isatty() and "--no-color" not in argv)
    now = time.time()
    rows = []

    # ---- stream --------------------------------------------------------------
    st = read_json(cfg.streamer_state, {}) or {}
    active = systemctl("is-active", "coc-streamer.service")
    fresh = (parse_iso(st.get("updated_at")) or 0) > now - 15
    progressing = fresh and st.get("ffmpeg_alive") and (st.get("seconds_since_progress") or 99) < 15
    if progressing and str(st.get("status", "")).startswith("streaming"):
        state = c(GREEN, "● LIVE 直播中")
    elif active in ("active", "activating", "") and fresh:
        state = c(YELLOW, f"● {st.get('status', 'starting')}")
    else:
        state = c(RED, f"● DOWN 已停止 (service: {active or 'unknown'})")
    up = parse_iso(st.get("service_started_at"))
    conn = parse_iso(st.get("session_started_at"))
    extra = []
    if up and fresh:
        extra.append(f"up {human_duration(now - up)}")
    if conn and progressing:
        extra.append(f"this connection {human_duration(now - conn)}")
    rows.append(("Stream 直播", state + (f"  ({', '.join(extra)})" if extra else "")))

    np = st.get("now_playing") or read_json(cfg.now_playing_json, None)
    if np:
        dur = f", {human_duration(np.get('duration') or 0)} long" if np.get("duration") else ""
        rows.append(("Now playing 播放中", f"{c(BOLD, np.get('title', '?'))}  "
                     f"{c(DIM, '(started ' + ago(parse_iso(np.get('started_at'))) + dur + ')')}"))
    if fresh and st.get("ffmpeg_alive"):
        rows.append(("Health 健康", f"speed {st.get('speed') or '?'} · {st.get('bitrate') or '?'} · "
                     f"reconnects {st.get('unexpected_restarts', 0)} · tracks played {st.get('tracks_played', 0)}"))
    if st.get("loop"):
        loop = Path(st["loop"])
        rows.append(("Loop video 畫面", f"{loop.parent.name}/{loop.name}"))

    # ---- library -------------------------------------------------------------
    batches = list_batches(cfg)
    tracks = list_tracks(cfg, batches)
    hours = sum(t.duration for t in tracks) / 3600
    size = dir_size(cfg.library) if cfg.library.exists() else 0
    lib = f"{len(tracks)} tracks · {hours:.1f} h · {len(batches)} batches · {human_bytes(size)}"
    if batches:
        b = batches[-1]
        lib += c(DIM, f"  (newest: {b.batch_id}, {b.series})")
    if cfg.series not in ("", "all"):
        lib += c(DIM, f"  [series filter: {cfg.series}]")
    rows.append(("Library 曲庫", lib if tracks else c(YELLOW, "empty 尚無歌曲 — run: sudo coc sync")))

    # ---- sync ----------------------------------------------------------------
    ls = read_json(cfg.last_sync_file, None)
    if ls:
        mark = c(GREEN, "OK") if ls.get("ok") else c(RED, "FAILED 失敗")
        msg = f"{mark} {ago(parse_iso(ls.get('finished_at')))} — {ls.get('message', '')}"[:140]
        if not ls.get("ok") and ls.get("last_success_at"):
            msg += f" (last OK {ago(parse_iso(ls.get('last_success_at')))})"
        rows.append(("Last sync 同步", msg))
    else:
        rows.append(("Last sync 同步", c(YELLOW, "never 尚未同步")))
    nxt = systemctl("show", "coc-sync.timer", "-p", "NextElapseUSecRealtime", "--value")
    if nxt and nxt not in ("n/a", "0"):
        rows.append(("Next sync 下次", nxt))

    # ---- disk ----------------------------------------------------------------
    try:
        du = shutil.disk_usage(cfg.home if cfg.home.exists() else "/")
        pct = du.used / du.total * 100
        txt = f"{human_bytes(du.free)} free of {human_bytes(du.total)} ({pct:.0f}% used)"
        rows.append(("Disk 磁碟", c(RED, txt) if du.free < cfg.min_free_gb * 1e9 else txt))
    except OSError:
        pass

    err = st.get("last_error") if fresh else ""
    if err:
        rows.append(("Last error 錯誤", c(DIM, err[:160])))

    width = max(len(k) for k, _ in rows) + 2
    print(c(BOLD, "Classic of Calm — stream status 直播狀態") + c(DIM, "   " + time.strftime("%Y-%m-%d %H:%M %Z")))
    print("─" * 64)
    for k, v in rows:
        print(f"{k:<{width}}{v}")
    print("─" * 64)
    print(c(DIM, "sudo coc logs · sudo coc sync · sudo coc restart · sudo coc help"))
    return 0


def check_loop_main(argv=None) -> int:
    """`coc check-loop FILE`: is this loop video OK for -c:v copy streaming?"""
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: coc check-loop stream_loop.mp4")
        return 2
    cfg = load_config()
    rc = 0
    for f in argv:
        ok, msgs, info = validate_loop(cfg, Path(f))
        print(f"{f}: {'OK' if ok else 'NOT OK'}  {info}")
        for m in msgs:
            print("  -", m)
        rc |= 0 if ok else 1
    return rc


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check-loop":
        sys.exit(check_loop_main(sys.argv[2:]))
    sys.exit(main())
