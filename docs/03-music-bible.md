# 03 — Music Bible（音樂聖經）v2

> 角色：Music Director｜版本：**v2.0（2026-11-13 改版）**
> 改版重點：① 融入中國傳統樂器 ② 視覺世界觀改為《山海經》 ③ 生成工具改為**開源 text-to-music 模型（預計 ACE-Step，研究中）**，prompt 改為通用的 tag／描述格式；Suno 版本降為附錄。
> 適用：原創 lofi／chill beats 頻道（24/7 直播＋每週一支 1–2 小時合輯，約 20 首新曲／週）
> 語言規則：說明用繁體中文；prompt 與曲名為英文（曲名可加中文副標）。
> 系列名稱暫定 Study/Focus、Sleep/Relax、Work/Café，之後可能由 Creative Director 改名（例如對應山海經的「山／海／荒」）；本文件用代號 **S／L／C** 指稱，改名不影響內容。

---

## 0. 生成工具基準（工具無關，以 ACE-Step 為主要假設）

### 0.1 通用 prompt 結構
開源 text-to-music 模型（ACE-Step 1.5、YuE、Stable Audio Open 等）普遍吃「逗號分隔的 tag／短描述」。本文件每個模板分成四行：

```
CAPTION: <類型>, <主奏樂器>, <和聲／伴奏樂器>, <鼓>, <質感>, <情緒>, <場景變數>, instrumental
PARAMS:  bpm={BPM} | key={KEY} | duration={DUR}
LYRICS:  [Instrumental]
NEG:     <若工具支援負面提示才填>
```

| 項目 | 作法（依目前供應商文件與社群指南整理，需在試產週驗證） |
|---|---|
| Caption 長度 | ACE-Step 1.5 的風格描述上限約 **512 字元**。本文件模板（變數展開後）控制在約 **250–420 字元**。最重要的詞放最前面。 |
| BPM／調性／長度 | ACE-Step 1.5 有獨立參數（bpm、key/keyscale、duration），**優先用參數設定，不要寫在 caption 內**。若工具無此參數（例如其他模型），再把 `{BPM} BPM, {KEY}` 加進 caption 開頭。 |
| 純音樂 | Lyrics 欄填 `[Instrumental]`（部分平台則是留空）。caption 末尾加 `instrumental`。 |
| 結構 | 若需引導結構，Lyrics 欄可用 `[Intro] [Instrumental] [Break] [Instrumental] [Outro]`；caption 裡提到的樂器要與結構一致。 |
| 長度 | duration 設 150–210 秒（S／C）、180–300 秒（L）。開源模型長度越長，後段越容易崩壞，建議**寧短勿長**。 |
| 固定種子 | 記錄每首的 seed；好聽的 seed 可在同模板換變數再用一次，但同 seed 同週最多 2 次。 |
| 中文名詞 | **不要在 caption 寫山海經的地名或生物名**（模型不認得，反而可能引入中文人聲或「古風歌曲」）。山海經只放在曲名與視覺；caption 用英文意象描述（misty jade mountain、glowing tree grove…）。 |
| 避免的泛用 tag | `chinese style`、`oriental`、`asian`、`guofeng`、`gufeng`、`chinese traditional music`、`wuxia`、`kung fu`。這些 tag 容易拉出刻板的五聲音階快跑、大鑼、古風人聲。**一律改寫具體樂器名＋lofi 類型**。 |
| 授權 | 每個模型的權重授權不同。ACE-Step 以寬鬆開源授權發佈（請確認目前版本授權條款）；**Meta MusicGen／AudioCraft 權重為 CC-BY-NC（非商業），不可用於營利頻道**；Stable Audio Open 採 Stability 社群授權（有營收門檻）。正式量產前由負責人確認並存檔授權文字。 |
| 紀錄 | 每首紀錄：模型名稱＋版本、checkpoint、seed、caption、params、生成日期 → `tracks.csv`。 |

---

## 1. 中國樂器 × lofi：核心美學原則

### 1.1 美學一句話
**「爵士和聲當地基，中國樂器當聲音、不當標語」**——中國樂器是聲音色彩與呼吸，不是「中國風」的提示鈴。

### 1.2 五聲調式與 lofi 和聲的結合

| 調式 | 音階（以 D 宮為例） | 對應西方色彩 | 適合 |
|---|---|---|---|
| 宮 gong | D E F# A B（do re mi sol la） | 大調五聲；搭 maj7 / 6/9 | C 系列主力；S 系列明亮曲 |
| 商 shang | E F# A B D（re mi sol la do） | 類 Dorian／sus 色彩；搭 m11、sus4 | **S 系列主力**（最接近 jazz-hop 的 Dorian） |
| 角 jue | F# A B D E（mi sol la do re） | 曖昧、懸浮；搭 maj7#11 或 m7 | L 系列少量（較少用，易不穩） |
| 徵 zhi | A B D E F#（sol la do re mi） | 類 Mixolydian；搭 dom9sus4、6/9 | **C 系列主力**（陽光、開放） |
| 羽 yu | B D E F# A（la do re mi sol） | 小調五聲；搭 m9、m7 | S 系列與 L 系列的夜晚曲 |

七聲擴充（點綴用）：清樂（≈Ionian）、雅樂（加變徵 #4，≈Lydian，**L 系列的漂浮感來源**）、燕樂（加閏 b7，≈Mixolydian）。

**結合技巧（避免俗套）：**
1. **五聲音 = 爵士延伸音**：五聲音階的音落在 maj7 / m9 / m11 / 6/9 和弦上天然就是 9、11、13 延伸音——旋律用五聲、和弦用 jazz voicing，兩者自然融合，不會互撞。
2. **四度疊置（quartal voicing）**：Rhodes／鋼琴用四度和弦，與古箏、古琴的五聲調弦同色系。
3. **旋宮轉調**：段落間做五度關係的「旋宮」（例如 D 宮 → A 宮），對應爵士的 ii–V 轉調，聽感新鮮又不突兀。
4. **一首只用一個中國主奏樂器**，最多再加一個中國質感樂器（共 ≤ 2 件）。
5. **用技法而非音階說話**：古箏的按音（bend）、吟揉（vibrato）、泛音；古琴的泛音與走手音（滑音）；簫的氣聲；琵琶的單音推拉——這些「演奏法」才是質感來源。
6. **呼吸與留白**：中國樂器旋律句子短、句間留 1–2 小節空白，讓 Rhodes 或吉他「回答」（call & response）。

