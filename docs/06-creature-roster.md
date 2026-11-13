# 06 — 異獸名冊（Creature Roster）v1

> 角色：Producer（團隊主筆）｜日期：2026-11-13｜取代 02 文件 §1.1 的初版 12 隻名冊
> 用途：每週「本週客人」的唯一來源。producer agent 依本檔的**排程表**決定主打異獸；copywriter 依本檔寫 Bestiary Card；art-director 依本檔的造型筆記畫圖；mythology-researcher 負責維護「查核狀態」欄。

---

## 0. 查核方法與限制（請先讀）

- **24 隻全部出自《山海經》本文**（不收白澤、鯤等後世或他書的生物，見 02 文件 §1.1）。
- 原文已對照兩個數位化版本逐句比對：
  1. 《正統道藏》本《山海經》（附郭璞注；殆知閣古籍語料 `道藏/正统道藏太玄部/山海经.txt`）
  2. 另一通行本全文（殆知閣 `史藏/志存记录/山海经.txt`）
  - 兩者都是**簡體 OCR 文字**，我們用 OpenCC 轉成繁體，所以可能有轉換造成的異體字（例如 叫／訆／詨、采／彩、鍾／鐘）。兩個版本都有 OCR 錯字，凡是兩本不一致的地方都在下表標出。
  - 維基文庫、ctext.org 在本工作環境連不上。**正式上線前**，mythology-researcher 仍要用維基文庫或 ctext 再逐字看一次（特別是標 ⚠️ 的項目）。
- **英文白話翻譯全部是我們自己翻的**（原文是公有領域；現代出版的英譯本有版權，不得引用）。
- 查核狀態代號：
  - ✅ 兩個版本一致（或差異只是明顯的 OCR 錯字），可直接使用
  - ⚠️ 有字無法確認、版本異文，或解讀有爭議：見該條說明，卡片上用保守寫法
- 卡片引用原則：**只引描述外形、聲音、祥瑞的句子**。「食之…」「佩之…」這類「吃牠／戴牠的皮可以治病」的句子，大多不放進卡片（不符合療癒品牌，也容易被誤讀成醫療建議）。

---

## 1. 前 12 週排程（輪播表）

輪播規則（4 週一輪）：**Study → Work → Sleep → Census 特輯**。Census 特輯的主角由當月 Bestiary Census 投票決定（三選一），沒有投票結果時用「預設」。節氣或節日可以和相鄰週對調（W52／W53 就是這樣）。12 週後依 YouTube Analytics 調整比重（例如 Study 流量明顯較高，就改成 Study, Sleep, Study, Work）。

| 週次 | 日期（週一） | No. | 系列 | 主打異獸 | 備註 |
|---|---|---|---|---|---|
| 2026-W47 | 11/16 | 001 | Study | **狌狌 Xingxing**（Sing 的同族） | **試產週**：ACE-Step 與 Stable Audio 3 盲聽比較 |
| 2026-W48 | 11/23 | 002 | Work | **鹿蜀 Lushu** | 本週一發第一次 Census 投票貼文 |
| 2026-W49 | 11/30 | 003 | Sleep | **旋龜 Xuangui** | |
| 2026-W50 | 12/07 | 004 | Census 特輯（2 小時） | 投票：**文鰩魚**／鳳皇／耳鼠（預設：文鰩魚） | 系列跟著得票異獸走 |
| 2026-W51 | 12/14 | 005 | Study | **灌灌 Guanguan** | 本週一發第二次投票貼文 |
| 2026-W52 | 12/21 | 006 | Sleep | **燭陰 Zhuyin** | 冬至（12/21）長夜特別篇；與 W53 對調 |
| 2026-W53 | 12/28 | 007 | Work | **當康 Dangkang** | 跨年；「見則天下大穰」＝新年豐收祝福 |
| 2027-W01 | 01/04 | 008 | Census 特輯 | 投票：**鸞鳥**／夔／讙（預設：鸞鳥） | |
| 2027-W02 | 01/11 | 009 | Study | **精衛 Jingwei** | 溫柔處理溺水的故事；本週一發第三次投票貼文 |
| 2027-W03 | 01/18 | 010 | Work | **帝江（Dandan）** | 「Dandan Session」：第 10 集由常駐樂師當主角 |
| 2027-W04 | 01/25 | 011 | Sleep | **冉遺之魚 Ranyi fish** | |
| 2027-W05 | 02/01 | 012 | Census 特輯 | 投票：**天馬**／乘黃／英招（預設：天馬） | 立春 2/4、農曆新年 2/6 在本週；畫面不做春節符號 |

