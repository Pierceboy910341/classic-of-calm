"""Builds notebooks/02_assemble.ipynb with nbformat. Edit cells here, then run:
    python notebooks/_build_02_assemble.py notebooks/02_assemble.ipynb
"""
import sys

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

MD_INTRO = r"""# 🎬 Classic of Calm — 02 組合輯（每週二）

這個筆記本會把你在審核時**留下的歌**做成本週的合輯影片。**你不需要看懂下面的程式。**
它會：疊上真實樂器音色 → 母帶處理（統一音量）→ 歌與歌之間交叉淡化 → 做出會動的循環畫面 → 組成 1–2 小時的 `compilation.mp4`，並寫好 YouTube 標題、說明和章節時間。

## 每週只要做這 4 步
1. **確認右側設定（只有第一次要設，之後會記住）**
   - **Session options → Accelerator**：選 **None**（這個筆記本只用 CPU，不需要 GPU）。
   - **Session options → Internet**：**On**。
   - **Add Input → Notebook Output**：加入「**01 Generate**」最新一版的輸出（第一次加好之後，每週會自動用最新版）。
   - **Add-ons → Secrets**（選填）：`GITHUB_TOKEN`，只有 repo 是「私人」時才需要，新增後記得**勾選**。
2. **改下面「設定」格子裡的 `WEEK`**（和 01 Generate 用同一週，例如 `"2026-W47"`）。
3. 確認 Claude 已經說「selection.json 已推送」，再按右上角 **Save Version → Save & Run All (Commit) → Save**。
4. 約 **1–2 小時**後，到這個筆記本的 **Output** 分頁下載：
   - `compilation.mp4`（要上傳的影片）
   - `thumbnail.png`（縮圖）
   - `youtube.txt`（標題、說明、標籤；Claude 會幫你整理好）
   然後回 Claude 對話說：「**本週上傳資料**」。

## 如果出錯
- 到 Version 的 **Log** 分頁，捲到最下面，把最後 20 行**截圖**貼給 Claude。
- 找不到候選曲：通常是忘了 **Add Input → Notebook Output** 加入 01 Generate 的輸出。
- 沒有 `selection.json` 也能跑：會自動挑自動檢查分數最高的版本（但最好還是先完成審核）。
"""

CFG = r'''# ====== ✏️ 設定（每週只要改 WEEK）======
WEEK = "2026-W47"                          # 本週代號，和 01 Generate 相同
REPO = "Pierceboy910341/classic-of-calm"  # GitHub repo（第一次設定好就不用再改）
BRANCH = "main"                            # 分支，通常不用改

# ---- 以下是進階設定，平常不用動 ----
LOOP_SECONDS = 40        # 循環動畫長度（20–60 秒）
CAPTIONS = True          # 影片左下角顯示目前曲名
CANDIDATES_DIR = None    # None = 自動在 /kaggle/input 裡找 01 Generate 的 candidates
SAMPLES_DIR = None       # None = 用 repo 的 samples/；也可指定某個 Kaggle Dataset 路徑
MAX_TRACKS = None        # 測試時可寫 3，只做前 3 首
X264_PRESET = "medium"   # 循環畫面的編碼速度（veryfast 較快、檔案較大）
'''

MD_RUN = r"""## ⚙️ 以下不用修改
直接執行即可。每一格會印出進度（中文）。
"""

