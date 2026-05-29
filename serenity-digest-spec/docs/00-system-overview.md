# 00 · 系統概觀

## 目標

每天清晨 06:00（台灣時間），自動產出一份 200-500 字的 Telegram 投研日報，內容濃縮 [analysissite.vercel.app](https://analysissite.vercel.app/) 的當日重點，並隨時間累積對該 KOL 思維框架的長期記憶。

目標不只是「轉述」，而是達成三件事：

1. **濃縮**：把該 KOL 的當日輸出壓縮成 5 分鐘可掃完的 brief。
2. **連結**：把今日訊號與歷史觀點對照（昨日變化、預測兌現、反例累積）。
3. **蒸餾**：長期累積成可獨立運作的「KOL 認知 OS + Claude 修正本」，即便原站停更也能繼續產出分析。

## 為什麼分三層

把系統拆成 Persona / Memory / Automation 三層，是為了讓**身份穩定性**、**經驗累積**、**執行頻率**三個正交的關注點各自演化、互不干擾。

```
┌─────────────────────────────────────────────────────┐
│ Persona Layer                                        │
│ ─────────────                                        │
│ serenity-perspective.md (nuwa 蒸餾產出)              │
│   ▸ 心智模型 (mental models)                          │
│   ▸ 決策啟發 (decision heuristics)                    │
│   ▸ 表達 DNA (vocabulary, rhythm, tonal markers)      │
│   ▸ 反模式 (anti-patterns, what KOL never says)       │
│   ▸ 誠實邊界 (acknowledged limits)                    │
│                                                      │
│ 每次 conversation 開頭注入。每季重新蒸餾一次。         │
└─────────────────────────────────────────────────────┘
                       ▲
                       │ informs
                       │
┌─────────────────────────────────────────────────────┐
│ Memory Layer                                         │
│ ────────────                                         │
│ knowledgeGraph MCP (SQLite + sqlite-vec + FTS5)      │
│   ▸ principle 節點 (KOL 原話片段，必含 quote)         │
│   ▸ pattern 節點 (觀察到的規律)                       │
│   ▸ inference 節點 (Claude 推論，永遠標記為推論)      │
│   ▸ 11 種 edge type                                   │
│   ▸ FSRS 衰減 + Benna-Fusi 4-level cascade            │
│                                                      │
│ auto-recall hook 在每次推理前注入相關記憶。            │
│ auto-capture hook 在推理後寫入新觀點。                 │
└─────────────────────────────────────────────────────┘
                       ▲
                       │ called by
                       │
┌─────────────────────────────────────────────────────┐
│ Automation Layer                                     │
│ ────────────────                                     │
│ Cowork 排程任務                                       │
│   ▸ 每天 06:00 台灣 → 主流程 (daily-brief)            │
│   ▸ 每週日 21:00 台灣 → 反思 (weekly-reflection)      │
│   ▸ 每季首日 → 重蒸餾 (re-distillation)              │
│                                                      │
│ 失敗自動 retry 一次，仍失敗則寫 log 並標記 brief。     │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Evidence Pool (被動)                                  │
│ ───────────────                                       │
│ ~/Desktop/serenity-digest/data/YYYY-MM-DD.json        │
│                                                       │
│ 純檔案、append-only、KG 暫不主動引用。                  │
│ 未來升 E 時節點 metadata.evidence_refs 啟用。           │
└─────────────────────────────────────────────────────┘
```

## 為什麼這樣設計

### 為什麼 Persona 單獨一層

每次 Claude 啟動時都從零開始。如果 KOL 的思維框架只存在 KG 裡，每次都要 retrieval 重新拼湊，**穩定性差且消耗 token**。

把它凝結成靜態的 `SKILL.md`，每次直接 inject 到 context，等同 prior。KG 變成「增量更新」而不是「主體承載」。

### 為什麼 Memory 用 KG 而不是 JSON

JSON 適合「事實」，KG 適合「知識」。

事實之間是並列的，知識之間有因果、推進、反駁、修正。當你想問「為什麼 NVDA 現在被列為高風險偏多」，KG 能往回追三步：

```
NVDA 高風險偏多 [principle, 2026-05-27]
  ▸ reason_for ← 出口管制風險 [principle, 2026-05-14]
  ▸ aligns_to  ← 半導體高關注度 + 估值收窄通用模式 [pattern, 2026-04-02]
  ▸ refined_by ← 800VDC 功率半導體線索 [inference, 2026-05-27]
```

JSON 做不到這種推導。

### 為什麼 Evidence Pool 被動

把「資料」和「知識」分開：

- KG = 經過思考、有語義關係、會衰減、會 consolidate 的知識
- Evidence Pool = 原始事實，不思考、不衰減、append-only

KG 保持純淨（不被噪聲淹沒），Evidence Pool 保持完整（不會因為衰減丟失原始證據）。

未來想升 E（KG 引用 evidence），只要在節點 metadata 加 `evidence_refs: ["news_2026-05-27_1234"]`。第一階段不啟用引用機制，節省複雜度。

## 不在這層做的事

- **價量分析**：用現成的 yfinance / TradingView 工具，不重造輪子。
- **新聞抓取**：原站已經做了，我們只用它的輸出，不另外接 GDELT / Finnhub。
- **多語言**：先做中文。原站是中文，Telegram brief 也是中文。
- **多 KOL**：先 focus Serenity。架構支援未來擴增（KG 的 `source` 標籤）。

## 名詞約定

- **KOL** = 原站作者，代號 Serenity
- **Brief** = 每日 Telegram 推播訊息
- **Snapshot** = 一天的爬蟲輸出 JSON
- **SKILL.md** = nuwa 蒸餾出的 Persona 檔
- **KG** = knowledgeGraph MCP 持有的 SQLite 知識圖
- **Evidence Pool** = 每日 JSON 累積的歷史檔案池
