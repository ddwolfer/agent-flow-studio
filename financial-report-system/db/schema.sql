-- Financial Report System — SQLite Schema
-- DB path in production: /mnt/c/FINANCIAL/data/financial.db
-- Tables touched by the daily report pipeline only.
-- Personal trade history table (tw_stock_trades) is intentionally excluded.

-- =========================================================
-- 1. Eason 訓練樣本（每月新增的影片標註樣本）
-- =========================================================
CREATE TABLE eason_training (
  id                   INTEGER PRIMARY KEY,
  video_id             TEXT,
  video_date           TEXT,
  video_title          TEXT,
  video_url            TEXT,
  month_batch          TEXT,
  taiex_change_pct     REAL,
  taiex_volume         REAL,
  stance               TEXT,           -- 看多 / 看空 / 中性 / 謹慎看多
  stance_score         INTEGER,        -- -5 ~ +5
  indicators_mentioned TEXT,           -- JSON array
  sectors_mentioned    TEXT,           -- JSON array
  stocks_mentioned     TEXT,           -- JSON array
  logic_chain          TEXT,           -- JSON / 結構化推理
  predictions          TEXT,           -- JSON
  action_advice        TEXT,
  risk_warnings        TEXT,
  tone_intensity       INTEGER,        -- 1 ~ 10
  transcript_summary   TEXT,
  raw_transcript       TEXT,
  created_at           TEXT DEFAULT (datetime('now'))
);

-- =========================================================
-- 2. Eason 每日觀點存檔（cron 每天寫入）
-- =========================================================
CREATE TABLE eason_daily (
  id                INTEGER PRIMARY KEY,
  timestamp         TEXT DEFAULT (datetime('now')),
  date              TEXT,
  pillar_seasonal   TEXT,           -- 四大支柱觀點：季節性
  pillar_chip       TEXT,           --              籌碼面
  pillar_micron     TEXT,           --              個股微觀
  pillar_otc        TEXT,           --              OTC / 中小型
  overall_signal    TEXT,           -- BULLISH / NEUTRAL / BEARISH
  confidence        REAL,           -- 0~10
  bias_flags        TEXT,           -- JSON array of detected biases
  key_levels        TEXT,           -- JSON
  eason_latest_view TEXT,           -- 完整段落引用
  report            TEXT            -- 完整 markdown / html 內容（可選）
);

-- =========================================================
-- 3. Eason 推薦個股紀錄（從每日報告萃取）
-- =========================================================
CREATE TABLE eason_picks (
  id               INTEGER PRIMARY KEY,
  pick_date        TEXT NOT NULL,
  ticker           TEXT NOT NULL,
  name             TEXT NOT NULL,
  entry_price      REAL,
  category         TEXT,           -- 散熱 / CPO / 記憶體 / ASIC / 被動元件 / 設備 / AI伺服器 / 金融 / 其他
  signal_type      TEXT,           -- 新推 / 抗跌觀察
  confidence       TEXT,           -- 強 / 中 / 弱
  reason_industry  TEXT,
  reason_technical TEXT,
  reason_chips     TEXT,
  reason_summary   TEXT,           -- ≤50 字
  source           TEXT,           -- 'Eason daily YYYY-MM-DD'
  status           TEXT DEFAULT 'active',   -- active / closed
  close_date       TEXT,
  close_price      REAL,
  close_reason     TEXT,           -- 'Eason 出場' / '停損' / 'manual'
  return_pct       REAL,
  user_notes       TEXT,
  created_at       TEXT DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- 4. 觀察名單（持倉 + 興趣股，stock-news cron 讀這張表）
-- =========================================================
CREATE TABLE stock_watchlist (
  id           INTEGER PRIMARY KEY,
  ticker       TEXT NOT NULL,
  name         TEXT NOT NULL,
  market       TEXT DEFAULT 'TW',     -- TW / US / HK
  added_date   TEXT NOT NULL,
  removed_date TEXT,
  active       INTEGER DEFAULT 1,
  notes        TEXT
);

-- =========================================================
-- 5. 個股新聞日報（含風險評估）
-- =========================================================
CREATE TABLE stock_daily_news (
  id           INTEGER PRIMARY KEY,
  ticker       TEXT NOT NULL,
  date         TEXT NOT NULL,
  headline     TEXT NOT NULL,
  source       TEXT,
  url          TEXT,
  risk_level   TEXT,           -- LOW / MEDIUM / HIGH / CRITICAL
  risk_summary TEXT,
  sentiment    TEXT,           -- POSITIVE / NEUTRAL / NEGATIVE
  created_at   TEXT DEFAULT (datetime('now'))
);

-- =========================================================
-- 6. 個股新聞日報 metadata（每日一筆）
-- =========================================================
CREATE TABLE stock_daily_report (
  id              INTEGER PRIMARY KEY,
  date            TEXT NOT NULL,
  report_path     TEXT,
  tickers_covered TEXT,           -- JSON array
  created_at      TEXT DEFAULT (datetime('now'))
);

-- 建議索引
CREATE INDEX idx_eason_daily_date ON eason_daily(date);
CREATE INDEX idx_eason_picks_date_ticker ON eason_picks(pick_date, ticker);
CREATE INDEX idx_eason_picks_status ON eason_picks(status);
CREATE INDEX idx_stock_news_date_ticker ON stock_daily_news(date, ticker);
CREATE INDEX idx_watchlist_active ON stock_watchlist(active);
