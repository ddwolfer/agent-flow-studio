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
