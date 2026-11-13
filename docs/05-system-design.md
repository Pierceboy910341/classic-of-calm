# 05 系統設計（建置規格）

給所有建置成員的共同約定。設計原則：擁有者完全不懂技術，所以他只做「按按鈕」「聽歌」「下載、上傳」三件事。其他工作交給 Kaggle 筆記本、直播主機，以及 Claude 對話裡的 agent 團隊。

## 每週流程

```
[週一] Claude 對話：「開始本週製作」
   └─ 製作人 agent 依 docs/03-music-bible.md 與輪播表，產生 weekly/<WEEK>/plan.json
      （主打異獸、系列、約 60 組提示詞、插畫提示詞、標題、說明），推到 GitHub
   └─ 美術 agent 呼叫 Gemini 生圖 API → weekly/<WEEK>/art/scene.png、thumbnail.png
[週一] 擁有者：在 Kaggle 打開「01 Generate」→ 按 Save & Run All（背景約 2–6 小時）
[週二] Claude 對話：「審核本週歌曲」
   └─ 品管 agent 用 Kaggle API 抓下候選曲，自動檢查（音量、靜音、削波、長度、尾奏）
   └─ 篩出約 30 首，轉成 mp3 試聽檔，用 SendUserFile 傳給擁有者
   └─ 擁有者回覆「留 1, 3, 5…」→ 寫入 weekly/<WEEK>/selection.json 並推送
[週二] 擁有者：在 Kaggle 打開「02 Assemble」→ Save & Run All（CPU，約 1–2 小時）
   └─ 疊加真實樂器音色、母帶處理、交叉淡化、算出循環動畫、組成合輯 mp4
   └─ 輸出：compilation.mp4、thumbnail.png、youtube.txt（標題、說明、標籤、章節時間）、stream_tracks/*.m4a
[週三] 擁有者：從 Kaggle 輸出頁下載 mp4 和縮圖，依 youtube.txt 手動上傳 YouTube（記得勾選 AI 合成內容）
[自動] 直播主機每天用 Kaggle API 抓 02 Assemble 最新輸出的 stream_tracks，更新直播歌單
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
samples/                  # 已確認可商用的中國樂器音色樣本（附 LICENSES.md）
stream/                   # VPS：install.sh、systemd 服務、FFmpeg 推流、同步、監控
weekly/<YYYY-Www>/        # plan.json、art/、selection.json、youtube.txt
guides/                   # 給擁有者的繁中圖文操作手冊
```

## 資料格式

### weekly/<WEEK>/plan.json
```json
{
  "week": "2026-W47",
  "trial": true,
  "series": "study",                     // study | sleep | work
  "creature": {"no": 1, "id": "shengsheng", "zh": "狌狌", "en": "Shengsheng",
               "quote_zh": "…", "quote_en": "…", "source": "南山經"},
  "models": ["ace-step-1.5", "stable-audio-3"],   // trial 週兩個都跑
  "tracks": [
    {"id": "s01", "series": "study", "title_en": "…", "title_zh": "…",
     "tags": "lofi hip hop, guzheng, rhodes, …", "negative": "vocals, singing, …",
     "bpm": 78, "key": "D dorian", "duration": 180, "seed": 1234,
     "layer": {"instrument": "guzheng", "role": "ornament"}}
  ],
  "art": {"scene_prompt": "…", "thumbnail_prompt": "…"},
  "youtube": {"title": "…", "description": "…", "tags": ["…"]}
}
```

### notebook 01 輸出（Kaggle kernel output）
`candidates/<track_id>__<model>__<take>.wav`（44.1 kHz stereo）＋ `candidates/manifest.json`：每筆含 file、track_id、model、take、seed、prompt、生成秒數。

### weekly/<WEEK>/selection.json
```json
{"week": "2026-W47",
 "picks": [{"file": "s01__ace-step-1.5__1.wav", "order": 1, "fade_out": null, "notes": ""}],
 "model_vote": {"ace-step-1.5": 0, "stable-audio-3": 0}}
```

### notebook 02 輸出
`compilation.mp4`（1920x1080、30 fps、AAC 320k）、`thumbnail.png`（1280x720）、`youtube.txt`、`stream_tracks/<n>_<slug>.m4a`（已響度正規化）、`stream_loop.mp4`（20–60 秒無縫循環，給直播用）。

## 連線與憑證
- notebook 讀 repo：公開 repo 用 raw URL；私人 repo 用 Kaggle Secret `GITHUB_TOKEN`。兩種都要支援。
- notebook 02 讀 notebook 01 的輸出：Kaggle「Add Input → Notebook Output」，路徑在 `/kaggle/input/<slug>/`。
- 直播主機與品管 agent 用 Kaggle API（使用者名稱＋key）執行 `kaggle kernels output`。
- Gemini API key：只放在 Claude 環境的憑證系統，絕不寫進 repo。

## 音訊規格
- Study／Work：-14 LUFS、-1 dBTP；Sleep：-16 LUFS、-1.5 dBTP
- 交叉淡化：Study 3–5 秒、Work 2–4 秒、Sleep 6–10 秒
- 疊加樂器的響度比伴奏低 6–12 dB，送進共用殘響，讓聲音融在一起
