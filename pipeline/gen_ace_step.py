"""ACE-Step 1.5 generation worker — run INSIDE the ACE-Step uv venv by notebook 01.

    <ace_repo>/.venv/bin/python gen_ace_step.py --jobs jobs.json --results results.jsonl \
        --deadline <epoch> --ace-dir <ace_repo> [--dit acestep-v15-xl-turbo] ...

Writes one JSON line per job to --results ({"status": "ok"|"failed"|"skipped_exists", ...}).
Exit codes: 0 = finished (maybe with per-track failures), 2 = stopped by time budget,
            3 = model could not be loaded at all.

API source (verified 2026-11-13 against github.com/ace-step/ACE-Step-1.5 @ main):
  docs/en/INFERENCE.md, acestep/inference.py, acestep/llm_inference.py,
  acestep/core/generation/handler/init_service_orchestrator.py
  - AceStepHandler().initialize_service(project_root, config_path, device, use_flash_attention,
        compile_model, offload_to_cpu, offload_dit_to_cpu, quantization, prefer_source, ...)
        -> (status_msg, success); pre-Ampere CUDA (T4/P100) automatically uses float16.
  - generate_music(dit_handler, llm_handler_or_None, GenerationParams, GenerationConfig, save_dir)
        -> GenerationResult(success, error, audios=[{"tensor": [ch, n] float32 CPU, "sample_rate": 48000, ...}])
  - XL DiT ~9 GB bf16/fp16; "≥12 GB with offload + quantization". Kaggle T4 = 15 GB → marginal tier.
UNVERIFIED (could not run a GPU here):
  - actual XL-turbo speed / peak VRAM on a T4 with offload_to_cpu + int8_weight_only + compile;
  - whether torchao int8 + torch.compile works on Turing (sm_75) — we fall back automatically;
  - the DiT has no negative-prompt input; `negative` is only used as lm_negative_prompt when --use-lm.
"""
from __future__ import annotations

import argparse
import dataclasses
import gc
import json
import os
import shutil
import sys
import tempfile
import time
import traceback

import kaggle_utils as ku


