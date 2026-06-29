# Morning Briefing 編寫框架 — Bloomberg Five Things × Daily Shot

這是一份 **盤前** 簡報,目標讀者一個人(報告作者本人),時間 07:00 TPE,
讀完時間上限 5 分鐘,實體 PDF 設計成 A4 一頁印得完。

風格參考:
- **Bloomberg "Five Things You Need to Know"** — 5 個 numbered headline + why-it-matters,
  每條 2-3 句, 不多寫。
- **The Daily Shot** — 頂部一張 cross-asset tape snapshot 表,後面才是文字。
- **編輯口吻** — 直接,不囉嗦,只在最後一段下短評。

## 報告 7 個固定 sections(順序不可換)

1. **Mood line** — 一句話,描述今天整體氛圍(這是 mood 不是 prediction)。例:
   「美股期指走平等 CPI, BTC 創新高後拉回, TWD 偏弱, 注意今晚 10y 標售」

2. **Tape snapshot** — 一張表,當日 / 最近交易日的 cross-asset 快照。固定欄位:
   `Asset | Last | 1D Δ | 1W Δ | Note`。涵蓋:
   - **股指期貨夜盤**:ES (^ES=F)、NQ (^NQ=F)
   - **利率**:UST 2y (DGS2)、UST 10y (DGS10)、2s10s (T10Y2Y) 與前次比的 bp 變化
   - **匯率**:DXY (DX-Y.NYB)、USDTWD (TWD=X)
   - **商品**:WTI (CL=F)、Gold (GC=F)
   - **波動度**:VIX (^VIX)、VIX9D、VIX9D/VIX 比值
   - **加密**:BTC (BTC-USD)、ETH (ETH-USD)
   - **加密 derivs**:BTC perp funding (8h, 年化, z-score)、BTC OI
   - **台股關聯**:TSM ADR premium 與 2330.TW 換算對比
   `Note` 欄位 **僅** 寫觀察事實(例如 "1y 92nd pct"、"backwardation flag <1.00"),
   不寫推論。

3. **Five things (why it matters)** — numbered 1-5,每條:
   - 標題 1 行(粗體事件 + 時間 + consensus 或數字)
   - 內文 1-2 句 why it matters(不是 prediction,是 framing)
   - 選材原則:今晚到明早會發生的 5 件最該關注的事 — FOMC speakers、CPI/PPI、
     大額國債標售、財報、地緣事件、加密 ETF 大流向異動、台股盤前異常。

4. **Today's calendar (TPE)** — 一張小表,固定欄位 `Time | Event | Consensus | Prior`。
   來源:
   - 美國經濟數據(FRED schedule + web-fetch BLS/Census)
   - Fed events:FOMC、Powell 發言、Fed minutes (用 `web-fetch` 美聯儲新聞稿頁)
   - 美債標售(extras JSON 的 treasury_auctions 已過濾)
   - 台股法說(TWSE / 鉅亨網,best-effort web-fetch)
   - 主要美股財報(yahoo-finance get_stock_info 的 earningsDate)

5. **TW open hint** — 台股盤前一段。固定包含:
   - 三大法人昨日 net buy(TWSE BFI82U)
   - 融資餘額 DoD(TWSE MI_MARGN)
   - TSMC ADR premium → 2330 開盤理論價 = 昨收 × (1 + premium adjusted)
   - TWD 24h Δ 對台股的解讀(偏弱通常利空電子)

6. **Editor's take** — 一段 1-2 句編輯短評。指出今天 **最該關注的 1 件事**,
   而非把 5 things 重複一次。允許條件式語言(「若 X 跌破 Y 則 Z」)。

7. **附註** — 最後一行:資料源列表 + 編譯時間(TPE)。

## 三個明確的 emoji flag(其餘中性)

只在以下三種條件出現時加 emoji 標記,**不可亂用**:
- 🚨 **VIX9D/VIX < 1.00** — backwardation,事件不確定性高
- ⚡ **BTC perp funding z-score > +2.0 or < -2.0** — 槓桿極端
- 🎯 **TSM ADR premium 1y percentile > 95 or < 5** — 開盤異常張力

其餘所有 section 保持純資料 + 觀察事實,不要為了「好看」加 emoji。

## 跨層原則

- **觀察 → 框架 → 推論** 三層分明。表格只放觀察,Five things 是框架,
  Editor's take 才允許條件式推論。
- 五件事不可重複五次同一個觀點。要是 cross-asset 的、不同維度(rates / FX /
  commodities / vol / crypto / TW)。
- 任一資料源完全失敗時,在該 section 明確標 **「該源不可用」**,繼續產出。
