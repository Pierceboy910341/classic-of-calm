# 01 — 技術研究報告（Technical Research）

> 撰寫：Technical Research Lead｜日期：2026-11-13
> 範圍：AI 音樂工具、YouTube 政策風險、24/7 直播主機、插畫生成、YouTube 自動上傳、月預算
> 研究方法說明：本報告以 2026 年 11 月的網路搜尋結果為準。本次環境無法直接開啟部分官方頁面（developers.google.com、techcrunch.com 等被網路政策擋下），所以有些數字來自引用官方頁面的第三方整理。**標註「⚠️ 待驗證」的項目，開帳號或付款前請在官方頁面再確認一次。**

---

## 0. 一頁結論（TL;DR）

| 項目 | 首選 | 次選 |
|---|---|---|
| AI 音樂 | **Suno Premier（年繳，約 US$24/月）** | Suno Pro（US$10/月）+ ACE-Step 1.5（免費開源）補量 |
| 直播主機 | **OVHcloud VPS-1（2 vCore / 4 GB / 流量不限，約 US$4.5–5.5/月）** | Contabo 入門 VPS（約 €4.4/月） |
| 插畫生成 | **Gemini API 影像模型（Nano Banana 系列，每張約 US$0.04–0.07）** | Leonardo.ai 免費方案（輸出公開、商用條款需確認） |
| 自動上傳 | **自建 YouTube Data API 專案 + 送審（audit）**；審核通過前先以「私人上傳 → 擁有者手動公開」過渡 | Upload-Post 免費方案（每月 10 次上傳，已通過審核的第三方 API） |
| 月預算 | **方案 A 約 US$29（剛好低於 US$30）**；保守方案 B 約 US$16 | |

最大的發現：**Suno 自 2026-09-03 起限制每月下載數（Pro 20 首、Premier 60 首）**，而且商用權是跟著「下載」走的。我們每週約需 20 首（每月約 80 首），所以 Pro 不夠用，必須選 Premier（Suno Studio 匯出不限次數），不然就要用其他工具補量。

---

## 1. AI 音樂工具

### 1.1 比較總表

| 工具 | 月費 | 商用權 / 所有權 | 下載 / 產量限制 | API | Lofi / Ambient 品質 | 結論 |
|---|---|---|---|---|---|---|
| **Suno Pro** | US$10（年繳約 $8） | 付費訂閱期間**下載的歌曲**有商用權，取消訂閱後仍保留；免費方案生成的歌升級後不會追溯取得商用權 | 2,500 credits（約 500 首生成），但 **2026-09-03 起每月只能下載 20 首** | 無官方公開 API（非官方 API 違反 ToS） | 業界最佳之一（v6，2026-09 推出，單次最長約 8 分鐘） | 品質夠，**下載數不夠** |
| **Suno Premier** | US$30（**年繳約 $24/月**） | 同上 | 10,000 credits；標準下載 60 首/月；**透過 Suno Studio 匯出不限次數** | 無 | 同上，另有 Studio（多軌、stem、MIDI） | **首選** |
| Udio | 約 $10 / $30 | 2025-10 與 UMG 和解後，**下載功能關閉**；2026 新平台採「封閉花園」；最新評論認為目前**沒有任何方案明確給商用權** | 無法下載 = 無法上 YouTube | 無 | 好 | **不建議** |
| ElevenLabs Music | Starter 約 $5–6、Creator $22 | 付費方案可商用（音樂條款各方案細節 ⚠️ 待驗證） | 依 credits，入門方案量少 | 有 | 好，偏影視配樂 | 備案 |
| Google Lyria 3 Pro / 3.5（Gemini API） | 按量計費，約 **US$0.08/首**（30 秒片段 $0.04） | Google 不主張擁有輸出內容，但**發行/營利音樂的授權沒有明確寫出**（開發者論壇仍有未解答的疑問）；輸出帶 SynthID 浮水印 | 每首最長約 2–3 分鐘 | **有**（可全自動） | 不錯 | 授權釐清後是很好的自動化選項 |
| **ACE-Step 1.5**（開源） | 免費（需 GPU，<4 GB VRAM 即可） | **MIT 授權**，模型卡寫明生成的音樂可商用 | 無限制 | 本機執行 | 官方自稱介於 Suno v4.5 與 v5 之間（自評，沒有獨立的 lofi 評測） | **次選／補量** |

