import datetime
from arb_sentinel.models import Opportunity
from arb_sentinel import run as run_mod

def test_run_rates_grades_and_notifies(monkeypatch, cfg, tmp_path):
    sample = [Opportunity(exchange="okx", category="flexible_earn", asset="USDC",
                          apr=0.06, apr_source="api")]   # 6% -> ACT_NOW
    monkeypatch.setattr(run_mod.okx, "collect_rates", lambda c: (sample, []))
    sent = []
    monkeypatch.setattr(run_mod.notify, "send_message", lambda text, c, **kw: sent.append(text) or True)
    n = run_mod.run_rates(cfg, state_path=tmp_path / "s.json", today=datetime.date(2026, 6, 16))
    assert n == 1 and len(sent) == 1
    # second identical run is deduped -> no send
    n2 = run_mod.run_rates(cfg, state_path=tmp_path / "s.json", today=datetime.date(2026, 6, 16))
    assert n2 == 0 and len(sent) == 1


def test_borrow_rates_takes_cheapest_across_exchanges(monkeypatch, cfg):
    monkeypatch.setattr(run_mod.okx, "collect_borrow", lambda c: ({"USDT": 0.025, "BTC": 0.005}, []))
    monkeypatch.setattr(run_mod.binance, "collect_borrow", lambda c: ({"USDT": 0.034, "ETH": 0.02}, []))
    best = run_mod.borrow_rates(cfg)
    assert best["USDT"] == 0.025      # OKX cheaper than Binance
    assert best["BTC"] == 0.005       # only OKX
    assert best["ETH"] == 0.02        # only Binance


def test_run_digest_consults_borrow_in_borrow_mode(monkeypatch, cfg):
    import types
    cfg2 = types.SimpleNamespace(**{**cfg.__dict__, "own_funds_mode": False})
    o = Opportunity(exchange="okx", category="flexible_earn", asset="USDT", apr=0.03, apr_source="api")
    monkeypatch.setattr(run_mod, "collect_all_rates", lambda c: ([o], []))
    called = {"borrow": False}
    monkeypatch.setattr(run_mod, "borrow_rates",
                        lambda c: called.__setitem__("borrow", True) or {"USDT": 0.03})
    monkeypatch.setattr(run_mod.notify, "send_message", lambda text, c, **kw: True)
    run_mod.run_digest(cfg2)
    assert called["borrow"] is True   # digest now subtracts borrow in borrow-mode (was a no-op bug)