- 流水號 `No.` 依**實際播出順序**編，不依名冊序號。投票落選的異獸回到候選池。
- 2026 年有 53 個 ISO 週，所以 W53 存在；資料夾名稱照用 `weekly/2026-W53/`。
- 若某週試產或生成失敗而延期，後面的週次整體順延，No. 不跳號。

---

## 2. 名冊總表（24 隻）

| # | 異獸 | 英文名（說明欄用） | 出處 | 系列 | 音樂情緒 | 查核 |
|---|---|---|---|---|---|---|
| 1 | 狌狌 | Xingxing | 南山經・招搖之山；海內南經 | Study | 溫暖、陪伴、夜讀 | ✅（兩章描述不同，見條目） |
| 2 | 鹿蜀 | Lushu | 南山經・杻陽之山 | Work | 明亮、會哼歌的午後 | ✅ |
| 3 | 旋龜 | Xuangui | 南山經・杻陽之山 | Sleep | 緩慢、木質 ASMR | ⚠️ 鳥首／烏首異文 |
| 4 | 文鰩魚 | Wenyao fish | 西山經・泰器之山 | Sleep（或 Work） | 夜飛、漂浮 | ✅ |
| 5 | 灌灌 | Guanguan | 南山經・青丘之山 | Study | 清醒、不分心 | ✅ |
| 6 | 燭陰 | Zhuyin | 海外北經・鍾山 | Sleep | 長夜、日夜交替 | ✅ |
| 7 | 當康 | Dangkang | 東山經・欽山 | Work | 豐收、輕快、勤勞 | ✅（叫／詨異文） |
| 8 | 鸞鳥 | Luan bird | 西山經・女牀之山 | Sleep | 安寧、祥和 | ✅ |
| 9 | 精衛 | Jingwei | 北山經・發鳩之山 | Study | 毅力、一點一點完成 | ⚠️ 烏／鳥、堙／煙 OCR |
| 10 | 帝江 | Dijiang（暱稱 **Dandan**） | 西山經・天山 | 全系列／特輯 | 識歌舞＝音樂本身 | ✅ |
| 11 | 冉遺之魚 | Ranyi fish | 西山經・英鞮之山 | Sleep | 無夢魘的深睡 | ⚠️「不眯」解讀 |
| 12 | 天馬 | Tianma | 北山經・馬成之山 | Work | 輕盈、飛起來的專注 | ✅（詨 字 OCR） |
| 13 | 乘黃 | Chenghuang | 海外西經・白民之國 | Sleep | 長久、悠遠 | ✅ |
| 14 | 鳳皇 | Fenghuang | 南山經・丹穴之山 | 特輯（Sleep） | 自歌自舞、天下安寧 | ✅ |
| 15 | 耳鼠 | Ershu | 北山經・丹熏之山 | Study | 小巧、輕快的翻頁 | ⚠️ 最後一句有缺字（不引用） |
| 16 | 夔 | Kui | 大荒東經・流波山 | Work（特輯） | 低沉鼓聲、雷雨 | ✅（聲／身 OCR） |
| 17 | 讙 | Huan | 西山經・翼望之山 | Work | 百種聲音＝取樣與拼貼 | ⚠️「奪百聲」缺字 |
| 18 | 英招 | Yingzhao | 西山經・槐江之山 | Work | 花園巡行、正午 | ✅ |
| 19 | 鵸鵌 | Qiyu bird | 西山經・翼望之山 | Sleep | 善笑、不做惡夢 | ⚠️ 名字有缺字 |
| 20 | 陸吾 | Luwu | 西山經・崑崙之丘 | Study | 守護、秩序、四季 | ✅（囿／圃異文） |
| 21 | 朏朏 | Feifei | 中山經・霍山 | Study | 解憂、毛茸茸的陪伴 | ⚠️ 名字兩本都是亂碼 |
| 22 | 三青鳥 | The Three Blue Birds | 西山經・三危之山；海內北經 | Study | 送信、往返、耐心 | ✅ |
| 23 | 騶吾 | Zouwu | 海內北經・林氏國 | Work | 五彩、日行千里 | ✅ |
| 24 | 九尾狐 | Nine-tailed fox | 南山經・青丘之山 | Sleep（**延後**） | 夜色、神秘 | ✅（但「能食人」，慎用） |

