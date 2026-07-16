# finance-workflows

> English version: [README.en.md](README.en.md)

個人每日財經報告 + 監控 + 內容發布系統。核心是一個精簡的 Python workflow
runner(編排 `claude -p` + 本地 MCP servers),加上兩個 sibling 系統:
確定性套利監控(arb-sentinel)與幣安廣場日更 pipeline。報告以 HTML/PDF
落地本機,並推送到私人 Telegram supergroup(依 workflow 分 forum topic)。

> Repo 名稱 `agent-flow-studio` 是歷史遺留 — 現行主體是 `finance-workflows/`。
> 專案層規則見 `CLAUDE.md`,runner 層規則見 `finance-workflows/CLAUDE.md`。

## 目錄結構

| 路徑 | 用途 |
|---|---|
| `finance-workflows/` | workflow runner、MCP servers、workflows、prompts、tests |
| `arb-sentinel/` | 交易所套利/費率監控 — 純確定性 Python,不經 LLM,launchd 排程 |
| `mcp/knowledge-graph/` | 本地長期記憶(SQLite + sqlite-vec + FTS5),主 session 與 workflows 共用 |
| `docs/superpowers/{specs,plans}/` | 設計文件與實作計畫的完整歷史 |
| `.claude/skills/` | 互動式 skills(`/deep-research-stock`、`/finance-loop`) |

## 排程總覽(2026-07 現況)

### launchd 排程(headless,`claude -p` 走 credit pool)

| Workflow | 排程(TPE) | 內容 |
|---|---|---|
| `serenity-digest` | 每日 06:00 | KOL 日報蒸餾 + KG 記憶 |
| `morning-briefing` | 每日 07:00 | 跨資產盤前簡報(tape + Five things + TW open;含 Binance funding/CBOE VIX/國債標售/穩定幣/TWSE 三大法人 pre-fetch) |
| `crypto-daily` | 每日 07:30 | 加密新聞/社群 digest(6 YouTube + web) |
| `us-macro` | 週一–五 09:30 | Fed/成長/通膨簡報(FRED + Yahoo + Fed RSS) |
| `eason-tw-stock` | (暫停) | 台股分析師逐字稿 |

### arb-sentinel(launchd,零 LLM)

monitor / rates / digest / announcements 四個 job 常駐;carry-guardian
(Bitget 借貸倉位監控)已隨 USDGO 補貼結束停用(`.plist.disabled`)。
告警進 Telegram topic,每則標明交易所。

### 互動式(訂閱池,2026-06-15 計費樞紐後的路徑)

| 項目 | 觸發 | 內容 |
|---|---|---|
| `/deep-research-stock T1 T2 ...` | 手動 | 自訂 watchlist 深度研究:Tier A(7 層 + 10-K + SMC §8)/ Tier B(精簡);自動 PDF + Telegram |
| binance-square 日更 | in-session cron 每日 10:43 | 產 3 篇廣場貼文候選(A 老手/B 偵探/C 陪伴)→ 對話中選文 → 官方 API 自動發布 + 發文日誌 |

> **為什麼分兩池:** 2026-06-15 起 `claude -p` 改計 credit pool,互動 session
> 仍走訂閱。重型/需要人工判斷的流程(deep-stock、廣場日更)搬進互動式;
> 輕量日報留在 launchd + `claude -p`。

## 核心模組

- **SMC 價格區間引擎** `finance-workflows/scripts/compute_zones.py`:
  確定性計算日線 Smart Money Concepts 結構(BOS/CHoCH、FVG、流動性池、
  premium/discount、買賣參考區 + 失效位)。股票與加密通吃(yfinance)。
  LLM 只讀 JSON 做敘事,不做計算。規格:`docs/superpowers/specs/2026-07-08-price-zone-design.md`
- **廣場發布 API**:幣安創作者中心官方 API(`X-Square-OpenAPI-Key`),
  100 篇/日。發文日誌 `reports/binance-square/_published.jsonl` —
  所有「上次說過」型自我引用必須對日誌驗證。用字規範:內文繁體、
  蹭熱題 hashtag 照抄平台原字串(通常簡體)、自創 hashtag 繁體或中性
- **Telegram 通知**:共用 supergroup + 每 workflow 一個 forum topic,
  topic id 在 `finance-workflows/.env`(gitignored)

## 手動跑一個 workflow

```bash
cd finance-workflows
mcp/.venv/bin/python run-workflow.py <name>
```

報告落在 `finance-workflows/reports/<name>/<date>.html`(`post.pdf: true`
則多一份 PDF);log 在同目錄 `_logs/`。workflow 若自行寫出 `_brief.md`,
該檔內容會直接作為 Telegram 訊息主體。

## 新增 workflow

只動 config + prompts,不改 runner(≤200 LoC 鐵律)。
見 `finance-workflows/CLAUDE.md`「Add a new workflow」。

## 測試

```bash
cd finance-workflows && mcp/.venv/bin/pytest tests/ -v
cd arb-sentinel && .venv/bin/pytest tests/ -v
```

## License

私人使用。
