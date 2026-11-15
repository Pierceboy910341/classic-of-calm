# 05 系統設計（建置規格）

給所有建置成員的共同約定。設計原則：擁有者完全不懂技術，所以他只做「按按鈕」「聽歌」「下載、上傳」三件事。其他工作交給 Kaggle 筆記本、直播主機，以及 Claude 對話裡的 agent 團隊。

## 每週流程

```
[週一] Claude 對話：「開始本週製作」
   └─ 製作人 agent 依 docs/03-music-bible.md 與輪播表，產生 weekly/<WEEK>/plan.json
      （主打異獸、系列、約 30 首：5 首 source=suno 主打曲＋約 25 首 ACE-Step、插畫提示詞、標題、說明），
      並寫 weekly/<WEEK>/suno.md（給擁有者的 Suno 複製貼上單），推到 GitHub
   └─ 美術 agent 呼叫 Gemini 生圖 API → weekly/<WEEK>/art/scene.png、thumbnail.png
[週一] 擁有者：在 Kaggle 打開「01 Generate」→ 按 Save & Run All（背景約 1–2 小時，只做 ACE-Step 曲）
[週一～二] 擁有者：照 suno.md 在 Suno 網頁生成 5 首（每首 2–3 次，網頁上試聽免費），只下載最好的 5 個
      → 上傳到私人 Kaggle Dataset「classic-of-calm-suno」（New Version，檔名不用改）
[週二] Claude 對話：「審核本週歌曲」
   └─ 品管 agent 用 pipeline/kaggle_fetch.py 抓下候選曲與 Suno 檔，自動檢查（音量、靜音、削波、長度、尾奏）
   └─ Suno 5 首是擁有者已在網頁上聽過、選過的主打曲：只做自動檢查，不放進盲聽
   └─ 篩出約 30 首，轉成 mp3 試聽檔，用 SendUserFile 傳給擁有者
   └─ 擁有者回覆「留 1, 3, 5…」→ 寫入 weekly/<WEEK>/selection.json 並推送
[週二] 擁有者：在 Kaggle 打開「02 Assemble」→ Save & Run All（CPU，約 1–2 小時）
   └─ 自動找到 Suno 檔（用歌名配對）→ 轉成 <track_id>__suno__1.wav，和 ACE-Step 曲走同一條流程
   └─ 疊加真實樂器音色、母帶處理、交叉淡化、算出循環動畫、組成合輯 mp4
   └─ 輸出：compilation.mp4、thumbnail.png、youtube.txt（標題、說明、標籤、章節時間）、stream_tracks/*.m4a
[週三] 擁有者：從 Kaggle 輸出頁下載 mp4 和縮圖，依 youtube.txt 手動上傳 YouTube（記得勾選 AI 合成內容）
[自動] 直播主機每天用 Kaggle API 抓 02 Assemble 最新輸出的 stream_tracks，更新直播歌單（含 Suno 曲）
```

## 目錄結構

```
CLAUDE.md                 # 未來每個 Claude 對話的「團隊章程」與每週指令
.claude/agents/*.md       # agent 團隊：producer、music-director、art-director、qa-engineer、copywriter
docs/                     # 研究與規範
notebooks/01_generate.ipynb   # Kaggle GPU：讀 plan.json → 生成候選曲
notebooks/02_assemble.ipynb   # Kaggle CPU：讀 selection.json → 後製 → 合輯
pipeline/                 # Python 套件（notebook 02 與品管 agent 共用）
  qa.py  master.py  layer.py  compile.py  visuals.py  metadata.py
  suno.py                 # Suno 檔案配對（歌名）與轉檔
  kaggle_fetch.py         # 只用標準函式庫的 Kaggle 下載工具（notebook 輸出、私人 dataset）
samples/                  # 已確認可商用的中國樂器音色樣本（附 LICENSES.md）
stream/                   # VPS：install.sh、systemd 服務、FFmpeg 推流、同步、監控
weekly/<YYYY-Www>/        # plan.json、suno.md、art/、selection.json、youtube.txt
guides/                   # 給擁有者的繁中圖文操作手冊
```

## 資料格式

