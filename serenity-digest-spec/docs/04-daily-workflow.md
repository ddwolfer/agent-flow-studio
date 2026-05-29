# 04 · 每日工作流（端到端）

## 觸發

Cowork 排程任務，每天台灣時間 06:00 觸發。

```
Cron 表達式 (UTC):  50 21 * * *
            (台灣):  06:00 每天
```

留 10 分鐘等原站快照（原站通常 05:50 左右更新），確保抓到當天版本。

## 完整時序

```
06:00:00  ┃ 排程觸發 → Claude 開啟新 conversation
          ┃
06:00:01  ┃ Persona Layer 注入
          ┃   讀 skills/serenity-distill/output/serenity-perspective-v{N}.md
          ┃   進 system prompt
          ┃
06:00:02  ┃ 讀今日 config
          ┃   ~/.config/serenity-digest/config.json
          ┃   含 Telegram bot token、chat_id、depth_preference
          ┃
06:00:03  ┃ ===== 階段 A：抓取 =====
          ┃   執行 scripts/scrape-snapshot.mjs
          ┃   ↓
          ┃   產出 ~/Desktop/serenity-digest/data/2026-05-29.json
          ┃   並更新 data/latest.json 指向今日
          ┃
06:00:08  ┃ ===== 階段 B：歷史 diff =====
          ┃   讀 data/2026-05-28.json
          ┃   計算：
          ┃     - newInTop10：今日進前 10
          ┃     - droppedFromTop10：昨日跌出前 10
          ┃     - priorityMovers：共同 ticker 的 priority delta top 3
          ┃
06:00:10  ┃ ===== 階段 C：KG 注入 =====
          ┃   auto-recall hook 觸發
          ┃   針對今日 priorityQueue 的每檔，search_memory：
          ┃     query: "{ticker} 過去 30 天觀點"
          ┃     filters: { metadata.ticker: ticker }
          ┃   回傳的記憶進 prompt
          ┃
06:00:13  ┃ ===== 階段 D：新聞重要性評分 =====
          ┃   對 snapshot.feedItems 跑 docs/06 的評分演算法
          ┃   挑 top 3-5 進 brief
          ┃
06:00:15  ┃ ===== 階段 E：組 brief =====
          ┃   執行 scripts/compose-brief.mjs
          ┃   輸入：snapshot + diff + KG retrieval + 評分後新聞
          ┃   套用 Persona 表達 DNA
          ┃   按 docs/05 的 tier 化策略決定列幾檔
          ┃   按 docs/07 的格式組成 Markdown 文字
          ┃   ↓
          ┃   產出 ~/Desktop/serenity-digest/briefs/2026-05-29.md
          ┃
06:00:22  ┃ ===== 階段 F：Telegram 推送 =====
          ┃   執行 scripts/send-telegram.sh
          ┃   POST https://api.telegram.org/bot$TOKEN/sendMessage
          ┃   parse_mode=Markdown
          ┃   如果 brief > 4000 字 → 自動分段
          ┃
06:00:25  ┃ ===== 階段 G：KG 寫入 =====
          ┃   auto-capture hook 觸發
          ┃   把今日新出現的 KOL 觀點存進 KG：
          ┃     - principle 節點（含 quote）
          ┃     - 連結到既有相關節點（refines / contradicts / aligns_to）
          ┃   Claude 對某些標的的延伸觀點：
          ┃     - inference 節點（標明 source: claude-daily）
          ┃
06:00:35  ┃ ===== 階段 H：日誌與後置 =====
          ┃   寫 ~/Desktop/serenity-digest/logs/2026-05-29.log
          ┃   含：抓取耗時、解析狀態、評分結果、KG 寫入清單
          ┃   寫 ~/Desktop/serenity-digest/data/index.jsonl 追加一行
          ┃
06:00:40  ┃ 完成
```

預期總耗時：**30-60 秒**。

## 階段細節

### A: 抓取

腳本路徑：`scripts/scrape-snapshot.mjs`
輸入：無
輸出：`~/Desktop/serenity-digest/data/YYYY-MM-DD.json`

詳細解析規則見 `docs/01-scraping.md`。

### B: 歷史 diff

```javascript
// pseudo-code
const today    = readJSON("data/2026-05-29.json");
const yesterday = readJSON("data/2026-05-28.json");

const todayTickers    = new Set(today.hotStocks.map(s => s.ticker));
const yesterdayTickers = new Set(yesterday.hotStocks.map(s => s.ticker));

const newInTop10      = [...todayTickers].filter(t => !yesterdayTickers.has(t));
const droppedFromTop10 = [...yesterdayTickers].filter(t => !todayTickers.has(t));

const priorityMovers = [...todayTickers]
  .filter(t => yesterdayTickers.has(t))
  .map(t => {
    const today_p     = today.hotStocks.find(s => s.ticker === t).priority;
    const yesterday_p = yesterday.hotStocks.find(s => s.ticker === t).priority;
    return { ticker: t, delta: today_p - yesterday_p };
  })
  .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
  .slice(0, 3);
```

如果昨日 snapshot 不存在（第一次跑 / 中斷過）：
- `newInTop10 = []`
- `droppedFromTop10 = []`
- `priorityMovers = []`
- brief 標記「（首次運行，無昨日對照）」

### C: KG 注入

