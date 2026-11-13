"""Visuals: seamless loop video from a still, caption bars, compilation.mp4, thumbnail.png.

Loop (default 40 s, allowed 20-60 s, 1920x1080, 30 fps). Every effect is periodic in the loop
length T, so frame N == frame 0 and the loop is seamless:
  * slow Ken Burns: zoom 1.03->1.06->1.03 and a small elliptical pan (returns to start)
  * drifting mist: band-limited noise whose Fourier components each advance an integer number of
    cycles per loop (travelling, morphing fog), alpha-blended in paper white
  * gentle light flicker + "Migu glow" breathing on warm highlights of the painting
  * procedural particles drawn with Pillow: falling petals (study gold / work pink) or rain (sleep);
    positions are functions of a wrapped fall phase, so respawns happen off-screen
  * static xuan-paper grain + soft vignette
Frames are generated in Python and piped raw into ffmpeg once (libx264, GOP = 1 s, no B-frames).

compilation.mp4: one short caption variant per track is made by overlaying a caption PNG on the
pre-encoded loop (a few seconds each); the full-length video is then assembled with the concat
demuxer using inpoint/outpoint on keyframes and ``-c:v copy`` (no per-frame re-encode of the
1-2 h video), and muxed with the compilation audio as AAC 320k. With captions disabled it is a
plain ``-stream_loop -1`` + ``-c:v copy`` mux.
"""
from __future__ import annotations

import logging
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from . import fonts
from .common import ffmpeg_bin, media_duration, run_ffmpeg, series_name, series_spec

log = logging.getLogger("pipeline.visuals")

PALETTE = {"azurite": (47, 93, 138), "malachite": (62, 142, 126), "cinnabar": (178, 58, 46),
           "gold": (232, 182, 81), "paper": (239, 228, 204), "ink": (36, 33, 30)}

SERIES_FX = {
    "study": dict(particles="petals", petal_colors=[(232, 182, 81), (240, 205, 130), (245, 225, 170)],
                  mist=0.16, glow=0.10, n_particles=26),
    "work": dict(particles="petals", petal_colors=[(242, 198, 194), (248, 226, 222), (236, 176, 170)],
                 mist=0.10, glow=0.05, n_particles=30),
    "sleep": dict(particles="rain", petal_colors=[], mist=0.24, glow=0.04, n_particles=150),
}
MOOD_LINES = {"study": "where the lamps are flowers", "sleep": "where the tide falls asleep",
              "work": "tea at the edge of the sky"}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(img.convert("RGB"), size, Image.LANCZOS, centering=(0.5, 0.5))