### 1.2 近期授權與唱片公司協議變化（重要）
- **Suno × Warner Music Group（2025-11）**：和解訴訟，Suno 承諾推出用 WMG 授權曲庫訓練的新模型。UMG 與 Sony 截至 2026 年中尚未和解。
- **Suno 新服務條款（2026-09-03 生效）**：依方案限制下載數（Pro 20/月、Premier 60/月、免費帳號終身 7 首），可加購下載但**價格沒有公開**。同一首歌下載 MP3＋WAV＋stems 只算 1 次，重複下載也只算 1 次，下載失敗不算。限制適用於 9/3 以前的舊作品。**Premier 用戶透過 Suno Studio 下載不受限制。**
- **Udio × UMG（2025-10-29）**：和解後立即停用下載，只開放 48 小時讓用戶搶救舊作品；2026 推出的授權平台作品「必須留在 Udio 平台內」。
- **Suno v6（約 2026-09-09）**：v6 / v6-wild 只開放給付費方案，單次生成最長約 8 分鐘，生成成本與 v5.5 相同（10 credits 產生 2 個版本）。

### 1.3 推薦
- **首選：Suno Premier（年繳）**
  理由：(1) 目前 lofi／jazzy／ambient 品質最好；(2) Studio 匯出不限次數，加上 60 次標準下載，足以應付每月約 80 首；(3) 付費期間下載的作品有商用權且永久保留；(4) 擁有者每週手動貼 prompt、下載的流程符合「15–30 分鐘/週」的人工步驟。
  注意：年繳要一次付約 US$288。**第一週請先實測「Studio 匯出」是否確實不扣下載額度**（⚠️ 待驗證，第三方說法不一）。
- **次選：Suno Pro（$10）+ ACE-Step 1.5**
  Pro 每月 20 次下載只用在 Study 與 Work/Café 的主打曲（盡量生成 6–8 分鐘的長曲）。Sleep/Relax 的 ambient 對品質較不敏感，改用 ACE-Step 1.5 生成（MIT、無上限）。ACE-Step 需要 GPU，可以由 Claude Code 準備好 Google Colab 筆記本，擁有者按「執行」即可，但比 Suno 多一道手續。
- **保留觀察：Gemini API 的 Lyria 3.x**：有 API、每首 US$0.08，可以全自動化。等 Google 明文允許音樂發行與營利後，可以替代 ACE-Step 的角色。

### 1.4 人工流程建議（擁有者每週約 20 分鐘）
1. Claude Code 每週產出 3 個系列的 prompt 清單（含 BPM、樂器、氛圍、Instrumental 開關）。
2. 擁有者貼到 Suno → 每個 prompt 會得到 2 個版本 → 試聽後挑 1 個 → 下載 WAV（或從 Studio 匯出）。
3. 把檔案丟進指定的雲端資料夾，之後的工作由程式接手。
4. **保留證據**：保存下載紀錄與訂閱收據（遇到 Content ID 爭議時用來證明權利）。

---

## 2. YouTube 政策風險

