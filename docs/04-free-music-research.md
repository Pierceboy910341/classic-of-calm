# 04 — 免費＋可商用 AI 音樂研究（國風 × Lofi／山海經主題）

> 撰寫：Technical Research Lead｜日期：2026-11-13
> 新需求：(1) 不訂閱 Suno，音樂生成要**免費**；(2) 頻道會營利，**必須可商用**；(3) 曲風要在 lofi／ambient／chill beats 中融入**古箏、琵琶、簫／笛子、二胡、編鐘、古琴**；(4) 視覺主題改為**山海經**；(5) YouTube 上傳改為**全手動**（取消 YouTube Data API 的工作，01 報告第 5 節作廢）。
> 研究方法：2026-11 網路搜尋。本環境無法直接開啟多數官方頁面，所以部分資訊來自引用官方頁面的第三方整理。**標 ⚠️ 的項目，正式使用前請打開官方 LICENSE 檔或條款再確認。**

---

## 0. 結論（TL;DR）

- **免費又確定可商用的「線上服務」在 2026 年幾乎不存在**：Suno、Udio、Mureka、AIVA、ElevenLabs、Mubert、Stable Audio 線上版的免費方案都是非商用或沒有寫清楚；Riffusion（現改名 Google Flow Music）的說法互相矛盾。→ **唯一可靠的路是開源模型＋免費 GPU。**
- **首選管線**：**ACE-Step 1.5 XL（MIT 授權）在 Kaggle 免費 GPU 上批次生成** → 用授權清楚的國樂取樣做「主旋律點綴層」 → 在 VPS 上用 Python／FFmpeg 自動混音、母帶處理、串成合輯。
- **次選管線**：**Stable Audio 3.0 Medium**（Stability AI Community License，年營收低於 US$100 萬可免費商用，官方表示使用授權資料訓練）在同一個 Kaggle 筆記本執行，特別適合 Sleep／Relax 的 ambient 系列。
- **每週 50–60 次生成，在 Kaggle 每週約 30 GPU 小時的額度內綽綽有餘**（估計只會用掉 2–6 小時）。
- **擁有者每週約 60–90 分鐘**（主要時間花在試聽與挑歌），比 Suno 方案的 15–30 分鐘多，因為開源模型的「成品率」比較低。
- **直播主機**：仍建議 **OVHcloud VPS-1（約 US$4.5–5.5/月）**。Oracle Cloud Always Free 可以當「零元實驗機」，但不建議當唯一主機。
- **每月總成本**：約 **US$5–8**（VPS＋少量插畫 API），音樂 US$0。

---

## 1. 開源音樂模型比較

