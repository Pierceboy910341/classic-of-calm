"""Stable Audio 3 generation worker — run INSIDE the stable-audio-3 uv venv by notebook 01.

    <sa3_repo>/.venv/bin/python gen_stable_audio.py --jobs jobs.json --results results.jsonl \
        --deadline <epoch> [--model medium] [--fallback-model small-music]

Exit codes: 0 = finished, 2 = stopped by time budget, 3 = model unavailable,
            4 = gated / needs HF_TOKEN (skipped with a clear message).

API source (verified 2026-11-13 against github.com/Stability-AI/stable-audio-3 @ main):
  README.md, docs/workflows/inference.md, stable_audio_3/model.py, stable_audio_3/cli.py
  - StableAudioModel.from_pretrained(name, device=None, model_half=True)   # fp16 when half
      names: "medium" (1.4B, ≤380 s, CUDA), "small-music" (433M, ≤120 s, CPU-capable), …
      weights: hf_hub_download("stabilityai/stable-audio-3-medium" | "...-small-music")
  - model.generate(prompt, negative_prompt, duration, steps=8, cfg_scale=1, seed, batch_size)
      -> tensor [batch, ch, n];  sample rate = model.model.sample_rate (SAME AE: 44.1 kHz stereo)
  - negative_prompt / cfg_scale only have an effect on "-base" checkpoints.
UNVERIFIED (could not run a GPU or reach huggingface.co from the build environment):
  - whether the HF repos are gated (we pass HF_TOKEN if present and skip cleanly on 401/403);
  - "medium requires Flash Attention" (README). Flash-attn 2 does NOT support T4/P100, so we run
    on the repo's built-in PyTorch SDPA fallback. README warns broken attention can produce a
    "static glitch" sound → every output is checked (audio_check.suspect); if the first medium
    output looks like noise we switch to small-music automatically.
  - speed / VRAM of medium on a T4 (README: ~6.5 GB peak on H200).
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
import traceback

import kaggle_utils as ku

MAX_LEN = {"medium": 380.0, "medium-base": 380.0, "small-music": 120.0, "small-music-base": 120.0}
GATED_HINT = (
    "Stable Audio 3 的模型需要 Hugging Face 授權：\n"
    "  1) 到 https://huggingface.co/stabilityai/stable-audio-3-medium 登入並按「同意授權」\n"
    "  2) 到 https://huggingface.co/settings/tokens 建立 Read token\n"
    "  3) 在 Kaggle 右側 Add-ons → Secrets 新增 HF_TOKEN（貼上 token）並勾選啟用\n"
    "  這次先跳過 Stable Audio 3，ACE-Step 的歌曲不受影響。"
)


def log(msg: str) -> None:
    print(f"[SA3 {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _is_gated(err: str) -> bool:
    t = err.lower()
    return any(s in t for s in ("401", "403", "gated", "gatedrepo", "access to model",
                                "restricted", "unauthorized", "authentication", "repository not found"))


def load(name: str):
    from stable_audio_3 import StableAudioModel

    log(f"載入 Stable Audio 3「{name}」… 第一次會下載模型")
    return StableAudioModel.from_pretrained(name, device="cuda", model_half=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--deadline", type=float, required=True)
    ap.add_argument("--model", default="medium")
    ap.add_argument("--fallback-model", default="small-music")
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--cfg", type=float, default=1.0)
    args = ap.parse_args()

    with open(args.jobs, encoding="utf-8") as f:
        jobs = json.load(f)
    todo = [j for j in jobs if not os.path.exists(j["path"])]
    for j in jobs:
        if os.path.exists(j["path"]):
            ku.append_jsonl(args.results, {"status": "skipped_exists", "file": j["file"]})
    log(f"共 {len(jobs)} 個任務，已存在 {len(jobs) - len(todo)} 個，待生成 {len(todo)} 個")
    if not todo:
        return 0

    import torch

    if not torch.cuda.is_available():
        log("找不到 GPU！請在 Kaggle 右側 Settings → Accelerator 選 GPU。")
        return 3
    if not os.environ.get("HF_TOKEN"):
        log("（沒有設定 HF_TOKEN；如果模型需要授權會自動跳過）")

    model, variant = None, None
    for name in [args.model, args.fallback_model]:
        if not name or (variant and name == variant):
            continue
        try:
            model, variant = load(name), name
            break
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            log(f"載入 {name} 失敗：{err[:400]}")
            if _is_gated(err):
                log(GATED_HINT)
                return 4
            gc.collect()
            torch.cuda.empty_cache()
    if model is None:
        return 3
    log(f"模型就緒：{variant}，取樣率 {model.model.sample_rate} Hz")

    timer = ku.JobTimer(args.deadline, first_guess_s=180.0)
    checked_first = False
    for n, job in enumerate(todo, 1):
        if not timer.can_start_next():
            log(f"時間預算快用完（剩 {ku.fmt_secs(timer.remaining())}），安全停止。")
            return 2
        dur_req = min(float(job["duration"]), MAX_LEN.get(variant, 120.0))
        log(f"({n}/{len(todo)}) 生成 {job['file']}  seed={job['seed']}  {dur_req:.0f}s")
        t0 = time.time()
        try:
            with torch.inference_mode():
                audio = model.generate(
                    prompt=job["prompt"],
                    negative_prompt=job.get("negative") or None,
                    duration=dur_req,
                    steps=args.steps,
                    cfg_scale=args.cfg,
                    seed=int(job["seed"]),
                    batch_size=1,
                )
            dur = ku.write_wav_44k_stereo(audio[0] if audio.dim() == 3 else audio,
                                          int(model.model.sample_rate), job["path"])
            gen_s = time.time() - t0
            check = ku.noise_suspect(job["path"])
            if (not checked_first and check.get("suspect") and variant != args.fallback_model
                    and args.fallback_model):
                # Likely the flash-attn "static glitch" failure mode → switch model, redo this job.
                log(f"  ⚠️ {variant} 的第一首聽起來像雜訊（可能是 T4 不支援 flash-attn），改用 {args.fallback_model}")
                os.remove(job["path"])
                del model
                gc.collect()
                torch.cuda.empty_cache()
                try:
                    model, variant = load(args.fallback_model), args.fallback_model
                except Exception as le:
                    log(f"備援模型也載入失敗：{le}")
                    return 3
                checked_first = True
                dur_req = min(float(job["duration"]), MAX_LEN.get(variant, 120.0))
                t0 = time.time()
                with torch.inference_mode():
                    audio = model.generate(prompt=job["prompt"], negative_prompt=job.get("negative") or None,
                                           duration=dur_req, steps=args.steps, cfg_scale=args.cfg,
                                           seed=int(job["seed"]), batch_size=1)
                dur = ku.write_wav_44k_stereo(audio[0] if audio.dim() == 3 else audio,
                                              int(model.model.sample_rate), job["path"])
                gen_s = time.time() - t0
                check = ku.noise_suspect(job["path"])
            checked_first = True
            entry = ku.manifest_entry(job, gen_s, dur, f"stable-audio-3-{variant}",
                                      extra={"negative_applied": variant.endswith("-base"),
                                             "duration_clamped": dur_req < float(job["duration"]),
                                             "audio_check": check})
            ku.append_jsonl(args.results, {"status": "ok", "entry": entry})
            timer.add(gen_s)
            warn = "  ⚠️ 疑似雜訊/靜音" if check.get("suspect") else ""
            log(f"  ✓ 完成 {dur:.0f}s 音檔，花 {gen_s:.0f}s{warn}")
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            log(f"  ✗ 失敗：{err[:400]}")
            ku.append_jsonl(args.results, {"status": "failed", "file": job["file"],
                                           "track_id": job["track_id"], "model": job["model"],
                                           "take": job["take"], "error": err[:2000],
                                           "trace": traceback.format_exc()[-3000:]})
            timer.add(time.time() - t0)
            gc.collect()
            torch.cuda.empty_cache()
    return 0


if __name__ == "__main__":
    sys.exit(main())
