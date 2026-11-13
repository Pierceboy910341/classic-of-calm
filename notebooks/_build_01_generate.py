"""Builds notebooks/01_generate.ipynb with nbformat. Edit cells here, then run:
    python notebooks/_build_01_generate.py notebooks/01_generate.ipynb
"""
import sys

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

MD_INTRO = r"""# 🎵 Classic of Calm — 01 生成候選曲（每週一）

這個筆記本會讀取本週的 `plan.json`，用 AI 模型產生約 60 首候選曲，存成 WAV 檔。**你不需要看懂下面的程式。**

## 每週只要做這 4 步
1. **確認右側設定（只有第一次要設，之後會記住）**
   - **Session options → Accelerator**：選 **GPU T4 x2**（或 GPU T4）。⚠️ 不要選 P100，新版模型可能不支援。
   - **Session options → Internet**：**On**（要先在 Kaggle 帳號完成手機驗證）。
   - **Add-ons → Secrets**（選填）：
     - `GITHUB_TOKEN`：只有 repo 是「私人」時才需要。
     - `HF_TOKEN`：Stable Audio 3 若需要 Hugging Face 授權才需要；沒設會自動跳過，不影響 ACE-Step。
     - 新增後記得**勾選**它，筆記本才讀得到。
2. **改下面「設定」格子裡的 `WEEK`**（例如 `"2026-W47"`）。Claude 會在對話裡告訴你本週要填什麼。
3. 按右上角 **Save Version → 選 Save & Run All (Commit) → Save**。
4. 關掉瀏覽器也沒關係。約 **2–6 小時**後，到這個筆記本的 **Output** 分頁，看到 `candidates` 資料夾就完成了。接著回 Claude 對話說：「**審核本週歌曲**」。

## 如果出錯
- 到 Version 的 **Log** 分頁，捲到最下面，把最後 20 行**截圖**貼給 Claude。
- 單一首失敗不會中斷整批；最後會列出成功與失敗的數量。
- 如果跑到一半時間用完，筆記本會自己安全停下並保存已完成的歌。可以在 **Add Input → Notebook Output** 加入上一版的輸出後再跑一次，已完成的歌會自動略過。
"""

CONFIG = r'''# ====== ✏️ 設定（每週只要改 WEEK）======
WEEK = "2026-W47"                      # 本週代號，對應 GitHub 上的 weekly/<WEEK>/plan.json（測試可用 "_example"）
REPO = "Pierceboy910341/classic-of-calm"  # GitHub repo（第一次設定好就不用再改）
BRANCH = "main"                        # 分支，通常不用改

# ---- 以下是進階設定，平常不用動 ----
TAKES_PER_MODEL = 1          # 每首歌、每個模型生成幾個版本（試產週 = 1）
MODELS_OVERRIDE = None       # None = 照 plan.json 的 models；也可寫 ["ace-step-1.5"] 只跑一個
ONLY_TRACKS = None           # None = 全部；測試時可寫 ["s01", "s02"]
TIME_BUDGET_HOURS = 11.0     # Kaggle 單次上限 12 小時；預留時間保存輸出

ACE_REF = "main"                      # ACE-Step-1.5 GitHub 版本（分支、tag 或 commit）
ACE_DIT_MODEL = "acestep-v15-xl-turbo"   # 主力：XL (4B) turbo
ACE_FALLBACK_DIT = "acestep-v15-turbo"   # VRAM 不夠時自動改用 2B turbo
ACE_USE_LM = False                    # True = 開啟 5Hz 語言模型（較慢、較吃 VRAM）
ACE_LM_MODEL = "acestep-5Hz-lm-0.6B"
SA3_REF = "main"                      # stable-audio-3 GitHub 版本
SA3_MODEL = "medium"                  # 1.4B，最長 380 秒
SA3_FALLBACK = "small-music"          # 433M，最長 120 秒
'''

