"""Shared helpers for notebooks/01_generate.ipynb (Kaggle) and its generation workers.

Design notes
------------
* Standard library only at import time, so the same file can be imported by the
  notebook kernel (Kaggle's Python) AND by the two model workers, which run inside
  their own isolated uv virtualenvs (ACE-Step 1.5 and Stable Audio 3 pin
  incompatible torch / transformers versions, so they cannot share one env).
* Audio helpers (``write_wav_44k_stereo``, ``noise_suspect``) import numpy / torch /
  soundfile lazily; they are only called from inside the worker venvs.
* Spec: docs/05-system-design.md (plan.json + candidates/manifest.json formats).
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MODEL_ACE = "ace-step-1.5"
MODEL_SA3 = "stable-audio-3"
KNOWN_MODELS = (MODEL_ACE, MODEL_SA3)

# Accept a few spellings a human / agent might write in plan.json["models"].
MODEL_ALIASES = {
    "ace-step-1.5": MODEL_ACE,
    "ace-step-1.5-xl": MODEL_ACE,
    "acestep-1.5": MODEL_ACE,
    "ace-step": MODEL_ACE,
    "ace": MODEL_ACE,
    "stable-audio-3": MODEL_SA3,
    "stable-audio-3.0": MODEL_SA3,
    "stable-audio-3-medium": MODEL_SA3,
    "stableaudio3": MODEL_SA3,
    "sa3": MODEL_SA3,
}

TARGET_SR = 44100  # spec: candidates are 44.1 kHz stereo WAV
USER_AGENT = "classic-of-calm-kaggle/1.0"


# ---------------------------------------------------------------------------
# Kaggle secrets
# ---------------------------------------------------------------------------
def get_secret(name: str) -> Optional[str]:
    """Return a Kaggle Secret (Add-ons -> Secrets) or env var, or None if absent.

    Never raises: a missing / un-attached secret simply returns None.
    """
    try:
        from kaggle_secrets import UserSecretsClient  # type: ignore

        value = UserSecretsClient().get_secret(name)
        if value:
            return value.strip()
    except Exception:
        pass
    value = os.environ.get(name)
    return value.strip() if value else None


# ---------------------------------------------------------------------------
# GitHub access (public raw URL or private repo via token)
# ---------------------------------------------------------------------------
class RepoFetchError(RuntimeError):
    pass


def _http_get(url: str, headers: Dict[str, str], timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def normalize_repo(repo: str) -> str:
    """Accept 'owner/name', 'https://github.com/owner/name(.git)', etc."""
    repo = repo.strip()
    m = re.search(r"github\.com[/:]([^/]+)/([^/#?]+)", repo)
    if m:
        repo = f"{m.group(1)}/{m.group(2)}"
    if repo.endswith(".git"):
        repo = repo[:-4]
    repo = repo.strip("/")
    if repo.count("/") != 1:
        raise ValueError(f"REPO 應該長得像 'owner/repo-name'，目前是：{repo!r}")
    return repo


def fetch_repo_file(repo: str, path: str, branch: str = "main",
                    token: Optional[str] = None, retries: int = 3) -> bytes:
    """Download one file from GitHub.

    * With token  -> GitHub contents API (works for private AND public repos).
    * Without     -> raw.githubusercontent.com (public repos only).
    """
    repo = normalize_repo(repo)
    path = path.lstrip("/")
    quoted = urllib.parse.quote(path)
    if token:
        url = (f"https://api.github.com/repos/{repo}/contents/{quoted}"
               f"?ref={urllib.parse.quote(branch)}")
        headers = {"Authorization": f"Bearer {token}",
                   "Accept": "application/vnd.github.raw",
                   "X-GitHub-Api-Version": "2022-11-28"}
    else:
        url = f"https://raw.githubusercontent.com/{repo}/{urllib.parse.quote(branch)}/{quoted}"
        headers = {}

    last_err: Optional[BaseException] = None
    for attempt in range(1, retries + 1):
        try:
            return _http_get(url, headers)
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (401, 403, 404):
                hint = ("找不到檔案，或 repo 是私人的。私人 repo 請在 Kaggle 右側 "
                        "Add-ons → Secrets 新增 GITHUB_TOKEN 並勾選啟用。"
                        if not token else
                        "GITHUB_TOKEN 沒有權限讀這個 repo，或檔案路徑／分支不存在。")
                raise RepoFetchError(
                    f"讀取 GitHub 檔案失敗（HTTP {e.code}）：{repo}@{branch}:{path}\n  → {hint}"
                ) from e
        except Exception as e:  # network blip
            last_err = e
        time.sleep(2 * attempt)
    raise RepoFetchError(
        f"連不上 GitHub（{repo}@{branch}:{path}）：{last_err}\n"
        "  → 請確認 Kaggle 右側 Settings 的 Internet 已開啟（需要手機驗證）。")


def load_plan(repo: str, week: str, branch: str = "main",
              token: Optional[str] = None) -> Dict[str, Any]:
    raw = fetch_repo_file(repo, f"weekly/{week}/plan.json", branch, token)
    try:
        return json.loads(raw.decode("utf-8-sig"))
    except json.JSONDecodeError as e:
        raise ValueError(f"weekly/{week}/plan.json 不是合法的 JSON：{e}") from e


# ---------------------------------------------------------------------------
# Plan validation / normalisation
# ---------------------------------------------------------------------------
REQUIRED_TRACK_FIELDS = ("id", "tags", "bpm", "key", "duration", "seed")


def normalize_model_name(name: str) -> Optional[str]:
    return MODEL_ALIASES.get(str(name).strip().lower())


def plan_models(plan: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for m in plan.get("models") or [MODEL_ACE]:
        n = normalize_model_name(m)
        if n and n not in out:
            out.append(n)
    return out


def validate_plan(plan: Dict[str, Any]) -> Tuple[List[str], List[str], List[str]]:
    """Return (errors, warnings, bad_track_ids). Tracks listed in bad_track_ids are skipped."""
    errors: List[str] = []
    warnings: List[str] = []
    bad: List[str] = []
    if not isinstance(plan, dict):
        return ["plan.json 最外層必須是物件 {…}"], warnings, bad
    tracks = plan.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        errors.append("plan.json 裡沒有 tracks（歌曲清單）")
        return errors, warnings, bad
    for m in plan.get("models") or []:
        if not normalize_model_name(m):
            warnings.append(f"不認得的模型名稱 {m!r}，會略過（認得：{', '.join(KNOWN_MODELS)}）")
    seen = set()
    for i, t in enumerate(tracks):
        tid = t.get("id") if isinstance(t, dict) else None
        label = tid or f"#{i + 1}"
        if not isinstance(t, dict):
            errors.append(f"第 {i + 1} 首不是物件")
            continue
        n_err = len(errors)
        missing = [f for f in REQUIRED_TRACK_FIELDS if t.get(f) in (None, "")]
        if missing:
            errors.append(f"歌曲 {label} 缺少欄位：{', '.join(missing)}")
        if tid:
            if not re.fullmatch(r"[A-Za-z0-9_-]+", str(tid)) or "__" in str(tid):
                errors.append(f"歌曲 id {tid!r} 只能用英數字、- 和單一 _（不可含 __）")
            if tid in seen:
                errors.append(f"歌曲 id {tid!r} 重複")
            seen.add(tid)
        try:
            bpm = int(t.get("bpm", 0))
            if not 30 <= bpm <= 300:
                warnings.append(f"歌曲 {label} 的 bpm={bpm} 超出 30–300")
        except (TypeError, ValueError):
            errors.append(f"歌曲 {label} 的 bpm 不是數字")
        try:
            dur = float(t.get("duration", 0))
            if not 10 <= dur <= 600:
                warnings.append(f"歌曲 {label} 的 duration={dur} 超出 10–600 秒，會自動夾在範圍內")
        except (TypeError, ValueError):
            errors.append(f"歌曲 {label} 的 duration 不是數字")
        if len(str(t.get("tags", ""))) > 512:
            warnings.append(f"歌曲 {label} 的 tags 超過 512 字元，ACE-Step 會截斷")
        if len(errors) > n_err and tid:
            bad.append(str(tid))
        elif len(errors) > n_err:
            bad.append(f"#{i + 1}")
    if plan.get("week") in (None, ""):
        warnings.append("plan.json 沒有 week 欄位")
    return errors, warnings, bad


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------
_MINOR_MODES = {"minor", "min", "m", "aeolian", "dorian", "phrygian", "locrian",
                "shang", "jue", "yu"}  # 商/角/羽 調式 → 小調色彩
_MAJOR_MODES = {"major", "maj", "ionian", "lydian", "mixolydian",
                "gong", "zhi", "pentatonic"}  # 宮/徵 → 大調色彩


def ace_keyscale(key: str) -> str:
    """Map 'D dorian' / 'A yu' / 'C major' → 'D minor' / 'A minor' / 'C major'.

    UNVERIFIED: ACE-Step docs only show 'C Major', 'Am', 'F# minor' examples; modal
    names are probably out-of-distribution, so we collapse to the nearest major /
    minor and keep the original modal name in the caption instead.
    """
    key = (key or "").strip()
    m = re.match(r"^([A-Ga-g])([#b♯♭]?)\s*(.*)$", key)
    if not m:
        return key
    tonic = m.group(1).upper() + m.group(2).replace("♯", "#").replace("♭", "b")
    mode = m.group(3).strip().lower()
    if not mode:
        return f"{tonic} major"
    first = mode.split()[0]
    if first in _MINOR_MODES:
        return f"{tonic} minor"
    if first in _MAJOR_MODES:
        return f"{tonic} major"
    return key


def _is_plain_major_minor(key: str) -> bool:
    return bool(re.match(r"^[A-Ga-g][#b]?\s*(major|minor|maj|min|m)?$", (key or "").strip(), re.I))


def _ensure_instrumental(tags: str) -> str:
    tags = (tags or "").strip().rstrip(",")
    if "instrumental" not in tags.lower():
        tags = f"{tags}, instrumental" if tags else "instrumental"
    return tags


def build_prompt(track: Dict[str, Any], model: str) -> Dict[str, Any]:
    """Return the exact text prompt + params a model will receive (also logged in manifest)."""
    tags = _ensure_instrumental(str(track.get("tags", "")))
    negative = str(track.get("negative") or "").strip()
    key = str(track.get("key") or "").strip()
    bpm = int(track.get("bpm") or 0) or None
    duration = clamp_duration(track.get("duration"), model)
    if model == MODEL_ACE:
        caption = tags
        if key and not _is_plain_major_minor(key):
            caption = f"{caption}, {key} mode"
        return {"prompt": caption[:512], "negative": negative, "bpm": bpm,
                "keyscale": ace_keyscale(key), "key": key, "duration": duration,
                "lyrics": "[Instrumental]"}
    # Stable Audio 3 has no bpm/key parameters → put them in the text (music bible §0.1).
    head = ", ".join(x for x in [f"{bpm} BPM" if bpm else "", key] if x)
    prompt = f"{head}, {tags}" if head else tags
    return {"prompt": prompt, "negative": negative, "bpm": bpm, "key": key,
            "duration": duration}


def clamp_duration(value: Any, model: str, sa3_max: float = 380.0) -> float:
    try:
        d = float(value)
    except (TypeError, ValueError):
        d = 180.0
    hi = 600.0 if model == MODEL_ACE else sa3_max
    return float(max(10.0, min(hi, d)))


# ---------------------------------------------------------------------------
# Jobs / filenames / seeds
# ---------------------------------------------------------------------------
def candidate_filename(track_id: str, model: str, take: int) -> str:
    return f"{track_id}__{model}__{take}.wav"


def take_seed(base_seed: Any, take: int) -> int:
    """Take 1 uses the plan seed exactly; later takes are deterministic offsets."""
    try:
        base = int(base_seed)
    except (TypeError, ValueError):
        base = 0
    return int((base + 7919 * (take - 1)) % (2 ** 31 - 1))


def build_jobs(plan: Dict[str, Any], model: str, takes: int, out_dir: str,
               only_tracks: Optional[Iterable[str]] = None,
               skip_ids: Iterable[str] = ()) -> List[Dict[str, Any]]:
    only = set(only_tracks) if only_tracks else None
    skip = set(skip_ids)
    jobs: List[Dict[str, Any]] = []
    for take in range(1, takes + 1):  # all take-1s first, so a time-out still covers every track
        for t in plan.get("tracks", []):
            tid = str(t.get("id", ""))
            if not tid or tid in skip or (only is not None and tid not in only):
                continue
            p = build_prompt(t, model)
            fname = candidate_filename(tid, model, take)
            jobs.append({
                "file": fname,
                "path": os.path.join(out_dir, fname),
                "track_id": tid,
                "series": t.get("series") or plan.get("series"),
                "title_en": t.get("title_en"),
                "model": model,
                "take": take,
                "seed": take_seed(t.get("seed"), take),
                **p,
            })
    return jobs


# ---------------------------------------------------------------------------
# Manifest (candidates/manifest.json) — a JSON list of entries
# ---------------------------------------------------------------------------
def atomic_write_json(path: str, data: Any) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_manifest(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):  # tolerate {"entries": [...]} if someone changes format
            data = data.get("entries", [])
        return [e for e in data if isinstance(e, dict) and e.get("file")]
    except Exception:
        return []


def merge_manifest(path: str, new_entries: Iterable[Dict[str, Any]],
                   out_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Upsert by file name, drop entries whose wav no longer exists, sort, save."""
    by_file = {e["file"]: e for e in load_manifest(path)}
    for e in new_entries:
        if e.get("file"):
            by_file[e["file"]] = e
    if out_dir:
        by_file = {k: v for k, v in by_file.items() if os.path.exists(os.path.join(out_dir, k))}
    entries = sorted(by_file.values(), key=lambda e: (e.get("track_id", ""), e.get("model", ""),
                                                      int(e.get("take", 0))))
    atomic_write_json(path, entries)
    return entries