### weekly/<WEEK>/plan.json
```json
{
  "week": "2026-W47",
  "trial": false,
  "series": "study",                     // study | sleep | work
  "creature": {"no": 1, "id": "shengsheng", "zh": "狌狌", "en": "Shengsheng",
               "quote_zh": "…", "quote_en": "…", "source": "南山經"},
  "models": ["ace-step-1.5"],            // 預設只有 ACE-Step；"stable-audio-3" 程式保留（需 HF_TOKEN，目前不用）
  "tracks": [
    {"id": "s01", "series": "study", "title_en": "…", "title_zh": "…",
     "tags": "lofi hip hop, guzheng, rhodes, …", "negative": "vocals, singing, …",
     "bpm": 78, "key": "D dorian", "duration": 180, "seed": 1234,
     "layer": {"instrument": "guzheng", "role": "ornament"}},
    {"id": "s02", "series": "study", "source": "suno", "title_en": "Jade Slips at Midnight", "title_zh": "…",
     "tags": "…", "negative": "…", "bpm": 74, "key": "A minor", "duration": 190, "seed": 1235,
     "layer": {"instrument": "xiao", "role": "ornament"},
     "suno": {"styles": "74 BPM, A minor, lofi jazz hop, …, instrumental, no vocals",
              "exclude": "vocals, choir, rap, gong, trap hi-hats, chinese pop",
              "title": "Jade Slips at Midnight"}}
  ],
  "art": {"scene_prompt": "…", "thumbnail_prompt": "…"},
  "youtube": {"title": "…", "description": "…", "tags": ["…"]}
}
```

#### 每首歌的來源：`source`（選填）與 `suno` 區塊
- `source`：`"ace-step"`（預設，沒寫就是它）或 `"suno"`。**notebook 01 會略過 `source: "suno"` 的歌**。
- 每週 **5 首**標 `suno`：本週最強的概念，也是合輯的主打曲（Suno Pro 每月 20 次下載，約每週 5 次，不累積）。
- `suno` 區塊（只有 `source: "suno"` 才有，且必填）：
  - `styles`：貼進 Suno「Styles」欄的文字，依音樂聖經附錄 A 格式（`{BPM} BPM, {KEY}, <caption 去掉結尾 instrumental>, instrumental, no vocals`），**≤ 1000 字元**（建議 ≤ 400）。
  - `exclude`：貼進「More Options → Exclude styles」，4–8 項。
  - `title`：貼進「Song Title」，**必須等於 `title_en`**（notebook 02 用它配對檔案）。
- Suno 歌的 `tags`／`negative`／`seed`／`layer` 照常寫（`tags` 留作紀錄與換回 ACE-Step 的備案；`layer` 照常疊加）；`bpm`、`key`、`duration` 照常寫（合輯排序用；`duration` 只是目標，實際長度以下載檔為準）。
- Suno 的 Lyrics 欄**留空**＝純音樂（v5.5／v6 網頁版 Advanced 模式）。

### weekly/<WEEK>/suno.md
給擁有者的繁中複製貼上單：5 首各有 Title、Styles、Exclude，加上「生成 2–3 次，在網頁上試聽，只下載最好的 1 個」，以及上傳到 Kaggle dataset 的步驟。內容必須與 plan.json 的 `suno` 區塊一字不差。

### Suno 輸入資料夾（notebook 02 與品管 agent）
- 擁有者只維護**一個私人 Kaggle Dataset：`classic-of-calm-suno`**（擁有者 `piercezheng910341`）。每週用 New Version 上傳當週 5 個下載檔（MP3 或 WAV），**檔名不用改**；舊檔可以留著。
- notebook 02 加入它為 Input（`/kaggle/input/classic-of-calm-suno/`，會遞迴搜尋）；沒有這個名字時，任何不是 notebook 01 候選曲（`<id>__<model>__<take>.wav`）、也不在 `candidates/`、`samples/`、`stream_tracks/` 下的 mp3/wav 資料夾都視為 Suno 輸入。設定格 `SUNO_DIR` 可手動指定。
- 配對（`pipeline/suno.py`）：用 `suno.title` 比對檔名與檔案內嵌的標題（不分大小寫、標點、重音；容許 `(1)` 之類的尾巴與輕微拼錯）；檔名符合**其他週** Suno 歌名的舊檔會被略過；仍配不到的檔依檔名排序，按 plan 順序補上（`how: "order"`，品管要再聽一次確認）。
- 轉檔：`<track_id>__suno__1.wav`（44.1 kHz stereo PCM16），之後和候選曲走同一條 QA → 疊加 → 母帶 → 合輯流程；配對結果寫進輸出的 `suno_map.json`。
- **Suno 曲有檔就一定進合輯**（即使自動檢查標 fail、或 selection.json 漏列）；selection.json 已有順序時，漏列的 Suno 曲插在最順的位置（不動第一首與最後一首）。
- plan 有 Suno 歌卻一首都找不到時，notebook 02 停下來提醒（設定格 `REQUIRE_SUNO = False` 可略過）；部分缺少只警告。