### 2.1 現行規則重點
- **「Inauthentic content」政策**：2025-07-15 由「repetitious content」更名，YouTube 強調這次沒有新增規則，也沒有全面限制 AI 內容。**2026-07** 再次說明，把不能營利的內容分成三類，其中第一類是「generic、repetitive、template-based、很容易用 AI／CGI／模板大量產出、影片之間差異很小」的內容。報導指出審查會看**整個頻道的模式**，而不只是單支影片。
- **使用 AI 本身不會讓頻道失去營利資格**；被針對的是「大量、近乎相同、缺乏原創投入」的內容。有些第三方指南把「通用的 beat 合輯、原封不動上傳文字轉歌曲的輸出」列為主要目標，但也有指南認為原創 lofi／AI 助眠內容仍然可行（各家說法不一）。
- **Altered or synthetic content 揭露**：Studio 的揭露設定主要針對「寫實」內容。2026-05 起 YouTube 會**自動偵測並標示** AI 內容，長影片的標籤移到播放器正下方。不過**非寫實、動畫或只有輕微修改的內容**仍然只在說明欄顯示。YouTube 表示**標籤本身不影響推薦與營利**。YouTube Music 也開始標示「主要由生成式 AI 製作」的歌曲。
- **Content ID**：Content ID 是比對音訊指紋，不是 AI 偵測器。主要風險有：(a) AI 生成的曲子剛好接近已登記的作品；(b) 有人把我們的曲子重新上傳並登記 Content ID，反過來對我們提出聲明（目前多為案例推演，沒有確認的實例）。被誤判時可以提出異議（dispute）。

### 2.2 本頻道必須做的事（保持可營利）
1. **每支影片都要有實質差異**：每週合輯使用新曲為主（不要把同一批曲子反覆重組成「新」合輯），每支影片都要有新插畫或至少新的場景變化，並附上曲目時間軸。
2. **三個系列各有清楚的身分**：不同的視覺世界觀、配色和角色（原創，不要模仿 Chillhop 的角色），讓頻道看起來是經過策劃的品牌，而不是模板工廠。
3. **標題和說明不要套用同一個模板**：Claude 每週撰寫不同的說明，例如季節、場景故事、這週的曲目亮點。
4. **公開透明**：在說明欄和「關於」頁寫明「Music generated with AI tools (Suno) and curated by [頻道名]; artwork AI-assisted and animated in-house」。Studio 的 altered/synthetic 開關建議**保守開啟**，因為不影響營利。
5. **人工策劃證據**：擁有者實際試聽與挑選曲子，保留紀錄（可以在 Claude Code 對話中留下選曲理由）。
6. **不要把 AI 曲送進 Content ID**：也就是不要透過 DistroKid 等通路開啟 YouTube Content ID 變現，以免和自己的直播與影片衝突、或誤傷他人。
7. **上傳頻率要克制**：每週 1 支長片加直播就夠了。不要短時間大量上傳相似影片。
8. 營利門檻依現行 YPP 規定（1,000 訂閱 + 12 個月內 4,000 小時公開長影片觀看時數，或 Shorts 觀看條件）⚠️ 送審前再確認。

---

## 3. 24/7 直播主機

### 3.1 市場現況（2026）
- **Hetzner 已經不再便宜**：2026-04 漲價 30–37%，2026-06-15 雲端再漲。CX23 €3.99→€5.49 而且**常常無法下單**；CPX22 漲到 €19.49。**不建議。**
- **Oracle Cloud Always Free**：ARM 額度據報導在 2026-08-18 從 4 OCPU/24 GB 減半到 2 OCPU/12 GB，搶不到機器、有回收風險、沒有 SLA。**不建議作為主要機器**。
- **OVHcloud VPS-1**：2 vCore / 4 GB RAM / 40 GB NVMe / **流量不限**（500 Mbps），美國頁面 US$4.54/月，歐洲 €4.49（未稅）。**首選。**
- **Contabo**：2 vCPU / 4 GB，約 €4.4/月，「不限流量」附帶條件，穩定性評價兩極。**次選。**

### 3.2 規格與 CPU 需求
| 模式 | CPU 需求（約） | 頻寬／月 |
|---|---|---|
| **預先渲染的 loop 影片 + `-c:v copy`（不重新編碼影像），只編碼音訊** | **<0.5 vCPU** | 1080p @ 4–4.5 Mbps ≈ 1.3–1.5 TB |
| 即時編碼 720p30（x264 veryfast） | 約 1–1.5 vCPU | 2.5–3 Mbps ≈ 0.8–1 TB |
| 即時編碼 1080p30（x264 veryfast） | 約 2–3 vCPU（2 vCore VPS 會很吃緊） | 4.5–6 Mbps ≈ 1.5–2 TB |