系列分布：Study 7、Work 7、Sleep 8、全系列／特輯 2（帝江、鳳皇）。

---

## 3. 條目

> 每條格式：出處｜原文｜白話英譯（我們自譯）｜系列與音樂｜造型筆記｜查核說明。
> 造型共通規則（art-director）：青綠山水＋明代版畫線條；異獸要能在縮圖小尺寸辨識；不做恐怖、血腥、恐怖谷；**人面異獸一律高度風格化**（面具感、版畫線條、閉眼或溫和表情）；不參考《觀山海》、遊戲或動畫造型，只參考明清古版畫（蔣應鎬本、汪紱本）的**構圖概念**。

### 1. 狌狌 Xingxing — No.001（Sing 的同族）
- **出處**：〈南山經〉南山經之首・招搖之山；另見〈海內南經〉
- **原文**：
  - 〈南山經〉「有獸焉，其狀如禺而白耳，伏行人走，其名曰狌狌，食之善走。」
  - 〈海內南經〉「狌狌知人名，其為獸如豕而人面，在舜葬西。」
- **英譯**："There is a beast here shaped like an ape, with white ears. It crawls on all fours and walks upright like a person. Its name is xingxing." / "The xingxing knows people's names."
- **系列與音樂**：Study。溫暖、陪伴感；古箏與 Rhodes 的對答、簫的夜讀曲。
- **造型**：同 Sing（白大耳、介於小猿與松鼠之間、松鼠尾），本週主角是一隻**年長的同族**：體型較大、銀灰毛、不穿衣服。避免像猴子或孫悟空。
- **查核**：✅ 兩本一致。郭璞注：「或作猩猩，字同耳」，所以讀音採 xīngxīng（英文 Xingxing）。⚠️ 注意：**〈海內南經〉的狌狌被描述成「如豕而人面」**，和〈南山經〉的白耳小猿不同。品牌選擇以〈南山經〉的外形＋〈海內南經〉的「知人名」，卡片上要誠實說明這一點（W47 說明欄已寫）。「食之善走」不放進卡片。
- **英文名注意**：不寫成「Sing Sing」（美國監獄名、2024 年電影名）。

### 2. 鹿蜀 Lushu — No.002
- **出處**：〈南山經〉杻陽之山
- **原文**：「有獸焉，其狀如馬而白首，其文如虎而赤尾，其音如謠，其名曰鹿蜀，佩之宜子孫。」
- **英譯**："There is a beast here shaped like a horse with a white head, striped like a tiger, with a red tail. Its voice sounds like a folk song. Its name is lushu."
- **系列與音樂**：Work。「其音如謠」＝會哼歌的動物；琵琶＋木吉他對話、明亮的徵調。
- **造型**：白頭、虎紋、紅尾的小型馬；邁步像在哼歌。紅尾用朱砂色，與印章呼應。
- **查核**：✅ 郭璞注「如人歌聲」。「佩之宜子孫」（指佩戴牠的皮）不放進卡片。

### 3. 旋龜 Xuangui — No.003
- **出處**：〈南山經〉杻陽之山（怪水）
- **原文**：「其中多玄龜，其狀如龜而鳥首虺尾，其名曰旋龜，其音如判木，佩之不聾，可以為底。」
- **英譯**："In its waters are many dark turtles, shaped like turtles but with a bird's head and a snake's tail. Their name is xuangui. Their voice sounds like wood being split."
- **系列與音樂**：Sleep。「判木」的木質聲可以做成極輕的木魚／木頭質感（每 2 小節一下以內）。
- **造型**：大而古老的龜，鳥喙狀的頭、細長蛇尾，半泡在月光淺灘裡睡覺。
- **查核**：⚠️ 道藏本作「烏首」，另一本作「鳥首」，多數通行本作「鳥首」，採「鳥首」；道藏本「其音曰一判木」為 OCR 錯字，郭璞注「如破木聲」可佐證「其音如判木」。

