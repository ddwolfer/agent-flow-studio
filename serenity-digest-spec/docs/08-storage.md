# 08 · 資料儲存版面

## 完整佈局

```
~/Desktop/serenity-digest/              ← 使用者可見區
├── config.json                          ← 不要 commit，用 .gitignore
│
├── data/                                ← Evidence Pool（被動）
│   ├── 2026-05-29.json                  ← 每日 snapshot
│   ├── 2026-05-28.json
│   ├── ...
│   ├── latest.json                      ← 軟連結或複製到今日
│   └── index.jsonl                      ← 每天一行的精簡日誌
│
├── briefs/                              ← Telegram 推送的 markdown 存檔
│   ├── 2026-05-29.md
│   ├── 2026-05-28.md
│   └── UNDELIVERED/                     ← 推送失敗的暫存區
│
├── logs/                                ← 詳細執行記錄
│   ├── 2026-05-29.log
│   └── ...
│
├── raw/                                 ← 原始 HTML（debug 用）
│   ├── 2026-05-29.html
│   └── ...                              ← 30 天後自動清理
│
├── pending-writes/                      ← KG 寫入失敗的等候區
│   └── 2026-05-29.json
│
└── README.md                            ← 給未來自己看的「這套系統怎麼跑」

~/.config/serenity-digest/               ← 系統配置區
├── config.json                          ← bot token、chat_id、預算、時區
├── knowledge.db                         ← KG SQLite
├── knowledge.db-wal                     ← SQLite WAL
└── persona-cache/                       ← SKILL.md 副本（為了 conversation 快速注入）
    └── current.md                       ← 軟連結到 skills/serenity-distill/output/v{N}.md

~/.mcp/knowledge-graph/                  ← KG MCP 安裝位置
├── main.js
├── lib/
├── hooks/
└── ...

~/.claude/                               ← Claude Code 設定
├── settings.json                        ← 含 hooks 設定
└── skills/serenity-digest/              ← 軟連結到 spec 的 skills/serenity-digest
```

## config.json

```json
{
  "$schema": "config-v1",
  "timezone": "Asia/Taipei",
  "telegram": {
    "bot_token": "PLACEHOLDER_REPLACE_ME",
    "chat_id": "PLACEHOLDER_REPLACE_ME"
  },
  "depth_preference": "medium",
  "schedule": {
    "daily_brief":      "0 6 * * *",
    "weekly_reflect":   "0 21 * * 0",
    "monthly_calibrate":"0 12 1 * *",
    "quarterly_distill":"0 14 1 */3 *"
  },
  "scraping": {
    "url":      "https://analysissite.vercel.app/",
    "user_agent":"SerenityDigest/1.0 (personal-digest; +mailto:910063@gmail.com)",
    "retry_count": 1,
    "retry_delay_seconds": 60
  },
  "retention": {
    "snapshots_keep_forever": true,
    "raw_html_keep_days": 30,
    "logs_keep_days": 90,
    "briefs_keep_forever": true
  },
  "kg": {
    "db_path": "~/.config/serenity-digest/knowledge.db",
    "max_writes_per_day": 20,
    "max_edges_per_day": 30,
    "soft_node_cap": 10000
  },
  "alerts": {
    "scraper_fail_threshold_days": 3,
    "telegram_fail_threshold_days": 2,
    "persona_drift_threshold_percent": 30
  }
}
```

## index.jsonl 規格

每天 brief 跑完追加一行：

```jsonl
{"date":"2026-05-29","topTickers":["NVDA","SIVE","LITE","IREN"],"activeSignals":445,"coverage":703,"writes":{"nodes":8,"edges":12},"briefLength":2456,"status":"ok","duration_seconds":32}
{"date":"2026-05-28","topTickers":["NVDA","SIVE","LITE"],"activeSignals":439,"coverage":701,"writes":{"nodes":7,"edges":9},"briefLength":2387,"status":"ok","duration_seconds":29}
```

用 jq 快速查詢：