### 1.3 刻板印象黑名單（AVOID）
- 「Oriental riff」：連續五聲音階快速上下行（尤其 do-re-mi-sol-la-sol-mi-re 那種 2 小節套句）。
- 開頭一聲大鑼（gong crash）或鈸、功夫片配樂式打擊。
- 二胡過度滑音哭腔、尖銳高把位長音。
- 笛子高音區長時間尖叫；琵琶輪指（tremolo）大量密集快彈。
- 平行四度的旋律疊、「中國城餐廳背景音樂」式配器。
- 編鐘大量連續敲擊（變成廟會）。
- 任何「古風歌曲」人聲、戲曲唱腔、吟誦。

### 1.4 長時間聆聽友善（Sustain-friendly）
- 中國樂器是**撥弦／吹管瞬態明顯**的樂器：混音時對古箏、琵琶、揚琴的 2–5 kHz 稍做柔化（-2～-3 dB）並加短 room reverb。
- 主奏樂器出現比例 ≤ 全曲 50%，其餘時間交給和聲墊與鼓。
- 不要讓中國樂器在高頻（> 8 kHz）有持續能量（笛、二胡高把位易刺耳）。

---

## 2. Sound Bible — S 系列：Study / Focus（爵士 lofi hip hop × 中國樂器）

**定位**：專注、溫暖、有爵士和聲；山海經的「書齋與高山」——夜讀、雲霧山房、迷穀之光。

| 項目 | 規格 |
|---|---|
| BPM | **70–90**（主力 76–86），swing 55–62% |
| 調性／調式 | 商調（≈Dorian）與羽調（≈小調五聲）為主；**D, E, G, A, C** 為優先主音（古箏、簫、笛常用調，取樣也較容易配合） |
| 和聲 | m9 / m11 / maj7 / 6/9、ii–V–I、四度疊置；4 或 8 小節循環 |
| 西方樂器（地基） | Rhodes／Wurlitzer（和聲主體）、upright bass 或柔和 sub、jazz guitar 點綴 |
| 鼓 | laid-back boom-bap，鬆、晚一點的 snare；可用 **muyu 木魚** 或 **paiban 拍板** 取代 rimshot（低量） |
| 質感 | vinyl crackle、tape hiss、低量雨聲／山風 |
| 混音 | 溫暖、偏暗、高頻柔化；中國主奏樂器置中略偏、帶短 room reverb |

**中國樂器角色表（S）**

| 樂器 | 角色 | 用法 |
|---|---|---|
| 古箏 guzheng | **主奏旋律**（首選） | 稀疏短句＋按音、泛音；不用刮奏（glissando）除非在段落轉換、且 ≤ 1 次 |
| 琵琶 pipa | 主奏旋律（次選） | 單音、推拉弦；**不用**密集輪指 |
| 簫 xiao | 主奏旋律（夜讀曲） | 低音區長音、氣聲；與 Rhodes 對答 |
| 古琴 guqin | 質感／裝飾 | 泛音點綴、段落開頭；（模型渲染差，建議後製疊加，見第 6 節） |
| 揚琴 yangqin | 裝飾 | 偶爾輕敲和弦分解，取代 vibraphone |
| 木魚 muyu | 打擊質感 | 取代 rim click，量很低 |
| 二胡 erhu | 少用 | 僅在 bridge 一句長音；情緒太強，不當主奏 |

**AVOID（S）**：人聲／vocal chop／rap、trap hi-hat、EDM drop、鑼鈸開場、古箏大刮奏連發、笛子尖銳高音、二胡哭腔獨奏。
**參考描述（不用真名）**："scholar's mountain study at night", "jazz chords meet plucked zither under lamplight", "dusty boom-bap from an old tea-house record", "misty pine studio, ink and rain".

**NEG（工具支援時）**：`vocals, singing, choir, rap, gong crash, cymbal crash, trap hi-hats, edm, chinese pop, opera`

---

## 3. Sound Bible — L 系列：Sleep / Relax（ambient × 中國樂器）

**定位**：入睡與放空；山海經的「海與夜」——十二個月亮、若木暮光、弱水、雲海。

| 項目 | 規格 |
|---|---|
| BPM | **50–70**；或無明確節拍（ambient）——開源模型的 free tempo 不穩定，建議仍設 bpm=56–62 並寫 `slow steady pulse` |
| 調性／調式 | 宮調＋雅樂（#4，≈Lydian）漂浮感；羽調做夜色。**D, G, F, C** |
| 和聲 | 長延音 pad、add9 / maj7 / sus2、根音 drone；2–4 小節才換和弦 |
| 西方樂器（地基） | warm analog pad、felt piano、soft sub drone、bowed strings 低量 |
| 鼓 | 無鼓為主；有鼓時只用 brushed／muffled kick，或**極輕的木魚**（每 2 小節一下以內） |
| 質感 | 遠處海浪、山風、雨、柔和 tape hiss（擇一，低量） |
| 混音 | 很暗、很寬、動態小、無尖銳瞬態；淡入淡出各 5–10 秒 |

**中國樂器角色表（L）**

| 樂器 | 角色 | 用法 |
|---|---|---|
| 古琴 guqin | **主奏**（首選，概念上最契合） | 泛音、慢速散板感短句、大量留白（渲染風險高 → 第 6 節後製方案） |
| 簫 xiao | **主奏** | 低音區、長音、氣息；最適合入睡 |
| 古箏 guzheng | 主奏／質感 | 只用泛音與單音，不要快速分解 |
| 寺鐘 temple bell／頌缽 | 裝飾 | 每 30–60 秒一下以內，低量、長尾；避免在曲末突然出現 |
| 編鐘 bianzhong | 裝飾（極少） | 段落開頭一聲，低通處理 |
| 二胡 erhu | 質感（選配） | 極低量、長弓長音如弦樂墊；不做旋律 |

**AVOID（L）**：任何人聲（含 choir「ahh」、吟誦）、木魚密集、鐘聲突然大聲、笛子（太亮）、琵琶與揚琴（瞬態太強）、不和諧音、音量突升、鳥叫等突發音效。
**參考描述**："moonlit sea of clouds", "a zither's harmonics in an empty mountain hall", "twelve moons bathing in a quiet lake", "slow tide under ancient pines".

