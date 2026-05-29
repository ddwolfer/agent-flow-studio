# 07 · Telegram 訊息格式

## 整體骨架

```
📊 {YYYY-MM-DD} Serenity 日報 ({HH:MM})

▎今日優先（Tier 1）
{ 4 檔深度條目 }

▎掃描清單（Tier 2）
{ 8 檔簡短條目 }

▎昨日 → 今日變化（Tier 3）
{ 進榜、退榜、漲跌最大 }

▎KOL 對照（KG 注入）
{ 若有，列 1-2 條 KOL 過去觀點與今日 alignment / divergence }

▎相關訊號
{ 3-5 條評分後的 feedItem }

📍 分析框架蒸餾自 analysissite.vercel.app | v{persona_version} | KG nodes: {count}
🔗 完整看板：https://analysissite.vercel.app/
```

## Markdown 規則

Telegram parse_mode=Markdown 支援：

- `*粗體*`
- `_斜體_`
- `` `等寬` ``
- `[文字](URL)`
- `__底線__`（部分 client）

**不**支援：

- 表格
- HTML
- 巢狀格式
- emoji 排版（但 emoji 字元本身 OK）

所以版面只能用：

1. emoji 當分節符號
2. 空行斷段
3. `*ticker*` 強調股票代號

## 詳細範本

### 標題
```
📊 *2026-05-29 Serenity 日報* (06:00 台北)
```

固定用 `📊`，日期粗體，括號內時間。

### Tier 1 條目

```
1. *NVDA* · 優先級 432 (+5) · 看多·高風險偏多
   存儲鏈條與功率半導體線索抬高生態映射優先級。
   需驗證：客戶集中度、產能承諾、出口管制邊際影響。
   _[KOL 連續 3 天列為首要]_
```

組件：

- 序號（1-5）
- ticker（粗體）
- 優先級 + 昨日 delta
- stance pills（用 `·` 串接）
- 換行
- 縮排 3 空格
- KOL 該檔的當日精煉理由（一句話）
- 「需驗證：」段（從 KOL 表達 DNA 抽出的 3-4 個 validation points）
- 第 4 行：可選的 KG 提示（連續、衝突、首次進榜等）

### Tier 2 條目

```
5. *MRVL* 311 看多·高風險偏多 _進榜_
6. *MSTR* 310 中性·高風險觀察
7. *RKLB* 301 看多·高風險偏多 _ATM 風險_
```

組件：

- 序號（接續 Tier 1）
- ticker（粗體）
- 優先級
- stance（無分隔點，緊接）
- 可選的 tail tag（斜體）

### Tier 3 變化摘要

```
▎*昨日變化*
🆕 進榜：MRVL, AVGO
👋 退榜：COHR, GOOGL
📈 漲幅最大：NVDA +25, SIVE +18
📉 跌幅最大：TSLA -42
```

四項任一為空就省略該行。

### KG 對照段

```
▎*KOL 對照*
• NVDA: 過去 30 天 KOL 提及 7 次，5 次標 bull_high_risk。今日強調「出口管制」是新邊際。
• SIVE: 5/14 KOL 首次提及，今日進前 5。Claude 推論：政策叙事可能高估。
```

組件：

- 用 `•` 起頭
- ticker（粗體）：歷史脈絡 1-2 句
- 如果是 Claude 推論，加 `_[AI 推論]_` 斜體標記

頻率：**每天最多 2 條**，避免淹沒。

### 相關訊號段

```
▎*相關訊號*
• ⚠️ NVDA · Reuters: Q1 earnings beat 12%, raised FY guidance
  _與 KG 中 5/14 看多論點強化_
• SIVE · 公司公告: EU Chips Act 2 補貼名單初稿
• LITE · CNBC: 800G 模塊需求對等
```

⚠️ 表示與 KG 觀點分歧的訊息。

### Footer

```
─────────
📍 分析框架蒸餾自 [analysissite.vercel.app](https://analysissite.vercel.app/)
🧠 Persona v1 · KG 1,247 nodes · 第 87 天
🔗 完整看板：https://analysissite.vercel.app/
```

組件：

- 分隔線（`─` × 9）
- 歸因句（KOL 來源連結）
- 系統狀態：Persona 版本、KG 節點數、運行天數
- 完整看板連結

## 長度策略

| 預算 | Tier 1 | Tier 2 | KG 對照 | 新聞 | 總長度 |
| --- | --- | --- | --- | --- | --- |
| short | 3 檔 | 5 檔 | 0-1 | 2 | ~1500 chars |
| medium | 4 檔 | 8 檔 | 1-2 | 3 | ~2500 chars |
| long | 5 檔 | 10 檔 | 2 | 5 | ~3500 chars |

## 分段策略

如果訊息 > 4000 chars：

```
訊息 1：標題 + Tier 1 + Tier 2          (1/2)
訊息 2：Tier 3 + KG + 新聞 + Footer     (2/2)
```

兩則訊息間隔 1 秒發送。

## 失敗狀態的訊息

爬蟲失敗：

```
📊 *2026-05-29 Serenity 日報* (06:00)

⚠️ [STATUS] 今日爬取異常，沿用 2026-05-28 快照。

（接著用昨日內容組 brief，加註「⚠️ 內容為昨日」）

📍 系統狀態：scraper failed at 06:00:08 (HTTP 503)
🔄 下次將自動重試
```

KG 不可用：

```
📊 *2026-05-29 Serenity 日報* (06:00)

（正常 Tier 1-3 內容）

▎*KOL 對照*
_本日 KG 服務暫時不可用，跳過歷史對照_

（正常新聞 + Footer）
```

## 字符限制

- Telegram 單訊息上限 4096 字元
- 預留 100 字元 buffer（Markdown escape 會增長）
- 實際 hard limit: 3996 chars/segment

## Anti-pattern 檢查

組完 brief，發送前跑一次：

```javascript
const BANNED = [
  /強烈推薦|strong buy/,
  /目標價|target price/,  // KOL 不用
  /翻倍|double/,
  /100%|百分百|肯定|絕對/,
  /必漲|必跌|穩漲|穩跌/
];

if (BANNED.some(re => re.test(brief))) {
  log.warn("anti-pattern detected, rewriting...");
  // 重新組或改寫違規句
}
```

## 例：完整 medium brief

見 `examples/sample-brief.md`。

## 驗收

- [ ] 連續 7 天訊息長度都 < 4000 chars
- [ ] Markdown 渲染在 Telegram 正常顯示（沒有亂掉的 `*` 或 `_`）
- [ ] 每天 Tier 1 都包含 KOL 表達 DNA 至少 2 個詞
- [ ] 每天 Footer 都有歸因句
- [ ] 沒有出現 anti-pattern 詞
- [ ] 系統異常天有 `[STATUS]` 標記
