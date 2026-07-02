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
| `announcements` | pull Bitget + OKX announcements → **deterministic promo heads-up** (no LLM), batched into one WATCH message. Set `announcement_llm: true` for Groq quantitative parsing | TG (GROQ only if `announcement_llm`) |
| `depeg` | alert when a tracked stablecoin pair deviates > `depeg_bps` from 1.0 | TG |
| `exits` | check `active_positions` for the 4 exit triggers (spec §7) | TG + keys |
| `monitor` | `depeg` + `exits` combined | TG + keys |
| `carry` | Bitget carry-guardian: check LTV / borrow / depth every 5 min. **Plan A: only 🔴 CRITICAL LTV + system health push.** WATCH/ALERT surface via `carry-digest`. See `docs/superpowers/specs/2026-07-02-carry-guardian.md` | TG (`TELEGRAM_TOPIC_CARRY`) + Bitget keys |
| `carry-digest` | Daily 08:00 TPE **heartbeat + full snapshot** (LTV / 24h LTV peak / payout audit via `totalProfit` delta / net spread / all 4 checks). **Missing digest = monitor dead** | TG (`TELEGRAM_TOPIC_CARRY`) + Bitget keys |

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
| `com.arbsentinel.carry` | **every 5 min, 24/7** (real-time LTV monitor) |
| `com.arbsentinel.carrydigest` | **daily 08:00 TPE** (heartbeat + full snapshot) |

Logs: `~/Library/Logs/arbsentinel-*.log`.

### carry-guardian one-time activation (users with active Bitget carry)

The `carry` + `carry-digest` tasks watch a specific Bitget carry position
(loan + collateral + savings). Requires 24/7 uptime — **MacBook must be
open, not asleep** (spec §7).

```bash
# 1. Open a new forum topic in your Telegram supergroup (dedicated carry alerts)
#    Note the numeric topic id.
# 2. Add to arb-sentinel/.env:
echo "TELEGRAM_TOPIC_CARRY=<topic_id>" >> .env

# 3. Edit arb-sentinel/config.yaml → carry.loan_order_id to your active
#    Bitget loan order ID (or leave blank for auto-first-active).

# 4. Install the 2 plists:
cp launchd/com.arbsentinel.carry.plist ~/Library/LaunchAgents/
cp launchd/com.arbsentinel.carrydigest.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.arbsentinel.carry.plist
launchctl load ~/Library/LaunchAgents/com.arbsentinel.carrydigest.plist

# 5. Verify:
launchctl list | grep arbsentinel.carry   # → 2 entries
.venv/bin/python -m arb_sentinel --task carry-digest  # → forces one digest now
```

**Deactivate temporarily** (e.g. before travel with laptop closed):
```bash
mv ~/Library/LaunchAgents/com.arbsentinel.carry.plist{,.disabled}
mv ~/Library/LaunchAgents/com.arbsentinel.carrydigest.plist{,.disabled}
launchctl unload ~/Library/LaunchAgents/com.arbsentinel.carry.plist.disabled
```
Rename back and `launchctl load` to resume.

**Alert model recap (Plan A, chosen 2026-07-02):**
- 🔴 **CRITICAL** (LTV ≥ 0.82) — 5-min immediate push, every tick until LTV falls
- 🟠 **風控失明** (3+ consecutive API failures) — one push
- 🟡 **訂單消失** (position closed/liquidated) — one push
- 📊 **Daily digest** — every 08:00 including WATCH/ALERT levels, borrow rate,
  depth check, payout audit, 24h LTV peak
- **Missing digest ≡ monitor dead.** Footer explicit; user must react.

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
