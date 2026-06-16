# Arbitrage Sentinel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal "Earn / borrow / launchpool / promotion" radar across OKX, Binance and Bitget that computes a *net interest-rate spread* (accounting for borrow cost and time windows) and pushes graded Telegram alerts only when something is genuinely worth acting on.

**Architecture:** A **deterministic Python package** (`arb-sentinel/`), a sibling to `finance-workflows/` in this same repo. Short-lived CLI runs fired by macOS **launchd** (`python -m arb_sentinel --task <kind>`): each run collects from exchange adapters → normalizes to one `Opportunity` schema → runs the **Net Spread Engine** (pure arithmetic: spread + time-window + tiering) → dedups against `state.json` → pushes graded Telegram alerts. It is **NOT** a `finance-workflows` workflow and does **NOT** invoke `claude -p` on a schedule — milestones M1/M2/M5 use zero LLM and cost $0. The one LLM step (M3, parsing announcement free-text) runs off-Claude-pool (Groq or Anthropic API) at most a few times/day.

**Tech Stack:** Python 3.11+, `httpx` (direct REST — OKX rate/ticker endpoints are public/keyless, verified live 2026-06-16), `pyyaml` (config), `pytest` (tests), stdlib `hmac`/`hashlib`/`base64` (Binance/Bitget signing at M4). Telegram via Bot API (`sendMessage` + `message_thread_id`, HTML parse_mode). Scheduling via launchd `StartCalendarInterval`.

---

## 0. How to read this plan

The user asked for a **full M1–M6 design to review before any code**. So:

- **M1 is build-ready**: fully-detailed TDD tasks with exact files, complete code, and exact commands. Implement it directly from this document.
- **M2–M6 are design-locked roadmap**: concrete files, verified endpoints/auth/fields, decisions and acceptance criteria — but *not* step-by-step TDD code. Each will be expanded into its own detailed plan (`docs/superpowers/plans/...`) when we reach it, because they depend on (a) live read-only API keys the user must create, (b) the M3 LLM billing decision, and (c) lessons from M1. Writing speculative complete code for them now would be guesswork and violate the no-placeholder rule.

**Open decisions for the user to confirm before execution** are collected in §9. None block M1.

---

## 1. Verified facts (the plan is built on these, not on the original spec's assumptions)

A verification workflow (2026-06-16) checked every API claim in the spec against current official docs, including **live keyless curl calls**. Results:

| Source | Endpoint | Auth | Key fields | Notes |
|---|---|---|---|---|
| **OKX** | `GET /api/v5/finance/savings/lending-rate-summary` | **public/keyless** ✅ | `ccy, estRate, avgRate, preRate, avgAmt, avgAmtUsd` | Live: USDT 2.5%, BTC 0.5%, ETH 1.5%, USDC 2.5% |
| **OKX** | `GET /api/v5/finance/savings/lending-rate-history` | **public/keyless** ✅ | `ccy, rate, lendingRate, amt, ts` | `lendingRate` added 2026-02-27 |
| **OKX** | `GET /api/v5/market/ticker?instId=USDC-USDT` | **public/keyless** ✅ | `last, askPx, bidPx, ...` | 20 req / 2 s; live last=1.0005 |
| **Binance** | `GET /sapi/v1/simple-earn/flexible/list` | **signed USER_DATA** ⚠️ | `asset, latestAnnualPercentageRate, tierAnnualPercentageRate, canPurchase` | read-only HMAC key; weight 150 |
| **Binance** | `GET /api/v3/ticker/price`, `/api/v3/depth` | public ✅ | `symbol, price` / `bids, asks` | de-peg, keyless |
| **Binance** | `GET /sapi/v1/margin/next-hourly-interest-rate` | signed ⚠️ | `asset, nextHourlyInterestRate` | borrow rate; no public feed |
| **Bitget** | `GET /api/v2/earn/savings/product` (+`subscribe-info`,`assets`) | **signed** ⚠️ | `apyList[]`, `currentApy`, `apyType(single\|ladder)` | APR is **tiered**, not flat `apy` |
| **Bitget** | `GET /api/v2/spot/market/tickers` | public ✅ | `lastPr, bidPr, askPr, ...` | de-peg, keyless |
| **Bitget** | `GET /api/v2/public/annoucements` | public ✅ | `annId, annTitle, annType, cTime, annUrl` | ⚠️ path typo "annoucements" is real; param `language`, max `limit=10`, paginate `cursor=annId` |

Other verified facts:
- **OKX SDK** is `python-okx` (import `okx`), keyless-capable — but since the three endpoints are plain public GETs, we use **`httpx` directly** (one fewer dependency, matches `finance-workflows` MCP server style). No SDK.
- **Binance signing**: `X-MBX-APIKEY` header + `timestamp` (ms) + `signature = hex(HMAC-SHA256(querystring, secret))` + optional `recvWindow`. A read-only key (no trade/withdraw) suffices.
- **Bitget signing**: headers `ACCESS-KEY / ACCESS-SIGN / ACCESS-PASSPHRASE / ACCESS-TIMESTAMP(ms)`; `ACCESS-SIGN = base64(HMAC-SHA256(timestamp + METHOD + requestPath + ('?'+query if any) + body, secret))`. Passphrase is user-chosen at key creation. Read-only key suffices.
- **Telegram**: `POST /bot<token>/sendMessage` with `chat_id` + `message_thread_id=1390` drops into the forum topic. Use **HTML parse_mode** (escape `< > &` only) instead of MarkdownV2 (which forces escaping `. - ( ) + =` etc. — painful with financial decimals). Limits: **1 msg/s per chat, 20 msg/min per group** → space multiple alerts ~1 s apart.
- **launchd**: use **`StartCalendarInterval`** (array of dicts). If asleep at the scheduled time it runs **once on next wake** (catch-up is one run, not per-missed-interval; powered-off = no catch-up). `StartInterval` *drops* firings during sleep — do not use. Sub-hourly cadence is therefore unreliable on a sleeping laptop → de-peg monitoring is best-effort (§ M5).

---

## 2. File structure

