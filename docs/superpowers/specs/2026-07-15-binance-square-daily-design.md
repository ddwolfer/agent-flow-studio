# Spec: binance-square-daily — 幣安廣場日更 pipeline

> 版本:v1.1(已上線 — 首篇已發、cron 已掛)
> 日期:2026-07-15
> 定位:**6 週實驗**,唯一 KPI = 追蹤數斜率;收益期望值 ≈ 0(見 §8)
> 前置研究:`finance-workflows/reports/binance-square-poc/`(drafts v1–v4 + square-style-study)
> KG 錨:`90d771bd`(可行性評估)、`7628581b`(貼文格式規則)、`3b5a218e`(官方 API 規格)

## v1.1 變更(推翻 v1 的兩個核心假設)

1. **官方發文 API 存在** — 創作者中心核發 key(`BINANCE_SQUARE_API_KEY`,.env 已填)。
   `POST /bapi/composite/v1/public/pgc/openApi/content/add`,header `X-Square-OpenAPI-Key`,
   payload `{contentType:1, bodyTextOnly}`。100 篇/日。已實測:2026-07-15 首篇
   post id 344963714872929(B 版美光文)。→「手動複製貼上」全部作廢,改全自動發文。
2. **執行環境改為常駐互動 session + in-session cron**(user 的 MacBook 24h 開機 +
   remote control 手機可回覆)→ 不再用 `claude -p`(**省下 credit pool,走訂閱池**),
   也不需要 Telegram listener — Claude 對話本身就是雙向選文通道。

### v1.1 每日流程(已上線)

```
10:43 cron(session 內,job 5e576b84)
  → compute_zones BTC/ETH(+ 熱題相關資產)
  → 對話中呈現 3 篇(A/B/C)+ 推薦
11:00 user 起床,手機 Claude 回「發A/發B/發C/skip」
  → 立即 API 發文 → 回報 shareLink → Telegram 1715 推發布紀錄(純 log)
14:00 fallback(一次性 job):user 未回覆 → 自動發 B(蹭話題篇,分發槓桿最大)
```

### 事件短文(2026-07-16 上線)

長文之外,每天 0-2 篇「事件反應短文」(1-3 句,實地研究顯示踩中熱點時刻的
短文 views 可達 24k,遠超長文)。機制:

- **兩個檢查點**:15:58(job a8f25c01,事件才發)與 21:04(job 45a15914,黃金時段
  **保底發文**:事件優先;無事件 → 發 1 篇「生活短文」— 2026-07-17 user 提議)
- **生活短文規則**:素材限「幣圈相鄰生活題」(恐懼貪婪指數眾生相 / 非財經大熱題的
  幣圈視角 / 交易者日常互動提問);**禁止編造個人經歷**(無虛構獲利餐、當年勇)—
  只能寫觀察、提問、通用交易文化;輕鬆有人味、結尾互動問句
- **觸發條件**:(a) BTC/ETH 日內 |漲跌| >3%;(b) 現價觸及/跌破「已發布」關鍵位
  (grep `_published.jsonl` 驗證);(c) 廣場熱題爆發且與覆蓋資產相關
- **短文規則**:1-3 句、有觀察零預測、不喊單;自我引用過日誌驗證;用字規範同 §2.2.5
- **自動發布**(短文時效性高,不等人工批准 — user 已同意);TG 留紀錄、事後可刪
- 上限 2 篇/日;21:04 檢查點若與 16:00 事件相同,須換角度或不發,不得重複敘事
- 發文時間全貌:長文 11:00-14:02(人工選/fallback)+ 短文 ~16:00 / ~21:00(事件才有)

### v1.5 自主選文(2026-07-22 上線 — user:「你可以自己決定發 AB 了」)

長文從「產 A/B 兩篇 → user 選」升級為「**我自主決策 + 立即發布 + 事後否決**」。
中間態達成(spec §自動化演進路徑的第 2 階段)。

**決策規則(從 8 天實際選擇反推,回測 8/8 全中):**
| 優先序 | 條件 | 選 |
|---|---|---|
| P1 | 有強熱題(>5k views)且與 BTC/ETH/QQQ 相關 | **B**(蹭話題) |
| P2 | 無強熱題,但幣有內部劇情(已發布關鍵位被測試/收復/突破、回扣兌現) | **A**(信譽鏈) |
| P3 | 跨資產故事(QQQ×幣圈脫鉤在發展) | **B**(差異化系列) |
| tie | 避免同資產/角度連兩天重複,選較新鮮的 | — |