**NEG**：`vocals, choir, chanting, singing, drums, snare, hi-hats, gong crash, bright flute, fast plucking`

---

## 4. Sound Bible — C 系列：Work / Café（木吉他 chill beats × 中國樂器，白天）

**定位**：白天、陽光、溫暖的工作節奏；山海經的「日與市」——羲和御日、湯谷十日、祝餘、當康豐年。

| 項目 | 規格 |
|---|---|
| BPM | **80–100**（主力 84–94） |
| 調性／調式 | 徵調（≈Mixolydian）與宮調（大調五聲）為主；**G, D, A, C, E** |
| 和聲 | maj7 / add9 / 6/9、I–vi–ii–V、IV–iii–ii–I |
| 西方樂器（地基） | nylon／steel acoustic guitar（和聲主體）、soft Rhodes、melodic bass |
| 鼓 | 清爽 lofi：tight snare、soft kick、shaker；**木魚、拍板**可做律動點綴 |
| 質感 | 輕量茶館／咖啡店底噪（不要人聲交談）、微風 |
| 混音 | 溫暖、中高頻比 S 稍亮；小空間 reverb |

**中國樂器角色表（C）**

| 樂器 | 角色 | 用法 |
|---|---|---|
| 琵琶 pipa | **主奏**（與木吉他對話） | 明亮單音短句、推拉；最多一小段輕輪指 |
| 揚琴 yangqin | **主奏／分解和弦** | 輕快分解，取代 kalimba／glockenspiel |
| 笛子 dizi | 主奏（短句） | 中低音區、短樂句；每首 ≤ 3 段 |
| 古箏 guzheng | 和聲質感 | 分解和弦搭配吉他 |
| 二胡 erhu | 旋律（選配） | 溫暖中音區一段 B 段旋律；避免哭腔滑音 |
| 木魚／拍板 | 打擊點綴 | 與 shaker 交替 |
| 葫蘆絲 hulusi | 選配 | 偶爾替代笛子，音色柔和（渲染不穩定，試產再決定） |

**AVOID（C）**：人聲、可辨識人聲交談、鑼鈸、「功夫片」式快速笛子、country twang、EDM synth、熱鬧廟會打擊、琵琶激烈輪指。
**參考描述**："sunlit tea-house terrace", "lute and acoustic guitar trading phrases", "morning market in a mountain town", "ten suns rising over a calm valley".

**NEG**：`vocals, singing, crowd talking, gong crash, cymbals, edm, country, rock drums, chinese pop`

---

## 5. Prompt 模板（每系列 10 個，工具無關格式）

### 5.1 變數 Slot 字典

| Slot | 可選值 |
|---|---|
| `{SEASON}` | early spring, late spring, midsummer, late summer, early autumn, deep autumn, early winter, midwinter |
| `{WEATHER}` | light rain, mountain drizzle, rolling fog, first snow, soft snowfall, clear sky, warm breeze, after-storm calm, misty morning haze, frosty air |
| `{TIME}` | dawn, early morning, late morning, noon, golden hour, dusk, blue hour, late night, 2am, 3am |
| `{SCENE}`（山海經意象，英文描述） | misty jade mountain, sea of clouds, glowing tree grove, ancient pine shrine, cliffside library, moonlit lake, hidden valley spring, bamboo forest path, quiet island temple, terraced tea hills, river of floating lanterns, peach blossom forest |
| `{BPM}` | 依各系列範圍 |
| `{KEY}` | 依各系列調性欄，例如 `D minor`、`G major` |
| `{DUR}` | S／C：150–210；L：180–300（秒） |

規則：同週同模板最多用 2 次；`{SCENE}` × `{SEASON}` 組合同月不重複；每週由「週變數卡」分配（第 9 節）。
若工具沒有 bpm／key 參數，把 `{BPM} BPM, {KEY}, ` 加到 caption 最前面。

### 5.2 S 系列模板（S01–S10）

```
S01
CAPTION: jazzy lofi hip hop, guzheng melody with gentle string bends, warm Rhodes jazz chords, upright bass, laid-back boom-bap drums, vinyl crackle, focused and calm, {WEATHER} over a {SCENE} at {TIME}, {SEASON}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
S02
CAPTION: lofi jazz hop, low bamboo flute xiao phrases with breathy tone, detuned Rhodes minor ninth chords, soft sub bass, lazy swung drums, tape hiss, late-night study mood, {TIME} in a cliffside library, {WEATHER}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
S03
CAPTION: chill boom-bap, pipa single-note melody, mellow electric piano, round upright bass, soft wooden block percussion instead of rimshot, dusty vinyl texture, contemplative, {SEASON} {TIME} at a {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
S04
CAPTION: jazzy lofi beat, quartal piano chords, sparse guzheng harmonics answering the piano, warm bass guitar, brushed snare, light {WEATHER} ambience, minimal and uncluttered, deep focus, {SCENE} at {TIME}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
S05
CAPTION: lo-fi jazz hip hop, hammered dulcimer yangqin arpeggios, Wurlitzer chords, walking upright bass, swung hi-hats, soft kick, cassette warmth, steady and productive, {SEASON} evening, {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
S06
CAPTION: mellow jazzhop, guzheng and Rhodes call and response, dorian mood, soft muted trumpet pad far in background, relaxed boom-bap groove, filtered breakdown, tape saturation, {WEATHER} at {TIME}, {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
S07
CAPTION: lofi hip hop study beat, pentatonic pipa phrases with slow bends, eleventh chords on electric piano, muted bass, dusty sampled drums with loose swing, vinyl crackle, calm concentration, {SEASON} {TIME}, {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
S08
CAPTION: late-night jazz lofi, breathy xiao melody, dreamy chorus Rhodes, soft plucked zither texture, brushed drums behind the beat, warm sub bass, light rain, dark warm mix, {TIME} in a {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
S09
CAPTION: dusty jazz beat, jazz guitar chords, guzheng short phrases with vibrato, plucked double bass, soft boom-bap, faint temple wood block, tape hiss, focused and warm, {WEATHER} {SEASON} afternoon, {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
S10
CAPTION: cozy lofi jazz, slow two-five-one progression, Rhodes and celesta, sparse yangqin ornaments, warm upright bass, lazy swung drums, half-time break with zither alone, vinyl crackle, {TIME}, {SEASON}, {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Intro] [Instrumental] [Break] [Instrumental] [Outro]
```

### 5.3 L 系列模板（L01–L10）

