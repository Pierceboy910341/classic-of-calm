"""Inspect a recorded FLV: timestamp continuity, keyframe spacing, silences.

    python3 tests/check_flv.py recording.flv [--expect-gap 2.0]

Exit 1 if video/audio timestamps jump or go backwards, keyframes are > 2.1 s
apart, or (with --expect-gap) a silence is not about the expected gap length.
"""
import argparse
import re
import subprocess
import sys


def packets(f, sel):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", sel, "-show_entries",
                          "packet=dts_time,flags", "-of", "csv=p=0", f],
                         capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        p = line.split(",")
        try:
            rows.append((float(p[0]), p[1] if len(p) > 1 else ""))
        except ValueError:
            pass
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--expect-gap", type=float)
    a = ap.parse_args()
    bad = False
    for sel, tol in (("v", 0.1), ("a", 0.05)):
        r = packets(a.file, sel)
        if not r:
            print(f"{sel}: NO PACKETS")
            bad = True
            continue
        jumps = [(round(x[0], 3), round(y[0] - x[0], 3)) for x, y in zip(r, r[1:])
                 if y[0] - x[0] > tol or y[0] - x[0] <= 0]
        line = f"{sel}: packets={len(r)} span={r[0][0]:.2f}-{r[-1][0]:.2f}s jumps={len(jumps)} {jumps[:5]}"
        if sel == "v":
            kf = [x[0] for x in r if "K" in x[1]]
            kgap = max((y - x for x, y in zip(kf, kf[1:])), default=0)
            line += f" max_keyframe_gap={kgap:.2f}s"
            bad |= kgap > 2.1
        bad |= bool(jumps)
        print(line)
    err = subprocess.run(["ffmpeg", "-v", "info", "-nostats", "-i", a.file, "-map", "0:a",
                          "-af", "silencedetect=n=-50dB:d=0.3", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    sil = [(float(m.group(1)), float(m.group(2)))
           for m in re.finditer(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", err)]
    print(f"silences: {len(sil)} " + ", ".join(f"{d:.2f}s@{e:.1f}" for e, d in sil))
    if a.expect_gap is not None:
        # the last silence may be cut by the end of the recording
        for e, d in sil[:-1]:
            if abs(d - a.expect_gap) > 0.25:
                print(f"  unexpected silence {d:.2f}s ending at {e:.1f}s")
                bad = True
    print("RESULT:", "FAIL" if bad else "OK")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