def _paper_texture(w: int, h: int, rng: np.random.Generator) -> np.ndarray:
    """Static multiplicative paper grain + fibres + vignette, shape (h, w, 1)."""
    small = rng.standard_normal((h // 2, w // 2)).astype(np.float32)
    grain = np.asarray(Image.fromarray(((small * 0.5 + 0.5).clip(0, 1) * 255).astype(np.uint8))
                       .resize((w, h), Image.BILINEAR), dtype=np.float32) / 255 - 0.5
    fib = Image.new("L", (w, h), 128)
    d = ImageDraw.Draw(fib)
    for _ in range(w * h // 9000):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        ang, ln = rng.uniform(0, math.pi), rng.uniform(8, 40)
        d.line([(x, y), (x + ln * math.cos(ang), y + ln * math.sin(ang))],
               fill=int(rng.choice([110, 145])), width=1)
    fib = np.asarray(fib.filter(ImageFilter.GaussianBlur(0.6)), dtype=np.float32) / 255 - 0.5
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    vign = 1 - 0.10 * np.clip(r - 0.55, 0, None) ** 1.5
    return ((1 + 0.035 * grain + 0.05 * fib) * vign)[..., None].astype(np.float32)


def _glow_mask(img: Image.Image) -> Image.Image:
    a = np.asarray(img, dtype=np.float32) / 255
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    m = np.clip((lum - 0.5) * 3, 0, 1) * np.clip((r - b - 0.1) * 4, 0, 1) * (g > b)
    mi = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(max(4, img.width // 80)))
    arr = np.asarray(mi, dtype=np.float32)
    mx = arr.max()
    if mx > 0:
        mi = Image.fromarray((arr / mx * 255).astype(np.uint8))
    return mi


class MistField:
    """Band-limited noise; each Fourier component advances an integer number of cycles per loop."""

    def __init__(self, w: int, h: int, rng: np.random.Generator, scale: int = 8):
        self.gw, self.gh = max(16, w // scale), max(16, h // scale)
        kx = np.fft.fftfreq(self.gw) * self.gw  # cycles per frame width
        ky = np.fft.fftfreq(self.gh) * self.gh
        KX, KY = np.meshgrid(kx, ky)
        k = np.sqrt(KX ** 2 + (KY * 1.6) ** 2)  # flatter (wider than tall) mist banks
        band = (k >= 1.5) & (k <= 7.0)
        amp = np.where(band, 1.0 / np.maximum(k, 1) ** 1.2, 0.0)
        self.F = amp * (rng.standard_normal(k.shape) + 1j * rng.standard_normal(k.shape))
        m = np.sign(KX)
        m[m == 0] = rng.choice([-1, 1], size=int((m == 0).sum()))
        m[k < 2.5] *= rng.integers(0, 2, size=int((k < 2.5).sum()))  # some big banks stay put
        self.m = m
        self.std = float(np.real(np.fft.ifft2(self.F)).std()) + 1e-9

    def at(self, phase: float) -> np.ndarray:
        f = np.real(np.fft.ifft2(self.F * np.exp(2j * np.pi * self.m * phase))) / self.std
        return np.clip(f * 0.35 + 0.5, 0, 1).astype(np.float32)


def _petal_sprites(colors, rng) -> list[list[Image.Image]]:
    """sprites[c][angle_idx] RGBA, anti-aliased by 4x supersampling."""
    out = []
    for col in colors:
        frames = []
        base = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        d = ImageDraw.Draw(base)
        d.ellipse([20, 34, 76, 62], fill=col + (235,))
        d.ellipse([30, 40, 60, 54], fill=tuple(min(255, c + 15) for c in col) + (255,))
        base = base.filter(ImageFilter.GaussianBlur(2))
        for a in range(0, 360, 10):
            frames.append(base.rotate(a, resample=Image.BICUBIC).resize((36, 36), Image.LANCZOS))
        out.append(frames)
    return out


class Particles:
    def __init__(self, kind: str, w: int, h: int, n: int, colors, rng: np.random.Generator):
        self.kind, self.w, self.h = kind, w, h
        self.margin = 80
        self.htot = h + 2 * self.margin
        self.wtot = w + 2 * self.margin
        self.n = n if kind != "none" else 0
        self.x0 = rng.uniform(0, self.wtot, self.n)
        self.y0 = rng.uniform(0, self.htot, self.n)
        if kind == "petals":
            self.fall = rng.choice([1, 1, 2], self.n)            # loops of the screen per T
            self.sway_amp = rng.uniform(15, 55, self.n)
            self.sway_m = rng.integers(2, 6, self.n)              # sway cycles per T
            self.sway_ph = rng.uniform(0, 2 * np.pi, self.n)
            self.drift = rng.uniform(-60, 140, self.n)            # px across one fall
            self.rot0 = rng.integers(0, 36, self.n)
            self.rot_m = rng.choice([-3, -2, -1, 1, 2, 3], self.n)  # turns per T
            self.scale = rng.uniform(0.55, 1.15, self.n)
            self.alpha = rng.uniform(0.55, 0.95, self.n)
            self.col = rng.integers(0, max(1, len(colors)), self.n)
            self.sprites = _petal_sprites(colors, rng)
            self.scaled: dict = {}
        elif kind == "rain":
            self.fall = rng.integers(16, 26, self.n)
            self.len = rng.uniform(14, 30, self.n)
            self.alpha = rng.uniform(45, 95, self.n).astype(int)
            self.slant = 0.12

    def draw(self, layer: Image.Image, phase: float) -> None:
        if self.n == 0:
            return
        yw = (self.y0 + self.fall * self.htot * phase) % self.htot  # wrapped fall phase
        if self.kind == "rain":
            d = ImageDraw.Draw(layer)
            x = (self.x0 + self.slant * yw) % self.wtot - self.margin
            y = yw - self.margin
            for i in range(self.n):
                dx = self.slant * self.len[i]
                d.line([(x[i], y[i]), (x[i] + dx, y[i] + self.len[i])], fill=(215, 225, 235, int(self.alpha[i])), width=1)
            return
        x = (self.x0 + self.drift * yw / self.htot
             + self.sway_amp * np.sin(2 * np.pi * self.sway_m * phase + self.sway_ph)) % self.wtot - self.margin
        y = yw - self.margin
        rot = (self.rot0 + np.round(36 * self.rot_m * phase).astype(int)) % 36
        for i in range(self.n):
            key = (int(self.col[i]), int(rot[i]), round(float(self.scale[i]), 2), round(float(self.alpha[i]), 2))
            spr = self.scaled.get(key)
            if spr is None:
                s = self.sprites[key[0]][key[1]]
                sz = max(8, int(36 * key[2]))
                s = s.resize((sz, sz), Image.LANCZOS)
                a = s.getchannel("A").point(lambda v, k=key[3]: int(v * k))
                s.putalpha(a)
                spr = self.scaled[key] = s
            layer.alpha_composite(spr, (int(x[i]), int(y[i])))


# ---------------------------------------------------------------------------
# loop rendering
# ---------------------------------------------------------------------------
class LoopRenderer:
    """Per-frame compositing is done with Pillow's C ops on uint8 images (~60 ms/frame at 1080p)."""

    def __init__(self, scene: str | Path | Image.Image, seconds: int = 40, fps: int = 30,
                 size: tuple[int, int] = (1920, 1080), series: str = "study", particles: str | None = None,
                 seed: int = 0):
        self.series = series_name(series)
        fx = dict(SERIES_FX[self.series])
        if particles:
            fx["particles"] = particles
            if particles == "rain":
                fx["n_particles"] = 150
            elif particles == "petals" and not fx["petal_colors"]:
                fx["petal_colors"], fx["n_particles"] = SERIES_FX["study"]["petal_colors"], 26
        self.fx = fx
        self.T, self.fps = int(seconds), int(fps)
        self.N = self.T * self.fps
        self.w, self.h = size
        rng = np.random.default_rng(seed)
        img = scene if isinstance(scene, Image.Image) else Image.open(scene)
        self.m = 1.07
        base = cover(img, (int(self.w * self.m), int(self.h * self.m)))
        self.base = base
        # glow mask is smooth -> transform it at 1/4 resolution, then upscale (cheap)
        self.gq = 4
        self.glow = (_glow_mask(base).resize((base.width // self.gq, base.height // self.gq), Image.BILINEAR)
                     if fx["glow"] > 0 else None)
        paper = _paper_texture(self.w, self.h, rng)[..., 0]
        self.paper_gain = float(paper.max())
        self.paper = Image.fromarray(np.clip(paper / self.paper_gain * 255, 0, 255).astype(np.uint8)).convert("RGB")
        self.mist = MistField(self.w, self.h, rng) if fx["mist"] > 0 else None
        if self.mist is not None:
            yy = np.linspace(0, 1, self.mist.gh, dtype=np.float32)[:, None]
            self.mist_weight = (0.35 + 0.65 * np.exp(-((yy - 0.62) / 0.28) ** 2)).astype(np.float32)
        self.mist_solid = Image.new("RGB", size, tuple(min(255, int(c * 1.02)) for c in PALETTE["paper"]))
        self.particles = Particles(fx["particles"], self.w, self.h, fx["n_particles"], fx["petal_colors"], rng)
        self.flick_ph = rng.uniform(0, 2 * np.pi, 3)
        self.glow_col = (1.0, 0.78, 0.35)

    def _affine(self, phase: float):
        z = 1.03 + 0.03 * (1 - math.cos(2 * math.pi * phase)) / 2
        a = self.m / z
        bw, bh = self.base.size
        px = 0.010 * self.w * math.sin(2 * math.pi * phase)
        py = 0.006 * self.h * math.sin(4 * math.pi * phase)
        cx, cy = bw / 2 + px, bh / 2 + py
        return (a, 0, cx - a * self.w / 2, 0, a, cy - a * self.h / 2)

    def mist_mask(self, phase: float) -> Image.Image:
        mf = self.mist.at(phase) * self.mist_weight
        alpha = np.minimum((mf * mf) * (2.2 * self.fx["mist"]), 0.5)
        return Image.fromarray((alpha * 255).astype(np.uint8)).resize((self.w, self.h), Image.BILINEAR)

    def frame(self, k: int) -> Image.Image:
        phase = (k % self.N) / self.N
        aff = self._affine(phase)
        img = self.base.transform((self.w, self.h), Image.AFFINE, aff, resample=Image.BILINEAR)
        if self.glow is not None:
            amp = self.fx["glow"] * (0.5 + 0.5 * math.sin(2 * math.pi * 3 * phase + self.flick_ph[2]))
            q = self.gq
            ga = (aff[0], 0, aff[2] / q, 0, aff[4], aff[5] / q)
            g = self.glow.transform((self.w // q, self.h // q), Image.AFFINE, ga, resample=Image.BILINEAR)
            g = g.resize((self.w, self.h), Image.BILINEAR)
            glow = Image.merge("RGB", [g.point(lambda v, c=c: int(v * amp * c)) for c in self.glow_col])
            img = ImageChops.add(img, glow)
        flick = (1 + 0.012 * math.sin(2 * math.pi * 2 * phase + self.flick_ph[0])
                 + 0.007 * math.sin(2 * math.pi * 7 * phase + self.flick_ph[1])) * self.paper_gain
        img = ImageChops.multiply(img.point(lambda v: min(255, int(v * flick))), self.paper)
        if self.mist is not None:
            img = Image.composite(self.mist_solid, img, self.mist_mask(phase))
        if self.particles.n:
            out = img.convert("RGBA")
            layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
            self.particles.draw(layer, phase)
            out.alpha_composite(layer)
            img = out.convert("RGB")
        return img


X264 = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high", "-bf", "0", "-sc_threshold", "0"]


def _x264_args(fps: int, crf: int, preset: str) -> list[str]:
    return X264 + ["-preset", preset, "-crf", str(crf), "-g", str(fps), "-keyint_min", str(fps),
                   "-r", str(fps), "-movflags", "+faststart"]


def make_loop(scene: str | Path, out_mp4: str | Path, seconds: int = 40, fps: int = 30,
              size: tuple[int, int] = (1920, 1080), series: str = "study", particles: str | None = None,
              seed: int = 0, crf: int = 17, preset: str = "medium") -> Path:
    """Render a seamless loop (no audio). Returns the path."""
    if not 20 <= seconds <= 60:
        log.warning("loop length %ss outside the 20-60 s spec", seconds)
    r = LoopRenderer(scene, seconds, fps, size, series, particles, seed)
    out_mp4 = Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{r.w}x{r.h}", "-r", str(fps), "-i", "-", *_x264_args(fps, crf, preset), "-an", str(out_mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for k in range(r.N):
            proc.stdin.write(r.frame(k).tobytes())
            if k % (fps * 10) == 0:
                log.info("loop frame %d/%d", k, r.N)
        proc.stdin.close()
    except BrokenPipeError:
        pass
    err = proc.stderr.read().decode(errors="ignore")
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg loop encode failed: {err[-2000:]}")
    return out_mp4


# ---------------------------------------------------------------------------
# captions
# ---------------------------------------------------------------------------
def _text_w(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    b = draw.textbbox((0, 0), text, font=font)
    return b[2] - b[0]


def _draw_seal(size: int, char: str | None, fallback: str) -> Image.Image:
    seal = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(seal)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=max(2, size // 12), fill=PALETTE["cinnabar"] + (240,))
    inset = max(2, size // 12)
    d.rectangle([inset, inset, size - 1 - inset, size - 1 - inset], outline=(250, 236, 220, 220), width=max(1, size // 30))
    cjk = fonts.load("cjk", int(size * 0.68)) if char else None
    txt, font = (char, cjk) if cjk else (fallback, fonts.load("title", int(size * 0.55)))
    bb = d.textbbox((0, 0), txt, font=font)
    d.text(((size - (bb[2] - bb[0])) / 2 - bb[0], (size - (bb[3] - bb[1])) / 2 - bb[1]), txt,
           font=font, fill=(250, 240, 228, 255))
    # tiny notch (Sing's white ear) at bottom-right corner, per logo brief
    d.ellipse([size - size // 4, size - size // 4, size + size // 10, size + size // 10], fill=(0, 0, 0, 0))
    return seal


def render_caption(title_en: str, title_zh: str | None, series: str, size=(1920, 1080),
                   number: int | None = None) -> Image.Image:
    """Full-frame transparent RGBA with a small paper caption bar bottom-left."""
    w, h = size
    s = h / 1080
    ov = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    f_en = fonts.load("title", int(34 * s))
    f_zh = fonts.load("cjk", int(30 * s))
    f_no = fonts.load("ui", int(20 * s), weight="Medium")
    seal_sz = int(46 * s)
    pad = int(16 * s)
    prefix = f"{number:02d}" if number else ""
    zh = f"  ·  {title_zh}" if (title_zh and f_zh) else ""
    tw = _text_w(d, title_en, f_en) + (_text_w(d, zh, f_zh) if zh else 0)
    nw = _text_w(d, prefix, f_no) + int(12 * s) if prefix else 0
    bw = pad + seal_sz + pad + nw + tw + pad + int(6 * s)
    bh = seal_sz + 2 * int(10 * s)
    x0, y0 = int(48 * s), h - int(48 * s) - bh
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([x0 + 3, y0 + 5, x0 + bw + 3, y0 + bh + 5], radius=int(10 * s), fill=(0, 0, 0, 70))
    ov.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6 * s)))
    d = ImageDraw.Draw(ov)
    d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=int(10 * s), fill=PALETTE["paper"] + (215,),
                        outline=PALETTE["ink"] + (90,), width=max(1, int(1.5 * s)))
    sp = series_spec(series)
    ov.alpha_composite(_draw_seal(seal_sz, sp["seal"], sp["label"][0]), (x0 + pad, y0 + int(10 * s)))
    cx = x0 + pad + seal_sz + pad
    cy = y0 + bh / 2
    if prefix:
        bb = d.textbbox((0, 0), prefix, font=f_no)
        d.text((cx, cy - (bb[3] + bb[1]) / 2), prefix, font=f_no, fill=PALETTE["cinnabar"] + (255,))
        cx += nw
    bb = d.textbbox((0, 0), title_en, font=f_en)
    d.text((cx, cy - (bb[3] + bb[1]) / 2), title_en, font=f_en, fill=PALETTE["ink"] + (255,))
    cx += bb[2]
    if zh:
        bb = d.textbbox((0, 0), zh, font=f_zh)
        d.text((cx, cy - (bb[3] + bb[1]) / 2), zh, font=f_zh, fill=PALETTE["ink"] + (230,))
    return ov


def caption_variant(loop_mp4: Path, caption_png: Path, out_mp4: Path, fps: int = 30, crf: int = 18,
                    preset: str = "medium") -> Path:
    run_ffmpeg(["-i", loop_mp4, "-loop", "1", "-i", caption_png, "-filter_complex",
                "[0:v][1:v]overlay=0:0:shortest=1,format=yuv420p[v]", "-map", "[v]",
                *_x264_args(fps, crf, preset), "-an", out_mp4])
    return out_mp4


# ---------------------------------------------------------------------------
# full compilation video
# ---------------------------------------------------------------------------
def build_concat_list(segments: list[tuple[Path, float, float]], loop_s: int) -> list[str]:
    """segments: (variant_mp4, start_s, end_s) on the global timeline with integer-second bounds.
    Each segment continues the loop phase (t mod T) so the picture never jumps."""
    lines = ["ffconcat version 1.0"]
    for path, start, end in segments:
        t = start
        while t < end - 1e-6:
            p = t % loop_s
            chunk = min(loop_s - p, end - t)
            lines += [f"file '{Path(path).resolve().as_posix()}'", f"inpoint {p:.3f}", f"outpoint {p + chunk:.3f}"]
            t += chunk
    return lines


def render_compilation(loop_mp4: str | Path, audio: str | Path, out_mp4: str | Path, chapters: list[dict] | None,
                       series: str = "study", loop_s: int | None = None, fps: int = 30, captions: bool = True,
                       size=(1920, 1080), work_dir: str | Path | None = None, audio_bitrate: str = "320k") -> dict:
    loop_mp4, out_mp4 = Path(loop_mp4), Path(out_mp4)
    total = media_duration(audio)
    loop_s = int(round(loop_s or media_duration(loop_mp4)))
    work = Path(work_dir or tempfile.mkdtemp(prefix="coc_vid_"))
    work.mkdir(parents=True, exist_ok=True)
    aac = ["-c:a", "aac", "-b:a", audio_bitrate, "-ar", "48000"]
    if not captions or not chapters:
        run_ffmpeg(["-stream_loop", "-1", "-i", loop_mp4, "-i", audio, "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", *aac, "-t", f"{total:.3f}", "-movflags", "+faststart", out_mp4])
        return {"mode": "stream_loop_copy", "duration_s": total}
    bounds = [0] + [int(round(c["start_s"])) for c in chapters[1:]] + [int(math.ceil(total))]
    segs = []
    for i, c in enumerate(chapters):
        cap = render_caption(c["title_en"], c.get("title_zh"), series, size, number=c.get("n"))
        cap_png = work / f"cap_{i + 1:02d}.png"
        cap.save(cap_png)
        var = work / f"loop_cap_{i + 1:02d}.mp4"
        caption_variant(loop_mp4, cap_png, var, fps)
        if bounds[i + 1] > bounds[i]:
            segs.append((var, bounds[i], bounds[i + 1]))
    lst = work / "concat.txt"
    lst.write_text("\n".join(build_concat_list(segs, loop_s)) + "\n", encoding="utf-8")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", lst, "-i", audio, "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy", *aac, "-t", f"{total:.3f}", "-movflags", "+faststart", out_mp4])
    return {"mode": "concat_copy_captions", "duration_s": total, "segments": len(segs)}


# ---------------------------------------------------------------------------
# thumbnail (1280x720) — proposal A4
# ---------------------------------------------------------------------------
def _shadow_text(img: Image.Image, xy, text, font, fill, shadow=(20, 18, 16, 170), blur=4, offset=(2, 3)):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((xy[0] + offset[0], xy[1] + offset[1]), text, font=font, fill=shadow)
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))
    ImageDraw.Draw(img).text(xy, text, font=font, fill=fill)


def make_thumbnail(base_img: str | Path, out_png: str | Path, series: str = "study", mood: str | None = None,
                   creature: dict | None = None, size=(1280, 720), scroll_edges: bool = True) -> Path:
    series = series_name(series)
    w, h = size
    img = cover(Image.open(base_img), size).convert("RGBA")
    d = ImageDraw.Draw(img)
    if scroll_edges:  # ~6% handscroll edges left/right (fixed brand memory point)
        ew = int(w * 0.06)
        for side in (0, 1):
            x0 = 0 if side == 0 else w - ew
            band = Image.new("RGBA", (ew, h), PALETTE["paper"] + (255,))
            bd = ImageDraw.Draw(band)
            rod = int(ew * 0.28)
            rx = 0 if side == 0 else ew - rod
            for i in range(rod):
                t = i / max(1, rod - 1)
                shade = int(70 + 60 * math.sin(math.pi * t))
                bd.line([(rx + i, 0), (rx + i, h)], fill=(shade + 30, int(shade * 0.65) + 10, int(shade * 0.4), 255))
            for yy in range(0, h, 3):
                bd.point((int(ew * 0.5), yy), fill=(210, 196, 168, 255))
            img.alpha_composite(band, (x0, 0))
            sh = Image.new("RGBA", (24, h), (0, 0, 0, 0))
            sd = ImageDraw.Draw(sh)
            for i in range(24):
                a = int(90 * (1 - i / 24) ** 2)
                xi = i if side == 0 else 23 - i
                sd.line([(xi, 0), (xi, h)], fill=(0, 0, 0, a))
            img.alpha_composite(sh, (ew if side == 0 else w - ew - 24, 0))
    margin = int(w * 0.06) + 28
    spec = series_spec(series)
    seal_sz = 104
    sx, sy = w - margin - seal_sz, 34
    img.alpha_composite(_draw_seal(seal_sz, spec["seal"], spec["label"][0]), (sx, sy))
    f_lab = fonts.load("ui", 22, weight="SemiBold")
    lab = spec["label"]
    _shadow_text(img, (sx + (seal_sz - _text_w(d, lab, f_lab)) / 2, sy + seal_sz + 8), lab, f_lab, (250, 245, 235, 255))
    mood = mood or MOOD_LINES[series]
    f_mood = fonts.load("title", 58)
    _shadow_text(img, (margin, 40), mood, f_mood, (250, 244, 232, 255), blur=6)
    if creature:
        f_c = fonts.load("title", 44)
        no = creature.get("no")
        line = f"No.{int(no):02d}  {creature.get('en', '')}" if no is not None else creature.get("en", "")
        _shadow_text(img, (margin, h - 40 - 50), line, f_c, (250, 244, 232, 255), blur=6)
        f_zh = fonts.load("cjk", 44)
        if f_zh and creature.get("zh"):
            x = margin + _text_w(d, line + "  ", f_c)
            _shadow_text(img, (x, h - 40 - 52), creature["zh"], f_zh, (250, 244, 232, 255), blur=6)
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_png, optimize=True)
    return out_png


def placeholder_scene(out_png: str | Path, size=(1920, 1080), seed: int = 0) -> Path:
    """Minimal blue-green layered-mountain placeholder used when art/scene.png is missing."""
    rng = np.random.default_rng(seed)
    w, h = size
    img = Image.new("RGB", size, PALETTE["paper"])
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        c = tuple(int(a * (1 - t) + b * t) for a, b in zip((214, 222, 214), PALETTE["paper"]))
        d.line([(0, y), (w, y)], fill=c)
    layers = [(PALETTE["malachite"], 0.42, 140), (PALETTE["azurite"], 0.55, 110), ((52, 110, 98), 0.70, 80),
              ((40, 70, 96), 0.84, 60)]
    for col, base, amp in layers:
        ph = rng.uniform(0, 6.28, 3)
        pts = [(0, h)] + [(x, int(h * base - amp * (0.6 * math.sin(x / 260 + ph[0]) + 0.3 * math.sin(x / 97 + ph[1])
                                                    + 0.1 * math.sin(x / 31 + ph[2])))) for x in range(0, w + 20, 20)] + [(w, h)]
        d.polygon(pts, fill=col)
    for _ in range(30):
        x, y = rng.uniform(0, w), rng.uniform(h * 0.45, h * 0.9)
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=PALETTE["gold"])
    img = img.filter(ImageFilter.GaussianBlur(1.0))
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    return Path(out_png)
