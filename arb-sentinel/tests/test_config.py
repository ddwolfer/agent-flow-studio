import os
import pytest
from arb_sentinel.config import load_settings, _load_dotenv

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


def test_dotenv_overrides_empty_env(tmp_path, monkeypatch):
    # os.environ.setdefault is a no-op when env var exists, including empty
    # string. Production case: user exports an empty TELEGRAM_BOT_TOKEN in
    # ~/.zshrc accidentally, .env value silently gets ignored → notify
    # disables itself with no warning.
    monkeypatch.setenv("DOTTEST_KEY", "")           # env present but empty
    env = tmp_path / ".env"
    env.write_text("DOTTEST_KEY=from-dotenv\n", "utf-8")
    _load_dotenv(env)
    assert os.environ["DOTTEST_KEY"] == "from-dotenv"


def test_dotenv_does_not_override_real_env(tmp_path, monkeypatch):
    # If the env var is set to a non-empty value, .env must NOT clobber it.
    # Keeps the "real shell env wins over dotfile" contract.
    monkeypatch.setenv("DOTTEST_REAL", "shell-value")
    env = tmp_path / ".env"
    env.write_text("DOTTEST_REAL=dotenv-value\n", "utf-8")
    _load_dotenv(env)
    assert os.environ["DOTTEST_REAL"] == "shell-value"


def test_dotenv_strips_quotes(tmp_path, monkeypatch):
    # User writes TOKEN="abc" (or TOKEN='abc') in .env. Without stripping,
    # os.environ["TOKEN"] becomes '"abc"' and Telegram returns 401 Unauthorized
    # — looks like an auth bug, is actually a parser bug.
    monkeypatch.delenv("DOTTEST_DBL", raising=False)
    monkeypatch.delenv("DOTTEST_SGL", raising=False)
    env = tmp_path / ".env"
    env.write_text('DOTTEST_DBL="hello"\nDOTTEST_SGL=\'world\'\n', "utf-8")
    _load_dotenv(env)
    assert os.environ["DOTTEST_DBL"] == "hello"
    assert os.environ["DOTTEST_SGL"] == "world"


def test_dotenv_handles_export_prefix(tmp_path, monkeypatch):
    # User copies a `export FOO=bar` line from a shell config. Without
    # stripping the "export " prefix, the env var name becomes "export FOO"
    # and FOO never gets set.
    monkeypatch.delenv("DOTTEST_EXPORT", raising=False)
    env = tmp_path / ".env"
    env.write_text("export DOTTEST_EXPORT=ok\n", "utf-8")
    _load_dotenv(env)
    assert os.environ.get("DOTTEST_EXPORT") == "ok"
    assert "export DOTTEST_EXPORT" not in os.environ
