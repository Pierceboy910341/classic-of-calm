# 04 租一台直播主機（VPS），開始 24 小時直播

**這是什麼？** VPS（虛擬主機）是你**租的一台小電腦**，放在 OVHcloud 公司的機房，24 小時開著。
它每天自動去 Kaggle 拿最新的歌，然後一直播到你的 YouTube 頻道。你裝好之後，**平常不用碰它**。

**開始前請準備好（放在記事本裡）：**
1. YouTube 頻道已開通直播（[03 手冊](03-youtube-channel.md) 第 3 部分，要先等 24 小時）
2. 你的 **Kaggle 使用者名稱** 和 **Kaggle API 權杖**（[02 手冊](02-kaggle-api-key.md)）
3. 「Classic of Calm 02 Assemble」筆記本的**網址**（[01 手冊](01-kaggle-notebooks.md) 第 2 部分）
4. 一張信用卡（VPS 約每月 US$5–8，**價格依地區、匯率和促銷而不同，以結帳頁為準**）

---

## 第 1 部分：購買 VPS

1. 打開 OVHcloud 的 VPS 頁面：
   - 美國版：**https://us.ovhcloud.com/vps/**
   - 或國際版：**https://www.ovhcloud.com/en/vps/**
2. 找**最便宜的那一款**（2026 年叫 **VPS-1**，大約 2 vCore（核心）／4 GB 記憶體／40 GB 以上硬碟，標示「Unlimited traffic」（流量不限））。按 「**Order**」／「**Configure**」（訂購／設定）。
   - 名字可能改成「VPS 2027」系列的 VPS-1，選最便宜、**流量不限**的就對了。
3. 設定頁照這樣選：
   - 「**Location**」（機房地點）：觀眾以英語圈為主，選 **US East（美國東部，例如 Vint Hill / Virginia）** 或 **Europe（例如 France 法國 / Germany 德國）**。都可以，選價格便宜的那個。
   - ⚠️ 避免 **Singapore／Sydney**：有網路資料說那裡的流量有上限，直播一個月大約要用 1.4 TB。
   - 「**Image / Operating system**」（作業系統）：選 **Ubuntu 24.04**（如果寫「Ubuntu 24.04 LTS」也一樣）。
     - 不要選有「Plesk」「cPanel」「Docker」等附加軟體的版本，選最單純的 Ubuntu。
   - 「**SSH key**」（SSH 金鑰）：**不用加**，留空。我們用密碼登入。
   - 其他加購（備份、額外 IP 等）：都**不用**。
   - 「**Commitment / billing period**」（合約期）：選**每月**（no commitment），比較有彈性。
4. 按 「**Continue**」（繼續）→ 建立 OVHcloud 帳號（email、密碼、地址）→ 付款。
5. 👀 付款後會收到確認信。**約 15 分鐘到幾小時**後，會收到另一封「**Your VPS is ready**」（你的 VPS 已準備好）的信。

## 第 2 部分：看懂開通信

開通信裡會有三樣東西，抄到記事本：
- **IPv4 address**（IP 位址）：像 `51.xx.xx.xx` 的四組數字。這是主機的「門牌號碼」。
- **Username**（使用者名稱）：應該是 `ubuntu`。
- **密碼**：信裡會有一個**安全連結**，點開才看得到臨時密碼（連結通常只能看一次，**看到就馬上抄到記事本**）。

## 第 3 部分：從你的 Windows 電腦連進主機

1. 按鍵盤的 `Windows 鍵`，輸入 `PowerShell`，點 「**Windows PowerShell**」。
   - 👀 會打開一個藍色或黑色的視窗，有一行像 `PS C:\Users\你的名字>` 的字。
2. 輸入（把 `51.xx.xx.xx` 換成你的 IP），按 `Enter`：
   ```
   ssh ubuntu@51.xx.xx.xx
   ```
3. 第一次會問：
   `Are you sure you want to continue connecting (yes/no/[fingerprint])?`
   （你確定要連線嗎？）這是正常的安全確認。輸入 `yes`（完整三個字母），按 `Enter`。
