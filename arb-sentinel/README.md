# arb-sentinel

Personal crypto **Earn / borrow / promo radar** across OKX, Binance, and Bitget.

For each opportunity it computes a **net interest-rate spread** (lend APR minus
the cheapest cross-exchange borrow cost, or own-funds) plus a **time-window
check**, grades it, and fires **graded Telegram alerts** — all from a
**deterministic Python process on macOS launchd**. It never runs `claude -p` on
a schedule. The only LLM use is announcement parsing (M3), which calls **Groq**
(off both Claude pools) and only on un-seen announcements.

Design plan: `../docs/superpowers/plans/2026-06-16-arb-sentinel.md`

## Architecture

```
launchd → python -m arb_sentinel --task <kind>
  collectors/ (okx, binance, bitget, announcements)   ← never raise
      → normalize to Opportunity
      → engine: net_spread + time_flag + estimate_yield + classify
      → state.json dedup (renotify-delta + tier-upgrade)
      → notify (Telegram, HTML, topic, 1 msg/s)
```

Grades (spec §5.4): 🔴 `ACT_NOW` (net ≥ high, timing OK, no directional risk) ·
🟠 `GOOD` (net ≥ mid) · 🟡 `WATCH` (directional risk / tight timing / modest net,
batched) · ⚫ `LOG_ONLY`. Directional risk and tight timing **cap at WATCH**.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env     # fill in credentials (see below)
```

`.env` keys: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_TOPIC_ARB`
(forum topic id); read-only `BINANCE_API_KEY/SECRET`,
`BITGET_API_KEY/SECRET/PASSPHRASE`; `GROQ_API_KEY` (announcement parsing).
**Exchange keys must be read-only — never enable trade/withdraw/transfer.**

## CLI tasks

```bash
.venv/bin/python -m arb_sentinel --task <task>
```

| task | what it does | needs |
|---|---|---|
| `test` | post a wiring test to the Telegram topic | TG creds |
| `rates` | pull flexible-earn APR (3 exchanges), grade, alert actionable, dedup | TG; exchange keys for Binance/Bitget |
| `digest` | post a grouped baseline-rate summary (all exchanges) | TG + keys |
| `announcements` | pull Bitget announcements, Groq-extract NEW promos, alert actionable | TG + GROQ |
| `depeg` | alert when a tracked stablecoin pair deviates > `depeg_bps` from 1.0 | TG |
| `exits` | check `active_positions` for the 4 exit triggers (spec §7) | TG + keys |
| `monitor` | `depeg` + `exits` combined | TG + keys |

Register a position so exit detection watches it:

```bash
.venv/bin/python scripts/add-position.py '{"exchange":"bitget","asset":"USDGO",
  "entry_date":"2026-06-01","min_hold_until":"2026-06-15",
  "activity_end_date":"2026-06-16","entry_price":1.0003,"entry_apr":0.12,"ref_amount":30000}'
```

## Scheduling (macOS launchd)

`StartCalendarInterval` jobs (sleep-tolerant: run once on next wake). Install:

```bash
cp launchd/com.arbsentinel.*.plist ~/Library/LaunchAgents/
for j in rates digest announcements monitor; do
  launchctl unload ~/Library/LaunchAgents/com.arbsentinel.$j.plist 2>/dev/null || true
  launchctl load   ~/Library/LaunchAgents/com.arbsentinel.$j.plist
done
```

| job | cadence |
|---|---|
| `com.arbsentinel.rates` | every 2h, 08–22 |
| `com.arbsentinel.digest` | daily 09:00 |
| `com.arbsentinel.announcements` | ~2h, 09:30–21:30 |
| `com.arbsentinel.monitor` | every 2h, 09–21 |

Logs: `~/Library/Logs/arbsentinel-*.log`.

## Configuration

All tunables in `config.yaml` (thresholds, `ref_capital`, schedule cadences,
`assets`, `exchanges`, `own_funds_mode`). `own_funds_mode: true` (default) →
`net_spread = lend APR`; set `false` to subtract the cheapest cross-exchange
borrow cost.

## Secrets & gitignore

`.env`, `state/*.json`, `logs/`, `.venv/` are gitignored. Never commit credentials.

## Status

**Done & live-verified:** M1 (OKX public rates → engine → Telegram), M2 (daily
digest + grading/dedup), M3 (Bitget announcements + Groq promo extraction),
M4 (signed Binance + Bitget rates, tiered-APR de-headlining, cross-exchange
borrow + net spread), M5 (exit detection + de-peg).

**Deferred (optional / advanced, per spec):** Bybit adapter (P3); dual-investment
category; OKX/Binance announcement HTML scraping (Bitget announcement API is
wired); Bitget borrow rate; BTC/ETH spot-price conversion for Bitget tier bands
(stablecoin tiers are correct; non-stablecoin tier pick is approximate).

## Tests

```bash
.venv/bin/python -m pytest -q
```
