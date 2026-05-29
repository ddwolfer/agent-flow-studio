# 06 · 新聞重要性評分

## 目標

每天 snapshot.feedItems 裡有 8-14 條訊息（推文 / 新聞 / 披露 / AI 觀點變化），不能全進 brief，要挑 3-5 條最值得提醒的。

## 評分公式（0-100）

```
score(item) =
    30 × tickerPriority(item)
  + 25 × concreteness(item)
  + 15 × sourceQuality(item)
  + 15 × recency(item)
  + 15 × kgRelation(item)
```

### 維度 1：標的優先級 (0-30)

```javascript
function tickerPriority(item) {
  const ticker = item.ticker;
  if (!ticker) return 0;
  
  // 從今日 hotStocks 找出該 ticker 的 priority
  const stock = today.hotStocks.find(s => s.ticker === ticker);
  if (!stock) return 5;  // 不在 top 10
  
  const rank = today.hotStocks.indexOf(stock) + 1;
  // rank 1 = 30, rank 10 = 3
  return Math.max(30 - (rank - 1) * 3, 3);
}
```

意義：訊息對應的標的越熱，這條訊息越值得放。

### 維度 2：新聞具體性 (0-25)

```javascript
function concreteness(item) {
  const text = (item.title + " " + item.body).toLowerCase();
  
  // 高具體（25 分）：明確事件
  const HIGH = [
    /財報|earnings|q[1-4]\s+earnings|beats|misses/,
    /fda|approval|approved/,
    /merger|acquisition|m&a/,
    /lawsuit|settlement|verdict/,
    /guidance|raised|lowered/,
    /spin-?off|ipo|listing/,
    /\$\d+/,  // 提到具體金額
    /\d+%/   // 提到具體百分比
  ];
  
  // 中具體（15 分）：訂單、合作、產品發布
  const MID = [
    /contract|deal|partnership|合作|订单|合同/,
    /launch|release|unveiled/,
    /investment|funding|raised/,
    /target|目标价/
  ];
  
  // 低具體（5 分）：純評論、預測、社群熱度
  const LOW = [
    /could|may|might|可能|或許/,
    /sentiment|情绪|热度/,
    /trader|investor.*betting/
  ];
  
  if (HIGH.some(re => re.test(text))) return 25;
  if (MID.some(re => re.test(text)))  return 15;
  if (LOW.some(re => re.test(text)))  return 5;
  return 10;  // 中性
}
```

### 維度 3：來源權威性 (0-15)

```javascript
function sourceQuality(item) {
  const TIER_A = [
    /reuters|路透/i,
    /bloomberg|彭博/i,
    /wsj|wall.*street/i,
    /financial times|金融时报/i,
    /sec\.gov|edgar/i
  ];
  
  const TIER_B = [
    /cnbc/i,
    /barron'?s/i,
    /seeking alpha/i,
    /benzinga/i
  ];
  
  const TIER_C = [
    /motley fool/i,
    /investopedia/i,
    /yahoo.*finance/i
  ];
  
  const text = item.body + " " + (item.url || "");
  if (TIER_A.some(re => re.test(text))) return 15;
  if (TIER_B.some(re => re.test(text))) return 10;
  if (TIER_C.some(re => re.test(text))) return 5;
  
  // 沒有明確來源（內部 AI 觀點等）
  if (item.kind === "ai") return 12;     // AI 觀點預設給 12
  if (item.kind === "filing") return 15; // SEC 披露最高
  if (item.kind === "tweet") return 8;   // 推文中等
  return 5;
}
```

### 維度 4：時效性 (0-15)

```javascript
function recency(item) {
  const now = new Date(today.fetchedAt);
  const itemTime = new Date(item.publishedAt);
  const hoursAgo = (now - itemTime) / (1000 * 60 * 60);
  
  if (hoursAgo < 6)   return 15;
  if (hoursAgo < 24)  return 12;
  if (hoursAgo < 48)  return 8;
  if (hoursAgo < 168) return 4;  // 一週內
  return 1;
}
```