### 4. 文鰩魚 Wenyao fish — Census① 預設
- **出處**：〈西山經〉泰器之山
- **原文**：「是多文鰩魚，狀如鯉魚，魚身而鳥翼，蒼文而白首赤喙，常行西海，遊於東海，以夜飛。其音如鸞雞，其味酸甘，食之已狂，見則天下大穰。」
- **英譯**："Here are many wenyao fish, shaped like carp, with a fish's body and a bird's wings, blue-green markings, a white head and a red beak. They travel the Western Sea and roam the Eastern Sea, flying by night. … When they appear, the whole world has a rich harvest."
- **系列與音樂**：Sleep（夜飛、漂浮的 pad、簫）；也可做 Work（豐收）。
- **造型**：鯉魚身、鳥翼、青綠紋、白頭紅喙；成群在月夜的海面上低飛。
- **查核**：✅（另一本「鯉裏」為 OCR 錯字）。

### 5. 灌灌 Guanguan — No.005
- **出處**：〈南山經〉青丘之山
- **原文**：「有鳥焉，其狀如鳩，其音若呵，名曰灌灌，佩之不惑。」
- **英譯**："There is a bird here shaped like a dove. Its call sounds like someone calling out. Its name is guanguan. Wear [its feathers] and you will not be confused."
- **系列與音樂**：Study。「不惑」＝專注、不分心；商調古箏、乾淨的 boom-bap。
- **造型**：圓胖的斑鳩形小鳥，羽色石青與石綠，停在書架或竹簡上。
- **查核**：✅ 郭璞注「如人相呵呼聲」。同一座青丘之山也是九尾狐的出處，**本集畫面不放九尾狐**。

### 6. 燭陰 Zhuyin — No.006（冬至）
- **出處**：〈海外北經〉鍾山
- **原文**：「鍾山之神，名曰燭陰，視為晝，瞑為夜，吹為冬，呼為夏，不飲，不食，不息，息為風。身長千里。……其為物，人面，蛇身，赤色，居鍾山下。」
- **英譯**："The god of Mount Zhong is called Zhuyin. When it opens its eyes it is day; when it closes them it is night. Its out-breath is winter, its call is summer. It does not drink, does not eat, does not breathe; when it breathes, that is the wind. Its body is a thousand li long. … It has a human face and a red serpent body, and lives at the foot of Mount Zhong."
- **系列與音樂**：Sleep（冬至長夜）。單向下降的能量曲線、長 drone、雅樂（Lydian）漂浮感。
- **造型**：以「閉著眼的巨大紅色蛇身」橫跨山脈，臉部**遠景、閉眼、面具化**；畫面重點是夜色與山脊上的微光。可做成直播的日夜循環。
- **查核**：✅（鍾／鐘 異體）。郭璞注「燭龍也」：英文說明可寫「also known as Zhulong」。

### 7. 當康 Dangkang — No.007
- **出處**：〈東山經〉欽山
- **原文**：「有獸焉，其狀如豚而有牙，其名曰當康，其鳴自叫，見則天下大穰。」
- **英譯**："There is a beast here shaped like a piglet, with tusks. Its name is dangkang, and it calls out its own name. When it appears, the whole world has a rich harvest."
- **系列與音樂**：Work。輕快、溫暖、揚琴分解和弦；跨年週的「豐收」祝福。
- **造型**：圓滾滾的小野豬、短獠牙、可愛不兇；可以圍著小圍裙在茶寮幫忙。
- **查核**：✅ 道藏本「自叫」，另一本「自詨」（訆／詨／叫 古籍常互通）。卡片用「其鳴自叫」。
- **文化提醒**：豬的形象在部分觀眾群體中較敏感，說明欄不做「吃」的玩笑。