→ **建議：1080p30 + 預先渲染 loop + 影像 copy**。所以 2 vCore 便宜 VPS 就夠，而且必須選**流量不限**的方案。

### 3.3 技術要點（給工程實作參考）
1. **預先渲染**：用 Python/FFmpeg 把插畫加上雨、蒸氣、燈光閃爍，渲染成 30–120 秒的**無縫循環** MP4（H.264 High、yuv420p、30 fps、**GOP = 2 秒，關鍵影格固定**、CBR 或 capped VBR 約 4–4.5 Mbps），符合 YouTube 直播編碼規格，才能直接 `copy`。
2. **推流**：`ffmpeg -re -stream_loop -1 -i loop.mp4` 加上**持續播放的音訊播放清單**（concat 播放清單或一個長的 radio 程序），`-map 0:v -map 1:a -c:v copy -c:a aac -b:a 160k -f flv rtmp://a.rtmp.youtube.com/live2/KEY`。
3. **穩定性**：用 systemd 管理，崩潰時自動重啟。每天在低峰時段排程重啟一次，避免時間戳記漂移。每次 loop 重新開始時可能出現瞬間斷點，需要在第一週觀察。
4. **不要在畫面即時疊「Now Playing」文字**：會被迫重新編碼影像。改用直播說明欄或置頂留言列出曲目。
5. **同一台 VPS 也負責每週合輯的渲染**：同樣用 loop 影片 copy 加上混好的音訊，1–2 小時的影片幾分鐘就能產生，不需要另外租機器。
6. 三個系列的直播：一台 VPS 推**一條** 24/7 流最穩。建議先開 1 條（例如 Study），其他系列以每週長片為主，之後再評估是否加第 2 條流（頻寬加倍，CPU 仍然很低）。

---

## 4. 插畫生成工具

| 工具 | 費用 | 商用 / 隱私 | 適合度 |
|---|---|---|---|
| **Gemini API 影像模型（Nano Banana = gemini-2.5-flash-image）** | **US$0.039/張**（batch $0.0195）。⚠️ 此模型預計 **2027-03-15 退役**，接替的 Nano Banana 2 約 $0.067/張（1K） | Google 條款不主張擁有輸出內容，由使用者負責使用方式；輸出含 SynthID 隱形浮水印；API 方案沒有可見浮水印 | **首選**：便宜、可以由 Claude Code 程式化呼叫、擅長「以參考圖維持角色與畫風一致」（方便生成分層素材做動畫） |
| Leonardo.ai 免費方案 | 每天 150 tokens | 免費方案輸出**公開**；商用權各來源說法互相矛盾 ⚠️ | 次選（或付費 Essential 約 $12） |
| Ideogram | 免費（公開）；付費 $7–15/月 | 付費才是私人且明確可商用 | 價格資訊不一 |
| Midjourney | $10 起，私人模式要 $60 | 品質最佳，但超出預算 | 不建議 |

用量估計：每週 1 張主視覺加分層素材（前景、背景、窗戶、杯子等）約 5–10 張，加上縮圖 → **每月約 30–40 張 ≈ US$1.5–2.5**，嘗試失敗的張數也算在內。

建議作法：先為三個系列各建立一張「風格參考圖」與角色設定，之後的每張圖都附上參考圖生成，確保手繪風格一致。動畫所需的分層素材（例如分開的雨幕遮罩、燈光區域）用圖像編輯或程式遮罩處理。

---

## 5. YouTube Data API 自動上傳

