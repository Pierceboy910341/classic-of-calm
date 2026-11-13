# 01 把兩個筆記本放進 Kaggle

**這是什麼？** Kaggle 是 Google 旗下的網站，每週**免費**借你一台有顯示卡（GPU，做 AI 音樂需要的零件）的電腦。
「筆記本」（notebook）就是一份「工作清單」，你按一個按鈕，它就照清單自己做完。
我們有兩本：

| 筆記本 | 做什麼 | 什麼時候按 | 要不要 GPU |
|---|---|---|---|
| **01 Generate** | 用 AI 做約 60 首候選歌 | 每週一 | 要（GPU T4 x2） |
| **02 Assemble** | 把你留下的歌做成 1–2 小時的影片 | 每週二 | 不要（None） |

**你需要先有：** 已經手機驗證過的 Kaggle 帳號（你已經有了 👍）、電腦上的 Chrome。

---

## 第 1 部分：匯入「01 Generate」

1. 打開 Chrome，到 **https://www.kaggle.com/code** ，確認右上角有你的頭像（代表已登入）。
2. 按左上角的 「**+ Create**」（建立）→ 選 「**New Notebook**」（新筆記本）。
   - 👀 你會看到一個新的編輯畫面，裡面有一格範例程式。
3. 在畫面上方的選單列按 「**File**」（檔案）→ 「**Import Notebook**」（匯入筆記本）。
   - 👀 會跳出一個小視窗，裡面有「拖曳檔案」區和「Link」（連結）欄位。
4. 在 「**Link**」（連結）欄位貼上這一行（整行複製）：
   ```
   https://raw.githubusercontent.com/Pierceboy910341/classic-of-calm/main/notebooks/01_generate.ipynb
   ```
   然後按 「**Import**」（匯入）。
   - 👀 原本的範例程式會被換掉，最上面出現大標題「🎵 Classic of Calm — 01 生成候選曲（每週一）」。
   - 如果沒有 Link 欄位：先在 Chrome 打開上面那個網址 → 按 `Ctrl + S` 存成檔案（檔名保留 `01_generate.ipynb`）→ 回到匯入視窗，把檔案拖進去。
5. 改名字：點左上角的筆記本名稱（通常是「notebook1234abcd」之類），改成：
   ```
   Classic of Calm 01 Generate
   ```
   按 `Enter`。
6. 設定右邊的面板（只有第一次要設，之後會記住）。如果右邊沒有面板，按畫面右上角的「**>|**」或「**Settings**」（設定）把它打開：
   - 「**Session options**」（工作階段選項）→ 「**Accelerator**」（加速器）→ 選 「**GPU T4 x2**」。
     - ⚠️ **不要選 P100**（新的音樂模型在 P100 上可能跑不動）。
     - 會跳出確認視窗說會用掉 GPU 額度，按 「**Turn on GPU T4 x2**」（開啟）或「OK」。
   - 「**Internet**」（網路）→ 打開成 **On**（開啟）。
   - 👀 右上角會顯示「GPU T4 x2」和綠色的「Internet on」之類的字樣。
7. 按右上角 「**Save Version**」（儲存版本）→ 在視窗裡選 「**Quick Save**」（快速儲存）→ 「**Save**」。
   - 這一步只是先把筆記本存起來，**還不用跑**。
8. 複製網址給 Claude：看 Chrome 最上面的網址列，會像 `https://www.kaggle.com/code/你的帳號/classic-of-calm-01-generate`。
   把它貼給 Claude，說「這是 01 的網址」。
   - 這個網址**不是秘密**，可以貼。

## 第 2 部分：匯入「02 Assemble」

1. 回到 **https://www.kaggle.com/code** → 「**+ Create**」→ 「**New Notebook**」。
2. 「**File**」→ 「**Import Notebook**」→ 在 「**Link**」貼上：
   ```
   https://raw.githubusercontent.com/Pierceboy910341/classic-of-calm/main/notebooks/02_assemble.ipynb
   ```
   → 「**Import**」。
   - 👀 最上面出現「🎬 Classic of Calm — 02 組合輯（每週二）」。