```
new_financial-report-system/            (this repo; root git rules apply)
├── finance-workflows/                  (report runner — UNTOUCHED)
└── arb-sentinel/                       ← NEW, self-contained package
    ├── README.md                       run/install instructions
    ├── CLAUDE.md                       folder rules (deterministic; no claude -p in cron)
    ├── requirements.txt                httpx, pyyaml, pytest  (+ groq/anthropic at M3)
    ├── .gitignore                      .env, state/, logs/, .venv/, __pycache__
    ├── .env.example                    documents every env var (real .env is gitignored)
    ├── config.yaml                     §11-style tunables (thresholds, ref_capital, schedule, assets)
    ├── arb_sentinel/
    │   ├── __init__.py
    │   ├── __main__.py                 CLI: python -m arb_sentinel --task rates|digest|test|announcements|depeg|exits
    │   ├── config.py                   load config.yaml + .env → Settings dataclass
    │   ├── models.py                   Opportunity dataclass (§4), Tier/TimeFlag constants, stable_id()
    │   ├── engine.py                   ★ net_spread / time_flag / estimate_yield / classify
    │   ├── state.py                    state.json load/save, dedup (renotify-delta + tier-upgrade), positions
    │   ├── notify.py                   Telegram sender (HTML, topic, ~1s spacing) + message formatters
    │   ├── run.py                      orchestrate one task: collect→normalize→engine→state→notify
    │   ├── collectors/
    │   │   ├── __init__.py
    │   │   ├── base.py                 helper: shaped HTTP GET that never raises → (json|None, error|None)
    │   │   ├── okx.py                  M1: public lending-rate-summary + ticker → [Opportunity]
    │   │   ├── binance.py              M4: signed simple-earn/flexible/list + public ticker
    │   │   ├── bitget.py               M4: signed earn/savings/* + public ticker
    │   │   └── announcements.py        M3: Bitget public ann API + HTML scrape (3 exchanges)
    │   ├── normalizer.py               M4: divergent exchange shapes → Opportunity (M1 folds this into okx.py)
    │   └── llm.py                      M3: announcement text → structured fields (Groq/Anthropic; off Claude pools)
    ├── tests/
    │   ├── conftest.py                 shared fixtures (frozen `today`, sample Settings)
    │   ├── test_models.py
    │   ├── test_engine.py              the heart — pure, no network
    │   ├── test_config.py
    │   ├── test_collectors_okx.py      monkeypatch httpx; assert shape; never raises
    │   ├── test_state.py
    │   ├── test_notify.py              message formatting + HTML escaping (monkeypatch httpx)
    │   ├── test_run.py                 end-to-end with everything monkeypatched
    │   └── fixtures/
    │       ├── okx_lending_summary.json
    │       └── okx_ticker_usdc_usdt.json
    ├── scripts/
    │   ├── run-task.sh                 launchd wrapper: cd + .venv/bin/python -m arb_sentinel --task "$1"
    │   └── install-launchd.sh          writes/loads plists (+ optional pmset wake)
    ├── launchd/
    │   ├── com.arbsentinel.rates.plist
    │   ├── com.arbsentinel.announcements.plist   (M3)
    │   └── com.arbsentinel.depeg.plist           (M5)
    ├── state/                          gitignored (state.json)
    │   └── .gitkeep
    └── logs/                           gitignored
        └── .gitkeep
```

**Design boundaries:** the engine (`engine.py`) is *pure* (no I/O) so it's trivially testable and is the one place correctness must be airtight. Collectors never raise — they return shaped data or an error string, so one exchange failing never crashes the run (spec §10.3). State and notify are the only stateful/side-effecting modules besides collectors.

---

## 3. Milestone roadmap (what each delivers + acceptance)

| M | Deliverable | LLM? | Keys? | Acceptance |
|---|---|---|---|---|
| **M1** | OKX public rates → engine (own-funds mode) → Telegram digest + threshold alerts; launchd `rates` job | none | none | `--task test` posts to topic 1390; `--task rates` posts a real OKX rate digest; all unit tests green |
| **M2** | Full §5 tiering + `config.yaml` all tunables + est-yield + WATCH daily digest + renotify/tier-upgrade dedup | none | none | grading + dedup proven by tests; no duplicate spam over repeated runs |
| **M3** | Announcement layer: Bitget public ann API + HTML scrape (3 exchanges) + `llm.py` field extraction; announcements launchd job | yes (off-pool) | none | new promo announcement → parsed `{start,end,apr,min_hold,entry_asset,subsidy}` → graded alert |
| **M4** | Signed Binance (`simple-earn/flexible/list`) + Bitget (`earn/savings/*`) collectors; cross-exchange `best_borrow_apr`; borrow-mode engine | none | **read-only keys** | both exchanges' APR ingested; net_spread uses cheapest borrow across exchanges |
| **M5** | Exit detection over `active_positions` (§7) + stablecoin de-peg monitoring; depeg launchd job | none | none | seeded position triggers all 4 exit conditions; de-peg ticker deviation alerts |
| **M6** | Bybit (optional), dual-investment category, hardening (retry/backoff, response cache, rate-limit throttle) | none | optional | resilience tests; rate-limit respected |

> **Reality check on M1 alerts:** live OKX base rates (BTC 0.5% … USDT/USDC 2.5%) sit *below* the 3% GOOD threshold, so M1 threshold alerts will rarely fire — which is *correct* per the spec's "rather miss than spam" ethos. The real 🔴 ACT_NOW signals come from **promotions (M3)** and **de-peg (M5)**. To make M1 visibly working and useful day-1, M1 ships a **`digest` task** that posts a compact 🟡 baseline-rates summary to topic 1390, plus a **`test` task** for wiring verification. Threshold alerting is built and tested in M1 but expected to be quiet on base rates.

---

## 4. Opportunity schema (§4 of spec, made concrete)

```python
# arb_sentinel/models.py
from dataclasses import dataclass, field
from datetime import date

# Tiers (spec §5.4)
ACT_NOW, GOOD, WATCH, LOG_ONLY = "ACT_NOW", "GOOD", "WATCH", "LOG_ONLY"
# Time flags (spec §5.2)
OK_TIME, TIGHT, TOO_LATE, NO_DEADLINE = "OK_TIME", "TIGHT", "TOO_LATE", "NO_DEADLINE"

@dataclass
class Opportunity:
    exchange: str                       # okx | binance | bitget
    category: str                       # flexible_earn | borrow | launchpool |
                                        # new_listing_earn | dual_investment |
                                        # promotion | stable_depeg
    asset: str
    apr: float | None                   # annualised decimal (0.123 = 12.3%); None if unknown
    apr_source: str                     # api | announcement | app_display
    apr_is_promotional: bool = False
    tier_info: str | None = None        # raw tier text if any
    borrow_apr_same_asset: float | None = None
    min_hold_days: int = 0
    start_date: date | None = None
    end_date: date | None = None
    entry_asset_required: str | None = None
    subsidy_note: str | None = None
    directional_risk: bool = False
    source_url: str | None = None
    raw_snapshot: dict = field(default_factory=dict)
    collected_at: str = ""              # ISO8601 UTC
```

**Dedup key (deviation from spec, with reason).** The spec's example id `okx-flex-USDC-20260616` embeds *today's date* — that would mint a new id every day and defeat dedup for standing products. Correct behaviour:

```python
def stable_id(o: Opportunity) -> str:
    base = f"{o.exchange}-{o.category}-{o.asset}"
    return f"{base}-{o.end_date.isoformat()}" if o.end_date else base
```

→ no-deadline products get a *stable* id (dedups across runs/days); dated activities key on their end_date (a re-run of the *same* activity dedups, a genuinely new activity period gets a new id).

---

## 5. Net Spread Engine (spec §5, made concrete — built & tested in M1)