### 5.1 現況
- **審核（audit）限制**：2020-07-28 之後建立、**未通過審核**的 API 專案，用 `videos.insert` 上傳的影片會被**鎖成私人（private）**，擁有者會收到「locked as private」的通知信，必須通過 YouTube API Services 合規審核才會解除。⚠️ 有第三方指出，2026-10 時的官方 `videos.insert` 文件似乎寫著未驗證專案「不再限制為私人」，但還沒有找到修訂紀錄證實。**實作時一律讀取 API 回傳的 `status.privacyStatus` 確認實際狀態。**
- **配額**：2025-12-04 起上傳成本從約 1,600 units 降到約 100 units。2026-06-01 起改為分桶配額：`videos.insert` 預設**每專案每天 100 次**，其他端點共用 10,000 units。我們每週上傳 1 支，配額完全不是問題。
- **OAuth 陷阱**：同意畫面如果停在「Testing」狀態，refresh token **7 天後失效**，每週都要重新登入。要改成「In production」（未驗證的 app 會顯示警告，但自己的帳號可以點「繼續」）。Token 如果 6 個月沒有使用也會失效。⚠️「未驗證但已發佈」的 app 是否仍受 7 天限制，各來源說法不一，第一週需實測。

### 5.2 非技術擁有者需要親自做的步驟（約 30–45 分鐘，一次性；Claude Code 會逐步引導）
1. 用頻道擁有者的 Google 帳號登入 Google Cloud Console → 建立專案。
2. 啟用「YouTube Data API v3」。
3. 設定 OAuth 同意畫面（External），加入 `youtube.upload` 權限範圍，把自己加為測試使用者，然後**改成 In production**。
4. 建立 OAuth 用戶端（Desktop app），下載 `client_secret.json` 交給 Claude Code。
5. 第一次執行上傳程式時，在瀏覽器登入並按「允許」（之後由程式自動更新 token）。
6. 填寫 **YouTube API Services Audit / Quota 表單**（說明用途：自有頻道每週上傳 1 支影片），等待回覆，通常需要數週 ⚠️。
7. YouTube 頻道完成電話驗證（直播與長片都需要），並提早 24 小時開通直播功能。

### 5.3 實際可行的替代方案
| 方案 | 說明 | 成本 |
|---|---|---|
| **A. 自建 API（首選）** | 審核通過前：程式以 private 上傳並排好標題、說明、縮圖，擁有者在 Studio 按「公開」（約 1 分鐘）。如果被「鎖私人」無法改，就改用 B 或 C | $0 |
| **B. Upload-Post 免費方案（次選）** | 第三方已通過審核的 API，免費方案每月 10 次上傳（每週 1 支夠用），但免費方案的 FFmpeg 處理只有 30 分鐘，長片可能受限 ⚠️ | $0（付費 $16–24/月，超出預算） |
| C. 手動上傳 | Claude 產出標題、說明、標籤、縮圖檔，擁有者拖進 YouTube Studio 排程 | $0，約 5 分鐘/週 |

---

## 6. 月預算表（US$）

### 方案 A — 品質優先（推薦）
| 項目 | 選擇 | 月費 |
|---|---|---|
| AI 音樂 | Suno Premier（年繳 $288 ÷ 12） | **$24.00** |
| 直播／渲染主機 | OVHcloud VPS-1（2 vCore/4 GB/流量不限） | **$4.54**（未稅；如需加 VAT 約 $5.5） |
| 插畫 | Gemini API（約 30–40 張） | **約 $0.50–2.50**（實際每週只需 3–5 張新圖時約 $0.5） |
| YouTube 上傳 | 自建 Data API | $0 |
| 網域／其他 | 不需要 | $0 |
| **合計** | | **約 US$29–29.9**（剛好在 $30 以內，緩衝很小） |

> 風險：如果適用 VAT／匯率不利，或插畫張數較多，可能小幅超過 $30。控制方法：每月限制在 15 張圖以內，或改用方案 B。

### 方案 B — 保守省錢（次選）
| 項目 | 選擇 | 月費 |
|---|---|---|
| AI 音樂 | Suno Pro（月繳；年繳約 $8） | $10.00 |
| AI 音樂補量 | ACE-Step 1.5（Google Colab 免費 GPU） | $0 |
| 主機 | OVHcloud VPS-1 | $4.54–5.50 |
| 插畫 | Gemini API | 約 $0.50–1.50 |
| 上傳 | 自建 API／Upload-Post 免費 | $0 |
| **合計** | | **約 US$15–17** |