C_SETUP = r'''# 1) 準備環境、從 GitHub 下載整個 repo（含 pipeline/、weekly/、samples/）
import os, sys, glob, json, shutil, subprocess, tarfile, time, io, urllib.request, urllib.error

class StopRun(Exception):
    """用來在發生無法繼續的錯誤時，以清楚的中文訊息停止整個筆記本。"""

RUN_START = time.time()
OUT_DIR = "/kaggle/working"            # 規格：compilation.mp4、thumbnail.png、youtube.txt、stream_tracks/、stream_loop.mp4
WORK = "/tmp/coc_assemble"             # 大型中間檔（不進 Output）
REPO_DIR = "/tmp/coc_repo"
os.makedirs(WORK, exist_ok=True)

def _secret(name):
    try:
        from kaggle_secrets import UserSecretsClient
        v = UserSecretsClient().get_secret(name)
        return v.strip() if v else None
    except Exception:
        v = os.environ.get(name)
        return v.strip() if v else None

GITHUB_TOKEN = _secret("GITHUB_TOKEN")
print("GITHUB_TOKEN：", "已設定（私人 repo 模式）" if GITHUB_TOKEN else "未設定（公開 repo 模式）")

def _download_repo():
    repo = REPO.strip().replace("https://github.com/", "").rstrip("/").removesuffix(".git")
    if GITHUB_TOKEN:
        url = f"https://api.github.com/repos/{repo}/tarball/{BRANCH}"
        hdr = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    else:
        url = f"https://codeload.github.com/{repo}/tar.gz/{BRANCH}"
        hdr = {}
    req = urllib.request.Request(url, headers={"User-Agent": "classic-of-calm-kaggle/1.0", **hdr})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        raise StopRun(f"❌ 下載不到 GitHub repo（HTTP {e.code}）。\n"
                      f"   請確認：① 設定格的 REPO = {REPO!r} 正確 ② repo 若是私人的，要設定並勾選 GITHUB_TOKEN。")
    except Exception as e:
        raise StopRun(f"❌ 連不上 GitHub：{e}\n   請確認右側 Settings 的 Internet 是 On。")
    shutil.rmtree(REPO_DIR, ignore_errors=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        tops = {m.name.split("/")[0] for m in tf.getmembers() if "/" in m.name}
        top = sorted(tops)[0]
        try:
            tf.extractall("/tmp/coc_repo_tmp", filter="data")
        except TypeError:
            tf.extractall("/tmp/coc_repo_tmp")
    shutil.move(f"/tmp/coc_repo_tmp/{top}", REPO_DIR)
    shutil.rmtree("/tmp/coc_repo_tmp", ignore_errors=True)

_download_repo()
if not os.path.isdir(f"{REPO_DIR}/pipeline"):
    raise StopRun("❌ repo 裡沒有 pipeline/ 資料夾，請告訴 Claude。")
print("✅ repo 下載完成")

# 安裝套件（Kaggle 已內建 numpy / scipy / Pillow；補上 soundfile、pyloudnorm）
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", f"{REPO_DIR}/pipeline/requirements.txt"], check=False)
if not shutil.which("ffmpeg"):
    print("…沒有 ffmpeg，正在安裝")
    r = subprocess.run("apt-get install -y -qq ffmpeg", shell=True)
    if r.returncode != 0 or not shutil.which("ffmpeg"):
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "imageio-ffmpeg"], check=False)
sys.path.insert(0, REPO_DIR)
import pipeline
from pipeline.common import ffmpeg_bin
print("✅ 套件就緒，ffmpeg：", ffmpeg_bin())
'''

C_FIND = r'''# 2) 找本週資料：plan.json、selection.json、插畫、01 Generate 的候選曲、樂器音色
WEEK_DIR = f"{REPO_DIR}/weekly/{WEEK}"
if not os.path.exists(f"{WEEK_DIR}/plan.json"):
    raise StopRun(f"❌ GitHub 上找不到 weekly/{WEEK}/plan.json。請確認 WEEK 有填對，或請 Claude 先推送。")
plan = json.load(open(f"{WEEK_DIR}/plan.json", encoding="utf-8"))
has_sel = os.path.exists(f"{WEEK_DIR}/selection.json")
cre = plan.get("creature") or {}
print(f"📅 週次：{WEEK}　系列：{plan.get('series')}　🐾 異獸：{cre.get('zh', '')} {cre.get('en', '')}")
print("📝 selection.json：", "有（照你留下的歌與順序）" if has_sel else "⚠️ 沒有 → 會自動挑分數最高的版本")
print("🖼️ 插畫 scene.png：", "有" if os.path.exists(f"{WEEK_DIR}/art/scene.png") else "⚠️ 沒有 → 先用臨時背景（請告訴 Claude）")

def _find_candidates():
    if CANDIDATES_DIR:
        return CANDIDATES_DIR
    hits = sorted(glob.glob("/kaggle/input/**/candidates/manifest.json", recursive=True))
    if hits:
        return os.path.dirname(hits[-1])
    wavs = [w for w in glob.glob("/kaggle/input/**/*.wav", recursive=True) if os.path.basename(w).count("__") >= 2]
    if wavs:
        return os.path.commonpath([os.path.dirname(w) for w in wavs])
    return None

CAND = _find_candidates()
if not CAND:
    raise StopRun("❌ 找不到 01 Generate 的候選曲。請在右側 Add Input → Notebook Output 加入「01 Generate」的輸出，再跑一次。")
n_wav = len(glob.glob(f"{CAND}/**/*.wav", recursive=True))
print(f"🎵 候選曲資料夾：{CAND}（{n_wav} 個 wav）")

SAMPLES = SAMPLES_DIR
if not SAMPLES:
    if glob.glob(f"{REPO_DIR}/samples/*/*.wav"):
        SAMPLES = f"{REPO_DIR}/samples"
    else:
        hits = [d for d in glob.glob("/kaggle/input/**/samples", recursive=True) if os.path.isdir(d)]
        SAMPLES = hits[0] if hits else f"{REPO_DIR}/samples"
n_smp = len(glob.glob(f"{SAMPLES}/*/*.wav"))
print(f"🪕 樂器音色：{n_smp} 個" + ("" if n_smp else "（沒有 → 這週不疊樂器，其他照常）"))
'''