```python
# arb_sentinel/engine.py
from datetime import date
from .models import (Opportunity, ACT_NOW, GOOD, WATCH, LOG_ONLY,
                     OK_TIME, TIGHT, TOO_LATE, NO_DEADLINE)

def net_spread(o: Opportunity, best_borrow_apr: float = 0.0) -> float | None:
    """apr − cheapest borrow cost for the asset. own-funds mode → best_borrow_apr=0."""
    if o.apr is None:
        return None
    return o.apr - (best_borrow_apr or 0.0)

def time_flag(o: Opportunity, today: date, default_horizon_days: int = 14) -> str:
    if o.end_date is None:
        return NO_DEADLINE
    days_left = (o.end_date - today).days
    if days_left < o.min_hold_days:
        return TOO_LATE
    if days_left < o.min_hold_days + 3:
        return TIGHT
    return OK_TIME

def estimate_yield(o: Opportunity, net: float | None, cfg) -> dict:
    """Reference-capital projection (spec §5.3). Returns {} if net is None."""
    if net is None:
        return {}
    holding_days = max(o.min_hold_days, cfg.default_horizon_days)
    est_gross = cfg.ref_capital * net * holding_days / 365
    entry_slip = cfg.ref_capital * cfg.entry_slippage_assumption
    # subsidy covering exit → no exit slippage; else symmetric to entry
    exit_slip = 0.0 if (o.subsidy_note and "exit" in o.subsidy_note.lower()) else entry_slip
    return {
        "holding_days": holding_days,
        "est_gross": round(est_gross, 2),
        "est_net": round(est_gross - entry_slip - exit_slip, 2),
    }

def classify(net: float | None, flag: str, o: Opportunity, cfg) -> str:
    """Grade (spec §5.4). Order matters: drop-outs first, then risk caps, then
    positive grades. directional_risk (dual-invest) and TIGHT timing cap at WATCH
    — they must never auto-act, even with a high net."""
    time_ok = flag in (OK_TIME, NO_DEADLINE)
    if net is None or flag == TOO_LATE:
        return LOG_ONLY
    if o.directional_risk or flag == TIGHT:
        return WATCH
    if net >= cfg.threshold_high and time_ok:
        return ACT_NOW
    if net >= cfg.threshold_mid and time_ok:
        return GOOD
    if net >= cfg.threshold_mid * 0.5:
        return WATCH
    return LOG_ONLY
```

---

## 6. M1 — build-ready TDD tasks

> Work from `arb-sentinel/`. Follow the repo git rule: stage only named paths, commit per slice with a *why* message, `git push origin main` after each task. Never `git add -A`.

### Task 1: Scaffold the package

**Files:**
- Create: `arb-sentinel/.gitignore`, `requirements.txt`, `.env.example`, `config.yaml`, `README.md`, `CLAUDE.md`
- Create: `arb-sentinel/arb_sentinel/__init__.py`, `arb-sentinel/tests/conftest.py`
- Create: `arb-sentinel/state/.gitkeep`, `arb-sentinel/logs/.gitkeep`

- [ ] **Step 1: Create directory + venv**

```bash
cd /Users/pochenkuo/AI/new_financial-report-system
mkdir -p arb-sentinel/arb_sentinel/collectors arb-sentinel/tests/fixtures arb-sentinel/scripts arb-sentinel/launchd arb-sentinel/state arb-sentinel/logs
cd arb-sentinel
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
touch arb_sentinel/__init__.py arb_sentinel/collectors/__init__.py state/.gitkeep logs/.gitkeep
```

- [ ] **Step 2: `.gitignore`**

```gitignore
.env
.venv/
state/*.json
logs/
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 3: `requirements.txt`**

```
httpx>=0.27
pyyaml>=6.0
pytest>=8.0
```

- [ ] **Step 4: `.env.example`** (real `.env` is gitignored; copy this and fill in)

```bash
# === Telegram (copy the two shared values from finance-workflows/.env) ===
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TELEGRAM_TOPIC_ARB=1390

# === Exchange READ-ONLY keys (M4 — leave blank until then) ===
# NEVER enable trade/withdraw/transfer on these keys.
BINANCE_API_KEY=
BINANCE_API_SECRET=
BITGET_API_KEY=
BITGET_API_SECRET=
BITGET_API_PASSPHRASE=

# === Announcement LLM (M3 — pick ONE; see plan §9) ===
# Option A (recommended, zero new setup, key already in finance-workflows/.env):
GROQ_API_KEY=
# Option B (higher extraction accuracy, needs console.anthropic.com credit):
ANTHROPIC_API_KEY=
```

- [ ] **Step 5: `config.yaml`** (spec §11)

```yaml
reference:
  ref_capital: 30000
  default_horizon_days: 14
  entry_slippage_assumption: 0.0005
thresholds:
  threshold_high: 0.05
  threshold_mid: 0.03
  renotify_delta: 0.02
  rate_drop_ratio: 0.5
  depeg_bps: 30
  exit_lead_days: 2
schedule_hours:
  rates: 2
  announcements: 1
  depeg_minutes: 30
assets: [BTC, ETH, USDT, USDC]
exchanges: [okx]            # binance, bitget added at M4
own_funds_mode: true        # true → borrow_apr=0, net_spread=apr (M1 default)
```

- [ ] **Step 6: `README.md` + `CLAUDE.md`** (record the deterministic / no-`claude -p` rule and run commands)

`CLAUDE.md` must state: *"This package is deterministic Python on launchd. Never invoke `claude -p` from a scheduled run (avoids the post-2026-06-15 credit pool). The only LLM use is `llm.py` (M3), which calls Groq/Anthropic API off both Claude pools, at most a few times/day. Collectors must never raise. Secrets, state, logs are gitignored."*

- [ ] **Step 7: `tests/conftest.py`** (shared fixtures)

```python
import datetime, types
import pytest

@pytest.fixture
def today():
    return datetime.date(2026, 6, 16)

@pytest.fixture
def cfg():
    return types.SimpleNamespace(
        ref_capital=30000, default_horizon_days=14, entry_slippage_assumption=0.0005,
        threshold_high=0.05, threshold_mid=0.03, renotify_delta=0.02,
        rate_drop_ratio=0.5, depeg_bps=30, exit_lead_days=2,
        assets=["BTC", "ETH", "USDT", "USDC"], exchanges=["okx"], own_funds_mode=True,
        telegram_bot_token="x", telegram_chat_id="-100", telegram_topic_arb="1390",
    )
```

- [ ] **Step 8: Commit**

```bash
cd /Users/pochenkuo/AI/new_financial-report-system
git add arb-sentinel/.gitignore arb-sentinel/requirements.txt arb-sentinel/.env.example arb-sentinel/config.yaml arb-sentinel/README.md arb-sentinel/CLAUDE.md arb-sentinel/arb_sentinel/__init__.py arb-sentinel/arb_sentinel/collectors/__init__.py arb-sentinel/tests/conftest.py arb-sentinel/state/.gitkeep arb-sentinel/logs/.gitkeep
git commit -m "feat(arb-sentinel): scaffold deterministic arbitrage monitor package

Sibling to finance-workflows; deterministic Python on launchd, no claude -p in cron.
Config, env template, gitignore, test fixtures."
git push origin main
```

### Task 2: `models.py` — Opportunity + stable_id

**Files:** Create `arb_sentinel/models.py`; Test `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
import datetime
from arb_sentinel.models import Opportunity, stable_id

def test_stable_id_no_deadline_is_date_independent():
    o = Opportunity(exchange="okx", category="flexible_earn", asset="USDC",
                    apr=0.025, apr_source="api")
    assert stable_id(o) == "okx-flexible_earn-USDC"

def test_stable_id_with_deadline_keys_on_end_date():
    o = Opportunity(exchange="bitget", category="promotion", asset="USDGO",
                    apr=0.12, apr_source="announcement",
                    end_date=datetime.date(2026, 6, 30))
    assert stable_id(o) == "bitget-promotion-USDGO-2026-06-30"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd arb-sentinel && .venv/bin/python -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'arb_sentinel.models'`

- [ ] **Step 3: Implement** — paste the full `models.py` from §4 above, then append:

```python
def stable_id(o: "Opportunity") -> str:
    base = f"{o.exchange}-{o.category}-{o.asset}"
    return f"{base}-{o.end_date.isoformat()}" if o.end_date else base
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add arb-sentinel/arb_sentinel/models.py arb-sentinel/tests/test_models.py
git commit -m "feat(arb-sentinel): Opportunity schema + stable dedup id