| 模型 | 程式碼授權 | **權重授權** | 可否商用 | Lofi／器樂品質 | 國樂器表現 | VRAM | 單首長度 | 速度 |
|---|---|---|---|---|---|---|---|---|
| **ACE-Step 1.5**（2026-01/02） | MIT | **MIT**（模型卡寫明「生成音樂可商用」；有一個第三方 wiki 寫成 Apache-2.0，兩者都可商用） | ✅ | 官方自評介於 Suno v4.5 與 v5 之間；NYU 上海的評測指出在 SongEval 勝過 Suno v5（以歌曲為主） | 宣稱支援「1000+ 樂器與風格、細緻音色描述」；**沒有找到古箏／二胡的獨立測試** ⚠️ 需要自己實測 | Turbo 版 **<4 GB** | 依平台 30 秒到 5–10 分鐘不等（官方 repo 為準）⚠️ | Turbo 在 A100 上 <2 秒、RTX 3090 上 <10 秒（T4 估計約 30–90 秒，未證實） |
| **ACE-Step 1.5 XL**（2026-04-02） | MIT | MIT（XL 沿用，沒有另外標示）⚠️ | ✅ | 媒體稱「Suno v5 以上」（自評）、ComfyUI 官方稱「commercial-grade」 | 同上，4B 參數音色更細 | **≥12 GB（offload＋量化）；建議 20 GB** → Kaggle T4（16 GB）可以跑但要開 offload | 約 10–360 秒（XL 指南） | 比 Turbo 慢，T4 估計每首 1–4 分鐘 ⚠️ |
| **Stable Audio 3.0 Small／Medium**（2026-05） | Stability 授權 | **Stability AI Community License**：個人或組織年營收 **< US$100 萬** 可免費商用，超過要買 Enterprise | ✅（附門檻） | 器樂與氛圍音樂是它的強項；官方強調使用**授權資料**訓練 | 沒有專門資料 ⚠️ | 沒有公開數字（Small 可以在手機上跑；Medium 估計 T4 可以跑）⚠️ | Small 約 2 分鐘；**Medium 約 6 分 20 秒** | 沒有找到數據 |
| Stable Audio Open 1.0／Open Small（舊版） | — | Community License（同上門檻） | ✅（附門檻） | 偏音效與 loop | — | 低 | **只有 47 秒／11 秒** → 不適合整首曲子 | 快 |
| **MusicGen／AudioCraft**（Meta） | MIT | **CC-BY-NC 4.0** | ❌ **非商用**（程式碼是 MIT 也不會讓權重變成可商用） | 器樂不錯 | 普通 | 約 8–16 GB | 30 秒（可延伸） | — |
| **YuE**（第 1 代） | Apache 2.0 | 2025-01-30 改為 Apache 2.0，開發者鼓勵商用並希望標註「YuE by HKUST/M-A-P」⚠️ | ✅（建議附註名） | **以人聲歌曲為主**，不適合純器樂 lofi | 中文歌曲訓練多 | **完整歌曲建議 80 GB**；RTX 4090 生成 30 秒約要 6 分鐘 | 數分鐘 | **很慢** → 免費 GPU 不可行 |
| **YuE2-3B**（2026-09） | — | 多個來源寫 **CC-BY-NC 4.0** ⚠️ | ❌ | 自稱勝過 Suno v5／v6（自評） | 評測集有 94 個中文 prompt | 24 GB | 完整歌曲 | — |
| **DiffRhythm 2**（ASLP-NWPU × 小米） | Apache 2.0 | **Apache 2.0**（HF README）。但舊版 README 曾寫「We do not make any profit from this model」⚠️ | ✅（大致可以，需確認） | 以「歌詞→歌曲」為主，純器樂需要測試 | 中文團隊，可能比較好（未證實） | 約 8 GB（估計） | 約 4–5 分鐘 | 快（flow matching） |
| **SongBloom**（騰訊 AI Lab） | 自訂 LICENSE | **沒有找到官方條款**；鏡像標示 Apache-2.0 不可信 ⚠️ | ❓ 不建議 | 以歌曲為主 | — | — | 150 秒 checkpoint | — |
| **SongGeneration 2／LeVo 2**（騰訊） | 自訂 License Terms | 自訂條款，vLLM 社群也標示「待審核」⚠️ | ❓ 不建議 | 歌曲為主 | 中文強 | 16–22 GB（大模型） | — | — |

### 1.1 篩選結論
- **可以安心商用、而且適合純器樂 lofi 的**：**ACE-Step 1.5／1.5 XL（MIT）**、**Stable Audio 3.0 Small／Medium（營收門檻內）**。
- **排除**：MusicGen（非商用）、YuE2（非商用）、YuE 第 1 代（太慢、主打人聲）、SongBloom 與 SongGeneration（授權不清楚）。
- **觀察**：DiffRhythm 2（Apache 2.0，但要確認「no profit」那句話是否已移除）。