MD_BELOW = "## ⚙️ 以下不用修改\n直接執行即可。每一格會印出進度（中文）。"

SETUP = r'''# 1) 準備環境、讀取 Secrets、從 GitHub 下載共用程式
import os, sys, time, shutil, subprocess, threading, glob, urllib.request, urllib.error

class StopRun(Exception):
    """用來在發生無法繼續的錯誤時，以清楚的中文訊息停止整個筆記本。"""

RUN_START = time.time()
HARD_DEADLINE = RUN_START + TIME_BUDGET_HOURS * 3600
SAVE_MARGIN_S = 10 * 60                      # 留 10 分鐘寫 manifest 與輸出

OUT_DIR = "/kaggle/working/candidates"       # 規格：candidates/<track>__<model>__<take>.wav + manifest.json
LOG_DIR = "/kaggle/working/logs"
WORK = "/tmp/coc"                            # 模型、venv、快取放這裡（不會進 Output，避免超過 20 GB）
PIPE_DIR = f"{WORK}/pipeline"
for d in (OUT_DIR, LOG_DIR, WORK, PIPE_DIR):
    os.makedirs(d, exist_ok=True)
MANIFEST = f"{OUT_DIR}/manifest.json"

def _secret(name):
    try:
        from kaggle_secrets import UserSecretsClient
        v = UserSecretsClient().get_secret(name)
        return v.strip() if v else None
    except Exception:
        v = os.environ.get(name)
        return v.strip() if v else None

GITHUB_TOKEN = _secret("GITHUB_TOKEN")
HF_TOKEN = _secret("HF_TOKEN")
print("GITHUB_TOKEN：", "已設定（私人 repo 模式）" if GITHUB_TOKEN else "未設定（公開 repo 模式）")
print("HF_TOKEN：", "已設定" if HF_TOKEN else "未設定（Stable Audio 3 若需授權會自動跳過）")

def _bootstrap_fetch(path):
    """在載入 kaggle_utils 之前，用最簡單的方式從 GitHub 抓一個檔案。"""
    repo = REPO.strip().replace("https://github.com/", "").rstrip("/").removesuffix(".git")
    if GITHUB_TOKEN:
        url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={BRANCH}"
        hdr = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.raw"}
    else:
        url = f"https://raw.githubusercontent.com/{repo}/{BRANCH}/{path}"
        hdr = {}
    req = urllib.request.Request(url, headers={"User-Agent": "classic-of-calm-kaggle/1.0", **hdr})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise StopRun(
            f"❌ 讀不到 GitHub 檔案 {path}（HTTP {e.code}）。\n"
            f"   請確認：① 設定格的 REPO = {REPO!r} 正確 ② repo 若是私人的，要設定並勾選 GITHUB_TOKEN。")
    except Exception as e:
        raise StopRun(f"❌ 連不上 GitHub：{e}\n   請確認右側 Settings 的 Internet 是 On。")

for fn in ("kaggle_utils.py", "gen_ace_step.py", "gen_stable_audio.py"):
    with open(f"{PIPE_DIR}/{fn}", "wb") as f:
        f.write(_bootstrap_fetch(f"pipeline/{fn}"))
sys.path.insert(0, PIPE_DIR)
import importlib, kaggle_utils as ku
importlib.reload(ku)
print("✅ 共用程式下載完成")
'''

