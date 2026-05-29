# 02 · Knowledge Graph 整合

## 安裝

依 `knowledgeGraph` repo 的 README：

```bash
git clone https://github.com/ddwolfer/knowledgeGraph.git ~/.mcp/knowledge-graph
cd ~/.mcp/knowledge-graph
npm install
# 首次啟動會自動下載 Qwen3-Embedding-0.6B ONNX（~560MB），一次性
```

主 agent 的 `.mcp.json` 加：

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "node",
      "args": ["~/.mcp/knowledge-graph/main.js"]
    }
  }
}
```

`~/.claude/settings.json` 加 hooks（見 `prompts/daily-brief.md` 的 hook 設定參考）。

DB 位置：`~/.config/serenity-digest/knowledge.db`

## Serenity 語境下的節點/邊約定

KG 預設有的型別已經夠用，這裡固定我們的使用慣例，方便檢索與一致性。

### 節點型別 (`type`)

| type | 用途 | 範例 |
| --- | --- | --- |
| `rule` | 投研守則 | 「先驗證 EDGAR 披露，再相信新聞標題」 |
| `procedure` | 操作流程 | 「進入 watchlist 前必跑：行業壓力檢查 → 公司財報結構 → 流動性」 |
| `observation` | 觀察到的市場事件或現象 | 「2026-05-27 NVDA 出口管制新聞發布」 |
| `insight` | 從觀察推導出的見解 | 「KOL 用『拆解客戶集中度』這個句型 = 想引入懷疑」 |
| `core` | 核心觀點，跨多檔重複出現 | 「政策叙事必須核驗文件，不等同於公司獲得訂單」 |
| `preference` | KOL 的偏好取向 | 「KOL 偏好半導體 / 光通信集群」 |

### Trust（來源信任，永久標籤）

| trust | 條件 | Serenity 例子 |
| --- | --- | --- |
| `principle` | KOL 親口說的，**必須附 quote**（原文片段 ≥ 20 字）| 「需要核验 EU 文件、公司公告、客戶合同」|
| `pattern` | 跨 5+ 檔重複出現，或 30 天內 3+ 次驗證 | 「KOL 對 800G 光通信標的多次採『驗證導向』語氣」|
| `inference` | Claude 自己推導的，**永久標記為推論** | 「KOL 對 SIVE 的政策叙事可能高估—— 未見訂單轉換證據」|

**Anti-fabrication 必守**：
- principle 沒有 quote → 必須拒絕儲存
- inference 不能建立 `must_precede` 或 `reason_for` 邊（這些是因果，需要 principle/pattern 才能宣告）
- trust 不會自動晉升（inference 永遠是 inference，即便 access 50 次）

### Metadata 約定

每個節點 metadata 至少包含：

```json
{
  "ticker": "NVDA",                       // 主要關聯標的（沒有就 null）
  "sector": "半導體",                      // 行業
  "stance": "bull_high_risk",             // KOL 觀點分類
  "category": "fundamental | creative",    // fundamental 永不衰減
  "first_seen": "2026-05-27",             // 首次出現日期
  "last_confirmed": "2026-05-29",         // 最後一次被驗證
  "confidence": 0.85,                     // 0-1，KOL 表達的把握度
  "evidence_refs": []                     // 預留欄位，第一階段不啟用
}
```

`category`:
- `fundamental`：投研守則、無爭議事實（公司財報數字、SEC 披露條目）→ 不衰減
- `creative`：KOL 的觀點、推論、預測 → 會衰減、可被反例挑戰

### 邊型別 (`edge`)

| edge | 語義 | Serenity 例子 |
| --- | --- | --- |
| `must_precede` | A 必先於 B（時序/邏輯）| 「驗證 SEC 披露」`must_precede` 「相信新聞標題」|
| `requires_reading` | 看 A 前要先看 B | 「NVDA 高風險偏多」`requires_reading` 「出口管制風險」|
| `refines` | A 是 B 的細化 | 「800VDC 線索」`refines` 「NVDA 生態映射」|
| `contradicts` | A 反駁 B | 「2026-06-15 NVDA 跌 30%」`contradicts` 「2026-05-27 看多 NVDA」|
| `reason_for` | A 是 B 的原因 | 「出口管制收緊」`reason_for` 「半導體高風險」|
| `causes` | A 導致 B | 「FOMC 升息」`causes` 「估值收窄」|
| `implies` | A 暗示 B | 「KOL 用『拆解客戶集中度』」`implies` 「KOL 想質疑」|
| `aligns_to` | A 對齊 B 的框架 | 「LITE 觀點」`aligns_to` 「驗證導向通用模式」|
| `tends_to` | A 傾向發展為 B | 「政策叙事」`tends_to` 「估值脫鉤」|
| `observed_in` | A 在 B 中被觀察到 | 「『需要核驗』句型」`observed_in` 「NVDA, SIVE, LITE」|

### Source 欄位

| source | 用途 |
| --- | --- |
| `serenity-site` | 從 analysissite 爬下來的 KOL 觀點 |
| `claude-daily` | Claude 在日常 brief 推論的內容 |
| `claude-reflect` | Claude 在週反思推論的內容 |
| `nuwa-v1` ~ `nuwa-vN` | nuwa 蒸餾出來的元觀點（標明版本）|
| `manual` | owner 手動加入（極少數）|

## 標準呼叫流程

### 每日 brief 中

```
auto-recall hook 觸發
  ↓