### 1.2 國樂器的現實評估（重要）
- 目前**沒有任何**公開評測專門測試古箏、二胡、琵琶的生成品質。依經驗推估：**古箏、笛子、二胡**這類常見音色有機會表現不錯；**編鐘、古琴、簫**很少見，AI 很容易生成「泛亞洲五聲音階」的刻板音色，甚至變成日本箏或尺八。
- 因此建議採用**「AI 生成伴奏底層＋真實取樣主旋律點綴」的混合作法**（見第 4 節），確保樂器辨識度，同時也能增加每首曲子的「人工創作投入」（對 YouTube 的 inauthentic content 政策有幫助）。
- ACE-Step 1.5 支援**參考音訊、重繪（repaint）、LoRA 微調**。之後可以用授權清楚的國樂錄音訓練一個小型「國風 LoRA」（Kaggle 也能跑），長期提升音色的正確性。

---

## 2. 免費 GPU 平台（給非技術擁有者）

| 平台 | 免費額度（2026-11） | 對非技術擁有者的易用性 | 結論 |
|---|---|---|---|
| **Kaggle Notebooks** | **約 30 GPU 小時／週**（P100 16 GB 或 2×T4），單次最長 **12 小時**；需要手機驗證才能開 GPU 和網路 ⚠️ 額度會浮動，以帳號設定頁顯示的為準 | ⭐⭐⭐⭐ 可以按「**Save Version → Save & Run All**」在背景執行，**關掉瀏覽器也會繼續跑**，跑完後到 Output 下載 zip | **首選** |
| Google Colab 免費版 | T4，單次最長約 12 小時，閒置約 90 分鐘會斷線；**Google 不公開額度、也不保證有 GPU**；2026-09 的方案更新不影響免費版 | ⭐⭐⭐ 要保持分頁開著，常常拿不到 GPU | 備援 |
| **Hugging Face Spaces（ZeroGPU）** | 免費帳號每天約 **5 分鐘** GPU（舊文件寫 3.5 分鐘）⚠️；PRO（US$9/月）約 40 分鐘 | ⭐⭐⭐⭐⭐ 網頁介面最直覺，但 5 分鐘只夠生成幾首 | 試聽、少量補歌用 |
| Lightning AI | 過去每月約 15 credits（約 80 小時可中斷 GPU）；**2026-09 改版後可能變成一次性贈送額度** ⚠️ | ⭐⭐ | 不建議依賴 |

### 2.1 50–60 次生成／週塞得進免費額度嗎？
- ACE-Step 1.5 Turbo：T4 估計每首 30–90 秒 → 60 首約 **0.5–1.5 小時**。
- ACE-Step 1.5 XL（offload）：估計每首 1–4 分鐘 → 60 首約 **1–4 小時**。
- 加上模型下載與載入（每次約 5–10 分鐘）→ **每週 2–6 小時，遠低於 Kaggle 的 30 小時。✅**
- 即使 T4 的速度比估計慢一倍，也還在額度內。

### 2.2 公開 Space 生成的音樂可以商用嗎？
- Hugging Face 不主張擁有使用者生成的內容。輸出能不能商用，**主要看模型授權**（例如 ACE-Step 是 MIT → 可以）。
- 但要注意：(a) 某些 Space 的作者會另外加上使用條款；(b) 公開 Space 的輸入與輸出可能被別人看到；(c) Space 可能改用別的模型或權重。**建議只使用官方組織（例如 ACE-Step 官方）的 Space，並保存截圖與模型版本作為紀錄。** ⚠️ 沒有找到 HF 官方對 Space 輸出商用的明文說明。

---

## 3. 有沒有「免費方案就給商用權」的商業服務？

