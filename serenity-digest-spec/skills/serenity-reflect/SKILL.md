---
name: serenity-reflect
description: 每週反思 + KG 維護。當排程觸發（每週日 21:00 台灣）或 owner 手動下達「跑 serenity 週反思」時使用。產出週報 Telegram 訊息與 KG 中的 insight 節點。
---

# Serenity Weekly Reflection

## When to invoke

- 排程觸發：每週日 21:00 台灣時間
- Owner 手動：「跑 serenity 週反思」
- KG 維護需求：節點數突增、contradicts 累積 ≥ 5 時手動觸發

## Prerequisites

- 過去 7 天每天的 daily-brief 都跑過（至少 5/7）
- knowledge-graph MCP 可用
- 過去 7 天 KG 節點數變化 > 0

## Procedure

### Step 1：KG 維護

跑內建 `maintain_graph` 工具：

```
maintain_graph({
  operations: ["merge", "validate", "orphan", "prune"]
})

回傳：
  - merged: 合併的節點數
  - validated: 驗證的邊數
  - orphans: 孤立節點數
  - pruned: 移除的弱邊數
```

過程中：

- vector similarity > 0.85 的節點 → 合併
- weight < 0.3 的邊 → 移除（pruned）
- 沒有任何邊的節點 + access < 2 → 標記 orphan，待處理
- 跑跨 session 計數，符合晉升條件的 → 升 memory_level

### Step 2：偵測 contradictions

過去 7 天 KOL 預測 vs 實際價量：

```
for ticker in last_7_days_tickers (Tier 1 出現過的):
    kol_stance = average stance over 7 days
    actual_change = fetchPrice(ticker, +7 days from each mention)
    
    if kol_stance == "bull" but actual < -5%:
        contradicts.append({ticker, kol_stance, actual})
    if kol_stance == "bear" but actual > +5%:
        contradicts.append(...)
```

對每個 contradicts 建邊：

```
connect_knowledge(
  from: actual_price_event_node,
  to:   kol_prediction_node,
  edge: "contradicts",
  metadata: { observed_at: today, magnitude: abs(actual - expected) }
)
```

### Step 3：尋找 emerging patterns

```
last_30_days_principles = list_knowledge({
  filters: { source: "serenity-site", trust: "principle",
             created_after: today - 30days }
})

# 用 vector similarity 找出可能 emerge 的 pattern
clusters = cluster_by_vector(last_30_days_principles, threshold: 0.75)

for cluster in clusters where cluster.size >= 5:
    # 這是個重複出現的句型/框架
    # 召集 owner review 後升為 pattern
    candidate = synthesize_cluster(cluster)
    store_knowledge({
      type: "insight",
      trust: "pattern",  # 注意：從 principle 集合升上來
      content: candidate.synthesis,
      quote: cluster[0].quote,  # 取第一個 instance 的 quote
      metadata: {
        ...,
        category: "creative",
        confidence: 0.8,
        promoted_from: cluster.ids
      },
      source: "claude-reflect"
    })
```

### Step 4：track record 評估

```
weekly_predictions = last_7_days.flatMap(d => d.priorityQueue.slice(0, 3))

results = await Promise.all(
  weekly_predictions.map(async p => ({
    ...p,
    actual: await fetchPrice(p.ticker, p.date, +7),
    correct: ...
  }))
)

accuracy = results.filter(r => r.correct).length / results.length
```

寫一則 insight 節點：

```
store_knowledge({
  type: "insight",
  trust: "inference",
  content: f"本週 KOL 預測準確率 {accuracy:.0%}（n={results.length}）。命中案例：[X, Y]。失準案例：[A, B]。",
  metadata: {
    period: "weekly",
    week_of: this_week,
    confidence: 0.7,
    category: "creative"
  },
  source: "claude-reflect"
})
```

### Step 5：產出週報 Telegram 訊息

格式範本：

```
📊 *2026-W22 Serenity 週反思* (週日 21:00)

▎*本週命中率*
{X}/{Y} = {accuracy:.0%}
- ✅ 命中：NVDA (+8% vs bull), SIVE (+12% vs bull)
- ❌ 失準：TSLA (-15% vs bull_high_risk), IREN (+25% vs bear)

▎*新發現的 pattern*
{若 Step 3 有產出 pattern → 列 1-2 條，否則「本週無新 pattern」}

▎*KG 維護*
- 合併重複節點：5
- 移除弱邊：12
- 新晉升 Level 2 節點：3
- 待處理孤立節點：1

▎*趨勢觀察*
{Claude 對本週的整體觀察，~80 字}
{例如：「本週半導體集中度增加，KOL 多次用『需要核驗訂單轉換』，
       與上週『純政策叙事』階段相比，要求嚴格度上升」}

📍 KG 1,287 nodes · Persona v1 · 系統運行 87 天
```

長度 ~600-800 字，比日報長。

### Step 6：推送

```
bash scripts/send-telegram.sh < weekly-report.md
```

### Step 7：寫日誌

```
寫 ~/Desktop/serenity-digest/logs/2026-W22-reflect.log
追加進 ~/Desktop/serenity-digest/data/weekly-index.jsonl
```

## Output

- KG 維護結果（合併、prune、晉升）
- 1+ 條 contradicts 邊（若有）
- 0-2 條 emerging pattern 節點
- 1 條 weekly insight 節點
- 週報 Telegram 推送
- `logs/2026-W22-reflect.log`

## Quality criteria

- maintain_graph 至少有 1 個操作（merge / prune / promote）
- 週報長度 500-1200 字
- track record 結果不是 NaN
- 週報結尾含系統狀態

## Failure modes

- 價量 API 不可用 → track record 跳過，週報註明
- KG 完全沒新節點 → 報告「本週 KG 無新增（可能日報未跑）」
- contradicts 偵測失敗 → 跳過 Step 2，繼續

## Related skills

- `serenity-digest`：日報的數據來源
- `serenity-distill`：季度蒸餾的觸發者（季度反思時建議跑）