```
L01
CAPTION: ambient lofi, slow guzheng harmonics, warm analog pads, soft felt piano, no drums, gentle sub drone, distant {WEATHER}, wide soft reverb, sleepy and peaceful, {SEASON} {TIME} over a {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
L02
CAPTION: slow dreamy ambient, low breathy xiao flute long notes, floating lydian synth pad, faint ocean waves, no percussion, slow steady pulse, warm dark mix, {TIME} by a {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
L03
CAPTION: sleep lofi, felt piano lullaby, sparse plucked zither notes, muffled soft kick, brushed snare very quiet, warm round bass, low-pass filtered, {WEATHER} at {TIME}, cozy {SEASON} night, {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
L04
CAPTION: ambient chill, sus2 and add9 pads, slow bowed strings low in the mix, single distant temple bell every phrase, granular shimmer, no drums, gentle mountain wind, soft and wide, {SEASON} night at a {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
L05
CAPTION: slow lofi ambient, meditative, warm Rhodes with long sustain, deep sub drone, very soft wooden block pulse, tape warble, distant {WEATHER}, {TIME} stillness, no sharp transients, {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
L06
CAPTION: dreamy sleep music, plucked zither harmonics and felt piano duet, airy synth pad, slow chord changes, quiet tape hiss, no drums, moonlit {SEASON} {TIME}, {SCENE}, very gentle dynamics, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
L07
CAPTION: ambient lofi, hazy and nostalgic, detuned cassette pad, low xiao melody with long silences, muffled soft kick, light rain on roof tiles, dark warm mix, long fade out, {TIME} in a {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
L08
CAPTION: calm ambient piano, sparse close-mic felt piano, warm string pad, soft erhu long tones blended like strings, subtle sub bass, no percussion, {WEATHER} drifting outside, {SEASON} {TIME}, {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
L09
CAPTION: lofi sleep beat, soothing, soft electric piano chords, gentle half-time brushed groove, warm round bass, guzheng single notes far in the background, very low vinyl hiss, slow filter sweeps, {WEATHER} at {TIME}, {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
L10
CAPTION: deep relaxation ambient, evolving warm drone, slow glassy pad, soft singing bowl and distant bronze bell, gentle wind texture, no drums, slow steady pulse, wide reverb, peaceful and still, {SEASON} {TIME} at a {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```

### 5.4 C 系列模板（C01–C10）

```
C01
CAPTION: acoustic lofi hip hop, fingerpicked nylon guitar, bright pipa answering phrases, soft electric piano, tight lofi drums with shaker, melodic bass, warm and upbeat, {SEASON} {TIME} at a {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
C02
CAPTION: chill acoustic beats, mixolydian, steel-string guitar riff, hammered dulcimer yangqin arpeggios, soft kick and rimshot, warm upright bass, breezy daytime mood, {WEATHER} over {SCENE}, clean warm mix, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
C03
CAPTION: tea-house lofi, mellow guitar chords maj7 and add9, short bamboo flute dizi melody in low register, brushed snare, soft kick, wooden block accents, gentle tape warmth, {TIME} at a {SCENE}, {SEASON} sunlight, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
C04
CAPTION: lofi guitar hip hop, warm fingerstyle guitar loop, guzheng arpeggios blending with guitar, light jazz chords on Rhodes, crisp swung hi-hat, round bass, small room reverb, laid-back and bright, {WEATHER} {TIME}, {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
C05
CAPTION: chillhop acoustic, hopeful and light, pipa melody with gentle slides, nylon guitar chords, soft string pad, shaker and clapper percussion, relaxed boom-bap kick, melodic bass, {SEASON} morning at a {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
C06
CAPTION: sunny lofi beat, easygoing, acoustic guitar strums and plucks, yangqin sparkle on top, Wurlitzer comping, tight snare, soft kick, faint tea cup clinks low in the mix, light vinyl, {TIME} {WEATHER}, {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
C07
CAPTION: acoustic chill hop, focused daytime groove, guitar and pipa interplay, warm bass guitar, brushed drums, short dizi phrase in the bridge, natural and clean, {SEASON} afternoon, {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Intro] [Instrumental] [Bridge] [Instrumental] [Outro]
```
```
C08
CAPTION: lofi café guitar, cozy and warm, warm erhu melody in mid register without heavy slides, fingerpicked guitar chords, soft piano, light shaker groove, round kick, warm tape, {WEATHER} at {TIME}, {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
C09
CAPTION: daytime chill beats, bright and steady, nylon guitar arpeggios, guzheng countermelody, crisp rimshot groove with wooden block, warm sub bass, gentle sidechain, polished warm mix, {SEASON} {TIME}, {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Instrumental]
```
```
C10
CAPTION: acoustic lofi hip hop, relaxed workflow mood, warm guitar loop with hammer-ons, soft Rhodes pads, yangqin melody, dusty but clean drums, melodic bass, short breakdown with plucked strings alone, {WEATHER} {SEASON} {TIME}, {SCENE}, instrumental
PARAMS: bpm={BPM} | key={KEY} | duration={DUR}
LYRICS: [Intro] [Instrumental] [Break] [Instrumental] [Outro]
```

### 5.5 填寫範例（S01）
```
CAPTION: jazzy lofi hip hop, guzheng melody with gentle string bends, warm Rhodes jazz chords, upright bass, laid-back boom-bap drums, vinyl crackle, focused and calm, mountain drizzle over a cliffside library at late night, deep autumn, instrumental
PARAMS: bpm=80 | key=D minor | duration=180
LYRICS: [Instrumental]
```
（caption 約 250 字元，低於 512 上限）

> 小技巧：模型常把 `guzheng` 誤成日本箏（koto）。若發生，caption 加 `chinese zither guzheng` 雙重描述；`xiao` 誤成尺八則加 `chinese end-blown bamboo flute xiao, soft and round`。

---

## 6. 中國樂器渲染風險與替代方案

> 下表是**試產前的預估**（依開源模型訓練資料以西方音樂為主的一般經驗），**不是量測結果**。第 0 週試產時每件樂器各生成 10 個 clip，由 Music Director 打分後更新本表。

