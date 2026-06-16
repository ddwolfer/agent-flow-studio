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
