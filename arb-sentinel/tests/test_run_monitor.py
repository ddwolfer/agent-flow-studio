import datetime, types
from arb_sentinel import run as run_mod
from arb_sentinel.models import Opportunity

def test_run_depeg_alerts_and_dedups(monkeypatch, cfg, tmp_path):
    o = Opportunity(exchange="okx", category="stable_depeg", asset="USDC-USDT",
                    apr=None, apr_source="api", raw_snapshot={"last": "0.99"})
    monkeypatch.setattr(run_mod.okx, "collect_depeg", lambda c, pairs=("USDC-USDT",): ([o], []))
    sent = []
    monkeypatch.setattr(run_mod.notify, "send_message", lambda t, c, **k: sent.append(t) or True)
    n = run_mod.run_depeg(cfg, state_path=tmp_path / "s.json")
    assert n == 1 and len(sent) == 1            # 100 bps > depeg_bps 30
    n2 = run_mod.run_depeg(cfg, state_path=tmp_path / "s.json")
    assert n2 == 0                              # same deviation -> deduped

def test_run_exits_fires_for_seeded_position(monkeypatch, cfg, tmp_path):
    monkeypatch.setattr(run_mod, "collect_all_rates", lambda c: ([], []))
    monkeypatch.setattr(run_mod.okx, "collect_depeg", lambda c, pairs=("USDC-USDT",): ([], []))
    sent = []
    monkeypatch.setattr(run_mod.notify, "send_message", lambda t, c, **k: sent.append(t) or True)
    run_mod.add_position({"exchange": "bitget", "asset": "USDGO",
                          "min_hold_until": "2026-06-15", "activity_end_date": None,
                          "entry_apr": 0.12}, state_path=tmp_path / "s.json")
    n = run_mod.run_exits(cfg, state_path=tmp_path / "s.json", today=datetime.date(2026, 6, 16))
    assert n >= 1 and any("已滿最低持有" in m for m in sent)