| 服務 | 免費方案商用？ | 說明 |
|---|---|---|
| Suno | ❌ | 免費方案明確寫「No commercial rights」 |
| Udio | ❌ | 下載功能已停用，各方案都沒有寫明可商用 |
| Mureka（崑崙萬維） | ❌ | 免費版非商用、有浮水印；付費約 $8–10 起才有商用權 |
| ElevenLabs Music | ❌ | 免費版非商用，必須標示來源 |
| AIVA | ❌ | 免費版非商用、版權歸 AIVA |
| Mubert | ❌ | 免費授權為非商用 |
| Riffusion／Producer.ai（→ Google Flow Music） | ❓ | 多數評論說非商用，只有一篇說可商用，條款無法驗證 |
| OpenMusic AI、MakeBestMusic 等小型網站 | ❓ | 自己宣稱「可商用」，但條款與訓練資料來源不透明，**營利頻道不建議使用** |

→ **結論：沒有可以放心用在營利頻道的免費商業服務。**

---

## 4. 混合作法：國樂取樣＋AI／程式化編曲

### 4.1 取樣來源（全部都要先確認授權 ⚠️）
- **Freesound.org**：用「CC0」篩選，搜尋 guzheng、erhu、pipa、dizi、xiao、guqin、bianzhong。CC0 可以商用、不需要標示。CC-BY 也可以商用，但要在說明欄標示作者。
- **DSK Asian DreamZ Vol. 1**（免費 SoundFont）：包含琵琶、琵琶輪指、阮、古箏、二胡、梆笛、打擊樂。**頁面沒有寫授權** → 寄信向作者確認後才能用。
- **ChineeGuZheng Classic**（改為免費軟體）：授權未知 ⚠️。
- **Spitfire LABS、Pianobook、Decent Sampler 的免費音色庫**：通常允許用於音樂創作（包含商用），但需要 DAW 或外掛宿主，不適合完全自動化 ⚠️。
- 編鐘、古琴這類稀有樂器：**優先找博物館或學術單位釋出的 CC0 錄音**，或在第一個月付一次小額費用購買單一取樣包（可選，非必要）。

### 4.2 自動化（不需要 DAW）
1. **Claude Code 撰寫 prompt 與「樂句腳本」**：依照山海經章節（〈南山經〉〈海外東經〉等）訂主題、調式（宮商角徵羽）、BPM。
2. **ACE-Step 生成伴奏底層**：lofi 鼓組、Rhodes、貝斯、黑膠雜訊、雨聲，prompt 也加上國樂器（讓 AI 先試）。
3. **程式化點綴層**：用 Python（`pretty_midi` 產生五聲音階樂句 → `FluidSynth`／`sfizz` 用 SoundFont／SFZ 演奏），或直接把 CC0 錄音片段切片後依拍點排列（`librosa` 偵測拍點、`pydub` 疊加）。
4. **自動混音與母帶**：在 VPS 上用 FFmpeg（`loudnorm` 標準化到 -14 LUFS、EQ、殘響、側鏈）。
5. **ACE-Step repaint／參考音訊**：選用，用來讓 AI 生成的段落「模仿」真實取樣的音色。

> 這套混合作法的額外好處：每首曲子都有可以證明的「人工設計層」，在 YouTube 審查 inauthentic content 時是有力的原創證據。

---

## 5. 24/7 直播主機：還有比 US$5 VPS 更便宜的嗎？

| 選項 | 月費 | 可靠度 | 評估 |
|---|---|---|---|
| **OVHcloud VPS-1**（2 vCore／4 GB／流量不限） | **US$4.54（未稅）／€4.49** | 高 | **首選**（細節見 01 報告第 3 節） |
| Contabo 入門 VPS | 約 €4.4 | 中 | 次選 |
| **Oracle Cloud Always Free（ARM）** | **US$0** | **中低** | 據報導 2026-08-18 起 ARM 額度從 4 OCPU／24 GB **減半為 2 OCPU／12 GB**，但仍然足以用「預先渲染＋copy」模式推 1080p 流；每月 10 TB 外流量也夠用。**風險**：常常搶不到機器；「閒置回收」規則（7 天內 CPU／網路／記憶體使用率低於 20%）。推流的網路用量應該高於門檻，但 copy 模式的 CPU 很低，有誤判的可能 ⚠️；註冊需要信用卡；不少用戶回報帳號被無預警停用；沒有 SLA。 |
| Hetzner | €5.49 起，而且常常缺貨 | 高 | 2026 年漲價兩次，已不划算 |