4. 出現 `ubuntu@51.xx.xx.xx's password:` 時，貼上臨時密碼：
   - 在 PowerShell 裡**按滑鼠右鍵**就是貼上（或 `Ctrl + V`）。
   - ⚠️ **打字或貼上時畫面什麼都不會顯示，連星號都沒有，這是正常的。** 貼完直接按 `Enter`。
5. 第一次登入會要你**換密碼**：
   - `Current password:`（目前密碼）→ 再貼一次臨時密碼，`Enter`
   - `New password:`（新密碼）→ 打一個新的長密碼（至少 12 個字，英文＋數字），`Enter`
   - `Retype new password:`（再打一次）→ 同一個新密碼，`Enter`
   - 新密碼請記在你的**密碼管理器**或紙本上，**不要告訴 Claude**。
   - 👀 換完後連線可能會自己斷掉。沒關係，重做第 2 步和第 4 步（這次用**新密碼**）。
6. 👀 成功時，最下面會變成像 `ubuntu@vps-xxxx:~$` 的樣子。代表你已經「在主機裡面」了。

## 第 4 部分：安裝直播程式（只要一行）

1. 在剛才的視窗裡，貼上這一整行（右鍵貼上），按 `Enter`：
   ```
   curl -fsSL https://raw.githubusercontent.com/Pierceboy910341/classic-of-calm/main/stream/install.sh | sudo bash
   ```
2. 如果問 `[sudo] password for ubuntu:`，輸入你的**新密碼**（一樣看不到字），`Enter`。
3. 👀 畫面會跑很多英文字（在安裝東西），大約 2–5 分鐘。然後會依序問你 **4 個問題**（每題都有中英文）：

   | 問題 | 你要做的 |
   |---|---|
   | `1/4 Paste your YouTube stream key (hidden while typing)`<br>貼上 YouTube 串流金鑰 | 到 YouTube Live Control Room → Stream settings → 「**Copy**」（[03 手冊](03-youtube-channel.md) 第 4 部分第 6 步），回到這裡右鍵貼上，`Enter`。**看不到字是正常的。** |
   | `2/4 Your Kaggle username`<br>你的 Kaggle 使用者名稱 | 打你的 Kaggle 使用者名稱，`Enter`。 |
   | `3/4 Paste your Kaggle API token or key (hidden)`<br>貼上 Kaggle API 權杖或金鑰 | 從記事本複製 `KGAT_` 開頭那串，右鍵貼上，`Enter`。**看不到字是正常的。** |
   | `4/4 Paste the address of the "02 Assemble" notebook`<br>貼上「02 Assemble」筆記本網址 | 貼上 02 筆記本的網址（`https://www.kaggle.com/code/…`），`Enter`。 |

   - 每個秘密貼完，畫面會顯示 `Got it 收到 (KG****)` 之類，只露出頭尾幾個字，這是正常的。
4. 👀 最後會出現 **`All done! 安裝完成！`**，接著自動顯示一張狀態表。
5. 回到 Chrome 打開 YouTube Live Control Room，**約 1 分鐘內**預覽畫面會出現。
   - 如果 02 Assemble 還沒跑過：先是一張**墨綠色的畫面、沒有音樂**，這是正常的。之後每天早上主機會自己去抓新歌（約早上 6 點，主機時間）。

## 第 5 部分：查看直播狀態

在主機視窗打（連進主機的方法同第 3 部分）：
```
coc status
```
（只打 `coc` 也可以。）👀 你會看到一張表：

| 那一列 | 正常的樣子 |
|---|---|
| `Stream 直播` | 綠色 **`● LIVE 直播中`** |
| `Now playing 播放中` | 現在播的歌名 |
| `Library 曲庫` | 有幾首歌（第一次可能是 `empty 尚無歌曲`，等同步完就有） |
| `Last sync 同步` | `OK` 加上多久以前 |
| `Disk 磁碟` | 還剩多少空間（不是紅字就好） |