### 維度 5：與 KG 觀點的關係 (0-15)

```javascript
async function kgRelation(item, ticker) {
  if (!ticker) return 5;
  
  // 從 KG 找該 ticker 的最近觀點
  const memory = await searchMemory({
    query: `${ticker} 觀點`,
    filters: { "metadata.ticker": ticker, trust: "principle" },
    limit: 3
  });
  
  if (memory.length === 0) return 8;  // 沒記憶，中性
  
  // 用 LLM 判斷：item 與既有觀點是強化、反駁、無關
  const judgement = await classifyRelation({
    item: item.body,
    memory: memory.map(m => m.content)
  });
  
  if (judgement === "contradicts") return 15;  // 反例 = 最重要
  if (judgement === "reinforces")  return 12;
  if (judgement === "neutral")     return 6;
  return 3;
}
```

「反例最重要」這條設計是因為：

- 反例改變判斷（高 actionability）
- 強化已知（中 actionability，但仍有確認價值）
- 無關（低 actionability）

## 排序與篩選

```javascript
async function rankNews(snapshot) {
  const scored = await Promise.all(
    snapshot.feedItems.map(async item => ({
      item,
      score: 
        tickerPriority(item) +
        concreteness(item) +
        sourceQuality(item) +
        recency(item) +
        await kgRelation(item, item.ticker)
    }))
  );
  
  scored.sort((a, b) => b.score - a.score);
  
  // 去重：同 ticker 最多保留 1 條
  const seenTickers = new Set();
  const deduped = scored.filter(({ item }) => {
    if (item.ticker && seenTickers.has(item.ticker)) return false;
    if (item.ticker) seenTickers.add(item.ticker);
    return true;
  });
  
  // 取前 3-5（按 depth_preference）
  const cap = config.depth_preference === "short" ? 2 :
              config.depth_preference === "long"  ? 5 : 3;
  return deduped.slice(0, cap);
}
```

## 反例特別標記

如果一條訊息的 `kgRelation === 'contradicts'`，在 brief 裡加 ⚠️ 前綴：

```
⚠️ NVDA · Reuters: 出口管制收緊新規 — 與 KG 中 2026-05-14 看多論點分歧
```

這種訊息**強制進 brief**，即便其他維度分數不高。

## 「弱訊號」的處理

如果評分後所有訊息都 < 40 分，brief 改寫成：

```
▎相關新聞
今日訊號偏弱，無明顯邊際變化。
```

不要硬塞低品質內容。

## 校準週期

每月第一天的月報，回顧：

- 過去 30 天評分 > 60 的訊息有多少是事後驗證有價值的？
- 評分 < 40 但事後重要的有多少？（漏網率）
- 各維度權重要不要調整？

如果漏網率 > 20%，考慮：

- 提升 `concreteness` 權重（更看重事實性）
- 提升 `kgRelation.contradicts` 權重（更看重反例）

## 範例

```
feedItem (input):
{
  "ticker": "NVDA",
  "kind": "news",
  "title": "Reuters: NVIDIA Q1 earnings beat by 12%",
  "body": "NVDA reported Q1 EPS of $5.32 vs $4.75 expected, raised FY guidance...",
  "publishedAt": "2026-05-29 04:30",
  "url": "reuters.com/..."
}

評分：
- tickerPriority: 30 (NVDA #1)
- concreteness: 25 (財報 + 具體百分比 + raised guidance)
- sourceQuality: 15 (Reuters)
- recency: 15 (1.5 小時前)
- kgRelation: 12 (強化 KG 中既有 bull_high_risk 論點)

總分: 97 → 強制進 brief top 1
```

## 邊界條件

- `feedItems.length === 0` → 完全跳過新聞段
- 全部訊息 `score < 30` → 跳過
- 同一 ticker 出現 ≥ 3 條訊息 → 合併成「NVDA 多條更新（X 條）」
- 多 ticker 在同一條 item → 拆成多條打分（每條只取最高 ticker 對應的分數）