### notebook 01 輸出（Kaggle kernel output）
`candidates/<track_id>__<model>__<take>.wav`（44.1 kHz stereo）＋ `candidates/manifest.json`：每筆含 file、track_id、model、take、seed、prompt、生成秒數。只含 `source` 不是 `suno` 的歌。
ACE-Step 預設 DiT：`acestep-v15-turbo`（2B；2026-11-13 在 Kaggle T4 實測每 60 秒音訊約 18–90 秒）。`acestep-v15-xl-turbo` 在 T4 float32 會 OOM，只當選用。

### weekly/<WEEK>/selection.json
```json
{"week": "2026-W47",
 "picks": [{"file": "s01__ace-step-1.5__1.wav", "order": 1, "fade_out": null, "notes": ""},
           {"file": "s02__suno__1.wav", "order": 2, "fade_out": null, "notes": "suno featured"}],
 "model_vote": {"ace-step-1.5": 0}}
```
Suno 曲的 `file` 一律是 `<track_id>__suno__1.wav`；`model_vote` 只計盲聽的生成模型（不計 Suno）。

### notebook 02 輸出
`compilation.mp4`（1920x1080、30 fps、AAC 320k）、`thumbnail.png`（1280x720）、`youtube.txt`、`stream_tracks/<n>_<slug>.m4a`（已響度正規化）、`stream_loop.mp4`（20–60 秒無縫循環，給直播用）、`suno_map.json`（有 Suno 曲時：哪個檔配到哪首）。

## 連線與憑證
- notebook 讀 repo：公開 repo 用 raw URL；私人 repo 用 Kaggle Secret `GITHUB_TOKEN`。兩種都要支援。
- notebook 02 讀 notebook 01 的輸出：Kaggle「Add Input → Notebook Output」，路徑在 `/kaggle/input/<slug>/`。
- notebook 02 讀 Suno 檔：Kaggle「Add Input → Datasets」加入私人 dataset `classic-of-calm-suno`。每週上傳新版本後，Input 面板若顯示有新版本要按更新（未實測 Kaggle 是否自動用最新版）。
- 直播主機用 Kaggle API（使用者名稱＋key）執行 `kaggle kernels output`。
- 品管 agent（Claude 環境）：Kaggle 憑證由 proxy 注入，`kaggle` CLI 會拒絕執行，所以一律用 `python -m pipeline.kaggle_fetch`（純 HTTPS、不帶 Authorization header）：
  - `kernel-output piercezheng910341/classic-of-calm-01-generate <dest>`（`ListKernelSessionOutput`）
  - `dataset piercezheng910341/classic-of-calm-suno <dest>`（`ListDatasetFiles` + `DownloadDataset` → 302 簽名網址）
- Suno：沒有 API。擁有者在網頁生成、試聽、按官方 Download。只有**訂閱 Pro 期間**生成、下載的歌才有商用權；每月 20 次下載，不累積到下個月。
- Gemini API key：只放在 Claude 環境的憑證系統，絕不寫進 repo。

## 音訊規格
- Study／Work：-14 LUFS、-1 dBTP；Sleep：-16 LUFS、-1.5 dBTP
- 交叉淡化：Study 3–5 秒、Work 2–4 秒、Sleep 6–10 秒
- 疊加樂器的響度比伴奏低 6–12 dB，送進共用殘響，讓聲音融在一起