stable_id is date-independent for no-deadline products so dedup works across days;
dated activities key on end_date."
git push origin main
```

### Task 3: `engine.py` — the heart (pure, fully tested)

**Files:** Create `arb_sentinel/engine.py`; Test `tests/test_engine.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine.py
import datetime
from arb_sentinel.models import Opportunity, ACT_NOW, GOOD, WATCH, LOG_ONLY, \
    OK_TIME, TIGHT, TOO_LATE, NO_DEADLINE
from arb_sentinel.engine import net_spread, time_flag, estimate_yield, classify

def _opp(**kw):
    base = dict(exchange="okx", category="flexible_earn", asset="USDC",
                apr=0.06, apr_source="api")
    base.update(kw)
    return Opportunity(**base)

def test_net_spread_own_funds_is_apr():
    assert net_spread(_opp(apr=0.06), 0.0) == 0.06

def test_net_spread_subtracts_borrow():
    assert abs(net_spread(_opp(apr=0.06), 0.017) - 0.043) < 1e-9

def test_net_spread_none_apr():
    assert net_spread(_opp(apr=None)) is None

def test_time_flag_no_deadline(today):
    assert time_flag(_opp(end_date=None), today) == NO_DEADLINE

def test_time_flag_too_late(today):
    o = _opp(end_date=datetime.date(2026, 6, 20), min_hold_days=14)  # 4 days left < 14
    assert time_flag(o, today) == TOO_LATE

def test_time_flag_tight(today):
    o = _opp(end_date=datetime.date(2026, 6, 30), min_hold_days=14)  # 14 left, <14+3
    assert time_flag(o, today) == TIGHT

def test_time_flag_ok(today):
    o = _opp(end_date=datetime.date(2026, 7, 15), min_hold_days=14)  # 29 left
    assert time_flag(o, today) == OK_TIME

def test_classify_act_now(cfg):
    assert classify(0.06, NO_DEADLINE, _opp(), cfg) == ACT_NOW

def test_classify_good(cfg):
    assert classify(0.035, OK_TIME, _opp(), cfg) == GOOD

def test_classify_directional_risk_caps_at_watch(cfg):
    assert classify(0.06, OK_TIME, _opp(directional_risk=True), cfg) == WATCH

def test_classify_too_late_is_log_only(cfg):
    assert classify(0.06, TOO_LATE, _opp(), cfg) == LOG_ONLY

def test_estimate_yield(cfg):
    est = estimate_yield(_opp(apr=0.06), 0.06, cfg)
    # 30000 * 0.06 * 14/365 = 69.04 gross; minus 2x 15 slippage = 39.04 net
    assert est["est_gross"] == 69.04
    assert est["est_net"] == 39.04
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m pytest tests/test_engine.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement** — paste the full `engine.py` from §5 above.

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_engine.py -v`
Expected: PASS (12 passed)

- [ ] **Step 5: Commit**

```bash
git add arb-sentinel/arb_sentinel/engine.py arb-sentinel/tests/test_engine.py
git commit -m "feat(arb-sentinel): net-spread engine (spread, time-window, tiering, est-yield)

Pure, no I/O. Time-window check is a first-class filter per spec; TOO_LATE and
missing/low net drop to LOG_ONLY before any positive grading."
git push origin main
```

### Task 4: `config.py` — load config.yaml + .env

**Files:** Create `arb_sentinel/config.py`; Test `tests/test_config.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_config.py
from arb_sentinel.config import load_settings

def test_load_settings(tmp_path, monkeypatch):
    (tmp_path / "config.yaml").write_text(
        "reference:\n  ref_capital: 30000\n  default_horizon_days: 14\n"
        "  entry_slippage_assumption: 0.0005\n"
        "thresholds:\n  threshold_high: 0.05\n  threshold_mid: 0.03\n"
        "  renotify_delta: 0.02\n  rate_drop_ratio: 0.5\n  depeg_bps: 30\n  exit_lead_days: 2\n"
        "schedule_hours:\n  rates: 2\n  announcements: 1\n  depeg_minutes: 30\n"
        "assets: [BTC, USDC]\nexchanges: [okx]\nown_funds_mode: true\n", "utf-8")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100")
    monkeypatch.setenv("TELEGRAM_TOPIC_ARB", "1390")
    s = load_settings(config_path=tmp_path / "config.yaml")
    assert s.ref_capital == 30000
    assert s.threshold_high == 0.05
    assert s.assets == ["BTC", "USDC"]
    assert s.own_funds_mode is True
    assert s.telegram_topic_arb == "1390"
```

- [ ] **Step 2: Run to verify fail** — `.venv/bin/python -m pytest tests/test_config.py -v` → FAIL.

- [ ] **Step 3: Implement**

```python
# arb_sentinel/config.py
import os, pathlib
from dataclasses import dataclass
import yaml

@dataclass
class Settings:
    ref_capital: float; default_horizon_days: int; entry_slippage_assumption: float
    threshold_high: float; threshold_mid: float; renotify_delta: float
    rate_drop_ratio: float; depeg_bps: float; exit_lead_days: int
    schedule_hours: dict; assets: list; exchanges: list; own_funds_mode: bool
    telegram_bot_token: str; telegram_chat_id: str; telegram_topic_arb: str

def _load_dotenv(path: pathlib.Path) -> None:
    if not path.exists():
        return
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

def load_settings(config_path: pathlib.Path | None = None) -> Settings:
    root = pathlib.Path(__file__).resolve().parent.parent
    config_path = pathlib.Path(config_path) if config_path else root / "config.yaml"
    _load_dotenv(root / ".env")
    raw = yaml.safe_load(config_path.read_text("utf-8"))
    ref, th = raw["reference"], raw["thresholds"]
    return Settings(
        ref_capital=ref["ref_capital"], default_horizon_days=ref["default_horizon_days"],
        entry_slippage_assumption=ref["entry_slippage_assumption"],
        threshold_high=th["threshold_high"], threshold_mid=th["threshold_mid"],
        renotify_delta=th["renotify_delta"], rate_drop_ratio=th["rate_drop_ratio"],
        depeg_bps=th["depeg_bps"], exit_lead_days=th["exit_lead_days"],
        schedule_hours=raw.get("schedule_hours", {}), assets=raw["assets"],
        exchanges=raw["exchanges"], own_funds_mode=raw.get("own_funds_mode", True),
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
        telegram_topic_arb=os.environ.get("TELEGRAM_TOPIC_ARB", ""),
    )
```

- [ ] **Step 4: Run to verify pass** — PASS (1 passed).
- [ ] **Step 5: Commit**

```bash
git add arb-sentinel/arb_sentinel/config.py arb-sentinel/tests/test_config.py
git commit -m "feat(arb-sentinel): config loader (config.yaml + .env, no extra deps)"
git push origin main
```

### Task 5: `collectors/base.py` + `collectors/okx.py` — public OKX collector

**Files:** Create `arb_sentinel/collectors/base.py`, `arb_sentinel/collectors/okx.py`; Test `tests/test_collectors_okx.py`; Fixtures `tests/fixtures/okx_lending_summary.json`, `okx_ticker_usdc_usdt.json`

- [ ] **Step 1: Save fixtures** (real keyless response shapes, verified 2026-06-16)

```json
// tests/fixtures/okx_lending_summary.json
{"code":"0","msg":"","data":[
  {"ccy":"USDT","estRate":"0.025","avgRate":"0.025","preRate":"0.025","avgAmt":"1","avgAmtUsd":"1"},
  {"ccy":"USDC","estRate":"0.025","avgRate":"0.024","preRate":"0.025","avgAmt":"1","avgAmtUsd":"1"},
  {"ccy":"BTC","estRate":"0.005","avgRate":"0.005","preRate":"0.005","avgAmt":"1","avgAmtUsd":"1"},
  {"ccy":"ETH","estRate":"0.015","avgRate":"0.015","preRate":"0.015","avgAmt":"1","avgAmtUsd":"1"}]}
