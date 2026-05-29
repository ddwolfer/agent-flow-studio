# 09 · 演化路徑與 90 天決策樹

## 三階段目標

```
Phase 1  (Day 0-30)    冷啟動：跑通流程，累積 evidence pool 與 KG
Phase 2  (Day 30-90)   收斂：v1 SKILL.md 上線，KG 開始 consolidate
Phase 3  (Day 90+)     蒸餾：v2 SKILL.md，評估升 E 與否
```

## Phase 1：冷啟動（Day 0-30）

**目標**：把流程跑通、開始累積。

**這階段不需要的**：

- 蒸餾 SKILL.md（語料不足）
- 完整的新聞評分（評分維度 5 需要 KG，但 KG 還是空的）
- 季度重蒸餾流程

**這階段每天做的**：

- 爬 → snapshot → diff（如果有昨日）→ 組 brief → 推送 → KG 寫入
- KG 寫入用「最樸素」模式：principle 節點為主，邊只建必要的 `refines`、`contradicts`

**Brief 在這階段**：

- Tier 1 直接引用 KOL 的當日 summary 改寫（不嘗試套用蒸餾框架）
- 不含「KOL 對照」段（KG 還沒料）
- 新聞段用簡單評分（維度 1-4，跳過維度 5）

**Day 30 檢查點**：

- [ ] 30 個 snapshot 全部成功
- [ ] KG 節點數 ≥ 200
- [ ] 每天 brief 都成功送達
- [ ] Logs 沒有重大 errors

通過 → 進 Phase 2。
失敗 → debug，看 docs/10-acceptance.md。

## Phase 2：收斂（Day 30-90）

**Day 30 同時做的**：

1. 跑首次蒸餾 → `serenity-perspective-v1.md`
2. 注入到 system prompt
3. 啟用完整新聞評分（含維度 5 kgRelation）
4. 開始週反思（每週日 21:00）

**這階段每天做的**（與 Phase 1 差異）：

- Brief 套用 v1 蒸餾的表達 DNA（句型、詞彙）
- 加入「KOL 對照」段
- 新聞評分啟用反例偵測
- Tier 1 條目的「需驗證：」段用 v1 抽出的 validation templates

**這階段每週做的**：

- 週日 21:00 跑 `weekly-reflect`：
  - `maintain_graph()`：合併、prune、晉升
  - 對照過去 7 天 priorityQueue top 3 與當前價量
  - Claude 寫 1 則 `insight` 節點：「本週發現」
  - 推送週報（~800 字）

**Day 60 中期評估**：

- [ ] KG 節點數 500-1500
- [ ] 至少 1 個節點晉升到 Level 2（Verifying）
- [ ] 至少 5 條 `contradicts` 邊（系統發現過反例）
- [ ] 每週反思生成的 insight 節點 ≥ 4 條

**Day 90 主要評估點**：

跑 `evaluate-track-record.mjs`，計算過去 60 天 KOL 預測準確率：

```javascript
function trackRecord() {
  const period = last60Days();
  const predictions = period.flatMap(day =>
    day.priorityQueue.slice(0, 3).map(s => ({
      ticker: s.ticker,
      stance: s.stance,
      date: day.fetchedAt
    }))
  );
  
  const results = await Promise.all(
    predictions.map(async p => {
      const priceData = await fetchPrice(p.ticker, p.date, +7);  // +7 days
      const change7d = (priceData.end - priceData.start) / priceData.start;
      
      // 配對：bull → +5% 算對、neutral → ±5% 內算對、bear → -5% 算對
      const expectedSign = 
        p.stance.includes("bull") ? 1 :
        p.stance.includes("bear") ? -1 : 0;
      
      const correct = 
        (expectedSign === 1  && change7d > 0.05) ||
        (expectedSign === -1 && change7d < -0.05) ||
        (expectedSign === 0  && Math.abs(change7d) < 0.05);
      
      return { ...p, change7d, correct };
    })
  );
  
  return {
    total: results.length,
    correct: results.filter(r => r.correct).length,
    accuracy: results.filter(r => r.correct).length / results.length
  };
}
```

## 90 天決策樹

