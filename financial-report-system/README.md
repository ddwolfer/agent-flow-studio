# Financial Report System

每日自動產出三份報告，推送到 Discord + LINE：

| 報告 | 排程 | 內容 |
|---|---|---|
| 個股新聞日報 | 每天 08:00 | 持倉 + 觀察名單個股當日新聞（WebSearch + 過濾） |
| 總經 × 台股戰情室 briefing | 平日 09:30 | 游庭皓總經觀點 + Eason 前日台股觀點 + 即時數據 |
| Eason 視角晚間報告 | 平日 20:00 | Eason 當日影片逐字稿萃取 + TWSE/Yahoo 即時數據 + 推薦股票入庫 |

---

## 系統架構（一句話）

`cron → bash 腳本 → claude -p（Claude Code CLI 帶 MCP 工具）→ HTML → Chrome headless 轉 PDF → Discord webhook + LINE Messaging API`

詳細請見 `skills/system-architecture.md`。

---

## 資料夾結構

```
financial-report-system/
├── README.md                ← 你正在看這個
├── crontab.example          ← cron 排程範例
├── scripts/                 ← 4 個 cron 腳本
│   ├── eason-daily.sh
│   ├── daily-briefing.sh
│   ├── stock-news-daily.sh
│   ├── stock-daily-news.sh
│   ├── notify.sh            ← Discord/LINE 推送共用 helper
│   └── .env.example         ← 所有需要的環境變數
├── skills/                  ← Claude Code skills（分析邏輯）
│   ├── eason-analysis/      ← 主力：Eason 視角分析
│   ├── yt-briefing/         ← YouTube 影片摘要
│   ├── macro-analysis/      ← 總經分析
│   ├── data-snapshot/       ← 即時數據快照
│   ├── market-scan/         ← 市場掃描
│   ├── generate-report/     ← HTML/PDF 報告產出
│   ├── data-query/          ← SQLite 歷史查詢
│   ├── cross-check/         ← 觀點交叉驗證
│   ├── deep-research/       ← 深度研究
│   ├── web-research/        ← 網路搜尋
│   ├── generate-pptx/       ← PPT 產出
│   ├── generate-docx/       ← Word 產出
│   └── system-architecture.md
├── db/
│   └── schema.sql           ← SQLite schema（不含個資表）
└── samples/                 ← 範例輸出
    ├── eason-sample.html    ← Eason 視角報告
    └── briefing-sample.html ← 早上 briefing 報告
```

---

## 系統依賴

- **OS**：WSL2 Ubuntu 24.04（理論上任何 Linux 都行）
- **Claude Code CLI**：`npm i -g @anthropic-ai/claude-code`，需要 Anthropic API key 或 Claude.ai 訂閱
- **MCP servers**（在 Claude Code config 內設定）：
  - `mcp__twse` — TWSE 開放資料 API
  - `mcp__yahoo-finance` — Yahoo Finance
  - `mcp__yt-dlp` — YouTube 影片 metadata + 字幕下載
  - `mcp__sqlite` — SQLite 讀寫
  - `mcp__fred` — FRED 經濟數據
  - `mcp__chart` — AntV 圖表生成
- **Chrome headless**：HTML → PDF / HTML → 截圖（`google-chrome`）
- **Python 3 + Pillow + numpy**：截圖切割（`apt install python3-pil python3-numpy`）
- **curl**：呼叫 Discord webhook / LINE API
- **SQLite 3**：本地資料庫

---

## 設置流程

```bash
# 1. clone / unzip 到任一目錄
cp -r financial-report-system /opt/  # 例

# 2. 填環境變數
cp scripts/.env.example scripts/.env
$EDITOR scripts/.env  # 填入 Discord webhook / LINE token / freeimage key

# 3. 建立 SQLite DB
mkdir -p data
sqlite3 data/financial.db < db/schema.sql

# 4. 安裝 Claude Code + 設定 MCP servers
npm i -g @anthropic-ai/claude-code
claude  # 第一次跑會引導登入

# 5. 把 skills 複製到 Claude Code 能找到的地方
cp -r skills /your-claude-config/.claude/skills/

# 6. 測試一條腳本（不丟到 cron）
bash scripts/stock-news-daily.sh

# 7. 確認 Discord 收到後，再加 cron
crontab -e   # 把 crontab.example 內容貼進去
```

---

## 已知問題 / 想要強化的點

請朋友看以下幾個方向，由急到緩：

### A. Bug / 數據驗證
1. **日期推論錯誤**（高頻發生）：報告產出邏輯依賴 LLM 推理「今天/明天/後天 對應星期幾」，常推錯（最近一次 2026-04-29 把 4/30 標成週三 + 勞動節，實際 4/30 是週四，5/1 才是勞動節）。**解法方向**：cron 腳本先算好行事曆事實塞進 prompt，不要讓 LLM 自己推。
2. **TWSE 數據新鮮度**：cron 8pm 跑時偶有 TWSE 當日 close 還沒更新，會用前一日數據但標籤標今日。應該驗證 TWSE 最新日期 = 今日才往下走，不一致就 retry / fallback。
3. **舊聞混入**：sentiment / 新聞段常抓到一週前甚至兩個月前的舊聞當當期數據（已寫硬規則進 prompt 但 LLM 仍偶犯）。

### B. 結構 / 維運
4. **路徑全部硬編 `/mnt/c/FINANCIAL`**：搬機器要改一堆地方，建議抽 `FIN_ROOT` env。
5. **錯誤處理薄**：claude -p 失敗時 cron 會傳「報告已產出」之類 fallback，使用者收不到 alert。應該推 error 通知到另一個 Discord 頻道。
6. **重試/idempotency**：cron 沒跑成功、或 Discord 推失敗，沒辦法重推；只能手動。
7. **prompt 都寫死在 bash heredoc 裡**：難 review 難測試。建議拉到獨立 prompt 檔。

### C. 加值方向（非必要）
8. **報告品質評分**：現在沒有自動 QA，靠使用者眼力 catch 錯誤。可加一個 LLM-as-judge 對 HTML 內容跑事實檢查。
9. **picks 持續追蹤**：`eason_picks` 表有 entry / close 欄位但沒有 cron 自動更新報酬率，每筆都要手動 close。可加 daily 補價。
10. **多分析師擴充**：目前只有 Eason + 游庭皓兩位。架構是 hardcode 的，加第三位要改不少程式。

---

## 安全 / 隱私

- 所有 token / webhook / 個人 ID 已從原 codebase 抽到 `.env`，**這份打包不含真實值**。
- DB schema 不含個人交易紀錄表（`tw_stock_trades`），那張表只在原機器上。
- 樣本報告（`samples/`）是市場分析內容，不含持倉 / 損益。

---

## 聯絡

報告產出邏輯由原作者 + Claude Code 共寫。如朋友需要原始 prompt 設計脈絡或想討論 trade-off，可以直接問。
