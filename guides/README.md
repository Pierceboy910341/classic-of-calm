# Classic of Calm 操作手冊（給擁有者）

這個資料夾是給你看的「一步一步」說明。你**不需要懂程式**。
你只做三件事：**按按鈕**、**聽歌**、**下載與上傳**。其他的事 Claude 和它的團隊會做。

> 小提醒：畫面上的英文按鈕，我們寫成「英文」（中文意思）。例如 「Save」（儲存）。
> 網站有時候會改版，按鈕位置可能稍微不同。找不到時，**截圖傳給 Claude**，說「我找不到 X」就好。

---

## 🔒 最重要的一條規則：密碼和金鑰不要貼在對話裡

「金鑰」（key／token）就像一把**家裡的鑰匙**。拿到的人可以用你的帳號花錢或開直播。

- **不要**把金鑰貼在 Claude 對話框裡、不要寄 email、不要截圖。
- 金鑰只放在三個安全的地方：
  1. **Kaggle 的 Secrets**（Kaggle 的保險箱）
  2. **直播主機安裝程式**問你的時候（打字時看不到，是正常的）
  3. **Claude 跳出來的安全表單**（Claude 會說「請在表單中填入」）
- 如果不小心貼出去了：告訴 Claude「我不小心貼了金鑰」，它會教你怎麼作廢、重新產生一把。

---

## 第一次設定：照這個順序做（大約 2–3 個晚上）

| 順序 | 做什麼 | 手冊 | 大約時間 |
|---|---|---|---|
| 1 | 建立 YouTube 頻道、**申請直播功能**（要等最多 24 小時，所以先做） | [03-youtube-channel.md](03-youtube-channel.md) 第 1–3 部分 | 20 分鐘＋等待 |
| 2 | 把兩個「筆記本」（notebook，就是在 Kaggle 上跑的工作清單）匯入 Kaggle | [01-kaggle-notebooks.md](01-kaggle-notebooks.md) | 30 分鐘 |
| 3 | 產生 Kaggle API 權杖，交給 Claude 的安全表單 | [02-kaggle-api-key.md](02-kaggle-api-key.md) | 10 分鐘 |
| 4 | 申請 Gemini 生圖金鑰，設定花費上限 | [05-gemini-key.md](05-gemini-key.md) | 20 分鐘 |
| 5 | 拿到直播用的「串流金鑰」 | [03-youtube-channel.md](03-youtube-channel.md) 第 4–5 部分 | 10 分鐘 |
| 6 | 租一台 24 小時開著的小電腦（VPS），裝好直播程式 | [04-vps-stream.md](04-vps-stream.md) | 40 分鐘 |

> 第 6 步最好在「02 Assemble」**至少跑完一次**之後再做，這樣直播一開始就有歌可以播。
> 先做也可以：直播會先播一張綠色的畫面，等有歌了會自動開始放。

---

## 每週例行（一頁看完）

| 星期 | 你在 Claude 對話打這句話 | 然後你要點的地方 | 要等多久 |
|---|---|---|---|
| 一 | **「開始本週製作」** | Claude 給你看 2 張圖，你回「用 1」或「用 2」。<br>接著打開 Kaggle 的 **01 Generate** → 把 `WEEK` 改成 Claude 說的週次 → 「Save Version」（儲存版本）→ 「Save & Run All (Commit)」（儲存並全部執行）→ 「Save」 | 2–6 小時（可以關掉瀏覽器） |
| 二 | **「審核本週歌曲」** | Claude 傳 01.mp3、02.mp3… 給你聽。你回「留 1, 3, 5…」。<br>接著打開 Kaggle 的 **02 Assemble** → 改 `WEEK` → 「Save Version」→ 「Save & Run All (Commit)」→ 「Save」 | 1–2 小時 |
| 三 | **「本週上傳資料」** | 從 Kaggle 下載 `compilation.mp4` 和 `thumbnail.png` → 上 YouTube Studio 上傳，照 Claude 給的清單貼標題、說明、標籤。<br>⚠️ **「Altered or synthetic content」（變造或合成內容）一定選「Yes」（是）** | 20 分鐘 |
| 隨時 | **「直播狀況」** | Claude 會告訴你 ✅ 正常／⚠️ 小問題／❌ 停了。必要時請你打開 YouTube Studio 看一眼 | 2 分鐘 |
| 每月一次 | **「月投票」** | Claude 給你投票貼文，你在 YouTube Studio「Create」（建立）→「Post」（貼文）→ 選投票，貼上 | 10 分鐘 |

其他常用的話：
- 「重做封面」：Claude 重新做 2–3 張圖給你選。
- 「這首不要了」：Claude 把那首拿掉，提醒你重跑 02 Assemble。
- 「下週要做什麼？」：Claude 用一句話告訴你。

---

## 卡住了怎麼辦（通用）

1. **截圖**整個畫面（Windows：按 `Windows 鍵 + Shift + S`，拉一個框，然後在對話框按 `Ctrl + V` 貼上）。
2. 在 Claude 對話打：「我在 ○○ 手冊第 ○ 步卡住了」，附上截圖。
3. 截圖前看一下：畫面上**有沒有金鑰或密碼**？有的話先把那部分遮掉或不要截。
4. Kaggle 跑失敗時：打開那一版的「Logs」（紀錄）分頁，捲到最下面，截最後 20 行給 Claude。

## 這些手冊哪些地方還沒親自確認（給 Claude 看的）
撰寫時（2026-11）無法登入各網站實際操作，以下是依網路資料與程式碼寫的，第一次照做時請 Claude 跟擁有者一起確認、再更新手冊：
- Kaggle：「File → Import Notebook」的視窗樣子、GPU 額度顯示的位置、新版 API 權杖按鈕名稱。
- YouTube：直播的「Altered or synthetic content」揭露是否在直播設定裡有選項（上傳影片時確定有）。
- OVHcloud：目前的 VPS 方案名稱與價格（2026 年有漲價、可能改成「VPS 2027」系列）。
- Gemini：新帳號是否必須「預付」（Prepay，最低 US$10）才能用付費功能。