```javascript
// pseudo-code: 對 priorityQueue 前 3 名做精細 retrieval
for (const stock of today.priorityQueue.slice(0, 3)) {
  const memory = await searchMemory({
    query: `${stock.ticker} ${stock.stance} 觀點演化`,
    filters: { "metadata.ticker": stock.ticker },
    limit: 5,
    sortBy: "memoryScore"
  });
  retrievals[stock.ticker] = memory;
}

// 對 priorityMovers 各做一次 retrieval
for (const mover of priorityMovers) {
  const memory = await searchMemory({
    query: `${mover.ticker} 變化原因`,
    filters: { "metadata.ticker": mover.ticker },
    limit: 3
  });
  retrievals[mover.ticker] = memory;
}
```

回傳的記憶包含「KOL 之前對這檔說過什麼」「Claude 之前的 inference 是否兌現」。

### D: 新聞重要性評分

詳見 `docs/06-news-scoring.md`。把 `feedItems` 過評分函式，挑前 3-5。

### E: 組 brief

詳見 `docs/05-stock-strategy.md` 與 `docs/07-telegram-format.md`。

關鍵：**用 Persona 蒸餾出的 DNA 寫**，不是用 Claude 預設口吻。
- 句型：「需要核驗 X、Y、Z」
- 詞彙：「邊際變化」「叙事 vs 證據」
- 不用：「強烈推薦」「目標價」「翻倍」

### F: Telegram 推送

```bash
curl -s "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -d chat_id=${CHAT_ID} \
  -d parse_mode=Markdown \
  -d disable_web_page_preview=true \
  --data-urlencode "text=${BRIEF}"
```

訊息超過 4096 chars → 分段發送，每段標 `(1/2)` `(2/2)`。

### G: KG 寫入

每天**最多寫入 20 個節點 + 30 個邊**，避免一次塞太多。

優先順序：
1. KOL 新出現的觀點（priorityQueue top 5 → principle 節點）
2. 重要的對照（contradicts、refines 邊）
3. Claude 對 top 3 的延伸 inference

低優先：
- feedItems 裡每條都建節點 → **不要**，會把 KG 淹了
- 大部分 feedItem 已是 priorityQueue 對應股票的延伸，合併進主節點 metadata 即可

### H: 日誌

`logs/2026-05-29.log` 結構：

```
2026-05-29T06:00:03+08:00 [INFO] scrape start
2026-05-29T06:00:08+08:00 [INFO] scrape success, 13 feedItems, 10 hotStocks
2026-05-29T06:00:10+08:00 [INFO] kg retrieval: NVDA(5), SIVE(3), LITE(4)
2026-05-29T06:00:13+08:00 [INFO] news scoring: top 4 selected
2026-05-29T06:00:15+08:00 [INFO] brief composed, 387 chars
2026-05-29T06:00:22+08:00 [INFO] telegram send success
2026-05-29T06:00:25+08:00 [INFO] kg writes: 8 nodes, 12 edges
2026-05-29T06:00:35+08:00 [INFO] complete, total 32s
```

`data/index.jsonl` 追加：

```json
{"date":"2026-05-29","topTickers":["NVDA","SIVE","LITE"],"activeSignals":445,"writes":{"nodes":8,"edges":12},"briefLength":387}
```

讓你 30 秒內可以掃過去 30 天的概況。

## 失敗處理

| 階段 | 失敗 | 處置 |
| --- | --- | --- |
| A 抓取 | HTTP 非 200 或 timeout | retry 1 次（隔 60 秒），仍失敗 → 用 `data/latest.json` + `[STATUS] 抓取失敗，沿用昨日` |
| B diff | 昨日 snapshot 不存在 | diff 區段省略，brief 標「首次運行」 |
| C 注入 | KG 無回應或 timeout (>10 秒) | 跳過 retrieval，brief 不含「歷史觀點」段 |
| D 評分 | feedItems 為空 | 跳過新聞段 |
| E 組 brief | 模板填入失敗 | 改寫一段 fallback「今日抓取異常，請查 logs」並推送 |
| F 推送 | Telegram 4xx/5xx | retry 2 次（隔 30、60 秒），仍失敗 → 寫 `briefs/UNDELIVERED/` 等明天合併推 |
| G 寫入 | KG MCP 不可用 | 寫入跳過，把今日節點寫進 `pending-writes/2026-05-29.json`，明天先消化 |

**所有失敗都不中斷 cron**。下一個階段該跑的還是跑。

## 每週反思（額外排程）

詳見 `skills/serenity-reflect/SKILL.md`。

每週日台灣時間 21:00：

1. `maintain_graph()` 自動跑：合併重複、處理 contradicts、prune
2. 過去 7 天的 priorityQueue top 3 取出，對照當前價量看哪些預測兌現
3. Claude 寫一則 `insight` 節點：「本週發現的 KOL 命中率與失準 pattern」
4. 推送一份週報到 Telegram（比日報長，~800 字）

## 每月校準（額外排程）

每月第一天台灣時間 12:00：

1. `memory_stats()` 報出 KG 統計
2. 推送月報：節點數、access 熱榜、近期 contradicts、待升級的 inference

## 季度重蒸餾（額外排程）

每季首日 14:00：

1. 從 KG 匯出近 90 天 corpus
2. 跑 `skills/serenity-distill/` 流程
3. 產出 `serenity-perspective-v{N+1}.md`
4. 與 v{N} diff → 推送 diff 概覽
5. 等 owner 24 小時內確認；確認後啟用 v{N+1}