PLAN = r'''# 2) 讀取本週 plan.json 並檢查
plan = ku.load_plan(REPO, WEEK, BRANCH, GITHUB_TOKEN)
errors, warnings, bad = ku.validate_plan(plan)
bad_ids = set(bad)
for w in warnings:
    print("⚠️ ", w)
for e in errors:
    print("❌ ", e)
if plan.get("week") and plan.get("week") != WEEK:
    print(f"⚠️  plan.json 寫的週次是 {plan.get('week')}，但設定格的 WEEK 是 {WEEK}（以 WEEK 為準）")
tracks_all = plan.get("tracks") if isinstance(plan.get("tracks"), list) else []
if not tracks_all or len(bad_ids) >= len(tracks_all):
    raise StopRun("❌ plan.json 有錯，沒有可生成的歌曲。請把上面的訊息截圖給 Claude。")

MODELS = [ku.normalize_model_name(m) for m in MODELS_OVERRIDE] if MODELS_OVERRIDE else ku.plan_models(plan)
MODELS = [m for m in MODELS if m]
TAKES = max(1, int(TAKES_PER_MODEL))
n_tracks = len([t for t in plan["tracks"] if t.get("id") not in bad_ids
                and (not ONLY_TRACKS or t.get("id") in ONLY_TRACKS)])
cre = plan.get("creature") or {}
print(f"📅 週次：{plan.get('week', WEEK)}　系列：{plan.get('series')}　試產週：{plan.get('trial', False)}")
print(f"🐾 本週異獸：{cre.get('zh', '')} {cre.get('en', '')}")
print(f"🎼 歌曲 {n_tracks} 首 × 模型 {len(MODELS)} 個（{', '.join(MODELS)}）× 每個 {TAKES} 版 = 共 {n_tracks * len(MODELS) * TAKES} 個檔案")
if bad_ids:
    print(f"   （跳過有問題的歌曲：{sorted(bad_ids)}）")

# 若有加入上一版的輸出（Add Input → Notebook Output），把同一週已完成的歌先複製回來，避免重做
restored = 0
for mpath in glob.glob("/kaggle/input/**/candidates/manifest.json", recursive=True):
    src_dir = os.path.dirname(mpath)
    for e in ku.load_manifest(mpath):
        if e.get("week", WEEK) != WEEK:
            continue
        src, dst = os.path.join(src_dir, e["file"]), os.path.join(OUT_DIR, e["file"])
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
            ku.merge_manifest(MANIFEST, [e])
            restored += 1
if restored:
    print(f"♻️  從上一版輸出接續：已複製 {restored} 個完成的檔案")
'''

GPU = r'''# 3) 檢查 GPU 與磁碟空間
smi = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                     capture_output=True, text=True)
if smi.returncode != 0 or not smi.stdout.strip():
    raise StopRun("❌ 沒有 GPU！請在右側 Session options → Accelerator 選「GPU T4 x2」後重新 Save & Run All。")
GPU_NAME = smi.stdout.strip().splitlines()[0]
print("🖥️  GPU：", GPU_NAME, "（只會用第 1 張）")
if "P100" in GPU_NAME:
    print("⚠️  偵測到 P100。ACE-Step 1.5 使用的新版 PyTorch (CUDA 12.8) 可能已不支援 P100（未經實測）。\n"
          "    若後面出現 'no kernel image' 錯誤，請改選 GPU T4 x2 再跑一次。")
for p in ("/tmp", "/kaggle/working"):
    du = shutil.disk_usage(p)
    print(f"💾 {p} 可用空間：{du.free / 2**30:.0f} GB")
'''

