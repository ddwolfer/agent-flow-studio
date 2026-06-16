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