```

```json
// tests/fixtures/okx_ticker_usdc_usdt.json
{"code":"0","msg":"","data":[{"instId":"USDC-USDT","last":"1.0005","askPx":"1.0005","bidPx":"1.0004","ts":"1750000000000"}]}
```

- [ ] **Step 2: Failing test**

```python
# tests/test_collectors_okx.py
import json, pathlib
import httpx
from arb_sentinel.collectors import okx

FIX = pathlib.Path(__file__).parent / "fixtures"

def _mock_client(monkeypatch, payload):
    def fake_get(self, url, **kw):
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)

def test_collect_rates_maps_to_opportunities(monkeypatch, cfg):
    _mock_client(monkeypatch, json.loads((FIX / "okx_lending_summary.json").read_text()))
    opps, errors = okx.collect_rates(cfg)
    assert errors == []
    usdc = next(o for o in opps if o.asset == "USDC")
    assert usdc.exchange == "okx" and usdc.category == "flexible_earn"
    assert usdc.apr == 0.025 and usdc.apr_source == "api"

def test_collect_never_raises_on_http_error(monkeypatch, cfg):
    def boom(self, url, **kw):
        raise httpx.ConnectError("down", request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", boom)
    opps, errors = okx.collect_rates(cfg)
    assert opps == [] and len(errors) == 1   # logged, not raised
```

- [ ] **Step 3: Run to verify fail** — FAIL.

- [ ] **Step 4: Implement**

```python
# arb_sentinel/collectors/base.py
import httpx

def get_json(url: str, params: dict | None = None, timeout: float = 15.0):
    """GET → (json, None) on success, (None, error_str) on any failure. Never raises."""
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.get(url, params=params)
        if r.status_code != 200:
            return None, f"{url} HTTP {r.status_code}"
        return r.json(), None
    except Exception as e:
        return None, f"{url} {type(e).__name__}: {e}"
```

```python
# arb_sentinel/collectors/okx.py
import datetime
from ..models import Opportunity
from . import base

BASE = "https://www.okx.com"
SUMMARY = "/api/v5/finance/savings/lending-rate-summary"
TICKER = "/api/v5/market/ticker"

def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def collect_rates(cfg) -> tuple[list[Opportunity], list[str]]:
    """OKX public flexible-earn lending rates for cfg.assets. Keyless. Never raises."""
    opps, errors = [], []
    data, err = base.get_json(BASE + SUMMARY)
    if err:
        return [], [err]
    by_ccy = {row.get("ccy"): row for row in (data.get("data") or [])}
    for asset in cfg.assets:
        row = by_ccy.get(asset)
        if not row:
            continue
        try:
            apr = float(row["estRate"])
        except (KeyError, ValueError, TypeError):
            errors.append(f"okx {asset}: bad estRate {row!r}")
            continue
        opps.append(Opportunity(
            exchange="okx", category="flexible_earn", asset=asset,
            apr=apr, apr_source="api",
            source_url="https://www.okx.com/earn/simple-earn",
            raw_snapshot=row, collected_at=_now_iso()))
    return opps, errors

def collect_depeg(cfg, pairs=("USDC-USDT",)) -> tuple[list[Opportunity], list[str]]:
    """OKX public ticker deviation from 1.0 for stablecoin pairs (foundation for M5)."""
    opps, errors = [], []
    for inst in pairs:
        data, err = base.get_json(BASE + TICKER, params={"instId": inst})
        if err:
            errors.append(err); continue
        rows = data.get("data") or []
        if not rows:
            continue
        try:
            last = float(rows[0]["last"])
        except (KeyError, ValueError, TypeError):
            errors.append(f"okx ticker {inst}: bad last"); continue
        opps.append(Opportunity(
            exchange="okx", category="stable_depeg", asset=inst,
            apr=None, apr_source="api",
            subsidy_note=f"last={last}", raw_snapshot=rows[0], collected_at=_now_iso()))
    return opps, errors
```

- [ ] **Step 5: Run to verify pass** — PASS (2 passed).
- [ ] **Step 6: Commit**

```bash
git add arb-sentinel/arb_sentinel/collectors/base.py arb-sentinel/arb_sentinel/collectors/okx.py arb-sentinel/tests/test_collectors_okx.py arb-sentinel/tests/fixtures/okx_lending_summary.json arb-sentinel/tests/fixtures/okx_ticker_usdc_usdt.json
git commit -m "feat(arb-sentinel): OKX public rate + ticker collector (keyless, never raises)

httpx direct to verified public endpoints; one HTTP failure returns an error
string and an empty list, never crashing the run (spec 10.3)."
git push origin main
```

### Task 6: `state.py` — dedup / renotify / tier-upgrade

**Files:** Create `arb_sentinel/state.py`; Test `tests/test_state.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_state.py
from arb_sentinel.models import Opportunity, ACT_NOW, WATCH
from arb_sentinel.state import State

def _opp(apr): return Opportunity(exchange="okx", category="flexible_earn",
                                  asset="USDC", apr=apr, apr_source="api")

def test_first_sighting_notifies(tmp_path, cfg):
    st = State(tmp_path / "state.json")
    assert st.should_notify(_opp(0.06), ACT_NOW, cfg) is True

def test_same_tier_same_apr_is_suppressed(tmp_path, cfg):
    st = State(tmp_path / "state.json")
    st.record(_opp(0.06), ACT_NOW)
    assert st.should_notify(_opp(0.06), ACT_NOW, cfg) is False

def test_tier_upgrade_renotifies(tmp_path, cfg):
    st = State(tmp_path / "state.json")
    st.record(_opp(0.06), WATCH)
    assert st.should_notify(_opp(0.06), ACT_NOW, cfg) is True

def test_apr_jump_beyond_delta_renotifies(tmp_path, cfg):
    st = State(tmp_path / "state.json")
    st.record(_opp(0.06), ACT_NOW)
    assert st.should_notify(_opp(0.09), ACT_NOW, cfg) is True  # +0.03 > renotify_delta 0.02

def test_state_persists_across_instances(tmp_path, cfg):
    p = tmp_path / "state.json"
    State(p).record(_opp(0.06), ACT_NOW)
    assert State(p).should_notify(_opp(0.06), ACT_NOW, cfg) is False
```

- [ ] **Step 2: Run to verify fail** — FAIL.

- [ ] **Step 3: Implement**

```python
# arb_sentinel/state.py
import json, pathlib
from .models import Opportunity, stable_id

_TIER_RANK = {"LOG_ONLY": 0, "WATCH": 1, "GOOD": 2, "ACT_NOW": 3}

class State:
    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.data = {"seen_opportunities": {}, "active_positions": []}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text("utf-8"))
            except Exception:
                pass
        self.data.setdefault("seen_opportunities", {})
        self.data.setdefault("active_positions", [])

    def should_notify(self, o: Opportunity, tier: str, cfg) -> bool:
        prev = self.data["seen_opportunities"].get(stable_id(o))
        if prev is None:
            return tier in ("ACT_NOW", "GOOD")          # first sighting: alert if actionable
        if _TIER_RANK[tier] > _TIER_RANK.get(prev.get("tier", "LOG_ONLY"), 0):
            return True                                  # tier upgraded
        if o.apr is not None and prev.get("last_apr") is not None:
            if abs(o.apr - prev["last_apr"]) >= cfg.renotify_delta:
                return True                              # APR jumped beyond delta
        return False

    def record(self, o: Opportunity, tier: str) -> None:
        self.data["seen_opportunities"][stable_id(o)] = {
            "last_apr": o.apr, "tier": tier, "last_collected": o.collected_at}
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), "utf-8")
```

- [ ] **Step 4: Run to verify pass** — PASS (5 passed).
- [ ] **Step 5: Commit**

```bash
git add arb-sentinel/arb_sentinel/state.py arb-sentinel/tests/test_state.py
git commit -m "feat(arb-sentinel): state store with dedup, renotify-delta and tier-upgrade