def log(msg: str) -> None:
    print(f"[ACE {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _filter_kwargs(cls, kwargs):
    """Drop kwargs a (future/older) ACE-Step version doesn't know, instead of crashing."""
    names = {f.name for f in dataclasses.fields(cls)}
    unknown = sorted(k for k in kwargs if k not in names)
    if unknown:
        log(f"注意：此版 ACE-Step 不支援參數 {unknown}，已略過")
    return {k: v for k, v in kwargs.items() if k in names}


def _is_oom(text: str) -> bool:
    t = (text or "").lower()
    return "out of memory" in t or "outofmemory" in t or "cuda oom" in t


class AceRunner:
    def __init__(self, args):
        self.args = args
        self.dit = None
        self.llm = None
        self.variant = None

    # -- loading ---------------------------------------------------------------
    def free(self):
        import torch
        self.dit = None
        self.llm = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def load(self, dit_name: str) -> bool:
        from acestep.handler import AceStepHandler

        self.free()
        # Try the memory-saving recipe first, then progressively simpler ones.
        recipes = [
            dict(offload_to_cpu=True, offload_dit_to_cpu=False,
                 quantization="int8_weight_only", compile_model=True),
            dict(offload_to_cpu=True, offload_dit_to_cpu=True,
                 quantization="int8_weight_only", compile_model=True),
            dict(offload_to_cpu=True, offload_dit_to_cpu=True,
                 quantization=None, compile_model=False),
        ]
        if self.args.no_quant:
            recipes = recipes[2:]
        for i, r in enumerate(recipes, 1):
            log(f"載入 {dit_name}（嘗試 {i}/{len(recipes)}：{r}）… 第一次會下載模型，約 5–15 分鐘")
            try:
                handler = AceStepHandler()
                msg, ok = handler.initialize_service(
                    project_root=self.args.ace_dir,
                    config_path=dit_name,
                    device="cuda",
                    use_flash_attention=False,  # flash-attn 2 does not support T4/P100
                    prefer_source="huggingface",
                    **r,
                )
                if ok:
                    self.dit = handler
                    self.variant = dit_name
                    log(f"模型就緒：{dit_name}")
                    if self.args.use_lm:
                        self._load_lm()
                    return True
                log(f"載入失敗：{str(msg)[:500]}")
            except Exception as e:
                log(f"載入例外：{type(e).__name__}: {str(e)[:500]}")
            self.free()
        return False

    def _load_lm(self):
        try:
            from acestep.llm_inference import LLMHandler

            llm = LLMHandler()
            msg, ok = llm.initialize(
                checkpoint_dir=os.path.join(self.args.ace_dir, "checkpoints"),
                lm_model_path=self.args.lm_model,
                backend="pt",  # vLLM KV cache is too hungry next to an offloaded XL DiT on 15 GB
                device="cuda",
                offload_to_cpu=True,
            )
            if ok:
                self.llm = llm
                log(f"語言模型（LM）就緒：{self.args.lm_model}")
            else:
                log(f"LM 載入失敗，改用 DiT-only：{str(msg)[:300]}")
        except Exception as e:  # LM is optional
            log(f"LM 載入例外，改用 DiT-only：{e}")
            self.llm = None

    # -- generation ------------------------------------------------------------
    def generate(self, job, out_tmp_dir):
        from acestep.inference import GenerationConfig, GenerationParams, generate_music

        turbo = "turbo" in (self.variant or "")
        use_lm = self.llm is not None
        p = dict(
            task_type="text2music",
            caption=job["prompt"],
            lyrics=job.get("lyrics") or "[Instrumental]",
            instrumental=True,
            vocal_language="unknown",
            bpm=job.get("bpm"),
            keyscale=job.get("keyscale") or "",
            timesignature="4",
            duration=float(job["duration"]),
            inference_steps=self.args.steps if self.args.steps else (8 if turbo else 50),
            seed=int(job["seed"]),
            shift=3.0 if turbo else 1.0,          # INFERENCE.md: set shift=3.0 for turbo
            guidance_scale=self.args.guidance,    # ignored (forced 1.0) by turbo models
            thinking=use_lm,
            use_cot_metas=False,                  # we already give bpm/key/duration
            use_cot_caption=False,                # keep our caption verbatim (logged in manifest)
            use_cot_language=False,
        )
        if use_lm and job.get("negative"):
            p["lm_negative_prompt"] = job["negative"]
        params = GenerationParams(**_filter_kwargs(GenerationParams, p))
        config = GenerationConfig(**_filter_kwargs(GenerationConfig, dict(
            batch_size=1, use_random_seed=False, seeds=[int(job["seed"])], audio_format="wav")))
        result = generate_music(self.dit, self.llm, params, config, save_dir=out_tmp_dir)
        if not result.success or not result.audios:
            raise RuntimeError(f"ACE-Step 生成失敗：{result.error or result.status_message}")
        a = result.audios[0]
        tensor, sr = a.get("tensor"), int(a.get("sample_rate") or 48000)
        if tensor is None and a.get("path"):
            import soundfile as sf
            data, sr = sf.read(a["path"], dtype="float32", always_2d=True)
            tensor = data.T
        return tensor, sr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--deadline", type=float, required=True)
    ap.add_argument("--ace-dir", required=True)
    ap.add_argument("--dit", default="acestep-v15-xl-turbo")
    ap.add_argument("--fallback-dit", default="acestep-v15-turbo")
    ap.add_argument("--use-lm", action="store_true")
    ap.add_argument("--lm-model", default="acestep-5Hz-lm-0.6B")
    ap.add_argument("--steps", type=int, default=0, help="0 = model default (turbo 8, sft/base 50)")
    ap.add_argument("--guidance", type=float, default=7.0)
    ap.add_argument("--no-quant", action="store_true")
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

    sys.path.insert(0, args.ace_dir)
    os.chdir(args.ace_dir)
    import torch

    if not torch.cuda.is_available():
        log("找不到 GPU！請在 Kaggle 右側 Settings → Accelerator 選 GPU T4 x2（或 T4）。")
        return 3
    log(f"GPU：{torch.cuda.get_device_name(0)}，VRAM {torch.cuda.get_device_properties(0).total_memory / 2**30:.1f} GB")

    runner = AceRunner(args)
    if not runner.load(args.dit):
        if args.fallback_dit and args.fallback_dit != args.dit:
            log(f"{args.dit} 載入失敗，改用備援模型 {args.fallback_dit}")
            if not runner.load(args.fallback_dit):
                return 3
        else:
            return 3

    timer = ku.JobTimer(args.deadline, first_guess_s=240.0)
    tmp_dir = tempfile.mkdtemp(prefix="ace_out_")
    for n, job in enumerate(todo, 1):
        if not timer.can_start_next():
            log(f"時間預算快用完（剩 {ku.fmt_secs(timer.remaining())}），安全停止。")
            return 2
        log(f"({n}/{len(todo)}) 生成 {job['file']}  seed={job['seed']}  {job['duration']:.0f}s")
        t0 = time.time()
        attempt = 0
        while True:
            attempt += 1
            try:
                tensor, sr = runner.generate(job, tmp_dir)
                dur = ku.write_wav_44k_stereo(tensor, sr, job["path"])
                gen_s = time.time() - t0
                check = ku.noise_suspect(job["path"])
                entry = ku.manifest_entry(job, gen_s, dur, runner.variant,
                                          extra={"lm_used": runner.llm is not None,
                                                 "negative_applied": runner.llm is not None,
                                                 "audio_check": check})
                ku.append_jsonl(args.results, {"status": "ok", "entry": entry})
                timer.add(gen_s)
                warn = "  ⚠️ 疑似雜訊/靜音" if check.get("suspect") else ""
                log(f"  ✓ 完成 {dur:.0f}s 音檔，花 {gen_s:.0f}s{warn}")
                break
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                is_oom = _is_oom(err) or isinstance(e, getattr(torch.cuda, "OutOfMemoryError", ()))
                if is_oom and attempt == 1 and runner.variant != args.fallback_dit and args.fallback_dit:
                    log(f"  VRAM 不足（{runner.variant}），改用較小的 {args.fallback_dit} 後重試")
                    if runner.load(args.fallback_dit):
                        continue
                log(f"  ✗ 失敗：{err[:400]}")
                ku.append_jsonl(args.results, {"status": "failed", "file": job["file"],
                                               "track_id": job["track_id"], "model": job["model"],
                                               "take": job["take"], "error": err[:2000],
                                               "trace": traceback.format_exc()[-3000:]})
                timer.add(time.time() - t0)
                runner_ok = runner.dit is not None
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                if not runner_ok:
                    return 3
                break
        shutil.rmtree(tmp_dir, ignore_errors=True)  # ACE also saves its own copy; keep only ours
        os.makedirs(tmp_dir, exist_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
