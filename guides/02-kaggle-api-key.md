# 02 產生 Kaggle API 權杖

**這是什麼？** 「API 權杖」（API token）是一把**只給機器用的鑰匙**。有了它：
- **Claude**（每週二）可以自己去 Kaggle 拿 01 做好的候選歌，切成試聽檔給你聽。
- **直播主機**（每天）可以自己去 Kaggle 拿 02 做好的歌，放進 24 小時直播。

你只需要產生一次，交給兩個地方：**Claude 的安全表單**、**直播主機安裝程式**（見 04 手冊）。

> 🔒 這把鑰匙是秘密。**不要貼在 Claude 對話框裡**，也不要截圖。

---

## 步驟

1. 打開 Chrome，到 **https://www.kaggle.com/settings** （或點右上角頭像 → 「**Settings**」（設定））。
2. 往下捲，找到 「**API**」區塊。
   - 👀 會看到一個按鈕 「**Generate New Token**」（產生新權杖），下面可能還有一個「Legacy API Credentials」（舊版憑證）區塊。
3. 按 「**Generate New Token**」（產生新權杖）。
   - 如果要你取名字，寫 `classic-of-calm`。
   - 👀 畫面會顯示一串很長、開頭是 **`KGAT_`** 的字。
4. 按旁邊的**複製圖示**。**這串字通常只會顯示一次。**
5. 先把它暫時貼在 Windows 的「記事本」（開始 → 輸入「記事本」或「Notepad」）。
   - 在同一個記事本裡，也記下你的 **Kaggle 使用者名稱**（右上角頭像 → 你的個人頁網址 `kaggle.com/` 後面那串字）。
   - ⚠️ 全部設定完（第 04 手冊做完）之後，**把記事本關掉、不要存檔**。

### 交給 Claude（安全表單）

6. 回到 Claude 對話，說：「**Kaggle 權杖準備好了**」。
7. Claude 會跳出一個**安全表單**（不是對話框）。
   - 👀 表單上會寫著主機名稱（例如 `api.kaggle.com`）和一個要你貼上的欄位。
   - 在欄位裡按 `Ctrl + V` 貼上 `KGAT_` 開頭那串字，按 「**Save**」（儲存）。
8. Claude 會說「已設定」。它**看不到**你的權杖內容，這是正常的。

### 交給直播主機

9. 等到做 [04-vps-stream.md](04-vps-stream.md) 時，安裝程式會問：
   `3/4  Paste your Kaggle API token or key (hidden)`（貼上 Kaggle API 權杖或金鑰，輸入時不會顯示）
   在那裡貼上同一串字。

---

## 卡住了怎麼辦

| 狀況 | 怎麼做 |
|---|---|
| 找不到「Generate New Token」，只有「Create New API Token」或「Create Legacy API Key」 | 按那個按鈕也可以。它會下載一個 `kaggle.json` 檔案。用記事本打開它，裡面 `"key":` 後面引號中的 32 個英數字就是金鑰。直播主機和 Claude 表單都收這種。用完把 `kaggle.json` 刪掉。 |
| 權杖沒複製到就關掉了 | 再按一次「Generate New Token」產生新的；舊的可以在同一頁「Expire」（作廢）。 |
| Claude 說「Kaggle 權杖失效」 | 權杖可能過期或被作廢。重做第 1–8 步，並在直播主機上打 `sudo coc setup` 重新輸入（見 04 手冊）。 |
| 不小心把權杖貼到對話或別處 | 馬上回到 Kaggle 設定頁把它作廢，產生新的，重做上面步驟。告訴 Claude 一聲。 |
| Claude 沒跳出表單 | 告訴 Claude「沒看到表單」。它會告訴你在環境設定的哪裡手動加入。**不要**改成貼在對話裡。 |

**未親自確認：** Kaggle 設定頁 2026 年的按鈕名稱（網路資料顯示是「Generate New Token」，舊版金鑰在「Legacy API Credentials → Create Legacy API Key」）、新權杖是否有到期日。

---

## 給 Claude（製作人）的技術備註（擁有者可以跳過）

- 依 repo 內程式：直播主機 `stream/install.sh` 接受新式 `KGAT_…` 權杖（寫成 `KAGGLE_API_TOKEN`）或舊式 32 字元金鑰（寫成 `KAGGLE_KEY`，搭配 `KAGGLE_USERNAME`）。
- qa-engineer 在 Claude 雲端對話中用 `kaggle kernels output <user>/<slug> -p …`。已檢查 kaggle CLI 2.2.5／kagglesdk 0.1.38 原始碼：
  - API 主機是 **`api.kaggle.com`**（不是 `www.kaggle.com`；後者只用於 OAuth 登入網址）。
  - 新式權杖送 `Authorization: Bearer <KGAT_…>`；舊式金鑰送 HTTP Basic（使用者名稱＋金鑰）。
- 因此建議用 `request_credential`：host `api.kaggle.com`、`suggested_type: bearer`（預設 Authorization: Bearer）。權杖由 proxy 注入，沙箱內只放假值讓 CLI 啟動：`KAGGLE_API_TOKEN=KGAT_placeholder`（CLI 啟動時會呼叫一次 token introspection，也會走同一主機）。若擁有者只有舊式金鑰，改用 `suggested_type: basic`（使用者名稱＋金鑰），沙箱內放 `KAGGLE_USERNAME=<真實帳號>`、`KAGGLE_KEY=placeholder`。
- **未驗證**：輸出檔下載可能被導向 `storage.googleapis.com` 等簽章網址；若出現 `request blocked: no rule allows host`，依 get_environment 的規則提出加入該主機（不需憑證）。也未在真實帳號上測過 proxy 注入 Bearer 是否能通過 introspection。
- 絕不寫 `~/.kaggle/kaggle.json` 或 `access_token` 進 repo；不要印出環境變數。