| 樂器 | 預估渲染品質 | 常見問題 | 替代方案 |
|---|---|---|---|
| 古箏 guzheng | 中～佳 | 變成日本箏、harp；按音不自然 | 雙重描述；不行就疊樣本 |
| 琵琶 pipa | 中 | 像 mandolin／banjo；輪指糊成雜音 | 只要單音；改後製疊加 |
| 揚琴 yangqin | 中～佳 | 變成 hammered dulcimer（其實可接受） | 可接受，或改 celesta 替代 |
| 簫 xiao | 中 | 變成尺八或西洋長笛 | 可接受的氣聲長笛即可；或疊樣本 |
| 笛子 dizi | 中～差 | 缺少笛膜（buzz）特色，像西洋長笛 | 疊真實樣本；或改簫 |
| 二胡 erhu | 差～中 | 像小提琴、音準漂移、刺耳 | **建議後製疊加或真人錄音**；生成時只當弦樂墊 |
| 古琴 guqin | 差 | 訓練資料少，變成吉他／一般撥弦 | **一律後製**（樣本或真人錄音） |
| 編鐘 bianzhong | 差 | 變成 glockenspiel、甘美朗 | 用樣本單擊點綴 |
| 寺鐘／頌缽 | 中 | 偶爾音量突兀 | 後製疊 CC0 樣本，可控音量 |
| 木魚／拍板 | 佳 | 偶爾過大聲 | 混音降低；或後製疊樣本 |
| 葫蘆絲 hulusi | 未知 | 可能變成單簧管 | 試產後決定是否保留 |

### 6.1 後製疊加流程（Layering Workflow）
1. **生成地基**：用模板生成，但把風險高的樂器從 caption 拿掉，改寫成 `space for a plucked lead melody` 或讓 Rhodes／吉他主奏。PARAMS 固定 key 與 bpm，方便對拍、對調。
2. **確認調性與速度**：用免費工具（例如 DAW 內建分析、或開源 key/BPM 偵測）確認實際輸出的調與速度（模型不一定 100% 準）。
3. **疊中國樂器**：
   - **CC0 樣本**：Freesound 篩選 License = Creative Commons 0；只用 CC0（CC-BY 需署名、CC-NC 不可商用，避免）。
   - **免費取樣音源／SoundFont**：逐一確認授權允許「用於商業音樂作品」，授權文字存檔。
   - **MIDI＋免費虛擬樂器**：Music Director 依五聲調式寫短句（每週可建立 20–30 句「樂句庫」重複利用但換調換節奏）。
   - **真人錄音（最推薦，中期目標）**：找音樂系學生或線上接案樂手錄製古琴、二胡、笛子短句與即興素材包（買斷授權、書面合約）。這同時是最強的「人類原創」證據（見第 11 節）。
4. **去除不良樂器**：若生成曲某條中國樂器線很糟，用開源人聲／樂器分離工具（例如 Demucs）分離後刪除或降低該軌，再疊上替代音源。
5. **局部重繪**：若使用的模型版本支援 repaint／inpaint／extend 等編輯功能（ACE-Step 系列有此類功能，需以實際版本確認），只重生成壞掉的片段，而非整首重做。
6. 疊加後的樂器一樣要遵守第 1.3 節黑名單，並做 2–5 kHz 柔化與 room reverb，讓它「坐進」lofi 質感（加一點 tape saturation 與 crackle）。

---

## 7. 曲名產生法（山海經靈感）

### 7.1 原則
- 格式：**English Title · 中文副標**（副標可選；上架標題字數不夠時只留英文）。
- 取材山海經的**地名、神獸、草木、神話意象**，再與系列情境結合（讀書、睡眠、工作）。
- 優先挑「功能吻合」的典故：例如 **迷穀**（佩之不迷 → 專注）、**冉遺之魚／鵸鵌**（食／服之不做惡夢 → 睡眠）、**祝餘**（食之不飢 → 工作日常）、**帝江**（識歌舞 → 頻道吉祥物候選）。
- 不使用凶神惡獸作為 L 系列曲名（窮奇、刑天等）。不使用現代商標、遊戲／影視作品專有名稱（例如某山海經題材遊戲的角色名）。
- 曲名庫 `titles.csv` 查重，不得重複；避免「Lofi Beat #37」式編號。
- 描述欄可附一句典故說明（觀眾價值＋原創策劃證據），例如：「迷穀——《南山經》記載招搖山上的樹，花光照四方，佩戴者不會迷路。」

### 7.2 公式
| 公式 | 範例 |
|---|---|
| A. 典故 + 情境動作 | *Baize Takes Notes · 白澤筆記* |
| B. 地名 + 時間／天氣 | *Rain over Qingqiu · 青丘雨* |
| C. 意象 + 物件 | *Ten Suns, One Teacup · 十日一盞* |
| D. Under / Where / Before + 典故 | *Under the Migu Tree · 迷穀之下* |

### 7.3 範例曲名（每系列 20 個）

**S — Study / Focus（書齋與高山）**
1. Under the Migu Tree · 迷穀之下
2. Kunlun Library · 崑崙書閣
3. Lamp of Zhuyin · 燭陰之燈
4. Baize Takes Notes · 白澤筆記
5. Zhaoyao Mountain Study · 招搖山課
6. The Kaiming Gate · 開明之門
7. Ink of the Western Hills · 西山墨
8. Yingzhao's Night Round · 英招夜巡
9. Jianmu Ladder · 建木之梯
10. Lu Wu Keeps Watch · 陸吾守夜
11. Rain over Qingqiu · 青丘雨
12. Nine Gates, One Candle · 九門一燭
13. Jade Slips at Midnight · 夜讀玉簡
14. Yinglong over the Inkstone · 應龍硯上
15. Wenyao Fish at the Window · 文鰩過窗
16. Scroll of the Great Wilderness · 大荒卷
17. Kui's Slow Drum · 夔鼓慢板
18. Archive of the Feathered People · 羽民書庫
19. Lamplight on Mount Buzhou · 不周燈火
20. Footnotes from the Eastern Sea · 東海註腳

