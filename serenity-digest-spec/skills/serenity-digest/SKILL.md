---
name: serenity-digest
description: 每日蒸餾 analysissite.vercel.app 並推送 Telegram brief。當 owner 觸發 "跑日報" / "produce serenity daily brief" 或排程觸發時使用。
---

# Serenity Daily Digest

## When to invoke

- 排程任務（每天 06:00 台灣時間）自動觸發
- Owner 手動下達「跑今天的 serenity 日報」「serenity daily」
- 系統異常恢復後手動補跑

## Prerequisites

- `~/.config/serenity-digest/config.json` 存在且含 telegram bot token + chat_id
- `~/Desktop/serenity-digest/data/` 資料夾存在
- 若進入 Phase 2+：`~/.config/serenity-digest/persona-cache/current.md` 為當前 SKILL.md 軟連結
- knowledge-graph MCP 可用（若不可用則 graceful degrade）

## Procedure

### Step 1：載入 Persona（若有）

```
if exists ~/.config/serenity-digest/persona-cache/current.md:
    read current.md
    把內容當 system context 的補充
else:
    使用「Phase 1 樸素模式」：不套蒸餾框架，直接基於 KOL 原文改寫
```

### Step 2：執行抓取

```
bash scripts/scrape-snapshot.mjs
  → 產出 ~/Desktop/serenity-digest/data/YYYY-MM-DD.json
  → 同步寫 raw/YYYY-MM-DD.html（原始 HTML，debug 用）
```

如果失敗：
- HTTP 4xx/5xx → retry 1 次（隔 60 秒）
- 仍失敗 → 沿用 `data/latest.json`，brief 加 `[STATUS] 抓取失敗`
- timeout > 30s → 同上

### Step 3：歷史 diff

```
read data/2026-05-28.json (yesterday)
compute:
  - newInTop10
  - droppedFromTop10
  - priorityMovers (top 3 by |delta|)
```

如果昨日不存在 → 設為空陣列，brief 標「首次運行」。

### Step 4：KG 注入（Phase 2+）

```
for each ticker in todayPriorityQueue[:3]:
    search_memory({
      query: f"{ticker} 觀點演化",
      filters: { "metadata.ticker": ticker },
      limit: 5
    })
    
for each mover in priorityMovers:
    search_memory({
      query: f"{mover.ticker} 變化原因",
      filters: { "metadata.ticker": mover.ticker },
      limit: 3
    })
```

10 秒內 KG 沒回 → 跳過此步，brief 不含「KOL 對照」段。

### Step 5：新聞評分

依 `docs/06-news-scoring.md` 公式：

```
score = 30 * tickerPriority
      + 25 * concreteness
      + 15 * sourceQuality
      + 15 * recency
      + 15 * kgRelation
```

取 top 3-5（按 depth_preference）。

`contradicts` 類加 ⚠️，**強制進** brief 即便其他維度不高。

### Step 6：組 brief

按 `docs/07-telegram-format.md` 範本：

```
📊 *YYYY-MM-DD Serenity 日報* (HH:MM 台北)

▎今日優先（Tier 1）
{tier1 條目}

▎掃描清單（Tier 2）
{tier2 條目}

▎昨日變化
{tier3 摘要}

▎KOL 對照 (若 Phase 2+ 且有 KG 內容)
{1-2 條對照}

▎相關訊號
{3-5 條新聞}

─────────
📍 分析框架蒸餾自 analysissite.vercel.app
🧠 Persona vN · KG X nodes · 第 Y 天
🔗 完整看板：analysissite.vercel.app
```

關鍵：**用 Persona DNA 的句型與詞彙寫**（如有 SKILL.md）。

寫完跑 anti-pattern 檢查：

```
BANNED = [強烈推薦, 目標價, 翻倍, 100%, 百分百, 必漲, 必跌]
if any banned word: 改寫該段
```

### Step 7：推送 Telegram

```
if len(brief) > 4000:
    split into 2 segments, mark (1/2) (2/2)

bash scripts/send-telegram.sh < brief.md
```

失敗 → retry 2 次（隔 30, 60 秒）→ 仍失敗存 `briefs/UNDELIVERED/`。

### Step 8：KG 寫入（Phase 2+）

對今日 priorityQueue top 5 的 KOL summary：

```
for each stock in top 5:
    if 該 ticker 今日有新句型 or 新 stance:
        store_knowledge({
          type: "insight",
          trust: "principle",
          content: "{KOL 的當日 reasoning 精煉}",
          quote: "{原文 20-50 字片段}",
          metadata: {
            ticker, sector, stance,
            category: "creative",
            first_seen: today,
            confidence: 估算 0.6-0.9
          },
          source: "serenity-site"
        })
    
    connect_knowledge(today_node, prev_node_for_same_ticker, "refines")
    
    if 該檔今日 stance ≠ 7 天前 stance:
        connect_knowledge(today, prev, "contradicts" if 立場翻轉 else "refines")
```

對今日 top 3 中 Claude 自己的延伸觀點：

```
store_knowledge({
  type: "insight",
  trust: "inference",       # 永遠是 inference
  content: "{Claude 推論}",
  metadata: { ticker, stance, category: "creative", confidence: 估算 },
  source: "claude-daily"
})
```

**Hard cap**：節點 ≤ 20，邊 ≤ 30 / 日。超過則按 priority 排序取前 N。

### Step 9：日誌與後置

```
寫 ~/Desktop/serenity-digest/logs/YYYY-MM-DD.log
追加一行進 ~/Desktop/serenity-digest/data/index.jsonl
```

## Output

- Telegram 推送（主要產出）
- `data/YYYY-MM-DD.json`（snapshot）
- `briefs/YYYY-MM-DD.md`（brief 存檔）
- `logs/YYYY-MM-DD.log`（執行日誌）
- KG 寫入（節點 + 邊）
- `index.jsonl` 追加一行

## Quality criteria

每次完成跑一次 `dailyAcceptance()`（見 `docs/10-acceptance.md`），不通過則寫進 log 但不阻止流程。

## Failure modes

- 爬蟲失敗 → 沿用昨日 + 標記
- KG 不可用 → 跳過 retrieval & 寫入（寫入暫存）
- Telegram 失敗 → retry + UNDELIVERED
- Persona 載入失敗 → fall back 樸素模式

## Related skills

- `serenity-distill`：當 Persona 需要重蒸餾時
- `serenity-reflect`：每週日跑反思
