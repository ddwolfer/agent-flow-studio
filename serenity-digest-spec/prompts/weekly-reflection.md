# Prompt: Weekly Reflection

> 每週日 21:00 台灣時間排程觸發。執行 KG 維護 + 週反思 + 週報推送。

---

你在執行 Serenity Digest 的週反思。本週是 {{WEEK_OF_ISO}}（例：2026-W22 = 5/25 - 5/31）。

## 流程

### Step 1：KG 維護

```
maintain_graph({
  operations: ["merge", "validate", "orphan", "prune"]
})
```

記下：
- merged: ?
- validated: ?
- orphans: ?
- pruned: ?
- promoted_to_level_2: ?
- promoted_to_level_3: ?

### Step 2：偵測 contradictions

從 `~/Desktop/serenity-digest/data/` 取過去 7 天每天的 priorityQueue Tier 1 ticker（去重）。

對每個 ticker：

```
fetchPrice({ticker}, fromDate, 7days)
  → priceChange = (end - start) / start

KOL stance（取過去 7 天的多數 stance）：
  bull / bull_high_risk → 期望 +5%+
  bear / caution        → 期望 -5%-
  neutral               → 期望 ±5% 內
```

若 KOL 預期方向與實際 7d 變化矛盾 → 建 contradicts 邊：

```
connect_knowledge(
  from: actual_price_node (建一個新的 observation 節點記錄這次價量),
  to:   kol_prediction_node (該檔過去 7 天的 principle 節點),
  edge: "contradicts",
  metadata: { magnitude: abs(actual - expected) }
)
```

### Step 3：尋找 emerging patterns

```
list_knowledge({
  filters: { source: "serenity-site", trust: "principle",
             created_after: 30 days ago },
  limit: 200
})
```

對結果做 vector clustering（相似度 > 0.75）：

```
clusters = cluster_by_vector(principles, threshold: 0.75)
```

對 cluster.size >= 5 的：

```
candidate_pattern = synthesize(cluster)  # 你自己寫一句總結
store_knowledge({
  type: "insight",
  trust: "pattern",          # 從 principle 集群升級
  content: candidate_pattern.synthesis,
  quote: cluster[0].quote,
  metadata: {
    category: "creative",
    confidence: 0.8,
    promoted_from: cluster.ids
  },
  source: "claude-reflect"
})
```

每週最多升 2 個 pattern。

### Step 4：track record 評估

```javascript
const predictions = last7Days.flatMap(d => 
  d.priorityQueue.slice(0, 3).map(s => ({
    ticker: s.ticker,
    stance: s.stance,
    date: d.fetchedAt
  }))
);

const results = await Promise.all(predictions.map(async p => {
  const change = await fetchPrice7dChange(p.ticker, p.date);
  const correct = matchesStance(p.stance, change);
  return { ...p, change, correct };
}));

const accuracy = results.filter(r => r.correct).length / results.length;
```

寫一則 insight 節點：

```
store_knowledge({
  type: "insight",
  trust: "inference",
  content: "本週 KOL 預測準確率 {accuracy:.0%}（n={total}）。命中：[...]。失準：[...]。",
  metadata: {
    period: "weekly",
    week_of: "{{WEEK_OF_ISO}}",
    confidence: 0.7,
    category: "creative"
  },
  source: "claude-reflect"
})
```

### Step 5：組週報

```
📊 *{{WEEK_OF_ISO}} Serenity 週反思* (週日 21:00)

▎*本週命中率*
{X}/{Y} = {accuracy:.0%}
- ✅ 命中：{ticker_list}
- ❌ 失準：{ticker_list}

▎*新發現的 pattern*
{若 Step 3 有產出 pattern → 列；否則「本週無新 pattern」}

▎*KG 維護*
- 合併重複節點：{merged}
- 移除弱邊：{pruned}
- 新晉升 Level 2 節點：{promoted_to_level_2}
- 新晉升 Level 3 節點：{promoted_to_level_3}
- 待處理孤立節點：{orphans}

▎*趨勢觀察*
{你對本週的整體觀察，~80 字。
 例如：「本週半導體集中度增加，KOL 多次用『需要核驗訂單轉換』，
       與上週『純政策叙事』階段相比，要求嚴格度上升」}

📍 KG {total_nodes} nodes · Persona {persona_version} · 系統運行 {days_since_day0} 天
```

長度 500-1200 字。

### Step 6：推送

```bash
echo "$WEEKLY_REPORT" | bash ~/Desktop/serenity-digest-spec/scripts/send-telegram.sh
```

### Step 7：日誌

寫 `~/Desktop/serenity-digest/logs/{{WEEK_OF_ISO}}-reflect.log`。
追加進 `~/Desktop/serenity-digest/data/weekly-index.jsonl`：

```json
{"week":"{{WEEK_OF_ISO}}","accuracy":0.62,"pattern_promoted":2,"kg_total":1287}
```

## 完成標準

- 至少 1 個 KG 維護操作有實際效果
- 週報 Telegram 推送成功
- weekly-index.jsonl 追加一行

完成後回應「✅ Weekly reflect done: {{WEEK_OF_ISO}}, accuracy {X}%」。