**每日流程(v1.5):**
```
10:43 → compute_zones BTC/ETH/QQQ + 抓熱題 → 依規則決策 A/B
      → 字數 gate(220–350)通過後立即 API 發布 + append 日誌
      → Telegram 推:兩篇完整原文 + 「已自動發 X · 理由」+「不同意回『換』」
      → 不再建 14:02 fallback(已發)
```

**事後否決:** user 回「換」→ 重發另一篇;能刪 API 刪錯的,不能刪則告知 post id
由 user 在 App 刪。平常完全不需 user 動作(全外包達成)。

**取捨(已與 user 確認接受):** 自主後偶爾選得與 user 當下不同(如 7/18 灰色地帶);
規則保證方向對,不保證每天合心情 —— 換來零人工介入。

### 自動化演進路徑(2026-07-16 定案)

觀察:user 連續 2 天選 B(但兩天皆有大熱題可蹭,B 天然最強;需看無熱題日的選擇)。
決策:**分三階段,不直接跳 launchd + claude -p**:

1. **現階段(~7/20)**:照舊人工選,收滿 7 天樣本,重點觀察無熱題日 user 選什麼
2. **中間態**(若 B 連勝到週末):in-session cron 改「產文後立刻自動發、TG 通知、事後可刪」
   — 保留訂閱池計費 + session 記憶;規則傾向「有熱題發 B,無熱題發 C」而非永遠 B
   (保留 persona A/B test 數據);加一個 launchd watchdog(15:00 檢查當日是否已發文,
   未發推 TG 警告)補 session 脆弱性
3. **終態**(僅當 session 斷線實際造成斷更 >1 次):遷 launchd + `claude -p`(credit pool)

理由:人工 gate 的價值不只選文,是冷啟動期的品牌聲音品控(已實證:太長、術語等
問題都在 gate 抓到);且「拿掉等待」≠「換執行環境」,中間態零成本達成全自動。

**已知限制:**
- in-session cron 是 session-only + 7 天自動過期 → session 重啟或到期需重掛
  (重掛 prompt 已固化在 cron job 內文,照抄即可;未來可做成 skill 一鍵重掛)
- API 無「看漲/看跌」方向 chip 欄位(App 手動發文才有)— 待研究是否有未文件化欄位
- 發文時間 ~11:00-14:00,非研究建議的 20:00-23:00 黃金時段 — 冷啟動期樣本太小
  測不出差異,接受;有追蹤數後再考慮「早選晚發」變形
- 圖片/影片 upload API 未接(v1 純文字;官方 scripts 參考 binance-skills-hub)

---

## 1. 目標與非目標

### 目標
每日 18:30 TPE 自動產出 **3 篇幣安廣場貼文候選**(不同 persona × 側重),推到
Telegram topic `TELEGRAM_TOPIC_BINANCE_SQUARE`(=1715),user 看心情挑一篇
(或都不發)手動貼上廣場。單日人工投入 ≤5 分鐘。

### 非目標
- ❌ 不自動發文(幣安無發文 API;人工 gate 也是反降權保險)
- ❌ 不做盤中(1H↓)分析 — 沿用 price-zone spec 的日線限定
- ❌ 不帶單:不給雙向進出場價、不曬單、不寫「建議買入」
- ❌ 不以收益為目標(冷啟動返佣 ≈ $0,見研究)

---

## 1.5 規則庫(2026-08-08 起,單一事實來源)

本文件以下各節記錄的是**決策脈絡與why**;**當日執行用的規則已抽成版控 YAML**:

```
finance-workflows/rules/square/
  selection.yaml          P1/P2/P3 + tie-break + 承諾/問責覆寫
  format.yaml             220–350 字、結構公式、用字、零術語、禁用措辭
  personas/a-veteran.yaml A 有立場老手
  personas/b-detective.yaml B 數據偵探
  shorts/event.yaml       事件短文觸發條件
  shorts/casual.yaml      生活短文素材與禁區
  standby/clarity-act.yaml 待命素材
```

**為什麼要抽出來**:規則原本散在 cron prompt、本文件、以及對話記憶三處。
in-session cron 每 7 天過期,重掛時若沒把期間累積的判準補回去,規則就**靜默
消失**且沒有任何東西會提醒。改成 YAML 後:cron prompt 只說「照
`rules/square/` 執行」,改規則 = 改檔案 + commit,有 diff、有歷史。