### 8. 鸞鳥 Luan bird — Census② 預設
- **出處**：〈西山經〉女牀之山
- **原文**：「有鳥焉，其狀如翟而五采文，名曰鸞鳥，見則天下安寧。」
- **英譯**："There is a bird here shaped like a long-tailed pheasant, with five-coloured patterns. Its name is luan. When it appears, all under heaven is at peace."
- **系列與音樂**：Sleep。「天下安寧」直接對應放鬆；古琴泛音、極少鼓。
- **造型**：長尾雉形、五彩但用礦物色低彩度表現；在夜裡收翅棲息。避免和遊戲中的鳳凰造型相似。
- **查核**：✅（采／彩 異體）。

### 9. 精衛 Jingwei — No.009
- **出處**：〈北山經〉發鳩之山
- **原文**：「有鳥焉，其狀如烏，文首，白喙，赤足，名曰精衛，其鳴自詨。是炎帝之少女，名曰女娃。女娃遊於東海，溺而不返，故為精衛。常銜西山之木石，以堙於東海。」
- **英譯**："There is a bird here shaped like a crow, with a patterned head, a white beak and red feet. Its name is jingwei, and it calls its own name. She was the youngest daughter of the Flame Emperor, named Nüwa. Nüwa went out on the Eastern Sea, drowned and never came back, and so became the jingwei. She carries twigs and pebbles from the Western Hills, again and again, to fill up the Eastern Sea."
- **系列與音樂**：Study。毅力、一次一顆石頭；穩定的 boom-bap、琵琶單音。
- **造型**：小黑鳥、花紋頭、白喙、紅腳，嘴裡銜一顆小石子；畫面溫柔，不畫溺水情節。
- **查核**：⚠️ 道藏本「其狀如鳥」「以煙於東海」為 OCR 錯字（郭璞注「煙，塞也，音因」證明原字是「堙」）；另一本作「如烏」「以堙」。採「如烏」「堙」。卡片可只引第一句與最後一句，溺水的部分用一句溫柔的英文帶過。
- **注意**：「女娃」（Nüwa）和女媧（Nüwa）英文拼法相同但不是同一人；英文寫「Nüwa (女娃, not the goddess 女媧)」。

### 10. 帝江 Dijiang／Dandan — No.010（常駐樂師）
- **出處**：〈西山經〉天山
- **原文**：「有神焉，其狀如黃囊，赤如丹火，六足四翼，渾敦無面目，是識歌舞，實惟帝江也。」
- **英譯**："There is a god here shaped like a yellow sack, red as cinnabar fire, with six feet and four wings. It is a formless blur with no face at all, and yet it knows song and dance. This is Dijiang."
- **系列與音樂**：全系列客串；No.010「Dandan Session」為 Work 特輯。代表「AI 作曲」：**沒有臉，卻懂得歌舞**。
- **造型**：圓滾滾的布囊身體、內部透出朱紅與金色的光、六隻短腳、四片小翅膀、**完全沒有臉**（沒有眼、鼻、口）。在 A 案的青綠山水畫風裡出現，不使用 B 案的剪紙風。每週 Study 場景可在遠處當小小的燈籠光客串。
- **查核**：✅（道藏本；另一本有「丹水」「無而目」等 OCR 錯字）。郭璞注把帝江和《莊子》的「混沌」連結，說明欄可以提一句。
- **命名注意**：英文標題與縮圖只用 **Dandan**；「Dijiang」只在卡片作學名（避開《明日方舟：終末地》的「帝江號」）。

### 11. 冉遺之魚 Ranyi fish — No.011
- **出處**：〈西山經〉英鞮之山
- **原文**：「是多冉遺之魚，魚身蛇首六足，其目如馬耳，食之使人不眯，可以禦凶。」
- **英譯**："Here are many ranyi fish, with a fish's body, a snake's head and six feet; their eyes are like a horse's ears. … They ward off misfortune."
- **系列與音樂**：Sleep。品牌敘事：「a fish that keeps bad dreams away」。極暗、極慢，簫與 pad。
- **造型**：在冰白的山溪裡（原文「鳥獸盡白」）緩慢游動的六足長魚；蛇首要圓潤、不兇。
- **查核**：⚠️ 道藏本可讀；另一本「其目如觀耳」為 OCR 錯字。「不眯」有兩種解讀：郭璞在〈翼望之山〉注引《周書》「厭者不眯」（＝不做惡夢），也提到「眯目」（眼睛進沙）。說明欄寫「traditionally read as 'free from nightmares'」，不要寫成確定的醫療功效。