3. 改名字為：
   ```
   Classic of Calm 02 Assemble
   ```
4. 右邊面板：
   - 「**Accelerator**」→ 選 「**None**」（不用 GPU，省額度）。
   - 「**Internet**」→ **On**。
5. 把 01 的成果接過來（**要等 01 至少成功跑完一次才看得到**，第一週週二再做也可以）：
   - 右邊面板找到 「**Input**」（輸入）→ 按 「**+ Add Input**」（加入輸入）。
   - 👀 會出現搜尋視窗。上方篩選選 「**Your Work**」（你的作品）或 「**Notebooks**」（筆記本）。
   - 找到「Classic of Calm 01 Generate」→ 按它右邊的 「**+**」（或「Add」）。
   - 👀 Input 底下會多一個「classic-of-calm-01-generate」資料夾。
6. 「**Save Version**」→ 「**Quick Save**」→ 「**Save**」。
7. 把 02 的網址也貼給 Claude（「這是 02 的網址」）。**直播主機安裝時也會用到這個網址**，請先存在記事本裡。

## 第 3 部分（選做）：讓 Stable Audio 3 也能跑

試產週（W47）我們要比較兩個 AI 音樂模型。其中 **Stable Audio 3** 需要你先在 Hugging Face（一個放 AI 模型的網站）按「同意授權」。
**不做也沒關係**：筆記本會自動跳過它，只用另一個模型（ACE-Step）。

1. 到 **https://huggingface.co/join** 註冊（可以按「Continue with Google」用 Google 帳號）。收信點驗證連結。
2. 打開 **https://huggingface.co/stabilityai/stable-audio-3-medium**
   - 👀 會看到一段授權說明和一個表單。填好（名字、國家等），勾選同意，按 「**Agree and access repository**」（同意並取得存取權）。
   - 頁面上如果還提到其他要同意的條款（例如文字模型的 Gemma 條款），也一起同意。
3. 再打開 **https://huggingface.co/stabilityai/stable-audio-3-small-music** ，同樣按同意（這是備用的小模型）。
4. 到 **https://huggingface.co/settings/tokens** → 「**+ Create new token**」（建立新權杖）。
   - 「Token type」（權杖類型）選 「**Read**」（唯讀）。
   - 名字寫 `kaggle`。
   - 按 「**Create token**」。
   - 👀 會出現一串 `hf_` 開頭的字。按旁邊的複製圖示。**這串字只會顯示一次，而且是秘密，不要貼給 Claude。**
5. 回到 Kaggle 的「Classic of Calm 01 Generate」編輯畫面 → 上方選單 「**Add-ons**」（附加元件）→ 「**Secrets**」（秘密）。
6. 按 「**+ Add Secret**」（新增秘密）：
   - 「Label」（名稱）輸入：`HF_TOKEN`（全部大寫，中間是底線）
   - 「Value」（值）：按 `Ctrl + V` 貼上剛才那串字
   - 按 「**Save**」。
7. 👀 清單裡出現 `HF_TOKEN`，旁邊有一個勾選框——**一定要打勾**，筆記本才讀得到。
8. 關掉 Secrets 視窗，按 「**Save Version**」→ 「**Quick Save**」→ 「**Save**」。

> `GITHUB_TOKEN` 這個秘密**不用設**——我們的 GitHub 是公開的。

---

## 每週怎麼按（週一跑 01、週二跑 02）

1. 打開 **https://www.kaggle.com/code** → 點 「**Your Work**」（你的作品）→ 點筆記本名稱。
2. 如果看到的是「閱讀畫面」，按右上角 「**Edit**」（編輯）進入編輯畫面。
3. 找到標題寫著「✏️ 設定」的那一格。裡面有一行：
   ```
   WEEK = "2026-W47"
   ```
   只改**引號裡面**的字，改成 Claude 告訴你的週次（例如 `2026-W48`）。引號要留著。
