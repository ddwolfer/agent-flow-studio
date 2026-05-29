# 05 · 股票列幾檔：tier 化 + 自適應

## 為什麼 tier 化

直接列前 10 配上完整推論 → 800+ 字，掃完要 10 分鐘，**失去日報的「快速建立 awareness」價值**。

但只列前 3 又會錯過「進榜的新標的」「跌出榜的舊愛」。

解法：**分 3 個 tier**，每個 tier 的呈現深度不同。

```
Tier 1：必讀（深度）
  - 列 3-5 檔
  - 每檔 50-80 字推理
  - 含 stance、priority、24h 變化、KOL 強調的驗證點
  - 句型套 Persona DNA

Tier 2：掃過（標題）
  - 列 5-10 檔（與 Tier 1 互斥）
  - 每檔 15-25 字
  - 只列 ticker + priority + 主要 tag

Tier 3：備註（變化）
  - 不列具體 ticker stance
  - 只說：進榜 X 檔、退榜 Y 檔、漲幅最大 Z 檔
```

## Tier 1 的數量決定（自適應）

不是固定 3 或 5，**根據訊號分布決定**。

```javascript
function decideTier1Count(priorityQueue) {
  const top10 = priorityQueue.slice(0, 10);
  const topPriority = top10[0].priority;
  const cutoff = topPriority * 0.95;  // 訊號強度 95% 內視為同 tier
  
  let count = top10.filter(s => s.priority >= cutoff).length;
  return Math.min(Math.max(count, 3), 5);  // 鎖 3-5
}
```

意義：

- 如果今天前 5 名很集中（priority 都在 400+），Tier 1 = 5
- 如果今天 #1 一支獨秀（440），其他 #2-#10 都 < 380 → Tier 1 = 3
- 永遠不會少於 3（保證足夠的 actionable 內容）
- 永遠不會多於 5（保證 Telegram 訊息長度可控）

## 哪些檔上 Tier 1

排序鍵（多級）：

1. 主鍵：`priority`（DESC）
2. 副鍵：`delta24h`（DESC，今日新增提及越多越上）
3. 三鍵：`aiChange === 'xhigh'` 優先（KOL 自己標記為高關注的）

額外加分（可以擠掉純 priority 排序）：

- 若 `ticker` 在 `priorityMovers` 前 3 → +50 虛擬 priority
- 若 `ticker` 在 `newInTop10` → +30 虛擬 priority
- 若 `ticker` 出現在今日 `contradicts` 偵測（KG 找出與過去觀點衝突）→ +40 虛擬 priority

## Tier 2 的數量

```javascript
function decideTier2Count(briefLengthBudget, tier1Items) {
  // tier1 平均 70 字，tier2 平均 20 字
  const usedByTier1 = tier1Items.length * 70;
  const remainingForTier2 = briefLengthBudget - usedByTier1 - 200; // 200 預留給其他段
  const maxTier2 = Math.floor(remainingForTier2 / 20);
  return Math.min(Math.max(maxTier2, 5), 10);
}
```

- 預算（briefLengthBudget）按用戶選的 depth_preference 決定：
  - short: 1500 chars
  - medium: 2500 chars
  - long: 3500 chars

## Tier 3：變化摘要

格式範本：

```
🆕 今日進榜：MRVL, AVGO（2 檔）
👋 今日退榜：COHR, GOOGL（2 檔）
📈 漲幅最大：NVDA +25
📉 跌幅最大：TSLA -42
```

如果四項都 0 → 整段省略，不要硬擠空白。

## Edge cases

| 情境 | 處理 |
| --- | --- |
| 今日 priorityQueue.length < 3 | Tier 1 縮到實際數量，加註「今日訊號稀疏」 |
| 全部 stance 都是 neutral | Tier 1 仍列前 3，但每檔加註「KOL 維持中性」 |
| `aiChange === 'xhigh'` 的數量 > 10 | Tier 1 不變，但在 brief 標題加「⚡ 高關注日」字樣 |
| 連續 3 天同一檔在 Tier 1 #1 | 第 3 天起加「（連續 N 天列為首要）」標記 |
| 同一行業壟斷 Tier 1 ≥ 3 檔 | 加註「⚠️ 同行業集中：[半導體]」 |

## 整體訊息長度的硬上限

| 預算等級 | 上限 | 適用 |
| --- | --- | --- |
| short | 1500 chars | 通勤時掃 |
| medium | 2500 chars | 正常閱讀 |
| long | 3500 chars | 想看完整 reasoning |

超過 4096 (Telegram 單訊息上限) → 分段。

預設 **medium**，在 `~/.config/serenity-digest/config.json` 可改：

```json
{
  "depth_preference": "medium",
  "telegram_bot_token": "...",
  "telegram_chat_id": "..."
}
```

## 內容深度比例

medium 預算 (2500 chars) 的典型分配：

```
標題 + 日期戳：          50 chars
Tier 1 (4 檔 × 70 字)：  280 chars
Tier 2 (8 檔 × 20 字)：  160 chars
Tier 3 變化摘要：         120 chars
昨日對照（priorityMovers reasoning）：250 chars
新聞 top 3 (每條 ~80)：  240 chars
KG 觀點提醒（若有）：    180 chars
footer + 歸因：           80 chars
緩衝：                    1140 chars 餘量
```

緩衝留充足，因為 Persona DNA 寫的句子比預估略長。

## 範例（medium 預算實際輸出）

見 `examples/sample-brief.md`。

## 驗收

- [ ] 連續 7 天 brief 長度都在預算 ± 20% 內
- [ ] Tier 1 每檔有具體 reasoning，不是「看多 / 看空」一句話
- [ ] Tier 2 全部都有 priority 數字
- [ ] 每天的 brief 開頭 5 個字內就出現 KOL 用過的標誌詞
- [ ] 沒有任何 brief 出現「強烈推薦 / 目標價 / 翻倍」這類 anti-pattern 詞