### 12. 天馬 Tianma — Census③ 預設
- **出處**：〈北山經〉馬成之山
- **原文**：「有獸焉，其狀如白犬而黑頭，見人則飛，其名曰天馬，其鳴自詨。」
- **英譯**："There is a beast here shaped like a white dog with a black head. When it sees people, it flies. Its name is tianma, and it calls out its own name."
- **系列與音樂**：Work。輕盈、起飛的感覺；揚琴、明亮的吉他。
- **造型**：雖然叫「天馬」，其實是**白身黑頭的小狗**（郭璞注：肉翅飛行）。英文說明可以用「the 'sky horse' that is really a small flying dog」當鉤子。
- **查核**：✅ 道藏本「自訓」、另一本「自訁交」皆為 OCR，採「自詨」。

### 13. 乘黃 Chenghuang
- **出處**：〈海外西經〉白民之國
- **原文**：「白民之國在龍魚北，白身被髮。有乘黃，其狀如狐，其背上有角，乘之壽二千歲。」
- **英譯**："The Land of the White People lies north of the Dragon Fish; its people have white bodies and loose hair. There is the chenghuang, shaped like a fox with horns on its back. Whoever rides it lives two thousand years."
- **系列與音樂**：Sleep。悠長、時間很慢；長 pad、古琴泛音。
- **造型**：金黃色的狐形，背上（不是頭上）有角；要和日本 kitsune 明顯不同：不畫狐面具、不用紅白配色，走古版畫的樸素線條。
- **查核**：✅（被／披 異體）。

### 14. 鳳皇 Fenghuang
- **出處**：〈南山經〉丹穴之山
- **原文**：「有鳥焉，其狀如雞，五采而文，名曰鳳皇，首文曰德，翼文曰義，背文曰禮，膺文曰仁，腹文曰信。是鳥也，飲食自然，自歌自舞，見則天下安寧。」
- **英譯**："There is a bird here shaped like a rooster, with five-coloured patterns. Its name is fenghuang. The pattern on its head reads 'virtue', on its wings 'righteousness', on its back 'propriety', on its breast 'benevolence', on its belly 'trust'. It eats and drinks as it pleases, sings by itself and dances by itself. When it appears, all under heaven is at peace."
- **系列與音樂**：特輯（Sleep 或長篇）。「自歌自舞」可與帝江並列為「音樂之神」。
- **造型**：雞形、五彩但低彩度；**避免現代遊戲／動畫的火鳥造型**。身上的「德義禮仁信」紋只做抽象紋樣，不寫真的文字（AI 會畫出假字）。
- **查核**：✅ 道藏本作「鳳皇」（另一本作「鳳凰」）；道藏本「有烏焉」為 OCR 錯字。

### 15. 耳鼠 Ershu
- **出處**：〈北山經〉丹熏之山
- **原文**：「有獸焉，其狀如鼠，而菟首麋身，其音如獋犬，以其尾飛，名曰耳鼠。」
- **英譯**："There is a beast here shaped like a mouse, with a hare's head and a deer's body. Its voice is like a howling dog. It flies with its tail. Its name is ershu."
- **系列與音樂**：Study。小巧、輕快、翻頁感。
- **造型**：兔頭、鹿身比例的小老鼠，用大尾巴滑翔；很適合當 Sing 的書桌朋友。
- **查核**：⚠️ 後面「食之不□，又可以禦百毒」的「□」兩本都缺字或亂碼，**不引用**；卡片只引到「名曰耳鼠」。

### 16. 夔 Kui
- **出處**：〈大荒東經〉流波山
- **原文**：「東海中有流波山，入海七千里。其上有獸，狀如牛，蒼身而無角，一足，出入水則必風雨，其光如日月，其聲如雷，其名曰夔。黃帝得之，以其皮為鼓，橛以雷獸之骨，聲聞五百里，以威天下。」
- **英譯**："In the Eastern Sea is Mount Liubo, seven thousand li out to sea. On it lives a beast shaped like an ox, blue-grey, hornless and one-footed. Whenever it goes into or out of the water there is wind and rain. It shines like the sun and moon, and its voice is like thunder. Its name is kui."
- **系列與音樂**：Work 或特輯。低沉的鼓、雨聲；適合「鼓組特別篇」。
- **造型**：一足、無角的青灰色牛形，在海上的風雨與微光中。
- **查核**：✅（道藏本「其身如雷」為 OCR，另一本與郭璞系統作「其聲如雷」）。**黃帝以其皮為鼓的段落不放進卡片**（涉及殺生，品牌調性不合），只在說明欄用一句「the old book links it to the first great drum」。