search_memory({
  query: "NVDA 高風險偏多",
  filters: { ticker: "NVDA" },
  limit: 10
})
  ↓
返回今天 NVDA 相關的：
  - KOL 過去 30 天對 NVDA 的觀點 (principle)
  - 已 consolidate 的 NVDA pattern
  - Claude 過去的 NVDA inference
  ↓
組進 prompt 當 retrieval context
  ↓
產出 brief
  ↓
auto-capture hook 觸發
  ↓
store_knowledge({
  type: "insight",
  trust: "principle",
  content: "今日 KOL 對 NVDA 強調出口管制 + 客戶集中度",
  quote: "出口管制、客户集中、产能承诺、生态投资和资本回报仍是一手证据核心",
  metadata: {
    ticker: "NVDA",
    sector: "半導體",
    stance: "bull_high_risk",
    category: "creative",
    first_seen: "2026-05-29",
    confidence: 0.85
  },
  source: "serenity-site"
})
  ↓
connect_knowledge(
  from: 今日節點,
  to: 2026-05-27 的 NVDA 節點,
  edge: "refines"
)
```

### 每週反思

```
maintain_graph 自動跑：
  - 偵測 contradicts（KOL 預測 vs 實際 7-day 價格）
  - 合併 vector similarity > 0.85 的重複節點
  - prune weight < 0.3 的弱邊
  - 晉升 access > 5 且跨 3+ session 的節點到 Level 2

recall_experience 找最近一週的 workflow trace，
Claude 自己寫一則 insight 節點：
  「本週發現 KOL 對 X 類標的判斷準確率高於 Y 類」
```

### 季度重蒸餾

```
list_knowledge({
  filters: { source: "serenity-site", category: "creative" },
  limit: 500
}) 
  ↓
匯出成 corpus
  ↓
餵給 nuwa 改造版（見 docs/03）
  ↓
產出 serenity-perspective-v{N}.md
  ↓
diff v{N-1}：超過 30% 偏離要 owner 確認
```

## 初始化（一次性）

第一次安裝後，跑 `scripts/kg-bootstrap.mjs`，種入幾個 anchor 節點：

```javascript
// 行業 anchor 節點
["半導體", "光通信", "光子", "存儲", "AI算力", "互聯網", "航天", "加密金融"]
  .forEach(sector => store({
    type: "core",
    trust: "principle",
    content: `行業分類：${sector}`,
    metadata: { category: "fundamental" },
    source: "manual"
  }));

// Stance anchor 節點
["bull", "bear", "neutral", "watch", "watch_high_risk", "bull_high_risk", "caution"]
  .forEach(stance => store({
    type: "core",
    trust: "principle",
    content: `觀點分類：${stance}`,
    metadata: { category: "fundamental" },
    source: "manual"
  }));
```

這些 anchor 節點之後讓 sector / stance 變成可被 traverse 的節點，而不只是字串。

## 效能預期

| 階段 | 節點數 | DB 大小 | 一次 search_memory 延遲 |
| --- | --- | --- | --- |
| Day 1 | ~30 (anchor + v1 蒸餾) | 5 MB | <100ms |
| Day 30 | ~500 | 15 MB | <200ms |
| Day 90 | ~1500 | 50 MB | <300ms |
| Day 365 | ~6000 | 200 MB | <600ms |

超過預期時觸發 maintain_graph 的 prune 模式。

## 失敗模式與處置

| 情境 | 處置 |
| --- | --- |
| `knowledge.db` 損壞 | 從 evidence pool 重播：`scripts/replay-snapshots.mjs` |
| Qwen3 model 下載失敗 | 改用 keyword + graph search，先不要 vector |
| store_knowledge 拒絕（缺 quote）| 降格為 inference 節點，標 `degraded: true` |
| 重複節點偵測失誤導致誤合 | 從 evidence pool 補回最近 7 天，rebuild affected 區域 |