**L — Sleep / Relax（海與夜）**
1. Ranyi Fish Lullaby · 冉遺魚搖籃曲
2. Where the Qiyu Birds Sleep · 鵸鵌棲處
3. Changxi Bathes the Moons · 常羲浴月
4. Ruomu Twilight · 若木暮光
5. Drifting on Weak Water · 弱水漂流
6. Fusang Before Dawn · 扶桑未曉
7. Tanggu Mist · 湯谷霧
8. Moonfox of Qingqiu · 青丘月狐
9. Zhulong Closes Its Eyes · 燭龍閉目
10. Night on the Kunlun Hill · 崑崙夜
11. Where the Luan Bird Rests · 鸞棲
12. Penglai Tide · 蓬萊潮聲
13. Sea of the Great Wilderness · 大荒之海
14. Qingniao Brings a Letter · 青鳥捎信
15. Shatang Fruit Dream · 沙棠夢
16. Jade Mountain Hush · 玉山靜
17. Snow on Mount Buzhou · 不周雪
18. Twelve Moons Asleep · 十二月眠
19. Northern Sea Drift · 北海浮夢
20. Sleeping Jianmu · 建木眠

**C — Work / Café（日與市）**
1. Zhuyu Leaves for Breakfast · 祝餘早餐
2. Xihe Drives the Morning · 羲和御日
3. Sunbath at Tanggu · 湯谷曬日
4. Lushu Trots to Market · 鹿蜀趕集
5. Dijiang Learns to Dance · 帝江學舞
6. Dangkang Harvest · 當康豐年
7. Phoenix Morning at Danxue · 丹穴鳳晨
8. Xingxing on the Terrace · 狌狌在陽台
9. Fusang Sunrise Brew · 扶桑晨煮
10. Feathered People's Market · 羽民市集
11. Honey from Mount Zhaoyao · 招搖山蜜
12. Errands in the Huaijiang Garden · 槐江園事
13. Kuafu's Peach Grove · 夸父桃林
14. Wenyao Fish Fly at Noon · 文鰩午飛
15. Ten Suns, One Teacup · 十日一盞
16. Kunlun Tea Road · 崑崙茶道
17. Bright Feather Bazaar · 彩羽市
18. Jingwei Carries Pebbles · 精衛銜石
19. The Qingqiu Teahouse · 青丘茶館
20. Bifang Lights the Stove · 畢方生火

> 注意：Wenyao Fish、Fusang、Zhaoyao、Kunlun、Qingqiu、Buzhou 在不同系列各出現一次，屬刻意的「世界觀串連」；同一系列內不重複使用同一典故超過 1 次／月。

---

## 8. QA 檢查清單（每首必過）

評等：✅ 通過｜⚠️ 可修（後製）｜❌ 淘汰（重生成）

### 8.1 聆聽檢查（完整 1x 速度聽完，耳機＋喇叭各一次）
| # | 項目 | 判定 |
|---|---|---|
| 1 | **人聲洩漏** | 任何人聲、哼唱、「ooh/ahh」、古風唱腔、吟誦、似說話音節 → ❌；極輕微可分離移除 → ⚠️ |
| 2 | **AI 瑕疵** | 金屬／水聲感、高頻 shimmer、樂器變形、和弦融化、音高漂移、鼓組換音色 → 輕微 ⚠️，明顯 ❌ |
| 3 | **中國樂器真實度** | 樂器聽起來是「壞掉的某種東西」（不像古箏也不像任何樂器）→ ❌ 或改走第 6.1 節疊加；聽起來像別國樂器但好聽（如箏→koto）→ ⚠️，視曲目決定 |
| 4 | **刻板印象檢查** | 出現第 1.3 節黑名單任一項（oriental riff、鑼鈸開場、二胡哭腔、笛子尖叫）→ ❌ |
| 5 | **調性衝突** | 五聲旋律與和弦明顯互撞（例如旋律停在與和弦衝突的音上很久）→ ❌；疊加樣本後必再檢查 |
| 6 | **主奏比例** | 中國主奏樂器 > 全曲 60% 時間、或同時出現 > 2 件中國樂器 → ⚠️（剪輯／降量） |
| 7 | **開頭** | 至少 1 小節 intro；硬切 → 剪並做 0.5–2 秒淡入 |
| 8 | **結尾** | 不可突然斷掉或在句中結束；修：段落結尾剪＋淡出（S／C 4–8 秒、L 8–15 秒）。最後 10–20 秒崩壞（開源模型常見）→ 剪掉 |
| 9 | **重複度** | 同一循環完全不變 > 60 秒 → ⚠️；整首無變化 → ❌ |
| 10 | **系列符合度** | BPM 偏差 > 10 或風格跑掉（trap、EDM、C-pop、古風流行）→ ❌ |
| 11 | **L 系列專屬** | 無突兀音量跳升、尖銳打擊、突然的鐘聲；以睡前低音量測試 |
| 12 | **相似度** | 與本週或曲庫曲目旋律／和弦過度相似 → 淘汰較差者 |
| 13 | **疑似模仿既有作品** | 聽起來像知名歌曲、知名古曲改編（如某首廣為人知的古箏名曲旋律）→ ❌ |
| 14 | **長度** | S／C 1:50–3:40；L 2:30–6:00 |

### 8.2 技術檢查
| # | 項目 | 標準 |
|---|---|---|
| 15 | 格式 | 母帶 WAV 48 kHz / 24-bit（若模型輸出 44.1 kHz，重取樣一次即可，不要重複轉檔）；上傳音軌 AAC ≥ 320 kbps |
| 16 | 削波／True Peak | 見 8.3 |
| 17 | 低頻 mono 相容 | 切 mono 試聽，低音不消失 |
| 18 | 首尾靜音 | 頭 ≤ 0.2 秒、尾 ≤ 1 秒 |
| 19 | 溯源紀錄 | 模型＋版本、checkpoint、seed、caption、params、疊加樣本來源與授權、真人錄音合約編號 → `tracks.csv` |

### 8.3 響度規格（Loudness Spec）
YouTube 會把較大聲的影片**往下**正規化到約 -14 LUFS，但不會把小聲的往上拉。

| 系列 | Integrated | True Peak 上限 | LRA |
|---|---|---|---|
| S — Study / Focus | **-14 LUFS**（±1） | **-1.0 dBTP** | 4–8 LU |
| C — Work / Café | **-14 LUFS**（±1） | **-1.0 dBTP** | 4–8 LU |
| L — Sleep / Relax | **-16 LUFS**（±1） | **-1.5 dBTP** | 3–7 LU |

- 中國撥弦樂器瞬態峰值高，常讓 True Peak 超標 → 用 true-peak limiter（oversampling 開啟），不要靠削波。
- 合輯匯出後整體再量一次，目標 ±0.5。
- 24/7 直播不保證有 VOD 的自動正規化 → 直播清單所有曲目**預先**標準化；L 時段可在直播軟體整體再降 1–2 dB。
- ffmpeg 量測範例：`ffmpeg -i in.wav -af loudnorm=I=-14:TP=-1.0:LRA=7:print_format=json -f null -`（第二次帶入量測值做兩段式正規化）。

