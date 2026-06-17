import datetime
from arb_sentinel import run as run_mod


def test_run_announcements_alerts_new_promo_then_dedups(monkeypatch, cfg, tmp_path):
    cfg.announcement_llm = True   # this test exercises the quantitative LLM path
    ann = {"_exchange": "bitget", "annId": "A1", "annTitle": "USDGO 補貼活動", "annDesc": "...", "annUrl": "http://x"}
    monkeypatch.setattr(run_mod.announcements, "fetch_all", lambda *a, **kw: ([ann], []))
    monkeypatch.setattr(run_mod.llm, "extract_promo", lambda title, body, **kw: {
        "is_promotion": True, "activity_name": "USDGO", "start_date": "2026-06-01",
        "end_date": "2026-07-15", "apr": 0.12, "min_hold_days": 14,
        "entry_asset": "USDT", "subsidy_note": "convert 補貼", "directional_risk": False})
    sent = []
    monkeypatch.setattr(run_mod.notify, "send_message", lambda text, c, **kw: sent.append(text) or True)
    n = run_mod.run_announcements(cfg, state_path=tmp_path / "s.json",
                                  today=datetime.date(2026, 6, 16), pause=0)
    assert n == 1 and len(sent) == 1           # 12% promo, OK_TIME -> ACT_NOW -> alert
    assert "USDT" in sent[0]

    # second run: announcement already seen -> no LLM call, no alert
    def _boom(*a, **k):
        raise AssertionError("LLM must not be called for an already-seen announcement")
    monkeypatch.setattr(run_mod.llm, "extract_promo", _boom)
    n2 = run_mod.run_announcements(cfg, state_path=tmp_path / "s.json",
                                   today=datetime.date(2026, 6, 16), pause=0)
    assert n2 == 0 and len(sent) == 1


def test_run_announcements_skips_non_promo(monkeypatch, cfg, tmp_path):
    cfg.announcement_llm = True
    ann = {"_exchange": "bitget", "annId": "B1", "annTitle": "系統維護公告", "annDesc": "...", "annUrl": "u"}
    monkeypatch.setattr(run_mod.announcements, "fetch_all", lambda *a, **kw: ([ann], []))
    monkeypatch.setattr(run_mod.llm, "extract_promo", lambda title, body, **kw: {"is_promotion": False})
    monkeypatch.setattr(run_mod.notify, "send_message", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no send")))
    n = run_mod.run_announcements(cfg, state_path=tmp_path / "s.json",
                                  today=datetime.date(2026, 6, 16), pause=0)
    assert n == 0


def test_run_announcements_headsup_batches_promos(monkeypatch, cfg, tmp_path):
    # default cfg has no announcement_llm -> deterministic heads-up path (no LLM)
    anns = [
        {"_exchange": "okx", "annId": "O1", "annTitle": "OKX Flash Earn is Now Live", "annUrl": "u1"},
        {"_exchange": "bitget", "annId": "B9", "annTitle": "Scheduled Maintenance: Email", "annUrl": "u2"},
    ]
    monkeypatch.setattr(run_mod.announcements, "fetch_all", lambda *a, **kw: (anns, []))
    monkeypatch.setattr(run_mod.llm, "extract_promo",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no LLM in heads-up mode")))
    sent = []
    monkeypatch.setattr(run_mod.notify, "send_message", lambda text, c, **kw: sent.append(text) or True)
    n = run_mod.run_announcements(cfg, state_path=tmp_path / "s.json")
    assert n == 1 and len(sent) == 1
    assert "Flash Earn" in sent[0] and "Maintenance" not in sent[0]   # only the promo batched
