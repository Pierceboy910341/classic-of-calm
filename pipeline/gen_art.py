"""Generate weekly artwork with the Gemini image API (Classic of Calm).

Usage (from the repo root):
    python pipeline/gen_art.py weekly/2026-W47                 # scene + thumbnail
    python pipeline/gen_art.py weekly/2026-W47 --only scene --n 3
    python pipeline/gen_art.py weekly/2026-W47 --dry-run       # print requests, no API call

Reads  weekly/<WEEK>/plan.json  -> art.scene_prompt, art.thumbnail_prompt
Writes weekly/<WEEK>/art/scene.png      (1920x1080, base for the loop animation)
       weekly/<WEEK>/art/thumbnail.png  (1280x720, text/seal are added later by the pipeline)
       weekly/<WEEK>/art/gen_log.json   (model, prompt hash, refs, time; never the key)
With --n > 1 it writes scene_v1.png, scene_v2.png ... instead, for the art director to choose.

API key
-------
* Never put the key in the repo, a commit, a log or a chat message.
* Preferred in Claude cloud sessions: the key is saved as an environment *network secret*
  for host generativelanguage.googleapis.com, header `x-goog-api-key`. The proxy injects it,
  so this script only sends a placeholder. Nothing secret exists inside the sandbox.
* Otherwise set the environment variable GEMINI_API_KEY (environment settings, not a file).

Model
-----
Checked 2026-11-13 by web search (ai.google.dev itself was not reachable from the build
session, so re-check if calls fail): Google's image-generation docs list
"Nano Banana 2" = `gemini-3.1-flash-image` (some pages still show `-preview`), and the
legacy `gemini-2.5-flash-image` (announced retirement 2027-03-15). This script tries them
in that order and falls back when a model id is rejected. Override with --model or
GEMINI_IMAGE_MODEL.

Standard library only (urllib). Pillow is used for resizing if installed.
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import hashlib
import json
import mimetypes
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL_FALLBACKS = [
    "gemini-3.1-flash-image",
    "gemini-3.1-flash-image-preview",
    "gemini-2.5-flash-image",
]
PLACEHOLDER_KEY = "injected-by-environment-proxy"

# Gemini has no negative-prompt field, so the shared negative list is appended as plain
# "Avoid:" text. Source: docs/02-brand-proposals.md section A6 (+ Dandan face rule).
AVOID = (
    "Avoid: Japanese style, ukiyo-e, torii gate, yokai, kitsune mask, anime, chibi, raccoon, "
    "girl with headphones at a window, Guan Shan Hai illustration style, modern game character "
    "design, 3D render, photorealism, neon, yin-yang symbol, fake Chinese characters, any text, "
    "letters, logos, watermark, signature, extra limbs, a face on the faceless red spirit."
)

TARGETS = {
    # name: (plan key, aspect ratio, final size)
    "scene": ("scene_prompt", "16:9", (1920, 1080)),
    "thumbnail": ("thumbnail_prompt", "16:9", (1280, 720)),
}

REPO = Path(__file__).resolve().parents[1]
DEFAULT_REF_DIR = REPO / "brand" / "refs"  # approved character / style reference images


def _ssl_context() -> ssl.SSLContext:
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        path = os.environ.get(var)
        if path and Path(path).is_file():
            return ssl.create_default_context(cafile=path)
    return ssl.create_default_context()


def _api_key() -> tuple[str, bool]:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key, False
    return PLACEHOLDER_KEY, True


def _ref_parts(paths: list[Path]) -> list[dict]:
    parts = []
    for p in paths:
        mime = mimetypes.guess_type(p.name)[0] or "image/png"
        parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(p.read_bytes()).decode()}})
    return parts


def _build_body(prompt: str, aspect: str, refs: list[Path], image_size: str | None) -> dict:
    text = prompt.strip()
    if refs:
        text = (
            "Use the attached reference image(s) only to keep the art style and the recurring "
            "characters (Sing; and Dandan if present) consistent. Do not copy their composition.\n\n"
            + text
        )
    text += "\n\n" + AVOID
    image_config: dict = {"aspectRatio": aspect}
    if image_size:
        image_config["imageSize"] = image_size
    return {
        "contents": [{"role": "user", "parts": [{"text": text}] + _ref_parts(refs)}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"], "imageConfig": image_config},
    }


def _post(model: str, body: dict, key: str, timeout: int = 180) -> dict:
    req = urllib.request.Request(
        f"{API_ROOT}/{model}:generateContent",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        return json.loads(resp.read().decode())


def _extract_image(resp: dict) -> bytes | None:
    for cand in resp.get("candidates", []) or []:
        for part in (cand.get("content") or {}).get("parts", []) or []:
            blob = part.get("inlineData") or part.get("inline_data")
            if blob and blob.get("data"):
                return base64.b64decode(blob["data"])
    return None


def generate(prompt: str, aspect: str, refs: list[Path], models: list[str], image_size: str | None) -> tuple[bytes, str]:
    key, via_proxy = _api_key()
    body = _build_body(prompt, aspect, refs, image_size)
    last_err = "no model tried"
    for model in models:
        for attempt in range(3):
            try:
                resp = _post(model, body, key)
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:400]
                if e.code in (401, 403):
                    hint = (
                        "No GEMINI_API_KEY and no proxy-injected credential for generativelanguage.googleapis.com."
                        if via_proxy else "GEMINI_API_KEY was rejected."
                    )
                    raise SystemExit(f"[gen_art] auth error {e.code}: {hint}") from None
                if e.code in (400, 404) and ("not found" in detail.lower() or "not supported" in detail.lower()):
                    last_err = f"{model}: {e.code} {detail}"
                    print(f"[gen_art] model {model} unavailable, trying next", file=sys.stderr)
                    break
                if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(10 * (attempt + 1))
                    continue
                raise SystemExit(f"[gen_art] HTTP {e.code} from {model}: {detail}") from None
            except urllib.error.URLError as e:
                if attempt < 2:
                    time.sleep(5)
                    continue
                raise SystemExit(f"[gen_art] network error: {e.reason}") from None
            img = _extract_image(resp)
            if img:
                return img, model
            last_err = f"{model}: no image in response ({json.dumps(resp)[:300]})"
            if attempt < 2:
                continue
            break
    raise SystemExit(f"[gen_art] failed: {last_err}")


def _fit(raw: bytes, size: tuple[int, int], out: Path) -> tuple[int, int] | None:
    """Cover-crop to the exact size with Pillow; save raw bytes if Pillow is missing."""
    from io import BytesIO

    try:
        from PIL import Image, ImageOps
    except ImportError:
        out.write_bytes(raw)
        print("[gen_art] Pillow not installed: saved original size", file=sys.stderr)
        return None

    img = Image.open(BytesIO(raw)).convert("RGB")
    orig = img.size
    img = ImageOps.fit(img, size, method=Image.LANCZOS)
    img.save(out, "PNG")
    return orig


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("week_dir", type=Path, help="e.g. weekly/2026-W47")
    ap.add_argument("--only", choices=sorted(TARGETS), help="generate just one image type")
    ap.add_argument("--n", type=int, default=1, help="variants per image (>1 writes *_vN.png)")
    ap.add_argument("--model", help="force one model id")
    ap.add_argument("--image-size", default="2K", help="1K | 2K | 4K (ignored by some models); '' to omit")
    ap.add_argument("--ref", type=Path, action="append", default=[], help="extra reference image (repeatable)")
    ap.add_argument("--no-refs", action="store_true", help=f"do not auto-attach {DEFAULT_REF_DIR.relative_to(REPO)}/*")
    ap.add_argument("--dry-run", action="store_true", help="print what would be sent and exit")
    args = ap.parse_args(argv)

    plan_path = args.week_dir / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    art = plan.get("art") or {}
    out_dir = args.week_dir / "art"
    out_dir.mkdir(parents=True, exist_ok=True)

    refs = list(args.ref)
    if not args.no_refs and DEFAULT_REF_DIR.is_dir():
        refs += sorted(p for p in DEFAULT_REF_DIR.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))
    refs = refs[:4]  # keep requests small; the style lock text does most of the work

    models = [args.model] if args.model else (
        [os.environ["GEMINI_IMAGE_MODEL"]] if os.environ.get("GEMINI_IMAGE_MODEL") else MODEL_FALLBACKS
    )
    log_path = out_dir / "gen_log.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else []

    for name in ([args.only] if args.only else list(TARGETS)):
        key, aspect, size = TARGETS[name]
        prompt = art.get(key, "").strip()
        if not prompt:
            print(f"[gen_art] plan.json art.{key} is empty, skipping {name}", file=sys.stderr)
            continue
        if args.dry_run:
            body = _build_body(prompt, aspect, [], args.image_size or None)
            print(f"--- {name} -> models {models}, refs {[str(r) for r in refs]}")
            print(json.dumps(body, ensure_ascii=False, indent=2)[:3000])
            continue
        for i in range(1, args.n + 1):
            raw, used = generate(prompt, aspect, refs, models, args.image_size or None)
            out = out_dir / (f"{name}.png" if args.n == 1 else f"{name}_v{i}.png")
            orig = _fit(raw, size, out)
            entry = {
                "file": out.name,
                "model": used,
                "prompt_sha1": hashlib.sha1(prompt.encode()).hexdigest()[:12],
                "refs": [str(r.relative_to(REPO)) if r.is_absolute() and REPO in r.parents else str(r) for r in refs],
                "source_size": list(orig) if orig else None,
                "created": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            }
            log.append(entry)
            print(f"[gen_art] wrote {out} ({used})")
    if not args.dry_run:
        log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