HELPERS = r'''# 4) 安裝與執行工具（每個模型裝在自己的獨立環境，跑完整個程序結束 → VRAM 一定會釋放）
def _log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def remaining_s():
    return HARD_DEADLINE - time.time()

def _stream(proc, logfile, prefix=""):
    """把子程序輸出即時印出來；進度條類的行最多每 30 秒印一次，避免洗版。"""
    last_bar = 0.0
    with open(logfile, "a", encoding="utf-8") as lf:
        for line in iter(proc.stdout.readline, ""):
            lf.write(line)
            s = line.rstrip()
            if not s:
                continue
            if ("%|" in s or "it/s" in s or "s/it" in s) and not s.startswith("["):
                if time.time() - last_bar < 30:
                    continue
                last_bar = time.time()
            print(prefix + s[-400:], flush=True)

def run(cmd, cwd=None, env=None, logfile=None, deadline=None, prefix=""):
    """執行指令並即時顯示輸出；超過 deadline 會被強制停止。回傳 exit code。"""
    logfile = logfile or f"{LOG_DIR}/install.log"
    full_env = {**os.environ, **(env or {})}
    for k in ("VIRTUAL_ENV", "PYTHONHOME"):
        full_env.pop(k, None)
    proc = subprocess.Popen(cmd, cwd=cwd, env=full_env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1, errors="replace")
    t = threading.Thread(target=_stream, args=(proc, logfile, prefix), daemon=True)
    t.start()
    while proc.poll() is None:
        if deadline and time.time() > deadline:
            _log("⏰ 超過時間上限，停止這個步驟")
            proc.terminate()
            try:
                proc.wait(60)
            except subprocess.TimeoutExpired:
                proc.kill()
            break
        time.sleep(2)
    t.join(timeout=10)
    return proc.returncode if proc.returncode is not None else -9

UV_ENV = {"UV_CACHE_DIR": f"{WORK}/uv-cache", "UV_LINK_MODE": "copy", "UV_NO_PROGRESS": "1",
          "UV_HTTP_TIMEOUT": "300"}
UV = [sys.executable, "-m", "uv"]

def ensure_uv():
    if subprocess.run(UV + ["--version"], capture_output=True).returncode != 0:
        _log("安裝 uv（Python 套件管理工具）…")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "uv"], check=True)

def clone(url, ref, dest):
    if os.path.exists(f"{dest}/.git"):
        return True
    _log(f"下載程式碼 {url} @ {ref}")
    if run(["git", "clone", "--depth", "1", "--branch", ref, url, dest]) == 0:
        return True
    # ref 可能是 commit hash：完整 clone 後 checkout
    shutil.rmtree(dest, ignore_errors=True)
    return (run(["git", "clone", url, dest]) == 0 and
            run(["git", "checkout", ref], cwd=dest) == 0)

def git_commit(dest):
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=dest, capture_output=True, text=True)
    return r.stdout.strip()

def install_repo(name, url, ref):
    """git clone + uv sync（使用官方 lockfile）。回傳 venv 的 python 路徑，失敗回傳 None。"""
    dest = f"{WORK}/{name}"
    py = f"{dest}/.venv/bin/python"
    if os.path.exists(py):
        return py
    ensure_uv()
    if not clone(url, ref, dest):
        _log(f"❌ 無法下載 {name}")
        return None
    _log(f"安裝 {name} 的套件（約 3–10 分鐘）…")
    code = run(UV + ["sync"], cwd=dest, env=UV_ENV, logfile=f"{LOG_DIR}/install_{name}.log",
               deadline=time.time() + 45 * 60)
    if code != 0 or not os.path.exists(py):
        _log(f"❌ {name} 安裝失敗（exit {code}），詳見 logs/install_{name}.log")
        return None
    return py

def worker_env():
    env = {"PYTHONPATH": PIPE_DIR, "PYTHONUNBUFFERED": "1", "CUDA_VISIBLE_DEVICES": "0",
           "HF_HOME": f"{WORK}/hf", "TOKENIZERS_PARALLELISM": "false",
           "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True", "ACESTEP_DOWNLOAD_SOURCE": "huggingface"}
    if HF_TOKEN:
        env["HF_TOKEN"] = HF_TOKEN
        env["HUGGING_FACE_HUB_TOKEN"] = HF_TOKEN
    return env

EXIT_MEANING = {0: "完成", 2: "時間預算用完，安全停止", 3: "模型無法載入", 4: "需要 Hugging Face 授權，已跳過",
                -9: "超時被停止"}
print("✅ 工具準備好了")
'''

