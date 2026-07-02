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
    binance_api_key: str = ""; binance_api_secret: str = ""
    bitget_api_key: str = ""; bitget_api_secret: str = ""; bitget_api_passphrase: str = ""
    groq_api_key: str = ""
    announcement_llm: bool = False
    # ── carry-guardian (Slice E) ─────────────────────────────────────────
    telegram_topic_carry: str = ""
    carry_enabled: bool = False
    carry_loan_order_id: str = ""       # "" = auto-take first active order
    carry_loan_coin: str = "USDC"
    carry_pledge_coin: str = "BTC"
    carry_earn_asset: str = "USDGO"
    carry_pair: str = "USDGOUSDC"
    # LTV thresholds (decimals; carry.py normalises pledgeRate from percent)
    ltv_watch: float = 0.72
    ltv_alert: float = 0.78
    ltv_critical: float = 0.82
    margin_call_ltv: float = 0.85
    liquidation_ltv: float = 0.91
    # Payout audit
    savings_apr_tiers: list = None      # [[cap|null, apr_decimal], ...]
    payout_ratio_floor: float = 0.9
    # Borrow rate (per-hour decimals, same normalisation as collector)
    borrow_hour_rate_warn: float = 0.0000057
    borrow_hour_rate_alert: float = 0.0000080
    net_spread_floor: float = 0.02
    # USDGO depth
    bid_floor_warn: float = 0.9990
    bid_floor_critical: float = 0.9970
    depth_multiple: float = 2.0


def _load_dotenv(path: pathlib.Path) -> None:
    """Minimal .env loader that survives three real-world copy-paste hazards
    without pulling in python-dotenv:

    1. `export FOO=bar` — strip the leading "export " so the key becomes FOO,
       not "export FOO".
    2. `TOKEN="abc"` / `TOKEN='abc'` — strip matched surrounding quotes so the
       token doesn't carry the quotation marks (would 401 against Telegram).
    3. Empty env var shadowing — `os.environ.setdefault` is a no-op when the
       variable EXISTS, including empty string. An empty TELEGRAM_BOT_TOKEN
       in ~/.zshrc would otherwise silently kill notify even with a valid
       .env. Override only when the existing value is empty.

    Real (non-empty) shell env always wins over .env."""
    if not path.exists():
        return
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if k.startswith("export "):
            k = k[len("export "):].strip()
        v = v.strip()
        # Strip matched surrounding quotes; preserve quotes that don't match.
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        # setdefault would no-op on an empty-string env; override that case.
        if not os.environ.get(k):
            os.environ[k] = v


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
        binance_api_key=os.environ.get("BINANCE_API_KEY", ""),
        binance_api_secret=os.environ.get("BINANCE_API_SECRET", ""),
        bitget_api_key=os.environ.get("BITGET_API_KEY", ""),
        bitget_api_secret=os.environ.get("BITGET_API_SECRET", ""),
        bitget_api_passphrase=os.environ.get("BITGET_API_PASSPHRASE", ""),
        groq_api_key=os.environ.get("GROQ_API_KEY", ""),
        announcement_llm=raw.get("announcement_llm", False),
        # ── carry-guardian ──────────────────────────────────────────────
        telegram_topic_carry=os.environ.get("TELEGRAM_TOPIC_CARRY", ""),
        **_carry_settings(raw.get("carry") or {}),
    )


def _carry_settings(c: dict) -> dict:
    """Extract carry-guardian settings from the YAML `carry:` block, with
    defaults matching Settings dataclass defaults for every field."""
    default_tiers = [[100000, 0.10], [1000000, 0.065], [None, 0.04]]
    return {
        "carry_enabled": bool(c.get("enabled", False)),
        "carry_loan_order_id": str(c.get("loan_order_id", "") or ""),
        "carry_loan_coin": str(c.get("loan_coin", "USDC") or "USDC"),
        "carry_pledge_coin": str(c.get("pledge_coin", "BTC") or "BTC"),
        "carry_earn_asset": str(c.get("earn_asset", "USDGO") or "USDGO"),
        "carry_pair": str(c.get("pair", "USDGOUSDC") or "USDGOUSDC"),
        "ltv_watch": float(c.get("ltv_watch", 0.72)),
        "ltv_alert": float(c.get("ltv_alert", 0.78)),
        "ltv_critical": float(c.get("ltv_critical", 0.82)),
        "margin_call_ltv": float(c.get("margin_call_ltv", 0.85)),
        "liquidation_ltv": float(c.get("liquidation_ltv", 0.91)),
        "savings_apr_tiers": c.get("savings_apr_tiers") or default_tiers,
        "payout_ratio_floor": float(c.get("payout_ratio_floor", 0.9)),
        "borrow_hour_rate_warn": float(c.get("borrow_hour_rate_warn", 0.0000057)),
        "borrow_hour_rate_alert": float(c.get("borrow_hour_rate_alert", 0.0000080)),
        "net_spread_floor": float(c.get("net_spread_floor", 0.02)),
        "bid_floor_warn": float(c.get("bid_floor_warn", 0.9990)),
        "bid_floor_critical": float(c.get("bid_floor_critical", 0.9970)),
        "depth_multiple": float(c.get("depth_multiple", 2.0)),
    }