取用方式:`python scripts/rules_loader.py --render square`
驗證:`python scripts/rules_loader.py --check`(壞掉的 YAML 會讓該份規則從
prompt 消失,所以 tests/test_rules_loader.py 對每個檔案都做解析與必要欄位檢查)

## 2. 內容規則(全部已實證定案)

### 2.1 長度與結構(KG `7628581b`)
- **220–350 字**(不含空白)。下限 = 挖礦資格 200 字 + buffer;上限 = user 親手濃縮示範的長度
- **結構公式:hook(1-2 句)→ 📌 條件式劇本/數據條列 → 開放式問句結尾**
- 砍掉中間說理鋪陳(滑動讀者不讀論證)
- 濃縮後通讀:引導句後必須有被引導的內容(懸空句檢查)

### 2.2 固定元素(每篇)
- `$幣種` 標籤 ×3 用滿(優先:當篇主角 > BTC > ETH/BNB)
- `#話題` ×5(至少 1 個蹭當日熱門話題,若有相關)
- ⚠️ 免責 footer:「非投資建議」+ 失效位 = 紀律線措辭
- 建議方向 chip(看漲/看跌)標注在草稿標頭,發文時選

### 2.2.5 用字規範(2026-07-16 定案,不再變動)

1. **內文:一律繁體中文**(發文者身分;廣場有「自動翻譯」,簡體讀者看到的是
   平台自動轉換後的簡體,觸及不受影響)
2. **蹭熱題 hashtag:照抄平台原字串,禁止繁簡轉換**(hashtag 為字串精確匹配,
   轉換 = 蹭到一個不存在的話題,失去話題頁分發)— 平台熱題通常為簡體