> 方案 B 的代價：Suno 每月只有 20 首可下載，每週合輯會有較高比例的 ACE-Step 曲子（品質略低，擁有者也要多一個 Colab 步驟）。

**建議**：先以**方案 B 的月繳 Pro 試營運 1 個月**，驗證 Studio 匯出規則、直播穩定度與觀眾反應，確認後再轉成方案 A 的 Premier 年繳。

---

## 7. 待辦與待驗證清單
- [ ] Suno：確認 Premier 的 Studio 匯出不扣下載額度，以及加購下載的價格（官方 Help Center）。
- [ ] YouTube Data API：確認 `videos.insert` 對未驗證專案的私人限制現況。
- [ ] OAuth：確認「In production 但未驗證」的 token 是否仍然 7 天過期。
- [ ] OVHcloud：確認擁有者所在地區的含稅價格與可用機房（建議選北美或歐洲，靠近 YouTube ingest）。
- [ ] Lyria／Gemini：持續觀察 Google 是否明文允許 AI 音樂營利發行。
- [ ] YPP：送審前重讀官方 inauthentic content 政策原文。

---

## 參考來源
**AI 音樂**
- Suno 官方：An update to our downloads policy and ToS — https://suno.com/blog/suno-updates-tos
- Suno Help：Upcoming Changes FAQ — https://help.suno.com/en/articles/13614785
- Suno Help：How many downloads come with my subscription? — https://help.suno.com/en/articles/13926209
- Suno Pricing 2026（diyai）— https://diyai.io/ai-tools/audio-generation/suno-pricing/
- Suno Download Limits 2026（veena.studio）— https://www.veena.studio/blog/suno-download-limits
- Suno Premier 60 download（Jack Righteous）— https://jackrighteous.com/blogs/guides-using-suno-ai-music-creation/suno-premier-60-song-download-limit-september-3-2026
- Suno Pricing（lumimusic）— https://lumimusic.ai/blog/suno-pricing
- Suno v6 vs v5.5 — https://hookgenius.app/learn/suno-v6-vs-v55/
- RouteNote：Suno 20 monthly downloads — https://routenote.com/blog/suno-announces-20-monthly-downloads-and-new-music-industry-models/
- Udio 停用下載（WebProNews）— https://www.webpronews.com/udio-halts-ai-song-downloads-after-copyright-settlement-with-umg-warner
- UMG × Udio 和解（news4jax/AP）— https://www.news4jax.com/business/2025/10/30/universal-music-and-ai-song-generator-udio-settle-lawsuit-and-partner-on-new-ai-music-platform/
- Udio pricing 2026 — https://dailyaifixs.com/blog/udio-pricing-2026-only-pro-can-sell-songs
- ACE-Step 1.5 模型卡 — https://huggingface.co/ACE-Step/acestep-v15-base/blob/main/README.md
- ACE-Step 1.5（ComfyUI Wiki）— https://comfyui-wiki.com/en/models/ace-step/ace-step-v1-5
- ElevenLabs pricing 2026 — https://bigvu.tv/blog/elevenlabs-pricing-2026-plans-credits-commercial-rights-api-costs/
- Lyria API pricing（BenchLM）— https://benchlm.ai/media-pricing/lyria
- Lyria 3.5 Gemini API guide — https://aicybr.com/blog/google-lyria-3-5-gemini-api-guide
- Lyria 發行授權疑問（Google AI 論壇）— https://discuss.ai.google.dev/t/can-music-generated-with-lyria-3-5-gemini-api-gemini-app-be-distributed-to-streaming-services-through-a-distributor-like-distrokid/191171
- Gemini API Additional Terms（archive）— https://ai.google.dev/gemini-api/terms-archive/terms_10_07_25

