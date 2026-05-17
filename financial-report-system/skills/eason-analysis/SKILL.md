---
name: eason-analysis
description: "Generate daily market reports using Eason (張貽程/@m168) analytical framework with real data + bias checking. Use when: user wants Eason-style analysis, '張貽程', 'Eason分析', '外資超錢線風格', daily AI sector report, or wants to retrain the framework. Two modes: default generates daily report, 'retrain' updates framework from accumulated data."
argument-hint: [retrain | no-video]
effort: high
user-invocable: true
---

# Eason 視角：台股 AI 戰情室

Generate daily market analysis using Eason (張貽程) analytical framework, verified against real-time data, with bias detection and multi-perspective cross-checking.

## Reference Files

**Read all reference files before starting.**

| File | Purpose |
|------|---------|
| [eason-framework.md](references/eason-framework.md) | 5-layer analysis logic, stance conditions, risk logic |
| [eason-indicators.md](references/eason-indicators.md) | Indicator list with MCP tool mapping |
| [eason-sectors.md](references/eason-sectors.md) | AI 6 sectors + avoid zones + stock rankings |
| [eason-vocabulary.md](references/eason-vocabulary.md) | Language style, catchphrases, tone guide |
| [report-template.md](references/report-template.md) | Output template + SQLite schema |

---

## Mode Selection

```
$ARGUMENTS check
├── "retrain" → Mode B: Framework Update
├── "no-video" → Mode A without video fetch
└── default (empty) → Mode A: Daily Report (with video)
```

---

## Mode A: Daily Report（每日報告）

### Phase 1: Eason 最新影片（預設執行）

1. Use **yt-dlp MCP** to search `@m168` for latest video:
   - `ytdlp_search_videos` query="張貽程 外資超錢線" maxResults=1 uploadDateFilter="today" (fallback to "week")
2. Download transcript: `ytdlp_download_transcript` language="zh-Hant"
   - If zh-Hant fails, try: zh → en (in that order)
   - If all fail, note "逐字稿不可用" and proceed with data-only mode
3. **Structure extraction** (same schema as training):
   - stance, stance_score, indicators_mentioned, sectors_mentioned, stocks_mentioned
   - logic_chain, predictions, action_advice, risk_warnings, tone_intensity
   - transcript_summary
4. **Store in SQLite** `eason_training` table (cumulative training data):
   ```sql
   INSERT INTO eason_training (video_id, video_date, video_title, month_batch,
     stance, stance_score, indicators_mentioned, sectors_mentioned, stocks_mentioned,
     logic_chain, predictions, action_advice, risk_warnings, tone_intensity, transcript_summary)
   VALUES (...);
   ```
   - Skip if video_id already exists (avoid duplicates)

### Phase 2: 即時數據收集

**平行執行 4 路數據**（use Agent tool for parallelism）：

#### 2A. TWSE 台股數據
- `get_daily_market_trading_info`: 加權指數、成交量
- `get_market_index_info`: 櫃買指數
- `get_margin_trading_info`: 外資買賣超、融資餘額
- `get_stock_daily_trading` for key stocks: 2408, 6187, 3006, 3324, 2317

#### 2B. Yahoo Finance 國際數據
- `get_stock_info` for: MU (美光), 2330.TW (台積電), TSM (台積電ADR)
- `get_stock_info` for: BZ=F (布蘭特原油), GC=F (黃金), DX-Y.NYB (美元指數)
- `get_stock_info` for: ^SOX (費半), ^IXIC (那斯達克)
- `get_historical_stock_prices` for TAIEX/MU to calculate 20MA and 60MA

#### 2C. FRED 總經數據
- `fred_get_series` for: FEDFUNDS, CPIAUCSL, T10Y2Y (10Y-2Y spread)

#### 2D. SQLite 歷史比對
- Query `eason_training` for last 5 entries → stance trend
- Query `eason_daily` for last report → compare signals

### Phase 3: Eason 框架評估

