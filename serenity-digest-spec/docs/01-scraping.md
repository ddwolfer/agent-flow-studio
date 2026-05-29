# 01 · 爬蟲與解析

## 目標

每天 06:00 抓取 `analysissite.vercel.app` 首頁與必要子頁，把渲染後的內容解析為結構化 JSON，作為當日所有後續處理的單一輸入源。

## 站台特性

- Next.js App Router 部署在 Vercel
- 首頁 server-side rendered，`fetch` 直接拿就有完整文字內容
- 客戶端再 hydrate 出互動樣式
- 路徑：
  - `/` 總覽
  - `/stocks/[ticker]` 個股
  - `/tweets` 信息流
  - `/llm` AI 觀點
- 字串編碼 UTF-8

## 抓取策略

### Phase 1（先做）：只抓首頁

首頁包含：
- 今日快照時間戳
- 6 個指標數字（活躍信號、覆蓋、24h/7D/30D 活躍、新聞驅動）
- 優先隊列 top 3
- 信息流 8-14 條（含每條的 ticker / 觀點 / 推論摘要）
- 隊列分布（5 個觀點分類人數）
- 熱點股票 top 10

90% 的 brief 內容能從首頁產生。

### Phase 2（之後）：依需求補抓子頁

- 當首頁某檔在 top 3 但 summary 字數 < 80 → 抓 `/stocks/{ticker}` 補
- 當「最新信息流」某條 ticker 不在 top 10 但被提及 → 抓 `/stocks/{ticker}` 補 context
- 一次抓不超過 5 個子頁（避免被認為是攻擊性爬取）

## 解析輸出格式

scrape-snapshot.mjs 產出的 JSON schema：

```json
{
  "$schema": "snapshot-v1",
  "fetchedAt": "2026-05-29T06:00:12+08:00",
  "source": {
    "url": "https://analysissite.vercel.app/",
    "siteSnapshotAt": "2026-05-29T05:50:00+08:00"
  },
  "metrics": {
    "activeSignals": 445,
    "coverage": 703,
    "delta24h": 18,
    "delta7d": 62,
    "delta30d": 184,
    "newsDriven": 79
  },
  "priorityQueue": [
    {
      "rank": 1,
      "ticker": "NVDA",
      "priority": 432,
      "stance": "bull_high_risk",
      "aiChange": "xhigh",
      "summary": "存儲鏈條與功率半導體線索...",
      "tags": ["看多", "高风险偏多", "GPT xhigh"],
      "updatedAt": "2026-05-29 05:49"
    }
  ],
  "hotStocks": [
    /* 10 條，schema 同 priorityQueue */
  ],
  "feedItems": [
    {
      "id": "feed-0",
      "ticker": "SIVE",
      "kind": "ai",
      "title": "GPT xhigh 更新 · SIVE",
      "body": "EU Chips Act 2...",
      "badges": [
        {"label": "GPT xhigh", "tone": "ai"},
        {"label": "看多", "tone": "bull"}
      ],
      "publishedAt": "2026-05-29 05:49"
    }
  ],
  "distribution": {
    "観察": 242,
    "积极观察": 186,
    "高风险观察": 122,
    "谨慎": 86,
    "高风险偏多": 70
  },
  "industries": null,
  "raw": {
    "html": "...html length...",
    "checksum": "sha256:..."
  }
}
```

關鍵欄位說明：

- `fetchedAt`：抓取的台灣時間（含時區）
- `source.siteSnapshotAt`：原站自身宣稱的快照時間（要解析首頁文字找出來）
- `raw.checksum`：原始 HTML 的 SHA-256，後續 diff 偵測用
- `industries: null`：Phase 1 不抓，Phase 2 補

## 解析的容錯規則

| 情境 | 處理 |
| --- | --- |
| 首頁 fetch HTTP 非 200 | retry 一次（間隔 30 秒），仍失敗 → 沿用昨日 snapshot 並標記 `stale: true` |
| HTML 結構變動，某欄解析失敗 | 該欄填 `null`，不中斷全流程，寫 log |
| 數字解析失敗（NaN）| 該指標填 `null`，brief 改顯示「—」 |
| Ticker 數量為 0 | 觸發 alert（log + brief 內顯示 `[STATUS] 爬蟲解析異常`）|
| HTML checksum 與昨日相同 | 標記 `unchanged: true`，brief 改顯示「原站今日尚未更新」 |

## 解析的反脆弱

原站作者可能改版。為了讓解析器活久一點：

1. **用文字錨點而非 CSS selector**：找「今日优先队列」「熱點股票」這些不太會改的中文 heading，從這些錨點往下吃內容。
2. **多錨點 fallback**：如果「今日优先队列」找不到，試 `priority queue`、`今日`、首頁第一個 `<h2>` 後的列表。
3. **每天比對 HTML 結構 hash**：頂層 DOM 樹的 schema hash 改變 → log 提示「站台可能改版」。
4. **保留 raw HTML**：snapshot 留一個 `raw.htmlPath: "raw/2026-05-29.html"`，方便人工檢查。

## Rate Limit 與禮儀

- 每天只抓一次（手動 retry 不超過 3 次/天）
- User-Agent 設成可辨識字串：`SerenityDigest/1.0 (personal-digest; +mailto:910063@gmail.com)`
- 不抓 `/api/*` 內部路徑（即便發現了也別碰）
- 遇到 429 / 503 立即停止，當天標記失敗

## 個股子頁解析（Phase 2）

```
GET /stocks/{ticker}
  ▸ 完整 summary（首頁是 line-clamp-3 版本）
  ▸ 推文時間序（如果原站有）
  ▸ 新聞列表（含外部連結）
  ▸ 披露列表
  ▸ AI 評級的歷史變化
```

Phase 2 啟用時，按本檔「抓取策略」的條件，加進 snapshot 的 `stockDetails: { "NVDA": {...} }` 欄位。

## 驗收

scrape-snapshot.mjs 通過以下測試才算 OK：

- [ ] 連續 7 天每天輸出有效 JSON，無 schema 錯誤
- [ ] 任一欄失敗時 fall back 至 null，不丟整份
- [ ] checksum 在原站不變時穩定一致
- [ ] 首頁字數 > 1000 中文字（避免抓到 client skeleton）
- [ ] `priorityQueue.length >= 3` 且 `hotStocks.length >= 10`