要離開主機：輸入 `exit` 按 `Enter`，然後可以關掉 PowerShell。**直播會繼續，跟你的電腦開不開機無關。**

其他偶爾會用到的指令（Claude 會告訴你什麼時候用）：
- `sudo coc sync`：現在就去 Kaggle 抓最新的歌（不用等明天早上）
- `sudo coc setup`：重新輸入那 4 個答案（換了串流金鑰或 Kaggle 權杖時用）
- `sudo coc restart`：重新連線

## 第 6 部分：從 YouTube Studio 確認有在直播（不用連主機）

1. 打開 **https://studio.youtube.com** （右上角是 Classic of Calm）。
2. 右上角 「**Create**」（建立）→ 「**Go live**」（開始直播）→ 進 **Live Control Room**。
3. 👀 正常：左上角預覽有畫面在動，狀態寫 **「LIVE」**（紅色），下面有「Stream health: Excellent / Good」（串流狀態：極佳／良好）。
4. 也可以直接用手機打開你的頻道，看有沒有紅色「LIVE」標誌。
5. 不確定時：截圖這個畫面給 Claude，或在對話說「**直播狀況**」。

---

## 卡住了怎麼辦

| 狀況 | 怎麼做 |
|---|---|
| `ssh` 說 `Connection timed out`（連線逾時） | IP 打錯，或主機還在開通中。核對開通信上的 IP；等 30 分鐘再試。 |
| `Permission denied, please try again`（權限被拒） | 密碼錯了。注意：打字看不到是正常的，慢慢重新貼一次。換過密碼後要用**新密碼**。 |
| 出現 `WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED` | 通常是主機重灌過。截圖給 Claude，**不要**自己亂改。 |
| PowerShell 說 `ssh` 不是可辨識的指令 | 改用 OVHcloud 網頁上的**備用螢幕**（見下方）。 |
| **備用方法：網頁 KVM 螢幕** | 登入 OVHcloud 「**Control Panel**」（控制台）→ 「**Bare Metal Cloud**」→ 「**Virtual Private Servers**」→ 點你的 VPS → 在「**Home**」（首頁）分頁、你的 VPS 名稱旁邊按 「**…**」→ 「**KVM**」。會打開一個黑色視窗，`login:` 打 `ubuntu`、`Password:` 打密碼（一樣看不到）。⚠️ KVM 視窗**不能貼上**，只能一個字一個字打——安裝那一行很長，請盡量用 PowerShell。 |
| 安裝時說 `Could not download` | 主機連不上 GitHub。等 10 分鐘再貼一次那一行（重跑很安全，不會壞掉）。 |
| 安裝最後說 Kaggle 登入失敗 | 使用者名稱或權杖貼錯了。打 `sudo coc setup` 重新回答 4 個問題。 |
| `coc status` 顯示紅色 `● DOWN 已停止` | 打 `sudo coc restart`，等 1 分鐘再打 `coc status`。還是紅的就截圖給 Claude（截圖前確認畫面上沒有金鑰）。 |
| `Library 曲庫` 一直是 `empty` | 02 Assemble 還沒跑過，或第 4 題網址錯了。先確認 02 有跑完，再打 `sudo coc sync`。 |
| YouTube 顯示「No data」（沒有資料）但主機說 LIVE | 串流金鑰可能錯了或被重設。回 YouTube 複製新金鑰，打 `sudo coc setup` 重新輸入。 |
| 忘記主機密碼 | OVHcloud 控制台可以重設密碼。截圖給 Claude 一起處理。 |

**未親自確認：** OVHcloud 2026 年 11 月的方案名稱與實際價格（網路資料顯示 2026 年 3 月漲價，且有「VPS 2027」新系列）、訂購頁欄位名稱、KVM 選單的確切位置、首次登入是否一定要求換密碼（OVHcloud 官方文件說會）。安裝程式本身在真正的 Ubuntu 24.04 主機上也還沒實測過（見 stream/README.md）。
