# finance-workflows

> 中文版(主文件):[README.md](README.md)

Personal daily financial reports + monitoring + content publishing. The core
is a lean Python workflow runner orchestrating `claude -p` + a small set of
local MCP servers, plus two sibling systems: a deterministic arbitrage
monitor (arb-sentinel) and a Binance Square daily-posting pipeline. Reports
land as HTML/PDF on disk and ship to a private Telegram supergroup (one
forum topic per workflow).

> The repo name `agent-flow-studio` is historical — the active codebase is
> `finance-workflows/`. Project rules in `CLAUDE.md`, runner rules in
> `finance-workflows/CLAUDE.md`.

## Layout

| Path | Purpose |
|---|---|
| `finance-workflows/` | runner, MCP servers, workflows, prompts, tests |
| `arb-sentinel/` | exchange arbitrage/rate monitor — deterministic Python, no LLM, launchd |
| `mcp/knowledge-graph/` | local long-term memory (SQLite + sqlite-vec + FTS5) |
| `docs/superpowers/{specs,plans}/` | full design & implementation history |
| `.claude/skills/` | interactive skills (`/deep-research-stock`, `/finance-loop`) |

## Schedules (as of 2026-07)

### launchd (headless, `claude -p` on the credit pool)

| Workflow | Schedule (TPE) | What it does |
|---|---|---|
| `serenity-digest` | daily 06:00 | KOL distillation + KG memory |
| `morning-briefing` | daily 07:00 | cross-asset pre-market brief (tape + Five Things + TW open; pre-fetches Binance funding / CBOE VIX / Treasury auctions / stablecoins / TWSE institutional flows) |
| `crypto-daily` | daily 07:30 | crypto news/social digest |
| `us-macro` | Mon–Fri 09:30 | Fed / growth / inflation brief (FRED + Yahoo + Fed RSS) |
| `eason-tw-stock` | (paused) | TW-stock analyst transcripts |

### arb-sentinel (launchd, zero LLM)

monitor / rates / digest / announcements jobs are live; carry-guardian
(Bitget loan-position monitoring) was retired when the USDGO subsidy ended.
Alerts go to a Telegram topic, each labelled with the exchange.

### Interactive (subscription pool — the post-2026-06-15 billing split)

| Item | Trigger | What it does |
|---|---|---|
| `/deep-research-stock T1 T2 ...` | manual | custom-watchlist deep research: Tier A (7 layers + 10-K + SMC §8) / Tier B (compact); auto PDF + Telegram |
| binance-square daily | in-session cron 10:43 | generates 3 post candidates (personas A/B/C) → pick in-chat → auto-publish via official API + publish log |

> **Why two pools:** since 2026-06-15, `claude -p` bills against a separate
> credit pool while interactive sessions stay on the subscription. Heavy /
> judgment-requiring flows moved interactive; light dailies stayed on launchd.

## Core modules

- **SMC price-zone engine** `finance-workflows/scripts/compute_zones.py`:
  deterministic daily-timeframe Smart Money Concepts structure (BOS/CHoCH,
  FVG, liquidity pools, premium/discount, buy/sell reference zones +
  invalidation). Works for stocks and crypto (yfinance). The LLM only
  narrates the JSON — it never computes.
  Spec: `docs/superpowers/specs/2026-07-08-price-zone-design.md`
- **Square publishing API**: Binance creator-center official API
  (`X-Square-OpenAPI-Key`), 100 posts/day. Publish log at
  `reports/binance-square/_published.jsonl` — every "as I said before"
  self-reference must verify against the log
- **Telegram**: shared supergroup + per-workflow forum topics; topic IDs in
  `finance-workflows/.env` (gitignored)

## Run a workflow manually

```bash
cd finance-workflows
mcp/.venv/bin/python run-workflow.py <name>
```

## Tests

```bash
cd finance-workflows && mcp/.venv/bin/pytest tests/ -v
cd arb-sentinel && .venv/bin/pytest tests/ -v
```

## License

Private personal use.