3. **自創 hashtag:繁體或中性**(#BTC #行情分析 #加密貨幣)

### 2.3 零術語規則(v3 定案)
發文禁用:CHoCH、BOS、FVG、equal lows/highs、liquidity、premium/discount、
invalidation、SMC、order block。每個結構概念用「行為描述」:

| SMC 術語 | 人話 |
|---|---|
| CHoCH / BOS | 「下跌的節奏第一次被打斷」「收盤站上前高」 |
| FVG | 「衝太快沒人成交的真空區」 |
| equal lows + 流動性池 | 「三次跌到同一位置都彈 → 大家停損掛同一處 → 大戶的提款機」 |
| liquidity sweep | 「往下捅一根把停損掃掉再漲」 |
| invalidation | 「跌破就代表我看錯」「紀律線」 |
| HH/HL | 「低點一個比一個高」 |
| range/equilibrium | 「箱內遊戲」「區間中軸」 |

### 2.4 Faithfulness 紅線
- 條件式立場 OK(「守住 X 看多,破了我錯」= 有 accountability 的劇本)
- 禁止:「必漲」「建議買入」「立刻上車」等誘導即時下單措辭
- 所有價位必須來自 zone JSON / 行情數據,LLM 不得發明價位
- **自我引用驗證(2026-07-16 新增,user 抓到的漏洞)**:任何「昨天說/上次提/之前給過」
  措辭,必須對 `reports/binance-square/_published.jsonl`(發文日誌:date/post_id/
  levels_mentioned/text)驗證通過才能寫。**草稿不算、TG 預覽不算,只有拿到 post id
  的才算「說過」。** 每次發文成功後必須 append 一筆進日誌。違規案例:短文範例寫
  「昨天說的 64,341」,但 7/15 實際發布的是美光文,64,341 只存在於未發布的草稿 —
  對讀者而言是引用了不存在的歷史,信譽風險同級於編造數據。

## 3. Persona × 側重

**Persona(2026-07-18 起兩篇制,C 退役):**
- **A 有立場老手**:第一人稱擔責(「我看多,但有條件」)、劇本 + 認錯位、跨日伏筆/回扣
- **B 數據偵探**:懸念 hook、優先蹭熱題、跨資產差異化
- ~~**C 日更陪伴**~~:**已退役** — user 不喜「抄作業」措辭(該梗字面邀請照抄操作,
  與「劇本不是指令」立場矛盾);4 天選文 C 被選 0 次;陪伴/儀式感角色由 21:04
  生活短文承接(形式更合適)。**「抄作業/直接抄」類措辭全域禁用。**
- Fallback 預設:改為「發當日推薦篇」(Day 4 學習:user 選的是當天最有戲的內容,
  與推薦高度重合),不再固定 B

**側重(方向感,由當日 zone JSON 決定,不互相矛盾):**
- 主劇本(結構偏多/偏空的正面敘述)
- 風險面(同一數據,鏡頭對準流動性池/套牢區)
- 觀望(多空分界未決,等收盤表態)

每日產 3 篇 = 3 persona 各配一個「當日盤面最誠實的側重」。方向是數據的函數,
只有風格和鏡頭是選擇 — 禁止對同一數據產出互相矛盾的結論讓 user 挑。

## 3.5 美股題材 = QQQ 單一錨(2026-07-20 定案,user 選純 QQQ 簡單化)

B 版(數據偵探)的選題池 = **BTC/ETH ⊕ QQQ**。不做個股(user 明確要簡單化)。

**為何是 QQQ 而非個股:**
- **$QQQ 可交易**(幣安 futures QQQUSDT,已驗證)→ $標籤返佣吃得到,不需個股
- **一檔涵蓋整個科技盤** → 不用天天挑寫哪隻,零挑選成本
- **跟幣圈連動最強** → 「QQQ 在幹嘛 → 幣圈跟不跟」跨資產敘事天然成立,正是差異化車道
- **compute_zones 完美吃 QQQ**(ETF,251 bars,已驗證)

**節奏 = 內容驅動(非硬性一天幣一天股):** B 發當天最有戲的(加密 or QQQ)。
- 科技盤有戲(大漲/大跌/與幣圈背離)→ B 寫 QQQ × 幣圈連動,$標籤可掛 $QQQ + BTC/ETH
- 加密是主戲 → B 寫幣
- A 版維持 BTC/ETH(信譽鏈建於幣的關鍵位回扣)

**執行:** 每日 compute_zones 加跑 `QQQ`(yfinance ticker=QQQ);價位/結構一律來自
QQQ zone JSON,不猜。$QQQ 標籤已驗證可用,無需每次重驗(個股才需驗證,但我們不寫個股)。

## 4. 選題邏輯(跨資產差異化 — 實地研究核心發現)

優先序:
1. **當日熱門話題有我們覆蓋的資產** → 蹭話題(例:#美光股价跌14% ↔ MU zone JSON)。
   話題頁自帶瀏覽量,是冷啟動唯一分發外掛
2. **官方活動話題進行中** → 額外產 1 篇活動文(故事體,不佔 3 篇分析文名額)
3. **加密大事件日**(CPI、FOMC、爆倉潮)→ BTC/ETH 事件驅動
4. **平淡日** → C 版日更 BTC/ETH + 一篇美股跨資產(用當日 deep-stock zone 資料)

跨資產是差異化主軸:我們有 FRED + 美股 zone + 加密 zone 三線,純幣圈作者沒有。

### 4.1 待命素材(有由頭才發,不硬發)

有些題材本身很好,但**沒有當日由頭時發出來會是一篇沒人看的說明文**。這類
題材登記在這裡,等觸發條件成立那天才用,由自主選文流程優先採用。

**登記格式**:題材 / 觸發條件 / 可寫角度 / 禁區。

---

#### 📌 CLARITY Act(美國加密市場結構法案)— 登記於 2026-07-29

**觸發條件(任一)**:
- 參議院把法案排上議程、進行 cloture 或全院表決
- 8/10 表決窗口前後出現明確進展或明確破局
- 三大爭議之一(官員持倉揭露 / Section 604 / 穩定幣收益)有突破或新妥協
- 廣場出現該題的 >5k views 熱題(hashtag 字串當天重新驗證)

**已查證事實(2026-07-29)**:
- 2026-05-12 參院銀行委員會釋出 309 頁文本;05-14 以 **15:9 通過**送全院
- 白宮原訂 7/4 前完成 → 未達成;2026-07-23 多數黨領袖 Thune 稱暑休前難通過
- **8/10** 為參議員返州前最後表決窗口;9 月僅剩約三週會期;11 月期中選舉
- 尚未完成:全院 cloture(需 **60 票**)、與參院農業委員會姊妹法案整合、
  眾議院通過、總統簽署
- 票數現實:共和黨 53 席,Hawley、Rand Paul 預期反對;民主黨僅 Gallego、
  Alsobrooks 投過贊成且均附條件
- 三大爭議:①官員加密持倉道德揭露(Gillibrand 要求 vs 白宮反對,委員會
  修正案已否決)②Section 604 非託管開發者豁免(DeFi 視為最重要創新 vs
  全美地方檢察官協會稱妨礙刑事調查)③穩定幣收益(禁閒置餘額付息、允許
  活動獎勵;美國銀行家協會稱在 GENIUS Act 禁令上開漏洞,涉平台數十億營收)

**可寫角度(依吸引力排序)**:
1. **Section 604 的張力** —— 「保護開發者 vs 妨礙辦案」,零術語就能講清楚
2. **票數算術** —— 53 席但兩個自己人反對、民主黨只有兩張附條件票
3. **慢變數 vs 短線** —— 制度在前進、價格不同步(7/26 已用過此框架,再用需換切角)

**禁區(硬規則)**:
- ❌ 不得寫「通過就會漲」或任何價格預測
- ❌ **不得把「委員會通過」講成「法案通過」** —— 差好幾關,幣圈內容常見的
  誤導,我們不跟
- ❌ 8/10 不得寫成「大限 / 決戰日」;錯過是**機率下降**,不是法案死亡
- ⚠️ hashtag 當天重新驗證確切字串(歷史熱題為簡體
  `#CLARITY法案拟奖励白帽黑客`,是子題不是主題),驗不到降級中性標籤

## 5. Pipeline 架構

```
launchd 每日 18:30 TPE(com.financeworkflows.binance-square.plist)
  → scripts/compute_zones.py BTC-USD ETH-USD(+ 依當日熱題可加個股,重用當日 _zones/ 已有 JSON)
  → run-workflow.py binance-square(claude -p,吃 credit pool — user 已確認選項 A)
      prompt 讀:zone JSONs + 本 spec 的內容規則 + 熱門話題(fetch 廣場熱題,best-effort)
      產出:3 篇草稿(persona × 側重)寫入 reports/binance-square/{date}.md
  → notify:推 TELEGRAM_TOPIC_BINANCE_SQUARE(1715),每篇一則訊息(方便長按複製)
  → user 挑一篇貼廣場(附 K 線、選 chip、20:00–23:00 發或預約)
```

- 新 workflow json:`workflows/binance-square.json`(model 沿用 claude-sonnet 級,max_turns 小)
- 熱門話題抓取:v1 先用 web-fetch best-effort 抓廣場熱題頁;抓不到就跳過蹭話題步驟,
  不擋主流程(never-raise 慣例)
- 幣安九周年類活動偵測:v1 不自動,user 在 Telegram 看到活動自己說一聲即可

## 6. 檔案清單(實作時)

| 檔案 | 動作 |
|---|---|
| `workflows/binance-square.json` | 新增 |
| `prompts/binance-square/{framework,voice,main}.md` | 新增(內容規則 §2-§4 固化於此) |
| `launchd/com.financeworkflows.binance-square.plist` | 新增(18:30 TPE) |
| `.env` | `TELEGRAM_TOPIC_BINANCE_SQUARE=1715` ✅ 已填 |
| `reports/binance-square/` | 產出目錄(gitignored) |

Runner 不改(≤200 LoC 鐵律);新能力 = workflow json + prompts,符合 CLAUDE.md 慣例。

## 7. 驗收標準

- ☐ 手動跑一次 workflow,3 篇草稿字數全部落在 220–350(不含空白)
- ☐ 全部零 SMC 術語(grep 禁用詞清單 = 0 hit)
- ☐ 每篇有:hook、📌 條列、問句結尾、⚠️ footer、$×3、#×5、方向 chip 建議
- ☐ 3 篇方向側重不互相矛盾(同一 zone JSON 的不同鏡頭)
- ☐ Telegram 1715 收到 3+1 則(header + 3 篇),可長按複製
- ☐ zone JSON 價位 spot-check:草稿中每個價位都在 JSON 裡
- ☐ launchd 掛上後隔日 18:30 自動觸發成功

## 8. 實驗設計與停損

- **期間:6 週**(至 ~2026-08-26)
- **唯一 KPI:廣場追蹤數斜率**(週記一次即可);views 為輔助觀察
- **明確不看:** 返佣收益(冷啟動 ≈ $0,已實證:14K 粉大號單篇也只 600–4k views)
- **停損條件:** 6 週後追蹤數無明顯斜率(如 <50)→ 停 launchd,pipeline 留檔不刪
- **人工投入上限:** 每天 ≤5 分鐘(挑文 + 貼上);超過即檢討流程