Apply the 5-layer logic chain from [eason-framework.md](references/eason-framework.md):

1. **利空本質判斷**：當前利空是人造還是結構性？
2. **台股優勢論**：台股 vs 美股相對強弱？AI供應鏈受損了嗎？
3. **籌碼信號**：外資淨空單趨勢？融資狀態？
4. **技術面定位**：季線/月線位置？歸離率？N字型態？
5. **選股方向**：哪些族群符合 Eason 的選股邏輯？

**對每個指標**，用 [eason-indicators.md](references/eason-indicators.md) 的判讀規則產出 🟢/🟡/🔴 信號。

### Phase 4: Eason 風格觀點生成

用 [eason-vocabulary.md](references/eason-vocabulary.md) 的語氣指南，生成「如果 Eason 看到今天的數據，他會怎麼說」的 3-5 段分析。

**規則**：
- 如果 Phase 1 有影片，以影片觀點為主，數據為輔
- 如果無影片（no-video 模式），純用框架 + 數據生成
- 語氣要像 Eason（直球、自信、用金句），但不能編造不存在的「命中」記錄

### Phase 5: 偏誤檢查 + 多視角驗證

**必做**。這是區別於純模擬的關鍵。

1. **Home bias 檢查**：台股真的比其他市場強嗎？（比較 S&P 500, KOSPI, 日經）
2. **Confirmation bias 檢查**：Eason 觀點忽略了哪些利空數據？
3. **Druckenmiller 視角**：宏觀趨勢、流動性、貨幣條件是否支持？
4. **Damodaran 視角**：估值是否合理？台股 PE 位置？ERP 狀態？
5. **Eason 忽略的風險**：明確列出

**信心評分**：Eason 觀點的數據支撐度 (1-10)

### Phase 6: 輸出報告

Follow [report-template.md](references/report-template.md) format. Store in SQLite `eason_daily` table.

---

## Mode B: Framework Retrain（框架更新）

When `$ARGUMENTS` = "retrain":

1. Read ALL data from `eason_training` table
2. Re-analyze:
   - stance_score distribution and trends
   - Top indicators by frequency
   - Top sectors/stocks by frequency
   - Logic patterns (recurring reasoning chains)
   - Stance transition conditions (when did he shift?)
   - Risk/conservative moments (when did he say 減碼?)
3. Compare with current framework files
4. **Update reference files** with new findings:
   - `eason-framework.md`: New logic patterns, updated stance conditions
   - `eason-indicators.md`: New indicators discovered
   - `eason-sectors.md`: New stocks/sectors, changed views
   - `eason-vocabulary.md`: New catchphrases
5. Report what changed:
   ```
   ## Framework Update Report
   - Training data: {N} videos ({date range})
   - New indicators discovered: {list}
   - Stance conditions updated: {changes}
   - New stocks added: {list}
   - Framework confidence: {low/medium/high} (based on sample size)
   ```

**建議頻率**：累積 10+ 新影片後跑一次 retrain。

---

## Integration with Other Skills

| Skill | How |
|-------|-----|
| `/yt-briefing m168` | Can be run first for deeper transcript analysis |
| `/data-snapshot TW` | Provides quick data for Phase 2 |
| `/cross-check` | Verify specific Eason claims |
| `/market-scan` | Full sector scan for Phase 3 |
| `/macro-analysis` | Druckenmiller/Damodaran lenses for Phase 5 |
| `/generate-report` | Export as HTML/PDF |

---

## Quality Checklist
- [ ] Eason latest video fetched and analyzed (or noted as unavailable)
- [ ] All Tier 1 indicators collected (季線、月線、外資淨空單)
- [ ] 6 AI sectors scanned
- [ ] Avoid zone checked (鴻海、航運、美債)
- [ ] Bias check performed (Home, Confirmation, Survivorship)
- [ ] Multi-perspective validation done (Druckenmiller + Damodaran)
- [ ] Report follows template
- [ ] Data stored in SQLite (eason_training + eason_daily)
