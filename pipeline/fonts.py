"""Font lookup with optional download of the brand's OFL fonts (proposal A, A3).

Brand fonts (all SIL Open Font License, free for commercial use, from Google Fonts):
  * Cormorant Garamond  — English titles      https://fonts.google.com/specimen/Cormorant+Garamond
  * Inter               — small UI text       https://fonts.google.com/specimen/Inter
  * Ma Shan Zheng 馬善政 — Chinese seal/落款   https://fonts.google.com/specimen/Ma+Shan+Zheng

How to get them
  1. Automatic: with internet (Kaggle "Internet ON") the first call downloads the .ttf files from
     the google/fonts GitHub repo into ``$COC_FONT_DIR`` (default ``~/.cache/classic-of-calm/fonts``).
     Set ``COC_FONT_DOWNLOAD=0`` to disable.
  2. Manual: download the three families from the links above and put the .ttf files into
     ``fonts/`` at the repo root (or ``$COC_FONT_DIR``). Keep the OFL.txt that ships with them.
Fallback when nothing is available: DejaVu Serif/Sans (Latin only). Chinese text is then only
drawn if a system CJK font (Noto CJK, WenQuanYi, Droid Sans Fallback) exists; otherwise the
renderer silently skips the Chinese characters (never draws tofu boxes).
"""
from __future__ import annotations

import glob
import logging
import os
import urllib.request
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

log = logging.getLogger("pipeline.fonts")

_GF = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
SOURCES = {
    "title": [("CormorantGaramond[wght].ttf", _GF + "cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf"),
              ("CormorantGaramond-SemiBold.ttf", _GF + "cormorantgaramond/CormorantGaramond-SemiBold.ttf")],
    "ui": [("Inter[opsz,wght].ttf", _GF + "inter/Inter%5Bopsz%2Cwght%5D.ttf")],
    "cjk": [("MaShanZheng-Regular.ttf", _GF + "mashanzheng/MaShanZheng-Regular.ttf")],
}
FALLBACK = {
    "title": ["DejaVuSerif-Bold.ttf", "DejaVuSerif.ttf", "LiberationSerif-Bold.ttf"],
    "ui": ["DejaVuSans.ttf", "LiberationSans-Regular.ttf"],
}
CJK_SYSTEM = ["/usr/share/fonts/**/NotoSerifCJK*.tt[cf]", "/usr/share/fonts/**/NotoSansCJK*.tt[cf]",
              "/usr/share/fonts/**/wqy*.tt[cf]", "/usr/share/fonts/**/DroidSansFallback*.ttf",
              "/System/Library/Fonts/PingFang.ttc", "C:/Windows/Fonts/msjh.ttc"]


def font_dirs() -> list[Path]:
    dirs = []
    if os.environ.get("COC_FONT_DIR"):
        dirs.append(Path(os.environ["COC_FONT_DIR"]))
    dirs.append(Path(__file__).resolve().parent.parent / "fonts")
    dirs.append(Path.home() / ".cache" / "classic-of-calm" / "fonts")
    return dirs


def _download(name: str, url: str) -> Path | None:
    if os.environ.get("COC_FONT_DOWNLOAD", "1") == "0":
        return None
    dst = font_dirs()[0 if os.environ.get("COC_FONT_DIR") else -1] / name
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=20) as r:
            data = r.read()
        if len(data) < 10000:
            return None
        dst.write_bytes(data)
        log.info("downloaded font %s", name)
        return dst
    except Exception as exc:
        log.info("font download failed (%s): %s — using fallback", name, exc)
        return None


@lru_cache(maxsize=None)
def font_path(kind: str) -> str | None:
    for name, url in SOURCES.get(kind, []):
        for d in font_dirs():
            if (d / name).exists():
                return str(d / name)
    for name, url in SOURCES.get(kind, []):
        p = _download(name, url)
        if p:
            return str(p)
    if kind == "cjk":
        for pat in CJK_SYSTEM:
            hits = sorted(glob.glob(pat, recursive=True))
            if hits:
                return hits[0]
        return None
    for name in FALLBACK.get(kind, []):
        hits = glob.glob(f"/usr/share/fonts/**/{name}", recursive=True)
        if hits:
            return hits[0]
    return None


def load(kind: str, size: int, weight: str | None = "SemiBold") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    p = font_path(kind)
    if not p:
        if kind == "cjk":
            return None  # caller skips CJK text
        return ImageFont.load_default(size=size)
    f = ImageFont.truetype(p, size)
    if weight and "[" in Path(p).name:  # variable font: pick a named instance if possible
        try:
            f.set_variation_by_name(weight)
        except Exception:
            pass
    return f


def has_cjk() -> bool:
    return font_path("cjk") is not None