Suppresses hourly re-spam; re-alerts only on tier upgrade or APR jump >= renotify_delta."
git push origin main
```

### Task 7: `notify.py` — Telegram (HTML, topic 1390, spacing)

**Files:** Create `arb_sentinel/notify.py`; Test `tests/test_notify.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_notify.py
import httpx
from arb_sentinel.models import Opportunity, ACT_NOW
from arb_sentinel import notify

def test_format_escapes_html(cfg):
    o = Opportunity(exchange="okx", category="flexible_earn", asset="A&B",
                    apr=0.052, apr_source="api")
    msg = notify.format_opportunity(o, 0.052, {"est_net": 60.0, "holding_days": 14}, "NO_DEADLINE", ACT_NOW, cfg)
    assert "A&amp;B" in msg          # & escaped
    assert "5.2%" in msg

def test_send_posts_to_topic(monkeypatch, cfg):
    captured = {}
    def fake_post(self, url, data=None, **kw):
        captured["url"] = url; captured["data"] = data
        return httpx.Response(200, json={"ok": True}, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx.Client, "post", fake_post)
    ok = notify.send_message("hi", cfg)
    assert ok is True
    assert captured["data"]["message_thread_id"] == "1390"
    assert captured["data"]["parse_mode"] == "HTML"
```

- [ ] **Step 2: Run to verify fail** — FAIL.

- [ ] **Step 3: Implement**

```python
# arb_sentinel/notify.py
import html, sys, time
import httpx
from .models import Opportunity

API = "https://api.telegram.org"
_TIER_EMOJI = {"ACT_NOW": "🔴", "GOOD": "🟠", "WATCH": "🟡", "LOG_ONLY": "⚫"}

def send_message(text: str, cfg, pause: float = 1.1) -> bool:
    """Best-effort send to the arb forum topic. HTML parse_mode. Never raises."""
    if not cfg.telegram_bot_token or not cfg.telegram_chat_id:
        return False
    data = {"chat_id": cfg.telegram_chat_id, "text": text,
            "parse_mode": "HTML", "disable_web_page_preview": "true"}
    if cfg.telegram_topic_arb:
        data["message_thread_id"] = cfg.telegram_topic_arb
    try:
        with httpx.Client(timeout=30.0) as c:
            r = c.post(f"{API}/bot{cfg.telegram_bot_token}/sendMessage", data=data)
        if r.status_code != 200:
            print(f"[telegram] {r.status_code}: {r.text[:200]}", file=sys.stderr)
            return False
        time.sleep(pause)          # respect 1 msg/sec/chat
        return True
    except Exception as e:
        print(f"[telegram] send failed (silent): {e}", file=sys.stderr)
        return False

def format_opportunity(o: Opportunity, net, est, flag, tier, cfg) -> str:
    e = lambda s: html.escape(str(s))
    emoji = _TIER_EMOJI.get(tier, "⚫")
    promo = " (促銷)" if o.apr_is_promotional else ""
    lines = [f"{emoji} <b>Earn 機會 | {e(o.exchange.upper())}</b>", "",
             f"{e(o.asset)} 活期 {o.apr*100:.1f}%{promo}"]
    if net is not None:
        mode = "自有資金" if cfg.own_funds_mode else f"借款 {((o.borrow_apr_same_asset or 0)*100):.1f}%"
        lines.append(f"淨利差 ≈ {net*100:.1f}% 年化 ({mode})")
    if est.get("est_net") is not None:
        lines.append(f"參考 {cfg.ref_capital:,.0f} × {est['holding_days']} 天 ≈ +${est['est_net']:,.0f}")
    if o.end_date:
        lines.append(f"⏳ 活動至 {o.end_date.isoformat()}({flag})")
    if o.source_url:
        lines.append(f"🔗 {e(o.source_url)}")
    lines.append(f"⚠️ 來源: {e(o.apr_source)}（顯示值未必可持續,進場前於 App 確認）")
    return "\n".join(lines)

