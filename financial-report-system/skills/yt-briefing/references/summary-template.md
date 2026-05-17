# YT Briefing Summary Output Template

## Per-Video Template

```markdown
---
### 🎬 {Video Title}
**頻道**: {Channel Name} ({@handle})
**日期**: {Upload Date} | **時長**: {Duration} | **觀看**: {View Count}
**影片連結**: https://www.youtube.com/watch?v={video_id}

---

#### 🎯 核心論述 (Core Thesis)
> {1-3 sentences capturing the main argument in Traditional Chinese}

**前提假設**: {The key assumption underlying the thesis}
**邏輯鏈**: {A → B → C → Conclusion}
**主持人信心**: {高/中/低 + 原因}

---

#### 📊 引用數據 (Data References)

| 指標 | 引用數值 | 引用期間 | 來源 | 目前實際值 | 差異 | 品質 |
|------|---------|---------|------|-----------|------|------|
| {indicator} | {cited value} | {period} | {source} | {actual or N/A} | {discrepancy or ✓} | {✅/⚠️/ℹ️} |
| ... | ... | ... | ... | ... | ... | ... |

**數據品質總評**: {overall data quality assessment}

---

#### 📈 市場觀點 (Market Views)

| 標的 | 方向 | 強度 | 時間框架 | 關鍵價位 | 催化劑 | 風險 |
|------|------|------|---------|---------|--------|------|
| {target} | {Bull/Bear/Neutral} | {Strong/Mild} | {Short/Med/Long} | {levels} | {catalyst} | {risk} |
| ... | ... | ... | ... | ... | ... | ... |

---

#### 💡 重點摘要 (Key Points)
1. {Key point 1 — most important takeaway}
2. {Key point 2}
3. {Key point 3}
4. {Key point 4}
5. {Key point 5}

---

#### 🔮 預測追蹤 (Predictions)

| 預測內容 | 目標日期/條件 | 信心度 | 驗證指標 | 狀態 |
|---------|-------------|--------|---------|------|
| {prediction} | {when} | {高/中/低} | {what to check} | {Pending} |

---

#### 🔄 與前期觀點比較 (Stance Changes)
{Compare with previous video(s) from same channel stored in SQLite}
- **上期觀點**: {previous stance}
- **本期觀點**: {current stance}
- **變化**: {Unchanged / Shifted bullish / Shifted bearish / Reversed}
- **原因**: {Why the change, if any}

---

#### ⚠️ 偏誤檢查 (Bias Check)
| 偏誤類型 | 偵測 | 說明 |
|---------|------|------|
| 確認偏誤 | {✓/✗} | {explanation if detected} |
| 近因偏誤 | {✓/✗} | {explanation if detected} |
| 錨定效應 | {✓/✗} | {explanation if detected} |
| 敘事謬誤 | {✓/✗} | {explanation if detected} |

**整體品質**: {★★★★★ rating with brief justification}

---

#### ✅ 待驗證項目 (To Verify)
- [ ] {Claim 1 to cross-check against actual data}
- [ ] {Claim 2 to cross-check}
- [ ] {Claim 3 to cross-check}
```

## Multi-Video Comparative Template (when processing both channels)

```markdown
## 📺 YT Briefing 雙頻道摘要 — {date}

### 觀點比較矩陣

| 議題 | 游庭皓 | 張貽程 | 共識？ |
|------|--------|--------|--------|
| {topic 1} | {view} | {view} | {Yes/No/Partial} |
| {topic 2} | {view} | {view} | {Yes/No/Partial} |
| ... | ... | ... | ... |

### 共識觀點 (Where Both Agree)
1. {Consensus point 1}
2. {Consensus point 2}

### 分歧觀點 (Where They Disagree)
1. {Divergence point 1}: 游庭皓認為{X}, 張貽程認為{Y}
2. {Divergence point 2}

### 綜合判讀
{2-3 paragraphs synthesizing both channels' views, noting where total economic (游庭皓) meets market structure (張貽程)}

### 建議後續動作
1. {Action item based on combined insights}
2. {Data to monitor}
3. {Risk to watch}
```