**YouTube 政策**
- TechCrunch（2026-07-20）— https://techcrunch.com/2026/07/20/youtube-clarifies-policies-around-ai-slop-and-upsetting-videos/
- AIR Media-Tech 2026 時間軸 — https://air.io/en/monetization/youtube-monetization-policy-changes-2026-a-complete-dated-timeline
- PPC Land：inauthentic content — https://ppc.land/youtube-clarifies-inauthentic-content-policy-changes/
- Metricool：What counts as slop — https://metricool.com/youtube-ai-content-rules-monetization/
- AI music monetization 2026（OutlierKit）— https://outlierkit.com/resources/ai-generated-music-youtube-monetization-2026/
- 自動標示 AI 影片（Music Business Worldwide）— https://www.musicbusinessworldwide.com/youtube-will-now-automatically-detect-and-label-ai-videos-even-when-creators-dont-disclose-it/
- AI 標籤位置（PPC Land）— https://ppc.land/youtube-shifts-generative-ai-labels-to-spots-viewers-will-actually-see/
- AI disclosure 2026（AIR）— https://air.io/en/youtube-hacks/youtube-ai-disclosure-in-2026-label-it-yourself-or-youtube-will
- YouTube Music AI 標示 — https://ppc.land/youtube-music-labels-songs-made-primarily-with-generative-ai/
- Content ID 與 AI 音樂 — https://sunowatermark.com/youtube-content-id-ai-music/
- No-AI 播放清單現象 — https://getcoai.com/news/youtube-creators-fight-ai-music-flood-with-no-ai-playlist-labels/

**主機／直播**
- Hetzner 漲價（Tom's Hardware）— https://www.tomshardware.com/tech-industry/hetzner-to-raise-prices-by-up-to-37-percent-from-april-1
- Hetzner 2026-06 漲價（wz-it）— https://wz-it.com/en/blog/hetzner-price-increase-june-2026-cpx-ccx-alternatives/
- Hetzner 官方價格調整 — https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/
- Hetzner 替代方案比價（2026-10）— https://dev.to/hostingsift/is-hetzner-still-the-cheapest-vps-we-priced-24-alternatives-october-2026-271g
- Contabo 價格 — https://contabo.com/en-us/pricing/
- Oracle Always Free 縮減 — https://braindetox.kr/en/posts/oracle_always_free_tier_reduced_2026.html
- 24/7 FFmpeg 直播（DEV）— https://dev.to/devlobb/how-i-built-a-stable-247-youtube-livestream-on-a-vps-using-ffmpeg-no-saas-required-1bid
- FFmpeg vs OBS CPU — https://www.host-stage.net/case-study/ffmpeg-vs-obs
- Lofi radio VPS 指南 — https://space-node.net/blog/lofi-radio-stream-vps-guide-2026

**插畫**
- Nano Banana API pricing（BenchLM）— https://benchlm.ai/media-pricing/nano-banana
- Nano Banana 各版本價格 — https://simplemetrics.xyz/how-much-per-image-is-nano-banana-and-nano-banana-pro/
- Gemini 影像模型退役資訊 — https://www.developersdigest.tech/models/image-generation/google-gemini-api
- 免費方案限制 2026 — https://nesyona.com/articles/ai-image-generator-free-tier-limits-2026
- Leonardo pricing 2026 — https://dev.to/techsifted/leonardo-ai-pricing-2026-free-credits-paid-plans-and-api-costs-16a2

**YouTube API**
- 上傳配額變化（timetopost）— https://timetopost.co/blog/how-to-upload-videos-youtube-api/
- videos.insert 指南（bulkpublish）— https://www.bulkpublish.com/blog/youtube-data-api-upload-guide/
- 未驗證 App 403（Ayrshare）— https://www.ayrshare.com/solutions/google-api-error-403-unverified-app-how-to-fix-the-audit-pipeline/
- OAuth refresh token 7 天 — https://www.unipile.com/google-oauth-refresh-token/
- Upload-Post 價格與限制 — https://docs.upload-post.com/resources/pricing-and-limits