**建議**：主力用 OVH（每月約 US$5，換來穩定）。Oracle 可以當「免費第二台」：用來跑第二條系列直播，或作為 OVH 掛掉時的備援。**不建議讓 Oracle 免費機當唯一的 24/7 主機。**

---

## 6. 推薦管線

### 6.1 首選：「ACE-Step 1.5 XL × Kaggle 批次 × 國樂取樣點綴」
```
[Claude Code] 每週產生 prompts.json（3 系列 × 約 20 首，含山海經主題、調式、BPM、國樂器標籤）
      ↓（擁有者把檔案上傳到 Kaggle Dataset，或由 Claude 直接更新 GitHub／Dataset）
[Kaggle Notebook] 擁有者按「Save & Run All」→ 背景執行 ACE-Step 1.5 XL（T4，offload）
      ↓ 1–4 小時後
[擁有者] 下載 output.zip → 試聽 → 在試聽表（Google Sheet）勾選約 20 首（可以加一句評語）
      ↓ 把勾選的檔案放進 Google Drive 指定資料夾
[VPS／Claude Code 腳本] 加入國樂取樣點綴層 → 混音、母帶（-14 LUFS）→
      串成每週 1–2 小時合輯（loop 影片用 copy 模式）→ 輸出 MP4、縮圖、標題、說明、時間軸
      ↓
[擁有者] 手動上傳到 YouTube Studio（約 5–10 分鐘），勾選 AI 揭露
      ↓
[VPS] 新曲自動加入 24/7 直播播放清單
```

### 6.2 次選：「Stable Audio 3.0 Medium × Kaggle」
- 同樣的管線，只換模型。優點：**官方表示使用授權資料訓練，法律風險最低**；單首約 6 分鐘，適合 Sleep／Relax。缺點：年營收超過 US$100 萬要改買 Enterprise 授權（對新頻道不是問題）；lofi 鼓組的律動與 Jazz 和聲可能不如 ACE-Step ⚠️ 需實測。
- **實務建議**：第 1 個月兩個模型都跑，用盲聽比較後決定各系列使用哪個模型，例如 Study 與 Work 用 ACE-Step、Sleep 用 Stable Audio 3。

### 6.3 擁有者每週實際時間
| 工作 | 時間 |
|---|---|
| 上傳 prompts 檔、按 Run All | 5 分鐘 |
| 下載並試聽 50–60 首（每首聽前 30–60 秒，跳著聽） | 40–60 分鐘 |
| 在試聽表勾選、放進資料夾 | 5–10 分鐘 |
| 審核 Claude 產出的合輯並手動上傳 YouTube | 10–15 分鐘 |
| **合計** | **約 60–90 分鐘／週** |

> 首次設定（Kaggle 帳號與手機驗證、Google Drive 資料夾、試跑）約 1–2 小時，Claude Code 會逐步引導。

---

## 7. 風險與因應