def read_jsonl(path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        f.flush()


def manifest_entry(job: Dict[str, Any], gen_seconds: float, duration_sec: float,
                   model_variant: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Spec fields first: file, track_id, model, take, seed, prompt, gen_seconds."""
    e = {
        "file": job["file"],
        "track_id": job["track_id"],
        "model": job["model"],
        "take": job["take"],
        "seed": job["seed"],
        "prompt": job["prompt"],
        "gen_seconds": round(float(gen_seconds), 2),   # 生成秒數（實際花費的運算時間）
        "duration_sec": round(float(duration_sec), 2),  # 音檔長度
        "negative": job.get("negative", ""),
        "bpm": job.get("bpm"),
        "key": job.get("key"),
        "keyscale": job.get("keyscale"),
        "duration_requested": job.get("duration"),
        "series": job.get("series"),
        "title_en": job.get("title_en"),
        "model_variant": model_variant,
        "sample_rate": TARGET_SR,
        "channels": 2,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if extra:
        e.update(extra)
    return e


# ---------------------------------------------------------------------------
# Time budget
# ---------------------------------------------------------------------------
class JobTimer:
    """Tracks per-job durations so a worker can stop before the deadline."""

    def __init__(self, deadline_epoch: float, first_guess_s: float = 300.0, safety: float = 1.5):
        self.deadline = float(deadline_epoch)
        self.durations: List[float] = []
        self.first_guess = first_guess_s
        self.safety = safety

    def add(self, seconds: float) -> None:
        self.durations.append(seconds)

    def estimate(self) -> float:
        if not self.durations:
            return self.first_guess
        recent = self.durations[-5:]
        return max(recent) * self.safety

    def remaining(self) -> float:
        return self.deadline - time.time()

    def can_start_next(self) -> bool:
        return self.remaining() > self.estimate()


def fmt_secs(s: float) -> str:
    s = int(max(0, s))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}小時{m:02d}分" if h else f"{m}分{sec:02d}秒"


# ---------------------------------------------------------------------------
# Audio helpers (used only inside worker venvs; heavy imports are lazy)
# ---------------------------------------------------------------------------
def write_wav_44k_stereo(audio: Any, sr: int, path: str) -> float:
    """Write a [channels, samples] (or [samples]) float tensor/array as 44.1k stereo PCM16.

    Resamples with torchaudio if needed. Writes to a temp file then renames, so a
    crash never leaves a half-written .wav that the resume logic would mistake for done.
    Returns the duration in seconds.
    """
    import numpy as np
    import soundfile as sf
    import torch

    x = audio if isinstance(audio, torch.Tensor) else torch.as_tensor(np.asarray(audio))
    x = x.detach().float().cpu()
    if x.dim() == 3:  # [batch, ch, n]
        x = x[0]
    if x.dim() == 1:
        x = x.unsqueeze(0)
    if x.shape[0] > x.shape[-1]:  # [n, ch] → [ch, n]
        x = x.transpose(0, 1)
    if x.shape[0] == 1:
        x = x.repeat(2, 1)
    elif x.shape[0] > 2:
        x = x[:2]
    if int(sr) != TARGET_SR:
        import torchaudio.functional as AF
        x = AF.resample(x, int(sr), TARGET_SR)
    x = torch.nan_to_num(x).clamp(-1.0, 1.0)
    data = x.transpose(0, 1).numpy()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".part"
    sf.write(tmp, data, TARGET_SR, subtype="PCM_16", format="WAV")
    os.replace(tmp, path)
    return data.shape[0] / TARGET_SR


def noise_suspect(path: str) -> Dict[str, Any]:
    """Cheap sanity check: flag silent or white-noise-like output (e.g. broken attention kernels)."""
    try:
        import numpy as np
        import soundfile as sf

        data, sr = sf.read(path, dtype="float32", always_2d=True)
        mono = data.mean(axis=1)
        rms = float(np.sqrt(np.mean(mono ** 2)) + 1e-12)
        seg = mono[: sr * 30]
        n = 4096
        frames = len(seg) // n
        flat = 0.0
        if frames:
            spec = np.abs(np.fft.rfft(seg[: frames * n].reshape(frames, n) * np.hanning(n), axis=1)) + 1e-10
            flat = float(np.mean(np.exp(np.mean(np.log(spec), axis=1)) / np.mean(spec, axis=1)))
        return {"rms_dbfs": round(float(20 * np.log10(rms)), 1), "spectral_flatness": round(flat, 3),
                "suspect": bool(rms < 1e-3 or flat > 0.5)}
    except Exception as e:  # never fail a generation because of the check
        return {"check_error": str(e)[:200]}