4. 右上角 「**Save Version**」（儲存版本）。
5. 視窗裡選 「**Save & Run All (Commit)**」（儲存並全部執行），按 「**Save**」。
   - 👀 左下角或右上角會出現「Version 2 … Running」之類的進度。
6. **可以關掉瀏覽器**，它會繼續跑。01 約 2–6 小時；02 約 1–2 小時。
7. 跑完後回 Claude 說下一句話（週一跑完說「審核本週歌曲」；週二跑完說「本週上傳資料」）。

## 怎麼看結果、下載檔案

1. 打開筆記本（閱讀畫面，不是編輯畫面）。
2. 上方有分頁，點 「**Output**」（輸出）。也可能在頁面下方或右邊的「Output」區塊。
   - 👀 01 會看到 `candidates` 資料夾；02 會看到 `compilation.mp4`、`thumbnail.png`、`youtube.txt`、`stream_tracks` 等。
3. 下載：把滑鼠移到檔名上，按旁邊的 **下載圖示（向下的箭頭 ⬇）** 或 「**Download**」。
   - 你只需要下載 02 的 `compilation.mp4` 和 `thumbnail.png`。01 的歌 Claude 會自己抓，**你不用下載**。
   - `compilation.mp4` 很大（約 1–3 GB），下載要一點時間。檔案會在 Windows 的「下載」資料夾。
4. 想看每一次跑的紀錄：按右上角的版本號（例如「Version 3」）→ 選某一版 → 「**Logs**」（紀錄）分頁。

## 怎麼看每週 GPU 額度

- Kaggle 每週給**大約 30 小時**免費 GPU 時間（實際數字由 Kaggle 決定，會變動），每週六（UTC 時間，台灣時間週六早上 8 點）重新計算。
- 看剩多少：在 01 的**編輯畫面**右邊面板，「Session options」附近會顯示類似「**GPU T4 x2 … 12 / 30 hrs**」的額度。也可以點右上角頭像 → 「**Settings**」（設定）往下找「Quotas」（額度）。
- 01 每週大約用 2–6 小時，**一週跑一次就夠**，不會用完。02 不用 GPU，不吃額度。
- Kaggle 單次最長可以跑 12 小時；筆記本會在 11 小時前自己安全停下並保存成果。

---

## 卡住了怎麼辦

| 狀況 | 怎麼做 |
|---|---|
| 「Import Notebook」找不到或匯入失敗 | 用「下載檔案再拖進去」的方法（第 1 部分第 4 步的備案）。還不行就截圖給 Claude。 |
| Internet 開關是灰色、開不了 | Kaggle 需要手機驗證。右上角頭像 → 「Settings」→ 「Phone verification」（手機驗證）再做一次。 |
| Accelerator 沒有 GPU 選項 | 同上，需要手機驗證；或本週 GPU 額度用完了，等週六重置。 |
| 跑完後 Logs 最後寫著「❌」 | 截最後 20 行給 Claude。單一首歌失敗不會中斷整批。 |
| 01 跑到一半時間用完 | 它會自動保存已完成的歌。告訴 Claude，它會教你「接著跑」。 |
| 02 說「找不到候選曲」 | 通常是忘了做第 2 部分第 5 步（Add Input 加入 01 的輸出）。 |
| 看到「Stable Audio 3 需要授權，已跳過」 | 不是錯誤。要用它就做第 3 部分；不做也可以。 |
| 不小心把 HF 權杖貼到對話 | 到 https://huggingface.co/settings/tokens 把那個權杖按「Invalidate／Delete」（作廢／刪除），重做第 3 部分第 4–7 步。 |

**未親自確認：** 「Import Notebook」視窗的實際樣子、「Add Input」搜尋視窗的篩選名稱、GPU 額度顯示位置、Kaggle 目前是否還有單張「GPU T4」選項（目前資料顯示是「GPU T4 x2」與「GPU P100」）。依 2026 年網路資料撰寫，第一次操作時請以畫面為準。
