# 05 申請 Gemini 生圖金鑰

**這是什麼？** Gemini 是 Google 的 AI。我們用它畫每週的**背景圖和縮圖**。
「API 金鑰」（API key）是讓 Claude 的美術 agent 可以用你的 Google 帳號叫 Gemini 畫圖的**鑰匙**——它會產生費用，所以是**秘密**。

**大概花多少錢？** 每張圖約 US$0.04–0.07，一週最多 8 張，**每月約 US$1–3**。我們會設一個**花費上限和提醒**，不會不知不覺花很多。

---

## 第 1 部分：產生 API 金鑰

1. 用 Chrome 打開 **https://aistudio.google.com** ，用你的 Google 帳號登入。
   - 第一次會要你同意服務條款，勾選後按 「**Continue**」／「**I accept**」（繼續／我同意）。
2. 左邊選單（或左下角）按 「**Get API key**」（取得 API 金鑰）。
   - 👀 會看到「API Keys」頁面。
3. 按 「**Create API key**」（建立 API 金鑰）。
   - 如果問你要放在哪個專案（project）：選 「**Create API key in new project**」（在新專案中建立），或選它幫你建好的預設專案。
   - 👀 會出現一串 **`AIza` 開頭**的字。
4. **先不要複製**。這把金鑰之後隨時可以回這一頁看（按金鑰名稱或複製圖示）。

## 第 2 部分：開啟付費（生圖功能需要）

畫圖的模型**沒有免費額度**，要開啟付費才能用。

1. 在 AI Studio 左下角按 「**Settings**」（設定）→ 「**Billing**」（帳單）或 「**Plan information**」（方案資訊）。
   - 或在 API Keys 頁面，金鑰旁邊寫著「Free」的地方，按 「**Set up billing**」（設定帳單）。
2. 照畫面建立 **Google Cloud 帳單帳戶**：國家、地址、信用卡。按 「**Submit**」／「**Start**」。
3. 如果畫面要你**先儲值**（「**Prepay**」／「**Buy credits**」，預付點數）：
   - 2026 年起有些新帳號必須先預付，**最低 US$10**。儲 **US$10** 就好，大約夠用 3–6 個月。
   - 預付的好處：用完就停，**不會多扣錢**。
4. 👀 回到 API Keys 頁，金鑰旁邊的方案從「Free」變成「**Tier 1**」或「**Paid**」（付費）。可能要等幾分鐘。

## 第 3 部分：設定花費上限和提醒（很重要）

**A. AI Studio 的每月上限（有的話）**
1. AI Studio 左邊選單 → 「**Spend**」（花費）。
2. 「**Monthly spend cap**」（每月花費上限）→ 「**Edit spend cap**」（編輯上限）→ 輸入 `5`（美元）→ 「**Save**」。
   - 👀 超過 US$5 時，生圖會暫停，不會多花。
   - 找不到這個選項也沒關係，做下面的 B。

**B. Google Cloud 的預算提醒（email 通知）**
1. 打開 **https://console.cloud.google.com/billing** 。
2. 點你的帳單帳戶名稱（通常叫「My Billing Account」（我的帳單帳戶））。
3. 左邊選單 「**Budgets & alerts**」（預算與快訊）→ 上方 「**+ Create budget**」（建立預算）。
4. 「Name」（名稱）：`Classic of Calm Gemini` → 「**Next**」（下一步）。
5. 範圍（Scope）不用改 → 「**Next**」。
6. 「**Budget type**」（預算類型）選 「**Specified amount**」（指定金額）→ 「**Target amount**」（目標金額）輸入 `5` → 「**Next**」。
7. 「**Alert threshold rules**」（提醒門檻）：保留 50%、90%、100%。勾選 「**Email alerts to billing admins and users**」（寄 email 給帳單管理員）。
8. 按 「**Finish**」（完成）。
   - 👀 預算清單出現「Classic of Calm Gemini — US$5」。花到 US$2.5、4.5、5 時，你的 Gmail 會收到提醒信。收到信就告訴 Claude。
   - ⚠️ 預算提醒**只會寄信，不會自動停止**花費；真正會停的是 A 的上限或預付用完。

## 第 4 部分：交給 Claude（安全表單）

1. 回到 Claude 對話，說：「**Gemini 金鑰準備好了**」。
2. Claude 會跳出一個**安全表單**（不是對話框）。
   - 👀 表單會寫著主機 `generativelanguage.googleapis.com`、標頭（header）名稱 `x-goog-api-key`。**這兩個不用改。**
3. 回到 AI Studio 的 API Keys 頁，按你那把金鑰旁邊的**複製圖示**。
4. 回到表單，在金鑰欄位按 `Ctrl + V` 貼上，按 「**Save**」（儲存）。
5. Claude 會說「已設定」，接著試畫一張圖確認可以用。Claude **看不到**你的金鑰內容，這是正常的。

> 🔒 **不要**把 `AIza…` 那串字貼在對話框、不要截圖、不要寄給任何人。

---

## 卡住了怎麼辦

| 狀況 | 怎麼做 |
|---|---|
| 找不到「Get API key」 | 直接打開 https://aistudio.google.com/apikey 。 |
| 說你所在的國家／地區不支援 | 截圖給 Claude。 |
| 付款被拒、或一直顯示「Free」 | 等 10–30 分鐘再看。還是不行，有人的解法是**在同一個專案再建一把新金鑰**。截圖給 Claude。 |
| Claude 說「金鑰被拒絕」或「額度用完」 | 可能是預付用完、或到了每月上限。到 AI Studio 的「Billing」頁看餘額，告訴 Claude 你看到什麼（不用給金鑰）。 |
| 收到預算提醒信 | 告訴 Claude「收到 Gemini 預算提醒」，它會檢查這週是不是生太多圖。 |
| 不小心把金鑰貼到對話或別處 | 到 AI Studio 的 API Keys 頁，把那把金鑰**刪除**（垃圾桶圖示），再建一把新的，重做第 4 部分。 |
| Claude 沒跳出表單 | 告訴 Claude「沒看到表單」。**不要**改成貼在對話裡。這週的圖可以之後再補，歌曲照常進行。 |

**未親自確認（依 2026 年 Google 官方部落格與網路資料撰寫）：** AI Studio 選單的確切名稱（「Settings → Plan information」、「Spend → Monthly spend cap」）；新帳號是否一定要預付（官方 2026-04 宣布預付在美國先上線、再逐步全球）；每張圖的實際價格。