C_RUN = r'''# 3) 執行整個後製流程（約 1–2 小時；每一步都會印出進度）
cmd = [sys.executable, "-m", "pipeline.run_week", "--week", WEEK, "--candidates", CAND,
       "--repo-root", REPO_DIR, "--out", OUT_DIR, "--work", WORK, "--samples", SAMPLES,
       "--loop-seconds", str(LOOP_SECONDS), "--preset", X264_PRESET]
if not CAPTIONS:
    cmd.append("--no-captions")
if MAX_TRACKS:
    cmd += ["--max-tracks", str(MAX_TRACKS)]
print("▶️ 開始：", " ".join(cmd[2:]))
proc = subprocess.Popen(cmd, cwd=REPO_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
tail = []
for line in proc.stdout:
    print(line, end="")
    tail = (tail + [line])[-40:]
if proc.wait() != 0:
    raise StopRun("❌ 後製過程出錯了。請到 Log 分頁把最後 20 行截圖給 Claude。")
print(f"\n✅ 完成！共花了 {(time.time() - RUN_START) / 60:.0f} 分鐘")
'''

C_LIST = r'''# 4) 要下載的檔案
def _size(p):
    s = os.path.getsize(p)
    return f"{s / 2**30:.2f} GB" if s > 2**30 else f"{s / 2**20:.1f} MB"

want = [("compilation.mp4", "⬇️ 要上傳 YouTube 的影片"),
        ("thumbnail.png", "⬇️ 縮圖"),
        ("youtube.txt", "⬇️ 標題、說明、標籤（Claude 會幫你整理）"),
        ("stream_loop.mp4", "（給直播主機，自動抓取，不用下載）")]
print("📦 Output 分頁裡的檔案：")
for name, note in want:
    p = os.path.join(OUT_DIR, name)
    print(f"  {'✅' if os.path.exists(p) else '❌'} {name:<18} {_size(p) if os.path.exists(p) else '':>10}  {note}")
st = sorted(glob.glob(f"{OUT_DIR}/stream_tracks/*.m4a"))
print(f"  ✅ stream_tracks/       {len(st)} 首  （給直播主機，自動抓取，不用下載）")
from pipeline.common import series_spec
rep = json.load(open(f"{OUT_DIR}/run_report.json", encoding="utf-8"))
v = rep["steps"].get("video", {})
loud = v.get("mp4_loudness", {})
print(f"\n⏱ 影片長度：{v.get('mp4_duration_s', 0) / 60:.1f} 分鐘　🔊 響度：{loud.get('lufs')} LUFS（目標 {series_spec(plan.get('series'))['lufs']}）")
print("\n".join(rep["steps"]["metadata"]["checks"]))
print("\n下一步：下載上面三個 ⬇️ 檔案，然後回 Claude 對話說「本週上傳資料」。")
'''


def build() -> nbformat.NotebookNode:
    nb = new_notebook()
    nb.cells = [new_markdown_cell(MD_INTRO), new_code_cell(CFG), new_markdown_cell(MD_RUN),
                new_code_cell(C_SETUP), new_code_cell(C_FIND), new_code_cell(C_RUN), new_code_cell(C_LIST)]
    nb.metadata = {
        "kaggle": {"accelerator": "none", "dataSources": [], "isGpuEnabled": False,
                   "isInternetEnabled": True, "language": "python", "sourceType": "notebook"},
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    }
    return nb


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "notebooks/02_assemble.ipynb"
    nb = build()
    nbformat.validate(nb)
    nbformat.write(nb, out)
    print("wrote", out)