```bash
# 最近 7 天執行狀態
tail -7 ~/Desktop/serenity-digest/data/index.jsonl | jq -c '{date, status, duration_seconds}'

# 最近 30 天哪些 ticker 上過 top
tail -30 index.jsonl | jq -r '.topTickers[]' | sort | uniq -c | sort -rn

# 平均 brief 長度
tail -30 index.jsonl | jq '.briefLength' | awk '{s+=$1; n++} END{print s/n}'
```

## snapshot JSON 規格

每天 `data/YYYY-MM-DD.json` 結構見 `docs/01-scraping.md` 的「解析輸出格式」段。

範例完整檔見 `examples/sample-snapshot.json`。

## brief markdown 規格

每天 `briefs/YYYY-MM-DD.md` = 實際推到 Telegram 的內容（純 markdown，未做 URL encode）。

開頭加 frontmatter：

```yaml
---
date: 2026-05-29
sent_at: 2026-05-29T06:00:28+08:00
chat_id: redacted
persona_version: v1
length: 2456
delivered: true
---

📊 *2026-05-29 Serenity 日報* (06:00 台北)
...
```

## log 規格

每天 `logs/YYYY-MM-DD.log`，純文字，格式 = ISO timestamp + level + message：

```
2026-05-29T06:00:00+08:00 [INFO] daily-brief start
2026-05-29T06:00:02+08:00 [INFO] persona loaded: v1 (skill md path: ...)
2026-05-29T06:00:03+08:00 [INFO] scrape start: https://analysissite.vercel.app/
2026-05-29T06:00:08+08:00 [INFO] scrape success: HTTP 200, content 12453 chars
2026-05-29T06:00:08+08:00 [INFO] parsed: 4 priorityQueue, 10 hotStocks, 14 feedItems
2026-05-29T06:00:09+08:00 [INFO] snapshot saved: data/2026-05-29.json (4382 bytes)
2026-05-29T06:00:10+08:00 [INFO] diff vs 2026-05-28: newInTop10=[MRVL], dropped=[COHR], movers=[NVDA:+5,SIVE:+18]
2026-05-29T06:00:10+08:00 [INFO] kg retrieval: NVDA(5 nodes), SIVE(3), LITE(4), IREN(2)
2026-05-29T06:00:13+08:00 [INFO] news scoring: 14 items → top 3 selected (avg score 78.3)
2026-05-29T06:00:15+08:00 [INFO] brief composed: 2456 chars, persona DNA marker count 7
2026-05-29T06:00:22+08:00 [INFO] telegram send: 200 OK, message_id 4582
2026-05-29T06:00:25+08:00 [INFO] kg writes: 8 nodes (NVDA principle ×3, SIVE principle ×2, MRVL principle ×1, claude inference ×2), 12 edges
2026-05-29T06:00:35+08:00 [INFO] daily-brief complete: 32 seconds
```

## 保留策略

| 類別 | 預設保留 | 上限 |
| --- | --- | --- |
| `data/*.json` | 永久 | 無 |
| `briefs/*.md` | 永久 | 無 |
| `logs/*.log` | 90 天 | 自動刪 90+ |
| `raw/*.html` | 30 天 | 自動刪 30+ |
| `pending-writes/*.json` | 寫入成功後刪 | 一週未消化 → alert |

一年的容量估算：

- snapshots: 365 × 5KB = 1.8MB
- briefs: 365 × 3KB = 1.1MB
- logs (90天上限): 90 × 5KB = 450KB
- 共 ~3.5MB

很省。

## 備份建議

最重要的兩個位置：

1. `~/.config/serenity-digest/knowledge.db` — KG 主檔
2. `~/Desktop/serenity-digest/data/` — 證據池

把這兩個放進 iCloud Drive / Dropbox / git annex / restic 都行。

不需要備份：

- `raw/`（爬蟲下次能再抓）
- `logs/`（可隨時重建）

## 安全注意

- `config.json` 內含 telegram bot token，**絕對不要 commit 進 git**
- `.gitignore` 必須包含：

  ```
  config.json
  *.db
  *.db-wal
  *.db-shm
  raw/
  ```

- 推送目標 chat_id 是私人 DM，不要設定到公開頻道