---

## 9. 合輯編排規則（Compilation Sequencing）

### 9.1 基本規格
- 1 小時（約 20–24 首）或 2 小時（約 40–45 首）；每支合輯 ≥ 60% 本週新曲，舊曲 8 週內不重複進合輯；任兩支合輯曲目重疊 ≤ 30%。
- 一支合輯一個系列＋一個山海經「篇章」主題（例如 S 系列「南山經・招搖山夜讀」、L 系列「大荒・十二月」、C 系列「東山經・湯谷晨市」）。

### 9.2 調性流
- 相鄰曲目依 **Camelot Wheel**：同號、±1、或關係大小調。五聲調式也可用「同宮系統」思考：D 宮的商調（E）、羽調（B）與 D 宮共享同一組五個音 → 這些曲目可直接相鄰，聽感無縫。
- 每 4–6 首允許一次五度「旋宮」（Camelot ±1）推進能量。
- 避免相鄰曲目差半音。

### 9.3 BPM 流
- 相鄰差 ≤ 6 BPM（L ≤ 4）；不做 beatmatch，靠 crossfade。

### 9.4 樂器流（新增）
- **相鄰兩首不可是同一件中國主奏樂器**（例如古箏 → 古箏）。建議循環：撥弦（古箏／琵琶／揚琴）→ 吹管（簫／笛）→ 無中國主奏（純 lofi 或只有質感）→ 撥弦…
- 每支合輯至少 25% 的曲目是「中國樂器僅作質感或完全沒有」，讓耳朵休息、避免主題疲勞。
- 鐘聲類（寺鐘、編鐘、頌缽）在合輯中每 10 分鐘最多出現一首。

### 9.5 能量曲線
| 系列 | 曲線 |
|---|---|
| S | 暖身（前 10%，柔、少鼓、簫或無中國主奏）→ 高原（中 70%，古箏／琵琶主奏穩定律動）→ 收尾（後 20%，漸柔）。選配：每 25 分鐘一首較柔曲當 Pomodoro 休息信號 |
| L | **單向下降**：前 1/3 有極輕律動＋古箏泛音 → 中段無鼓簫／古琴 → 末 1/3 最暗、只剩 pad 與 drone。後段絕不放鐘聲突出的曲子 |
| C | 晨光開場（揚琴／吉他）→ 中段最明亮（琵琶、笛子）→ 尾段溫和（像午後茶館） |

### 9.6 Crossfade
| 系列 | 長度 | 方式 |
|---|---|---|
| S | 3–5 秒 | equal-power；以 crackle／雨聲為黏著劑 |
| C | 2–4 秒 | equal-power；允許 1–2 秒換片空隙 |
| L | 6–10 秒 | 長 equal-power；不可有靜音空洞 |

- 第一首 2 秒淡入；最後一首完整淡出（L 15–30 秒）。完成後量整體響度。
- 描述欄附 tracklist 時間碼與每首一句典故說明。

### 9.7 24/7 直播
- 時段輪播（主要觀眾時區）：06–12 C｜12–18 S／C 交錯｜18–23 S｜23–06 L。
- 同曲重播間隔 ≥ 12 小時；直播清單同樣遵守 9.4 樂器流（播放清單可預排）。
- 每週加入通過 QA 的新曲、移除表現差的曲目。

---

## 10. 每週製作時程與輪替

### 10.1 產量配置（20 首新曲／週）

| 週次 | 主打（合輯） | 新曲配置（主／副／副） |
|---|---|---|
| 第 1 週 | S — Study / Focus | S 10、C 5、L 5 |
| 第 2 週 | L — Sleep / Relax | L 10、S 5、C 5 |
| 第 3 週 | C — Work / Café | C 10、L 5、S 5 |
| 第 4 週 | 山海經特輯（季節＋篇章，例如冬至「燭龍閉目」長夜 L 合輯、立春「扶桑」C 合輯） | 主題 10、其他各 5 |

- 開源模型在本機／免費 GPU 上生成，通過率預估比商業工具低（約 25–40%），每週需生成約 **60–80 個 clip**；生成本身快，但**試聽與疊加**是時間瓶頸。
- 預估每週約 4–8 首需要第 6.1 節的樣本疊加。

### 10.2 第 0 週：試產（正式上線前必做）
1. 確認最終模型與授權（工具研究結果出爐後）。
2. 樂器渲染測試：第 6 節表格中每件樂器各 10 個 clip → 更新風險表。
3. 每系列各測 10 個模板 × 2 組變數 → 刪除表現差的模板、調整用詞。
4. 建立 CC0／授權樣本庫與第一批 MIDI 樂句庫。
5. 確認母帶流程（響度、格式）可重複。

### 10.3 每週時程

| 日 | 工作 | 負責 |
|---|---|---|
| 週一 | 發布「週變數卡」（模板＋變數＋BPM／調／主奏樂器分配、山海經篇章主題）；檢視上週數據 | Music Director |
| 週二 | 生成批次 1（主打系列，約 30–40 clips）＋初篩 | 頻道主 |
| 週三 | 生成批次 2（副系列，約 30–40 clips）＋初篩 | 頻道主 |
| 週四 | QA 精篩、樣本疊加／分離修正、取曲名＋典故說明、母帶 | Music Director＋頻道主 |
| 週五 | 合輯編排、匯出、響度複檢；交視覺／上架團隊 | Music Director |
| 週六 | 合輯上架（tracklist、典故、AI 揭露）；更新直播清單 | 上架負責人 |
| 週日 | 緩衝／樂句庫與樣本庫維護／下週構想 | — |

---

## 11. 變化策略：避免「重複／大量製作內容」（inauthentic content）判定

**背景**：YouTube 於 2025-07-15 將 YPP 的 "repetitious content" 改名為 **"inauthentic content"**；官方表示使用 AI 本身不違規，打擊對象是大量製作、模板化、重複、被觀眾視為垃圾內容的影片。AI 音樂頻道是外界常點名的類型。

