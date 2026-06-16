# arb-sentinel

Personal crypto Earn / borrow / promo radar across OKX, Binance, and Bitget.

Computes net interest-rate spread + time-window for each opportunity, grades
it (HIGH / MID / LOW), and fires graded Telegram alerts — all from a
deterministic Python process on macOS launchd. No LLM in the critical path
(LLM is optional M3 enhancement for announcement parsing).

The full design plan lives at:
`../docs/superpowers/plans/2026-06-16-arb-sentinel.md`

---

## Setup

```bash
# 1. Create virtualenv and install deps
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Copy the env template and fill in your Telegram credentials
cp .env.example .env
# Edit .env — at minimum set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
# (copy from finance-workflows/.env if you already have them there)
```

Exchange API keys are only needed starting at Milestone 4 (M4). Leave the
`BINANCE_*` and `BITGET_*` fields blank until then.

---

## Running

```bash
# Smoke-test the setup (no network, no secrets required)
.venv/bin/python -m arb_sentinel --task test

# Pull current rates and evaluate opportunities
.venv/bin/python -m arb_sentinel --task rates

# Pull rates + check announcements + depeg guard, send digest alert
.venv/bin/python -m arb_sentinel --task digest
```

---

## Configuration

All tunable parameters live in `config.yaml` — thresholds, schedule cadences,
asset list, and exchange list. Do not hard-code values in the source files.

---

## Secrets & gitignore

`.env`, `state/*.json`, `logs/`, and `.venv/` are all gitignored. Never commit
real credentials.