| 風險 | 影響 | 因應 |
|---|---|---|
| 國樂器音色不道地（尤其編鐘、古琴、簫） | 品牌可信度 | 用真實取樣點綴；長期可以訓練國風 LoRA；試聽表把「樂器正確性」列為必勾項目 |
| 授權變動（模型改授權、Stability 修改條款） | 法律 | **保存當時的 LICENSE 檔、模型版本與雜湊值**；固定使用某個版本的權重；建立生成紀錄（日期、模型、prompt、seed） |
| 訓練資料的法律不確定性（開源模型的訓練來源） | 侵權風險 | 優先使用宣稱用授權資料訓練的模型（Stable Audio 3）；不使用含藝人名字或作品名稱的 prompt |
| Content ID 誤判或撞曲 | 收益被拿走 | 保留生成紀錄作為證據並提出異議；不把曲子登記到 Content ID |
| YouTube inauthentic／重複內容 | 喪失營利資格 | 每週新曲為主＋人工選曲＋國樂點綴層＋山海經故事化說明；AI 揭露 |
| Kaggle／Colab 免費額度縮水或條款變更 | 產量 | 有 3 個平台可以互相備援（Kaggle → Colab → HF Space）；最壞情況租雲端 GPU，每週約 US$1–2 |
| 成品率低，擁有者試聽很累 | 時間超出預期 | 由 Claude 先用自動指標（響度、靜音、削波、長度、節拍穩定度）淘汰明顯失敗的曲子，減少要人工試聽的數量 |
| 文化與題材敏感度（山海經、宗教或民族元素） | 社群反應 | 原創角色與神獸詮釋；說明欄附上典故出處；避免刻板的「東方」視覺 |
| Oracle 免費機被回收或停用 | 直播中斷 | 主力使用付費 VPS，Oracle 只當備援 |

---

## 8. 待驗證清單
- [ ] ACE-Step 1.5 XL：打開官方 LICENSE 確認 XL 權重也是 MIT；在 Kaggle T4 實測速度與 VRAM。
- [ ] Stable Audio 3.0 Medium：打開 HF 模型卡確認授權全文、VRAM、可以生成器樂的長度。
- [ ] DiffRhythm 2：確認「no profit」那句話是否已經移除。
- [ ] Kaggle：在帳號設定頁確認本週 GPU 額度，以及背景執行（commit）是否可以下載 HF 權重。
- [ ] 每一個國樂取樣：逐一確認 CC0／CC-BY／商用條款，並把授權截圖存檔。
- [ ] Oracle：用新帳號實測能否開到 ARM 機器，觀察 2 週是否被判定閒置。

---

## 參考來源
**模型**
- ACE-Step 1.5 GitHub — https://github.com/ACE-Step/ACE-Step-1.5
- ACE-Step 1.5 模型卡（MIT）— https://huggingface.co/ACE-Step/acestep-v15-base/blob/main/README.md
- ACE-Step 1.5 論文 — https://arxiv.org/abs/2602.00744
- ACE-Step 1.5 專案頁 — https://ace-step.github.io/ace-step-v1.5.github.io
- ACE-Step 1.5 XL 發布（Gigazine）— https://www.gigazine.net/gsc_news/en/20260409-ace-step-1-5-xl/
- ACE-Step 1.5 XL（techno-edge）— https://www.techno-edge.net/article/2026/04/13/4986.html
- ACE-Step 1.5 XL in ComfyUI — https://blog.comfy.org/p/ace-step-15-xl-commercial-grade-music
- ACE-Step 1.5 XL Turbo 模型卡 — https://huggingface.co/ACE-Step/acestep-v15-xl-turbo
- ACE-Step XL VRAM／長度（DeepInfra）— https://deepinfra.com/ACE-Step/acestep-v15-xl-sft
- NYU Shanghai RITS 評論 — https://rits.shanghai.nyu.edu/ai/ace-step-1-5-open-source-music-generation-that-rivals-commercial-ai/
- Stable Audio 3 官方公告 — https://stability.ai/news-updates/meet-stable-audio-3-the-model-family-built-for-artistic-experimentation-with-open-weight-models
- Stable Audio 3（The Decoder）— https://the-decoder.com/stability-ai-launches-stable-audio-3-0-with-up-to-six-minute-tracks-and-open-weights/
- Stable Audio 3（Gigazine）— https://gigazine.net/news/20260522-stable-audio-3/
- Stability AI License — https://stability.ai/license
- MusicGen 模型卡（CC-BY-NC 4.0）— https://facebookresearch.github.io/audiocraft/model_cards/MUSICGEN_MODEL_CARD.html
- YuE（Apache 2.0、硬體需求）— https://ai-search.io/tool/yue
- YuE2-3B（非商用）— https://mer.vin/news/yue2-3b-claims-it-beats-suno-v6-on-open-music-generation/
- YuE2-3B（ComfyUI Wiki）— https://comfyui-wiki.com/en/models/yue2/yue2-3b
- YuE2 分析（innovatopia）— https://innovatopia.jp/ai/ai-news/117767/
- DiffRhythm 2 README — https://huggingface.co/ASLP-lab/DiffRhythm2/blob/main/README.md
- DiffRhythm 2 README 修訂 — https://huggingface.co/ASLP-lab/DiffRhythm2/commit/21b1b2799450c7671c3ab5729e9beb2702bee99f
- SongBloom HF — https://huggingface.co/CypressYang/SongBloom
- SongGeneration（騰訊）— https://huggingface.co/tencent/SongGeneration
- SongGeneration 2 VRAM — https://insmelo.com/blog/levo-2-song-generation