### 11.1 音樂層面
1. **模板 × 變數矩陣**：30 模板 × 季節 × 天氣 × 時間 × 山海經場景 × 調式 × 主奏樂器；週變數卡確保同週無重複組合。
2. **主奏樂器配額**：每週每系列同一中國主奏樂器 ≤ 40% 曲目；≥ 25% 曲目無中國主奏。
3. **調式配額**：每週每系列至少 3 種調式（宮／商／徵／羽…）、4 個不同主音。
4. **每月輪換 2 個模板**／系列。
5. **兄弟版淘汰**：同 prompt 的兩個輸出只留一首；另一首 4 週後、不同合輯才能用。
6. **人工創作層**（最重要的差異化）：每首至少一項——疊加 Music Director 寫的 MIDI 樂句、真人錄音片段、重排段落、自製 intro／outro 環境音。紀錄於 `edit_notes`。**中期目標：每週至少 3–5 首含真人演奏（古琴、二胡、笛子等）**。
7. **固定 seed 限制**：同 seed 同週 ≤ 2 次。

### 11.2 頻道層面（給其他部門的建議）
1. 每支合輯有獨立山海經篇章主題、獨立主視覺與敘事描述；不用編號標題。
2. 描述欄：tracklist、每首一句典故、AI 工具使用揭露（上傳時依規定勾選合成內容）。
3. 一週一支合輯＋直播；不一天多支相似影片。
4. 保存創作紀錄（變數卡、prompt、QA 評語、編排表、樣本授權、錄音合約），作為人工策劃證據。

### 11.3 紅線
- caption 寫真實藝人、樂團、廠牌、頻道、影視／遊戲作品名稱；要求「像某首歌／某首古曲」。
- 使用非商業授權的模型權重或樣本（CC-NC、MusicGen 權重等）。
- 未經 QA 上架；同一首改名當新曲上傳；一週上傳 > 3 支長合輯。
- 刻板「中國風」標語式音樂（第 1.3 節）。

---

## 12. 檔案與欄位規範

`tracks.csv` 欄位：
`track_id, series, title_en, title_zh, lore_note, template_id, season, weather, time, scene, mode, key, bpm, lead_cn_instrument, texture_cn_instrument, model, model_version, checkpoint, seed, duration_req, gen_date, layered_sources, sample_licenses, live_recording_ref, qa_status, qa_notes, edit_notes, lufs_i, true_peak, duration, used_in_compilations, live_playlist`

命名：`{S|L|C}-{YYYYWW}-{nn}_{title-slug}.wav`，例如 `S-202646-03_under-the-migu-tree.wav`

---

## 附錄 A：Suno 版本（備用，若日後仍採用 Suno）

- 開 **Instrumental** 開關；Style 欄（v4.5／v5／v5.5 約 1,000 字元上限，會靜默截斷）；Exclude Styles 用第 2–4 節的 NEG 清單（4–6 項即可）。
- 轉換規則：把任一模板的 CAPTION 去掉 `instrumental` 結尾，前面加 `{BPM} BPM, {KEY}, `，結尾加 `instrumental, no vocals`；LYRICS 欄放結構 tag：`[Intro] [Instrumental] [Break] [Instrumental] [Outro] [Fade Out] [End]`（Lyrics 欄**不要寫括號說明**，Suno 會唱出來）。
- Suno 不接受真實藝人名稱（會擋或忽略），一律用聲音描述。
- 商業使用需在付費方案期間生成；每季確認 ToS。
- 單次生成約 2–4 分鐘；避免 Extend（v5.5 Extend 有時變成另一首歌）。

範例：
```
S (Suno): 80 BPM, D minor, jazzy lofi hip hop, guzheng melody with gentle string bends, warm Rhodes jazz chords, upright bass, laid-back boom-bap drums, vinyl crackle, focused and calm, mountain drizzle over a cliffside library at late night, instrumental, no vocals
Exclude: vocals, choir, rap, gong, trap hi-hats, chinese pop

L (Suno): 58 BPM, G major, slow dreamy ambient, low breathy xiao flute long notes, floating lydian synth pad, faint ocean waves, no percussion, warm dark mix, 3am by a moonlit lake, instrumental, no vocals
Exclude: vocals, choir, chanting, drums, gong, bright flute

C (Suno): 90 BPM, G major, acoustic lofi hip hop, fingerpicked nylon guitar, bright pipa answering phrases, soft electric piano, tight lofi drums with shaker, melodic bass, warm and upbeat, late spring morning at terraced tea hills, instrumental, no vocals
Exclude: vocals, crowd talking, gong, cymbals, edm, country
```

---

## 附錄 B：研究來源（2026-11 查證）

- ACE-Step 1.5 參數（bpm／keyscale／duration、512 字元描述上限）：<https://help.scenario.com/articles/8442039029-ace-step-1-5-edit-the-essentials>
- ACE-Step 1.5 API（`[Instrumental]` 用法、duration 範圍）：<https://fal.ai/models/fal-ai/ace-step-1.5/api>、<https://replicate.com/fishaudio/ace-step-1.5/versions/74e3a7d383b18815e277de5223f5fe9d53d38832de15aa567fe729fa129d0d85/api>
- ACE-Step 1.5 README：<https://cdn.jsdelivr.net/gh/ace-step/ace-step-1.5@main/README.md>
- ACE-Step prompting 指南：<https://deapi.ai/blog/ace-step-1-5-prompting-guide-how-to-write-tags-structure-lyrics-and-generate-better-music>、<https://skills.sh/ace-step/ace-step-1.5/acestep-songwriting>
- 中國傳統音樂 waveform 生成的研究缺口（CPTGZ, IEEE Access 2024）：<https://doaj.org/article/07f3ba106248461481073364b09feea8>
- Suno 字元上限、Exclude、meta tags：<https://hookgenius.app/learn/suno-character-limits/>、<https://help.suno.com/en/articles/3161921>、<https://blakecrosley.com/guides/suno-ai-music-generation>、<https://jackrighteous.com/en-gb/blogs/guides-using-suno-ai-music-creation/extend-suno-song>
- YouTube inauthentic content 政策：<https://techcrunch.com/2025/07/09/youtube-prepares-crackdown-on-mass-produced-and-repetitive-videos-as-concern-over-ai-slop-grows>、<https://www.socialmediatoday.com/news/youtube-clarifies-monetization-update-inauthentic-repeated-content/752892/>

> 註：開源模型的 prompt 格式各供應商不一；中國樂器渲染品質目前沒有公開的比較評測（搜尋未找到），第 6 節為預估值，以第 0 週試產結果為準。