RUN = r'''# 5) 逐一模型生成（主力 ACE-Step 先跑；時間平均分給各模型，先跑完的會把剩餘時間讓給下一個）
MODEL_SETUP = {
    ku.MODEL_ACE: dict(name="ACE-Step-1.5", url="https://github.com/ace-step/ACE-Step-1.5.git", ref=ACE_REF,
                       worker="gen_ace_step.py",
                       args=lambda repo: ["--ace-dir", repo, "--dit", ACE_DIT_MODEL, "--fallback-dit", ACE_FALLBACK_DIT,
                                          "--lm-model", ACE_LM_MODEL] + (["--use-lm"] if ACE_USE_LM else [])),
    ku.MODEL_SA3: dict(name="stable-audio-3", url="https://github.com/Stability-AI/stable-audio-3.git", ref=SA3_REF,
                       worker="gen_stable_audio.py",
                       args=lambda repo: ["--model", SA3_MODEL, "--fallback-model", SA3_FALLBACK]),
}
order = sorted(MODELS, key=lambda m: 0 if m == ku.MODEL_ACE else 1)
STATUS, FAILURES, COMMITS = {}, [], {}

for i, model in enumerate(order):
    left = len(order) - i
    budget = (remaining_s() - SAVE_MARGIN_S) / left
    if budget < 15 * 60:
        STATUS[model] = "時間不夠，未執行"
        _log(f"⏭️  {model}：剩餘時間不足 15 分鐘，跳過")
        continue
    deadline = time.time() + budget
    setup = MODEL_SETUP.get(model)
    print("\n" + "=" * 70)
    _log(f"▶️  開始 {model}（這個模型最多可用 {ku.fmt_secs(budget)}）")
    print("=" * 70)
    try:
        jobs = ku.build_jobs(plan, model, TAKES, OUT_DIR, only_tracks=ONLY_TRACKS, skip_ids=bad_ids)
        todo = [j for j in jobs if not os.path.exists(j["path"])]
        if not todo:
            STATUS[model] = "全部已存在，略過"
            _log("這個模型的檔案都已存在，略過")
            continue
        py = install_repo(setup["name"], setup["url"], setup["ref"])
        if not py:
            STATUS[model] = "安裝失敗"
            continue
        repo_dir = f"{WORK}/{setup['name']}"
        COMMITS[model] = git_commit(repo_dir)
        jobs_path = f"{LOG_DIR}/jobs_{model}.json"
        results_path = f"{LOG_DIR}/results_{model}.jsonl"
        ku.atomic_write_json(jobs_path, jobs)
        cmd = [py, f"{PIPE_DIR}/{setup['worker']}", "--jobs", jobs_path, "--results", results_path,
               "--deadline", str(deadline)] + setup["args"](repo_dir)
        code = run(cmd, cwd=repo_dir, env=worker_env(), logfile=f"{LOG_DIR}/worker_{model}.log",
                   deadline=deadline + 20 * 60)  # 留 20 分鐘讓正在跑的那首收尾
        STATUS[model] = EXIT_MEANING.get(code, f"異常結束（exit {code}）")
    except Exception as e:
        STATUS[model] = f"錯誤：{type(e).__name__}: {e}"
        _log(f"❌ {model} 發生錯誤：{e}")
    finally:
        # 不論成功與否，都把已完成的檔案寫進 manifest
        results = ku.read_jsonl(f"{LOG_DIR}/results_{model}.jsonl")
        new = []
        for r in results:
            if r.get("status") == "ok":
                e = r["entry"]
                e["week"] = WEEK
                e["code_commit"] = COMMITS.get(model, "")
                new.append(e)
            elif r.get("status") == "failed" and not os.path.exists(os.path.join(OUT_DIR, r.get("file", "?"))):
                FAILURES.append(r)
        ku.merge_manifest(MANIFEST, new, out_dir=OUT_DIR)
        _log(f"⏹️  {model}：{STATUS.get(model)}；剩餘總時間 {ku.fmt_secs(remaining_s())}")

# 清掉生成中途留下的半成品
for p in glob.glob(f"{OUT_DIR}/*.part"):
    os.remove(p)
'''