### 17. 讙 Huan
- **出處**：〈西山經〉翼望之山
- **原文**：「有獸焉，其狀如狸，一目而三尾，名曰讙，其音如奪百聲，是可以禦凶，服之已癉。」
- **英譯**："There is a beast here shaped like a wildcat, with one eye and three tails. Its name is huan. It can mimic a hundred different sounds, and it wards off misfortune."
- **系列與音樂**：Work。「能作百種物聲」＝取樣拼貼、Foley 質感的 lofi；也可以當「AI 模仿聲音」的誠實寓言。
- **造型**：狸貓形、三條尾巴；「一目」要畫得可愛（像一隻大圓眼），避免恐怖感。
- **查核**：⚠️「奪」字兩本都缺（道藏本「其音如□百聲」、另一本亂碼）；通行本作「奪百聲」。郭璞注「言其能作百種物聲也」是解讀依據。**上線前務必用維基文庫確認**。

### 18. 英招 Yingzhao
- **出處**：〈西山經〉槐江之山
- **原文**：「實惟帝之平圃，神英招司之，其狀馬身而人面，虎文而鳥翼，徇於四海，其音如榴。」
- **英譯**："This is truly the Lord on High's hanging garden, and the god Yingzhao keeps it. It has a horse's body and a human face, tiger stripes and a bird's wings. It patrols the four seas."
- **系列與音樂**：Work（Work 系列的地點 Huaijiang Garden 就是牠的花園）。
- **造型**：馬身、虎紋、鳥翼；**人面要面具化**（像古代青銅面具的簡化線條）、遠景或側面。
- **查核**：✅（道藏本「四梅」為 OCR）。「其音如榴」郭璞自己也說「未詳」，卡片不翻這句。

### 19. 鵸鵌 Qiyu bird
- **出處**：〈西山經〉翼望之山
- **原文**：「有鳥焉，其狀如烏，三首六尾而善笑，名曰鵸鵌，服之使人不厭，又可以禦凶。」
- **英譯**："There is a bird here shaped like a crow, with three heads and six tails, and it loves to laugh. Its name is qiyu. … It is said to keep away bad dreams and ward off misfortune."
- **系列與音樂**：Sleep。郭璞注「不厭夢也」＝不做惡夢；溫柔、帶一點笑意的催眠曲。
- **造型**：三個頭要畫成可愛的「三兄弟擠在一起」，六條長尾像緞帶。
- **查核**：⚠️ 名字第二字在道藏本正文是缺字（「鵸□」），另一本作「奇餘」；道藏本圖讚中有「鵸鵌鳥」，通行本作「鵸鵌」。道藏本作「如鳥」、另一本作「如烏」。**上線前要確認**。

### 20. 陸吾 Luwu
- **出處**：〈西山經〉崑崙之丘
- **原文**：「是實惟帝之下都，神陸吾司之。其神狀虎身而九尾，人面而虎爪；是神也，司天之九部及帝之囿時。」
- **英譯**："This is truly the Lord on High's lower capital, and the god Luwu keeps it. It has a tiger's body with nine tails, a human face and tiger claws. This god governs the nine regions of heaven and the seasons of the Lord's gardens."
- **系列與音樂**：Study（崑崙書閣的守門人）。秩序、季節感；穩定的四度和聲。
- **造型**：虎身九尾、人面面具化、坐姿守門；九尾要和九尾狐明顯不同（虎紋、粗尾）。
- **查核**：✅ 道藏本作「囿時」，另一本作「圃時」（郭璞注作「苑圃之時」）。不要和 #23 騶吾混淆。

