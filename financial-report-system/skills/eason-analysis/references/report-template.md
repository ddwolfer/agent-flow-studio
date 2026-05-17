# Eason 分析報告輸出模板

## 報告格式

```
══════════════════════════════════════════════════
  EASON 視角：台股 AI 戰情室
  {YYYY-MM-DD}
══════════════════════════════════════════════════

## 一、Eason 最新觀點（from 影片）

> 影片：{title}（{date}）
> 核心立場：{stance}（{stance_score}/+5）
> 語氣強度：{tone_intensity}/10

**核心論述**：
{transcript_summary}

**邏輯鏈**：
{logic_chain}

---

## 二、Eason 指標儀表板

| 指標 | 當前值 | Eason 判讀 | 信號 |
|------|--------|-----------|------|
| 加權指數 vs 季線 | {value} | 季線{上/下} = {多/空} | 🟢/🔴 |
| 加權指數 vs 月線 | {value} | 月線{上/下} | 🟢/🔴 |
| 外資淨空單 | {value}口 | {增/減} = {避險/回補} | 🟢/🟡/🔴 |
| 成交量 | {value}億 | {量增/量縮} | 🟢/🟡 |
| 美光(MU) vs 月線 | ${value} | 月線{撐/破} = 記憶體{可買/觀望} | 🟢/🔴 |
| 櫃買指數 | {value} | {創高/回落} | 🟢/🟡 |
| 布蘭特原油 | ${value} | {<100正常 / 100-120警戒 / >120危險} | 🟢/🟡/🔴 |
| 歸離率(月) | {value}% | {<10正常 / 10-15偏高 / >15過熱} | 🟢/🟡/🔴 |

**綜合信號**：{BULLISH/NEUTRAL/BEARISH}
**Eason 會說**：「{用 Eason 風格的一句話總結}」

---

## 三、AI 族群快掃

| 族群 | 代表股 | 今日表現 | Eason 態度 | 備註 |
|------|--------|---------|-----------|------|
| 記憶體 | 南亞科/華邦電/晶豪科 | {%} | {看法} | {美光狀態} |
| 散熱 | 雙鴻/奇鋐 | {%} | {看法} | |
| 設備 | 萬潤/弘碩 | {%} | {看法} | |
| PCB | 金像電/華通/聯茂 | {%} | {看法} | |
| CPO | 上詮/波若威/華星光 | {%} | {看法} | |
| 封測 | 齊邦/日月光 | {%} | {看法} | |

### Eason 避雷區
| 類別 | 代表 | 今日表現 | 避雷原因 |
|------|------|---------|---------|
| 權值股 | 鴻海 | {%} | 外資提款 |
| 航運 | 陽明/萬海 | {%} | 高油價=高成本 |
| 美債ETF | 00679B等 | {%} | 不降息無利多 |

---

## 四、偏誤檢查 & 平衡觀點

### Eason 可能的偏誤
- [ ] **Home bias**：{是否過度強調台股優勢？其他市場表現如何？}
- [ ] **Confirmation bias**：{是否只引用支持多頭的數據？有哪些利空被忽略？}
- [ ] **Survivorship bias**：{只展示成功案例？有沒有失敗的推薦？}

### 反面論點（Druckenmiller/Damodaran 視角）
- **Druckenmiller**：{宏觀趨勢是否真的支持？流動性條件？}
- **Damodaran**：{估值是否合理？ERP 狀態？}

### Eason 忽略的風險
{列出 Eason 可能忽略的風險因素}

---

## 五、操作建議摘要

**Eason 的建議**：
{action_advice}

**建議的修正**（考慮偏誤後）：
{adjusted_advice}

**關鍵價位**：
- 加權支撐：{季線位置}
- 加權壓力：{前高位置}
- 美光觀察：${MU 月線位置}

---

## 六、數據來源
{列出所有引用的 MCP 數據源}

══════════════════════════════════════════════════
```

## SQLite 儲存

報告產出後存入 `eason_daily` 表（如尚未建立則先建立）：
```sql
CREATE TABLE IF NOT EXISTS eason_daily (
  id INTEGER PRIMARY KEY,
  timestamp TEXT DEFAULT (datetime('now')),
  date TEXT,
  pillar_seasonal TEXT,
  pillar_chip TEXT,
  pillar_micron TEXT,
  pillar_otc TEXT,
  overall_signal TEXT,
  confidence REAL,
  bias_flags TEXT,
  key_levels TEXT,
  eason_latest_view TEXT,
  report TEXT
);
```