SUMMARY = r'''# 6) 總結
entries = ku.merge_manifest(MANIFEST, [], out_dir=OUT_DIR)
# 失敗清單只保留「最後仍沒有檔案」的那些
final_fail = {}
for f in FAILURES:
    if not os.path.exists(os.path.join(OUT_DIR, f.get("file", "?"))):
        final_fail[f["file"]] = f
ku.atomic_write_json(f"{LOG_DIR}/failures.json", list(final_fail.values()))

expected = {j["file"] for m in MODELS for j in ku.build_jobs(plan, m, TAKES, OUT_DIR,
                                                              only_tracks=ONLY_TRACKS, skip_ids=bad_ids)}
done = {e["file"] for e in entries} & expected
suspects = [e["file"] for e in entries if (e.get("audio_check") or {}).get("suspect")]
ku.atomic_write_json(f"{LOG_DIR}/run_summary.json", {
    "week": WEEK, "models": MODELS, "takes": TAKES, "status": STATUS, "code_commits": COMMITS,
    "expected": len(expected), "succeeded": len(done), "failed": len(final_fail),
    "not_started": len(expected - done - set(final_fail)), "suspect_noise": suspects,
    "gpu": GPU_NAME, "elapsed_hours": round((time.time() - RUN_START) / 3600, 2)})

print("\n" + "🎶" * 25)
print(f"本週 {WEEK} 生成結果")
print("🎶" * 25)
for m in MODELS:
    n_ok = sum(1 for e in entries if e.get("model") == m and e["file"] in expected)
    n_exp = sum(1 for f in expected if f"__{m}__" in f)
    print(f"  • {m}：成功 {n_ok} / {n_exp} 首　（{STATUS.get(m, '未執行')}）")
print(f"\n✅ 成功：{len(done)} 首　❌ 失敗：{len(final_fail)} 首　⏸️ 未開始：{len(expected - done - set(final_fail))} 首")
print(f"⏱️  總共花了 {ku.fmt_secs(time.time() - RUN_START)}")
if suspects:
    print(f"⚠️  其中 {len(suspects)} 首聽起來可能是雜訊或靜音，審核時會優先檢查：{suspects[:5]}{' …' if len(suspects) > 5 else ''}")
if final_fail:
    print("\n失敗的歌（前 10 首）：")
    for f in list(final_fail.values())[:10]:
        print(f"  - {f['file']}：{str(f.get('error', ''))[:150]}")
print("\n👉 下一步：到這個筆記本的 Output 分頁確認有 candidates 資料夾，")
print("   然後回 Claude 對話說「審核本週歌曲」。")
if len(done) < len(expected):
    print("   （沒做完的歌：可以 Add Input → Notebook Output 加入這一版，再 Save & Run All 一次，會從中斷處接著做。）")
'''


def build(out_path):
    nb = new_notebook()
    nb.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
        # Kaggle reads these when the notebook is imported/pushed (UNVERIFIED that the UI honours
        # them on "Import Notebook"; the owner guide still says to set GPU + Internet manually).
        "kaggle": {"accelerator": "nvidiaTeslaT4", "isGpuEnabled": True, "isInternetEnabled": True,
                   "language": "python", "sourceType": "notebook", "dataSources": []},
    }
    nb.cells = [
        new_markdown_cell(MD_INTRO),
        new_code_cell(CONFIG),
        new_markdown_cell(MD_BELOW),
        new_code_cell(SETUP),
        new_code_cell(PLAN),
        new_code_cell(GPU),
        new_code_cell(HELPERS),
        new_code_cell(RUN),
        new_code_cell(SUMMARY),
    ]
    nbformat.validate(nb)
    nbformat.write(nb, out_path)


if __name__ == "__main__":
    build(sys.argv[1])