def format_digest(graded: list[tuple], cfg) -> str:
    """graded = [(Opportunity, net, tier)]. Compact baseline summary."""
    lines = [f"🟡 <b>套利哨兵 | OKX 利率基線</b> ({len(graded)} 項)"]
    for o, net, tier in graded:
        apr = f"{o.apr*100:.2f}%" if o.apr is not None else "—"
        lines.append(f"{_TIER_EMOJI.get(tier,'⚫')} {html.escape(o.asset)} {apr}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run to verify pass** — PASS (2 passed).
- [ ] **Step 5: Commit**

```bash
git add arb-sentinel/arb_sentinel/notify.py arb-sentinel/tests/test_notify.py
git commit -m "feat(arb-sentinel): Telegram notifier (HTML parse_mode, topic 1390, 1s spacing)

HTML escaping avoids MarkdownV2 decimal-point escaping pain; respects per-chat rate limit."
git push origin main
```

### Task 8: `run.py` + `__main__.py` — orchestrate one task

**Files:** Create `arb_sentinel/run.py`, `arb_sentinel/__main__.py`; Test `tests/test_run.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_run.py
import datetime
from arb_sentinel.models import Opportunity
from arb_sentinel import run as run_mod

def test_run_rates_grades_and_notifies(monkeypatch, cfg, tmp_path):
    sample = [Opportunity(exchange="okx", category="flexible_earn", asset="USDC",
                          apr=0.06, apr_source="api")]   # 6% → ACT_NOW
    monkeypatch.setattr(run_mod.okx, "collect_rates", lambda c: (sample, []))
    sent = []
    monkeypatch.setattr(run_mod.notify, "send_message", lambda text, c, **kw: sent.append(text) or True)
    n = run_mod.run_rates(cfg, state_path=tmp_path / "s.json", today=datetime.date(2026, 6, 16))
    assert n == 1 and len(sent) == 1
    # second identical run is deduped → no send
    n2 = run_mod.run_rates(cfg, state_path=tmp_path / "s.json", today=datetime.date(2026, 6, 16))
    assert n2 == 0 and len(sent) == 1
```

- [ ] **Step 2: Run to verify fail** — FAIL.

- [ ] **Step 3: Implement**

```python
# arb_sentinel/run.py
import datetime, sys
from .collectors import okx
from . import engine, notify
from .state import State

def _today():
    return datetime.date.today()

def run_rates(cfg, state_path="state/state.json", today=None) -> int:
    """Collect OKX rates → grade → dedup → alert actionable. Returns #notifications sent."""
    today = today or _today()
    st = State(state_path)
    opps, errors = okx.collect_rates(cfg)
    for err in errors:
        print(f"[collect] {err}", file=sys.stderr)
    sent = 0
    for o in opps:
        borrow = 0.0 if cfg.own_funds_mode else (o.borrow_apr_same_asset or 0.0)
        net = engine.net_spread(o, borrow)
        flag = engine.time_flag(o, today, cfg.default_horizon_days)
        tier = engine.classify(net, flag, o, cfg)
        if st.should_notify(o, tier, cfg):
            est = engine.estimate_yield(o, net, cfg)
            if notify.send_message(notify.format_opportunity(o, net, est, flag, tier, cfg), cfg):
                sent += 1
        st.record(o, tier)
    return sent

def run_digest(cfg, state_path="state/state.json", today=None) -> int:
    """Post a compact baseline rate digest (proves the pipeline; not deduped)."""
    today = today or _today()
    opps, errors = okx.collect_rates(cfg)
    for err in errors:
        print(f"[collect] {err}", file=sys.stderr)
    graded = []
    for o in opps:
        net = engine.net_spread(o, 0.0 if cfg.own_funds_mode else (o.borrow_apr_same_asset or 0.0))
        flag = engine.time_flag(o, today, cfg.default_horizon_days)
        graded.append((o, net, engine.classify(net, flag, o, cfg)))
    return 1 if (graded and notify.send_message(notify.format_digest(graded, cfg), cfg)) else 0

def run_test(cfg) -> int:
    return 1 if notify.send_message("✅ 套利哨兵 wiring test → topic OK", cfg) else 0
```

```python
# arb_sentinel/__main__.py
import argparse, sys
from .config import load_settings
from . import run as run_mod

def main(argv=None):
    p = argparse.ArgumentParser(prog="arb_sentinel")
    p.add_argument("--task", required=True,
                   choices=["rates", "digest", "test", "announcements", "depeg", "exits"])
    args = p.parse_args(argv)
    cfg = load_settings()
    dispatch = {"rates": run_mod.run_rates, "digest": run_mod.run_digest, "test": lambda c: run_mod.run_test(c)}
    fn = dispatch.get(args.task)
    if fn is None:
        print(f"[run] task '{args.task}' not implemented yet (later milestone)", file=sys.stderr)
        return 0
    n = fn(cfg)
    print(f"[run] task={args.task} notifications={n}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run to verify pass** — `.venv/bin/python -m pytest tests/ -v` → all green.
- [ ] **Step 5: Commit**

```bash
git add arb-sentinel/arb_sentinel/run.py arb-sentinel/arb_sentinel/__main__.py arb-sentinel/tests/test_run.py
git commit -m "feat(arb-sentinel): run orchestrator + CLI (rates/digest/test tasks)

run_rates dedups via state; digest posts baseline; test verifies Telegram wiring.
Unimplemented tasks no-op with a log line (filled in at later milestones)."
git push origin main
```

### Task 9: launchd wiring + manual end-to-end verification

**Files:** Create `scripts/run-task.sh`, `launchd/com.arbsentinel.rates.plist`

- [ ] **Step 1: `scripts/run-task.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
TASK="${1:?usage: run-task.sh <task>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec "$ROOT/.venv/bin/python" -m arb_sentinel --task "$TASK"
```

```bash
chmod +x arb-sentinel/scripts/run-task.sh
```

- [ ] **Step 2: `launchd/com.arbsentinel.rates.plist`** — `StartCalendarInterval` every 2 h, 08:00–22:00 TW (sleep-tolerant: runs once on wake)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.arbsentinel.rates</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/Users/pochenkuo/AI/new_financial-report-system/arb-sentinel/scripts/run-task.sh</string>
    <string>rates</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/Users/pochenkuo/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string></dict>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>10</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>14</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>16</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>20</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>22</integer><key>Minute</key><integer>0</integer></dict>
  </array>
  <key>StandardOutPath</key><string>/Users/pochenkuo/Library/Logs/arbsentinel-rates.log</string>
  <key>StandardErrorPath</key><string>/Users/pochenkuo/Library/Logs/arbsentinel-rates.log</string>
  <key>RunAtLoad</key><false/>
</dict></plist>
```

- [ ] **Step 3: Manual verification — Telegram wiring** (requires real `.env` with the two Telegram values copied from `finance-workflows/.env`)

Run: `cd arb-sentinel && cp .env.example .env` then fill `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`; then:
`.venv/bin/python -m arb_sentinel --task test`
Expected: `[run] task=test notifications=1` AND a "✅ wiring test" message appears in topic **1390**.

- [ ] **Step 4: Manual verification — real OKX digest**

Run: `.venv/bin/python -m arb_sentinel --task digest`
Expected: `notifications=1` AND a 🟡 digest with live USDT/USDC ≈2.5%, BTC ≈0.5%, ETH ≈1.5% in topic 1390. (Confirms keyless OKX call + grading + Telegram end-to-end.)

- [ ] **Step 5: Install launchd job**

```bash
cp arb-sentinel/launchd/com.arbsentinel.rates.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.arbsentinel.rates.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.arbsentinel.rates.plist
launchctl list | grep arbsentinel   # expect the label listed
```

- [ ] **Step 6: Commit**

```bash
git add arb-sentinel/scripts/run-task.sh arb-sentinel/launchd/com.arbsentinel.rates.plist
git commit -m "feat(arb-sentinel): launchd rates job (StartCalendarInterval, sleep-tolerant)

8 fixed times/day (run-once-on-wake); StartInterval avoided (drops during sleep)."
git push origin main
```

**M1 done when:** all unit tests pass, `--task test` and `--task digest` both post to topic 1390, and the launchd job is loaded.

---

## 7. M2–M6 — design-locked roadmap (each expands into its own detailed plan)

### M2 — Engine completeness, config, digest, dedup polish
- **What:** the §5/§5.4 logic is already built in M1; M2 hardens it — full est-yield in alerts, the 🟡 **daily WATCH digest** (batch WATCH-tier into one message, spec §8.2), and exposes every threshold from `config.yaml`. Add `--task digest` to a once-daily launchd time.
- **Files:** extend `engine.py`, `notify.py` (`format_daily_digest`), `run.py` (`run_daily_digest`).
- **Acceptance:** repeated runs never double-alert the same standing rate; WATCH items collapse into one daily message; thresholds change behaviour when edited in `config.yaml` (test-covered).

### M3 — Announcement layer + LLM extraction  *(the only LLM milestone)*
- **What:** collect promotions the rate APIs can't see. Sources, by stability: **Bitget public announcements API** `GET /api/v2/public/annoucements` (keyless; note the baked-in typo), then HTML scrape of Binance/OKX announcement list pages via the existing `web-fetch` capability, then X/TG as last resort. Feed each *new* announcement's title+body to `llm.py` → `{activity_name, start_date, end_date, apr, min_hold_days, entry_asset, subsidy_note, directional_risk}` → Opportunity(category="promotion") → engine → alert.
- **Files:** `collectors/announcements.py`, `llm.py`, `launchd/com.arbsentinel.announcements.plist` (hourly, `StartCalendarInterval`).
- **Fault tolerance:** HTML structure changes must downgrade gracefully (log + skip), never crash (spec §2.4, §10.3). Only NEW (un-seen) announcements hit the LLM → cost is bounded to a few calls/day.
- **LLM billing — see §8 (decision required).**
- **Acceptance:** a sample promo announcement parses to correct dates/APR; `TOO_LATE` activities are filtered; LLM is called only on un-seen announcements.

### M4 — Signed Binance + Bitget collectors, cross-exchange borrow
- **What:** read-only-key collectors. **Binance** `GET /sapi/v1/simple-earn/flexible/list` (HMAC-SHA256 hex signature + `X-MBX-APIKEY` + `timestamp`/`recvWindow`); fields `asset`/`latestAnnualPercentageRate`/`tierAnnualPercentageRate`/`canPurchase`. **Bitget** `GET /api/v2/earn/savings/product` etc. (base64 HMAC-SHA256 prehash signing; headers `ACCESS-KEY/SIGN/PASSPHRASE/TIMESTAMP`); APR is **tiered in `apyList[]`** — take `currentApy` (handle `apyType` single/ladder). Add `borrow` collectors (Binance `next-hourly-interest-rate`, signed) and compute `best_borrow_apr(asset)` = min across exchanges; engine switches from own-funds to true net-spread when `own_funds_mode: false`.
- **Files:** `collectors/binance.py`, `collectors/bitget.py`, `normalizer.py` (now justified — 3 divergent shapes), `engine.py` (cross-exchange borrow lookup), signing helpers (stdlib `hmac`/`hashlib`/`base64`).
- **User dependency:** create **read-only** keys (steps already given) and fill `.env`. Add `binance, bitget` to `config.yaml` `exchanges`.
- **Acceptance:** signed calls succeed with a read-only key; Bitget tiered APY parsed correctly; net-spread uses cheapest cross-exchange borrow.

### M5 — Exit detection + de-peg monitoring
- **What:** spec §7 over `state.json` `active_positions` — 4 triggers (approaching activity end ≤ `exit_lead_days`; past `min_hold_until`; rate halved below entry × `rate_drop_ratio`; stablecoin ticker deviates > `depeg_bps` from 1.0). De-peg uses the already-built `okx.collect_depeg` + Binance/Bitget public tickers.
- **Files:** `exits.py`, `run.py` (`run_exits`, `run_depeg`), `launchd/com.arbsentinel.depeg.plist`.
- **Reality:** de-peg "every 15–30 min" is **best-effort only** on a sleeping laptop (launchd run-once-on-wake). Schedule hourly; document the limitation. A position is added to `active_positions` manually (or via a small `--add-position` helper) when the user actually enters a trade.
- **Acceptance:** a seeded position fires each of the 4 exit messages under the right conditions.

### M6 — Bybit (optional), dual-investment, hardening
- **What:** Bybit adapter behind the same Collector interface; `dual_investment` category with `directional_risk=True` (always WATCH); resilience — per-collector retry/backoff, short response cache, explicit rate-limit throttling (OKX 20/2s, Bitget 10/s, Telegram 1/s).
- **Acceptance:** a simulated exchange outage degrades to other sources without crashing; rate limits never exceeded under burst.

---

## 8. M3 LLM billing plan (decision required — §9)

The announcement parser is the **only** LLM use, runs **a few times/day** on *new* announcements only, and must stay **off both Claude pools** (subscription pool *and* the post-2026-06-15 Claude Code credit pool). It is a programmatic API call from Python, never `claude -p`.

| Option | Model | Billing | Setup | Quality on date/APR extraction | Cost |
|---|---|---|---|---|---|
| **A — Groq (recommended)** | Llama 3.3 70B (or current) | Groq pay-as-you-go (often free tier) | **none** — `GROQ_API_KEY` already in `finance-workflows/.env` | Good with a tight JSON-schema prompt; verify on dates | ~$0 |
| **B — Anthropic API** | Claude Haiku | Anthropic API credit (separate, cheap pool) | new: `console.anthropic.com` key + a little credit | Best on subtle date/subsidy nuance | a few ¢/day |

**Recommendation:** start with **Option A (Groq)** — zero new setup, zero cost, key already present, and extraction of structured fields from short announcement text is well within Llama's range. Build `llm.py` with a strict JSON-schema prompt and a validation/repair step (brace-balanced JSON extract, never bare-line parse). Add a **quality gate**: if Groq's date/APR extraction proves unreliable on real announcements, switch the same `llm.py` interface to **Option B (Haiku)** — it's a one-line client swap behind the interface. Never wire `claude -p`.

---

## 9. Open decisions for the user (confirm before/at execution; none block M1)

1. **M3 LLM provider** — Groq (recommended, free, key exists) vs Anthropic Haiku (better, needs new key+credit). *Default: Groq with a Haiku upgrade path.*
2. **Scheduling aggressiveness** — passive (run-once-on-wake, battery-friendly, alerts only when laptop is awake) vs active `pmset` wakes for guaranteed cadence (battery cost). *Default: passive + reuse the existing morning wake; opt into pmset later if cadence matters.*
3. **Telegram credentials** — copy the two shared values into `arb-sentinel/.env` (self-contained, recommended) vs read `finance-workflows/.env` directly (no duplication, slight coupling). *Default: copy into own `.env`.*
4. **own_funds_mode** — M1 ships `true` (net_spread = earn APR, no borrow). Flip to `false` at M4 once cross-exchange borrow rates exist. *Default: true for M1.*

---

## 10. Self-review (against the spec)

- **§0 design philosophy (filter > scrape; time-window first-class; APR source skepticism):** time-window is a first-class engine stage (`time_flag`, M1); every Opportunity carries `apr_source` and alerts print it (`format_opportunity`); "rather miss than spam" enforced by dedup + thresholds. ✅
- **§1 monitoring scope:** assets BTC/ETH/USDT/USDC in `config.yaml`; categories enumerated in `Opportunity.category`; exchanges phased OKX(M1)→Binance/Bitget(M4)→Bybit(M6). ✅
- **§2 feasibility:** replaced with *verified* §1-of-plan facts (live-tested). ✅
- **§3 architecture (5 stages):** collectors → normalizer → engine → state → notifier all present as modules. ✅
- **§4 Opportunity schema:** `models.py`, with corrected dedup id. ✅
- **§5 engine (spread/time/est/grade):** `engine.py`, fully test-covered in M1. ✅
- **§6 state/dedup:** `state.py` (renotify-delta + tier-upgrade), `active_positions` carried for M5. ✅
- **§7 exit detection:** M5, all 4 triggers. ✅
- **§8 Telegram formats:** `notify.py` (opportunity, digest; exit format at M5). ✅
- **§9 milestones:** mapped M1–M6 (§3 of plan). ✅
- **§10 hard constraints:** read-only keys (M4 steps), no transfer/trade code anywhere, collectors never raise, rate-limit respect (M6 throttle + 1s Telegram spacing), APR source labelled, time-window mandatory, secrets/state/logs gitignored. ✅
- **§11 config.yaml:** created verbatim-ish in Task 1. ✅
- **Placeholder scan:** M1 tasks contain complete code + exact commands; M2–M6 are explicitly scoped as design roadmap (not placeholders — each becomes its own detailed plan). ✅
- **Type consistency:** `Opportunity`, `stable_id`, `net_spread/time_flag/estimate_yield/classify`, `State.should_notify/record`, `notify.send_message/format_opportunity/format_digest`, `run_rates/run_digest/run_test` names are consistent across all tasks. ✅
```
