# Serenity Digest — 規格書與基礎骨架

> 給接手的 Claude (Opus) — 這份規格書描述一個每日蒸餾 [analysissite.vercel.app](https://analysissite.vercel.app/) 的代理系統，
> 透過 Telegram 推播個人化日報，並用 Knowledge Graph 累積對該 KOL 的長期記憶。

## 60 秒理解

```
[06:00 台灣時間 cron]
       ↓
[Persona Layer]  載入 skills/serenity-distill/output/serenity-perspective.md
[Memory Layer]   knowledgeGraph MCP retrieval（auto-recall hook）
       ↓
[Scraper]        fetch analysissite.vercel.app → 解析為今日 snapshot.json
       ↓
[Composer]       根據 SKILL.md + KG 記憶 + 今日 snapshot 組 Telegram 訊息
       ↓
[Push]           POST Telegram sendMessage
       ↓
[Memory Capture] auto-capture hook → 寫今日新觀點進 KG，連結到既有節點
       ↓
[Snapshot Persist] 寫 ~/Desktop/serenity-digest/data/YYYY-MM-DD.json（被動證據池）
```

## 三層架構

| Layer | 工具 | 在哪 |
| --- | --- | --- |
| **Persona** | nuwa-skill 蒸餾的 `serenity-perspective.md` | `skills/serenity-distill/output/` |
| **Memory** | `knowledgeGraph` MCP（SQLite + sqlite-vec + FTS5）| 跟主 agent 同 host |
| **Automation** | Cowork 排程任務 + 6 個 KG hooks | `~/.claude/settings.json` + 排程 |
| **Evidence Pool**（被動）| JSON-per-day | `~/Desktop/serenity-digest/data/` |

## 資料夾地圖

```
serenity-digest-spec/
├── README.md                 ← 你在這裡
│
├── docs/                     ← 規格細節，按順序讀
│   ├── 00-system-overview.md     架構哲學與層級職責
│   ├── 01-scraping.md            爬蟲與解析
│   ├── 02-knowledge-graph.md     KG 節點/邊在金融語境的約定
│   ├── 03-persona-distillation.md nuwa-skill 對 Serenity 的改造
│   ├── 04-daily-workflow.md      端到端流程與時序
│   ├── 05-stock-strategy.md      列幾檔、tier 化策略（Q1）
│   ├── 06-news-scoring.md        新聞重要性 0-100 評分（Q2）
│   ├── 07-telegram-format.md     訊息格式、長度、範例
│   ├── 08-storage.md             資料儲存版面
│   ├── 09-evolution.md           90 天演化路徑與決策樹（Q3）
│   └── 10-acceptance.md          驗收標準
│
├── skills/                   ← 可掛到 Claude Code skills/ 下的 SKILL.md
│   ├── serenity-digest/SKILL.md     每日 brief 主流程
│   ├── serenity-distill/SKILL.md    nuwa 改造後的蒸餾流程
│   └── serenity-reflect/SKILL.md    每週反思 + maintain_graph
│
├── scripts/                  ← 可直接執行的骨架腳本
│   ├── scrape-snapshot.mjs       爬今日 snapshot 並輸出 JSON
│   ├── compose-brief.mjs         組 Telegram Markdown 訊息
│   ├── send-telegram.sh          curl Telegram API
│   ├── kg-conventions.json       KG 節點/邊型別常數
│   └── nightly.sh                主排程 orchestrator
│
├── prompts/                  ← 排程任務的提示詞範本
│   ├── daily-brief.md
│   ├── weekly-reflection.md
│   └── distillation-bootstrap.md
│
└── examples/                 ← 參考輸出
    ├── sample-snapshot.json
    ├── sample-brief.md
    └── sample-kg-nodes.json
```

## 先決條件

接手前要確認：

- [ ] Cowork 排程任務功能可用（`mcp__scheduled-tasks__*`）
- [ ] `knowledgeGraph` MCP 已安裝且 `knowledge.db` 寫入路徑可寫
- [ ] Node.js 18+（執行 `.mcp` script）
- [ ] Telegram bot token + chat_id 已準備好放進 `~/.config/serenity-digest/config.json`
- [ ] 對 `analysissite.vercel.app` 的網路存取允許（web_fetch）

## 啟動順序

```
1. 讀 docs/00 → docs/04，理解架構與流程
2. 依 docs/03，跑 distillation-bootstrap（產出 v1 SKILL.md）
3. 依 docs/02，初始化 KG 並建立常數節點（行業、stance、source）
4. 依 docs/08，建立 ~/Desktop/serenity-digest/ 資料夾結構與 config
5. 依 docs/04 + scripts/nightly.sh，先手動跑一次完整流程驗證
6. 把 prompts/daily-brief.md 設成 Cowork 排程（每天 06:00 台灣時間）
7. 觀察一週，依 docs/10 的驗收清單檢查
```

## 設計原則（不要違反）

1. **歸因清楚**：所有 brief 必須有「📍 分析框架蒸餾自 analysissite.vercel.app」的歸因。原始觀點來自 KOL，Claude 的延伸要標 `[AI 推論]`。
2. **私人使用**：產出的 brief 只發給設定的 chat_id，不公開發佈、不分享至公開頻道、不轉存可被搜尋的位置。
3. **Anti-fabrication**：principle 節點必須有 quote（KOL 原文片段）。inference 節點不能建立 `must_precede` 或 `reason_for` 因果邊。
4. **可逆性**：每天的 snapshot.json 永久保留，KG 可從零重建（用 snapshot 重播）。任何破壞性操作（delete/forget）必須在 log 留軌跡。
5. **失敗不靜默**：爬蟲失敗、Telegram 推送失敗、KG 寫入失敗都要寫 `logs/YYYY-MM-DD.log`，並在當天 brief 內以 `[STATUS]` 段標示。

## 90 天決策點（見 docs/09 完整版）

| 觀察指標 | 命中率 | 動作 |
| --- | --- | --- |
| KOL 預測準確率（Claude 評估）| > 60% | 升 E（接 evidence pool 引用）|
| | 30-60% | 維持 D，調整 trust level 與 consolidation 參數 |
| | < 30% | 重新評估 nuwa 蒸餾品質與 KG 範圍 |

## 開放問題

接手後若遇到下列情形請回報，由 owner 決策：

1. KOL 改版網站 schema，爬蟲解析失敗 > 3 天
2. KG 節點數超過 10,000 且 consolidation 效能下降
3. Telegram 推送連續失敗 > 2 天
4. SKILL.md v2 蒸餾後與 v1 偏離超過 30%（按關鍵句子 cosine 比對）

---

**版本**：spec v1.0 · 2026-05-29
**Owner**：Po Chen <910063@gmail.com>
**Handoff target**：Claude (Opus)，跑在另一套已內建 Telegram 推播的 agent 系統內