```
                 ┌─── trackRecord.accuracy >= 0.60 ───┐
                 │                                     │
                 │                                     ▼
                 │              升 E：在 KG 節點 metadata 啟用
                 │              evidence_refs，主動引用 snapshot
                 │              中的具體事件、新聞、披露
                 │
                 │── 0.30 <= accuracy < 0.60 ──────────┐
trackRecord()    │                                     │
                 │                                     ▼
                 │              維持 D：調整 KG 參數
                 │              - trust level 升級門檻放寬
                 │              - consolidation 相似度閾值放寬
                 │              - 蒸餾框架的「決策啟發」加權重
                 │
                 └── accuracy < 0.30 ──────────────────┐
                                                       │
                                                       ▼
                                  砍掉重練：
                                  - 檢討 nuwa 蒸餾的品質
                                  - 評估 KG 範圍是否錯（要不要納入市場事件）
                                  - 考慮加另一個 KOL 對照
```

## Phase 3：蒸餾（Day 90+）

**Day 90 同時做的**（不論升 E 與否）：

1. 跑 v2 蒸餾 → `serenity-perspective-v2.md`
2. 產出 `diff-v1-v2.md`
3. owner review diff（24 小時內）
4. 通過 → 啟用 v2

**升 E 後的差異**：

每天 KG 寫入時，把 snapshot 中具體的 feedItem 用 evidence ID 形式存進 `data/evidence/`：

```
~/Desktop/serenity-digest/data/evidence/
├── news/
│   ├── 2026-08-29-reuters-NVDA-earnings.json
│   └── ...
├── filings/
│   └── 2026-08-29-EDGAR-NVDA-10Q.json
└── tweets/
    └── 2026-08-29-author-tweet-1234.json
```

KG 節點 metadata 啟用 `evidence_refs`：

```json
{
  "evidence_refs": [
    "news/2026-08-29-reuters-NVDA-earnings.json",
    "filings/2026-08-29-EDGAR-NVDA-10Q.json"
  ]
}
```

搜尋時可以選擇是否把 evidence 內容 fetch 進 context（增加成本但提高可解釋性）。

## 半年 / 一年里程碑

### Day 180

- 跑 v3 蒸餾，看是否仍朝同方向收斂
- 評估「Claude 獨立判斷」品質：把 inference 節點的 access > 10 的篩出來，看有多少已經晉升到 Level 3+
- 如果 Level 3+ inference 節點 ≥ 30，**已經有一套小型的 Claude 自有判斷體系**

### Day 365

- 跑 v4
- 評估「即便 KOL 停更，系統還能繼續產出」的可行性：
  - 把 SKILL.md v4 + KG 全部 export
  - 試跑「離線模式」：不爬原站，只用既有材料 + 一般市場新聞，產出 brief
  - 與真實 KOL 該天的輸出比對（如果他還在更）
  - 一致性 > 70% → 系統已蒸餾成功

## KOL 停更的 fallback

當原站連續 > 3 天無更新（HTML checksum 不變、`siteSnapshotAt` 沒推進）：

```
Day 1 unchanged: brief 標「原站今日尚未更新，沿用前次內容」
Day 3 unchanged: 切換為「KOL 暫離模式」：
  - 不爬原站
  - 用 SKILL.md + KG 對外部新聞做獨立判斷
  - Brief 標明「[KOL 暫離] Claude 獨立判斷」
Day 30 unchanged: 推送一則「KOL 已 30 天未更新，是否仍要繼續系統？」owner 決定
```

## 多 KOL 擴增（未來）

如果想加入第二位 KOL：

- KG 的 `source` 標籤天然支援多來源
- 蒸餾流程跑兩次，產出 `KOL_A-perspective.md` + `KOL_B-perspective.md`
- Brief 改為「兩位 KOL 的對比+ 共識」格式

**此設計從第一天就支援**，未來不需要 migration。

## 失敗的訊號

以下任一情況 ≥ 2 個出現，要重新審視整個架構：

- [ ] KG 節點數爆炸（> 50k）但 access 集中在少數幾個（< 5%）
- [ ] 連續 4 週 trackRecord.accuracy 都 < 0.4
- [ ] nuwa v2 與 v1 偏離 > 50%（蒸餾沒收斂）
- [ ] 每週反思生成的 insight 重複度 > 70%（沒學到新東西）
- [ ] Telegram 推送成功率 < 90%（基礎建設不穩）

## 成功的訊號

以下出現 3 個以上 = 系統運作良好：

- [ ] Brief 平均 read time（如能量化）> 90 秒，< 5 分鐘
- [ ] KG 中 Level 3+ 節點佔比 > 5%
- [ ] 季度重蒸餾的 diff 顯示明確收斂方向
- [ ] 有過 ≥ 3 次 Claude inference 後來被 KOL 觀點 vindicate（aligns_to）
- [ ] owner 主動回頭問系統「上次 X 是怎麼想的」並能找到答案