**免費 GPU**
- Colab 免費版限制 — https://www.hivenet.com/post/google-colaboratory-gpu-complete-guide-to-free-cloud-gpu-access-and-limitations
- Colab／Google AI 方案更新 — https://pasqualepillitteri.it/en/news/17594/colab-google-ai-plans-premium-gpu
- 免費 GPU 2026 概況 — https://gpuperhour.com/blog/free-cloud-gpus-and-credits
- Kaggle 額度 — https://www.gmicloud.ai/en/blog/best-free-gpu-cloud-options-for-ai-startups-and-researchers
- HF ZeroGPU 文件 — https://huggingface.co/docs/hub/spaces-zerogpu
- HF ZeroGPU 免費額度討論 — https://discuss.huggingface.co/t/what-is-the-free-zerogpu-quota-for-1-space/178610
- Lightning AI 2026-09 改版 — https://www.usagepricing.com/blueprint/activity/lightning-ai-2026-09-21-gpu-rate-card-reprice
- Lightning AI 免費方案 — https://costbench.com/software/ai-ml-platforms/lightning-ai/free-plan/

**商業服務免費方案**
- 免費 AI 音樂生成器商用比較 — https://imagera.ai/blog/best-free-ai-music-generator-2026
- Royalty-free AI music 免費方案 — https://sonilo.com/blog/guides/royalty-free-ai-music-youtube-ads-client-videos
- Free vs Paid — https://songcreator.pro/blog/free-vs-paid-ai-music-generators
- Mureka 免費 vs 付費 — https://aitoolsatlas.ai/tools/mureka/free-vs-paid
- Producer.ai → Google Flow Music — https://sunowatermark.com/blog/producer-ai-review-2026/
- Producer.ai 評論 — https://fast.io/resources/producer-ai-review-2026/
- Suno 免費方案非商用 — https://dailyaifixs.com/blog/suno-pricing-2026-free-songs-stay-non-commercial

**取樣**
- DSK Asian DreamZ（rekkerd）— https://rekkerd.org/?p=5846
- ChineeGuZheng Classic（rekkerd）— https://rekkerd.org/?p=40769
- Freesound — https://freesound.org

**主機**
- Oracle Always Free 縮減 — https://braindetox.kr/en/posts/oracle_always_free_tier_reduced_2026.html
- Oracle 閒置回收規則 — https://oracommit.blogspot.com/2026/02/understanding-oci-always-free-compute.html
- Oracle 免費 VPS 風險 — https://space-node.net/blog/oracle-cloud-free-tier-vps-2026
- Hetzner 替代方案比價（OVH VPS-1）— https://dev.to/hostingsift/is-hetzner-still-the-cheapest-vps-we-priced-24-alternatives-october-2026-271g
- Hetzner 2026-06 漲價 — https://wz-it.com/en/blog/hetzner-price-increase-june-2026-cpx-ccx-alternatives/