### 21. 朏朏 Feifei
- **出處**：〈中山經〉霍山
- **原文**：「有獸焉，其狀如狸而白尾，有鬣，名曰朏朏，養之可以已憂。」
- **英譯**："There is a beast here shaped like a wildcat, with a white tail and a mane. Its name is feifei. Keep one, and your worries will go away."
- **系列與音樂**：Study（考試壓力、解憂）。毛茸茸、溫暖的 Rhodes。
- **造型**：白尾、有鬃毛的小狸貓；很適合周邊與直播客串。
- **查核**：⚠️ **名字兩本都是亂碼**（「フフ」「腦腦」），「朏朏」是通行本的寫法，本次未能從數位本確認；其餘字句兩本一致。郭璞注音「普珠反」（OCR 可能有誤）。**排程前必須確認名字**。

### 22. 三青鳥 The Three Blue Birds
- **出處**：〈西山經〉三危之山；〈海內北經〉
- **原文**：
  - 〈西山經〉「三危之山，三青鳥居之。是山也，廣員百里。」
  - 〈海內北經〉「西王母梯几而戴勝杖，其南有三青鳥，為西王母取食，在崑崙虛北。」
- **英譯**："On Mount Sanwei live the three blue birds. The mountain is a hundred li around." / "The Queen Mother of the West leans on a low table, wearing her headdress and holding a staff. To her south are three blue birds, who fetch food for her."
- **系列與音樂**：Study（送信、往返、耐心）。曲名可延用「Qingniao Brings a Letter」。
- **造型**：三隻石青色的鳥，一起飛或並排停著。
- **查核**：✅ 兩本一致（几／幾 異體；郭璞注「梯謂憑也」）。

### 23. 騶吾 Zouwu
- **出處**：〈海內北經〉林氏國
- **原文**：「林氏國有珍獸，大若虎，五采畢具，尾長於身，名曰騶吾，乘之日行千里。」
- **英譯**："In the Land of Linshi there is a rare beast as big as a tiger, with all five colours, and a tail longer than its body. Its name is zouwu. Ride it and you can travel a thousand li in a day."
- **系列與音樂**：Work（效率、長途）。
- **造型**：五彩但低彩度的大貓、尾巴比身體長；**避開《怪獸與牠們的產地》系列電影中的 Zouwu 造型**（現代電影角色，有版權與辨識度風險）。
- **查核**：✅ 兩本一致。

### 24. 九尾狐 Nine-tailed fox（延後登場）
- **出處**：〈南山經〉青丘之山
- **原文**：「有獸焉，其狀如狐而九尾，其音如嬰兒，能食人，食者不蠱。」
- **英譯**："There is a beast here shaped like a fox with nine tails. Its voice is like a baby's cry. It can eat people; whoever eats it is safe from evil influences."
- **系列與音樂**：Sleep（若登場）。
- **造型**：只能採古版畫造型；避免日本 kitsune、韓國 gumiho、遊戲角色（例如 LoL 的 Ahri）。
- **查核**：✅（郭璞注「即九尾狐」）。**延後原因**：最接近 WA-HOP 的「妖怪」感，又容易和日韓形象混淆；原文「能食人」也不適合療癒頻道的卡片。建議 No.030 之後再評估。

---

## 4. 預備名單（已初步查核，未排入 24 隻）
狡（西山經・玉山：「其狀如犬而豹文，其角如牛……見則其國大穰」）、吉量（海內北經：「縞身朱鬣，目若黃金……乘之壽千歲」）、何羅魚（北山經：「一首而十身」）、類（南山經：「其狀如狸而有髦」）、夫諸（中山經：「其狀如白鹿而四角」，但「見則其邑大水」，慎用）、畢方（西山經章莪之山：「其狀如鶴，一足」，但「見則其邑有訛火」，慎用）。

## 5. 不收錄（不在《山海經》或不適合）
- **白澤**：出自後世《白澤圖》等，不在《山海經》。
- **鯤**：出自《莊子・逍遙遊》。
- **窮奇、刑天、蠱雕、犀渠等凶獸／食人獸**：不做主角，也不用於 Sleep 曲名。
- **鳳皇、九尾狐等現代流行造型很多的異獸**：可以做，但造型要回到古版畫，避免任何現代 IP 的樣子。
