# System Architecture — 11 Skills 整體數據流

## Skill 互動關係

```
                    ┌─────────────────────────────────────┐
                    │         數據取得層 (Input)            │
                    │                                     │
                    │  /data-snapshot ─┐                   │
                    │  /market-scan ───┤── 寫入 SQLite ──┐ │
                    │  /yt-briefing ───┤                 │ │
                    │  /web-research ──┘                 │ │
                    └──────────────────────────────────│──┘
                                                      │
                                                      ▼
                    ┌─────────────────────────────────────┐
                    │            SQLite DB                  │
                    │  /mnt/c/FINANCIAL/data/financial.db  │
                    │                                     │
                    │  macro_snapshots  ← /data-snapshot   │
                    │  market_scans     ← /market-scan     │
                    │  yt_summaries     ← /yt-briefing     │
                    │  web_research     ← /web-research    │
                    │  macro_analyses   ← /macro-analysis  │
                    │  deep_research    ← /deep-research   │
                    │  cross_checks     ← /cross-check     │
                    └──────────────────────────────────│──┘
                                                      │
                         ┌────────────────────────────┤
                         │                            │
                         ▼                            ▼
                    ┌──────────────┐          ┌──────────────┐
                    │  分析層       │          │ /data-query  │
                    │              │          │ (歷史查詢)    │
                    │ /macro-      │◄─────────│              │
                    │  analysis    │          └──────────────┘
                    │              │
                    │ /deep-       │
                    │  research    │
                    │              │
                    │ /cross-check │
                    └──────┬───────┘
                           │
                           │ 分析結果
                           ▼
                    ┌─────────────────────────────────────┐
                    │         輸出層 (Output)               │
                    │                                     │
                    │  /generate-pptx  → .pptx            │
                    │  /generate-docx  → .docx            │
                    │  /generate-report → .html / .pdf    │
                    │                                     │
                    │  輸出至: /mnt/c/FINANCIAL/reports/   │
                    └─────────────────────────────────────┘
```

## 數據流詳細說明

### 1. 數據取得層 → SQLite
每個取得層 skill 都必須：
- 取得數據後**立即寫入 SQLite**
- 使用統一的 timestamp 格式: ISO 8601 UTC `datetime('now')`
- JSON 欄位用 TEXT 存，查詢時用 `json_extract()`

### 2. SQLite → 分析層
分析層 skill 啟動時**先查 SQLite**：
- `/macro-analysis` 查 macro_snapshots (最新數據) + yt_summaries (分析師觀點) + 之前的 macro_analyses (避免重複分析)
- `/deep-research` 查所有表（全面整合已有資訊）
- `/cross-check` 查 yt_summaries (取得待驗證觀點) + macro_snapshots (取得驗證數據)

### 3. 分析層 → SQLite
分析結果也寫回 SQLite，形成累積知識庫：
- `/macro-analysis` → macro_analyses 表
- `/deep-research` → deep_research 表
- `/cross-check` → cross_checks 表

### 4. 分析層 → 輸出層
輸出層從**對話上下文**或**SQLite**取得分析結果：
- 如果剛做完分析 → 從對話上下文直接取
- 如果要產生過去的分析報告 → 從 SQLite 查詢

### 5. /data-query 是橋梁
`/data-query` 是唯一專門用來**讀取** SQLite 歷史數據的 skill，其他 skill 寫入為主。

---

## 共用標準

### SQLite Schema 一致性
所有 skill 使用相同的 schema（定義在 data-snapshot/references/sqlite-schema.md）。
任何 skill 修改 schema 都必須同步更新該檔案。

### 中英混合格式
所有 skill 統一：
- 分析文字用繁體中文
- 指標名稱用英文（GDP, CPI, Core PCE, VIX）
- 表格欄位名可中可英，但同一張表內要一致

### Signal Output Format
需要產生投資信號的 skill 統一使用：
```
╔══════════════════════════════════════════════╗
║              INVESTMENT SIGNAL               ║
╠══════════════════════════════════════════════╣
║ Signal:      BULLISH / NEUTRAL / BEARISH     ║
║ Confidence:  HIGH / MEDIUM / LOW             ║
║ Horizon:     SHORT / MEDIUM / LONG-TERM      ║
║ Score:       X.X / 10                        ║
╠══════════════════════════════════════════════╣
║ Conviction:  STRONG / MODERATE / WEAK        ║
╚══════════════════════════════════════════════╝
```
適用 skill: /macro-analysis, /market-scan, /cross-check

### 報告輸出路徑
所有輸出檔案統一放在：
```
/mnt/c/FINANCIAL/reports/{YYYY-MM-DD}_{topic_slug}.{ext}
/mnt/c/FINANCIAL/reports/assets/  ← 圖表等資產
```

### Chart 生成統一標準
所有需要圖表的 skill 使用 Chart MCP (AntV)：
- 配色：專業藍灰色系為預設，可根據主題調整
- 中文標題，英文 axis labels
- 圖表儲存為 SVG/PNG 到 reports/assets/

---

## 典型使用流程

### 流程 A：每日追蹤
```
/data-snapshot → /yt-briefing → /cross-check (驗證 YT 觀點)
```

### 流程 B：議題分析
```
/data-snapshot → /macro-analysis "議題" → /generate-report html
```

### 流程 C：完整週報
```
/data-snapshot all
/market-scan all
/yt-briefing all
/macro-analysis "本週重點"
/generate-pptx "週報"
/generate-docx "週報"
```

### 流程 D：深度研究
```
/web-research cbc "最新利率決議"
/data-snapshot US TW
/deep-research "台灣央行升息對房市影響"
/generate-report pdf
```

### 流程 E：歷史回顧
```
/data-query "CPI" 1y
/data-query "yt_summaries" 3m
/macro-analysis "回顧上季預測準確度"
```
