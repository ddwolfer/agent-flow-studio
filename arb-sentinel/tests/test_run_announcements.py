import datetime
from arb_sentinel import run as run_mod


def test_run_announcements_alerts_new_promo_then_dedups(monkeypatch, cfg, tmp_path):
    cfg.announcement_llm = True   # this test exercises the quantitative LLM path
    cfg.groq_api_key = "fake-key-for-test"   # required since Slice 7 fast-fail on missing key
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
    cfg.groq_api_key = "fake-key-for-test"
    ann = {"_exchange": "bitget", "annId": "B1", "annTitle": "系統維護公告", "annDesc": "...", "annUrl": "u"}
    monkeypatch.setattr(run_mod.announcements, "fetch_all", lambda *a, **kw: ([ann], []))
    monkeypatch.setattr(run_mod.llm, "extract_promo", lambda title, body, **kw: {"is_promotion": False})
    monkeypatch.setattr(run_mod.notify, "send_message", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no send")))
    n = run_mod.run_announcements(cfg, state_path=tmp_path / "s.json",
                                  today=datetime.date(2026, 6, 16), pause=0)
    assert n == 0


def _bg_item(page, url, running=0, projects=None):
    return {"page": page, "url": url,
            "running_num": running, "wait_start_num": 0,
            "projects": projects or []}


def _bg_proj(pid, reward, stake="USDT", apr="10.0", rewards="1000"):
    return {"id": pid, "reward_coin": reward, "stake_coin": stake,
            "apr_percent": apr, "total_rewards": rewards,
            "detail_url": f"https://example/{pid}"}


def test_bitget_events_check_fires_on_new_project_id(monkeypatch, cfg, tmp_path):
    # First run: PoolX has 0 projects → no alert (baseline).
    # Second run: PoolX has 3 NEW projects (JTO/BLUAI/O) → alert mentions all 3.
    state_path = tmp_path / "s.json"
    monkeypatch.setattr(run_mod.announcements, "fetch_all", lambda *a, **kw: ([], []))
    sent = []
    monkeypatch.setattr(run_mod.notify, "send_message",
                        lambda text, c, **kw: sent.append(text) or True)
    seq = iter([
        ([_bg_item("PoolX", "https://x"),
          _bg_item("Launchpool", "https://y")], []),
        ([_bg_item("PoolX", "https://x", running=3, projects=[
              _bg_proj("id-JTO", "JTO", stake="BGSOL", apr="20.88"),
              _bg_proj("id-BLUAI", "BLUAI", stake="ETH", apr="5.75"),
              _bg_proj("id-O", "O", stake="BTC", apr="3.90")]),
          _bg_item("Launchpool", "https://y")], []),
    ])
    monkeypatch.setattr(run_mod.bitget_events, "fetch_event_status",
                        lambda *a, **kw: next(seq))
    n1 = run_mod.run_announcements(cfg, state_path=state_path)
    assert n1 == 0 and not sent
    n2 = run_mod.run_announcements(cfg, state_path=state_path)
    assert n2 == 1 and len(sent) == 1
    msg = sent[0]
    assert "BITGET" in msg                  # exchange labelled (memory rule)
    assert "PoolX" in msg
    # All 3 token names surface
    for tok in ("JTO", "BLUAI", "O", "BGSOL", "ETH", "BTC"):
        assert tok in msg, f"missing {tok}: {msg}"


def test_bitget_events_check_silent_when_project_ends(monkeypatch, cfg, tmp_path):
    # Same project IDs across two polls (project hasn't changed) → silent.
    # Project ending and disappearing → still silent (no NEW ids).
    state_path = tmp_path / "s.json"
    monkeypatch.setattr(run_mod.announcements, "fetch_all", lambda *a, **kw: ([], []))
    sent = []
    monkeypatch.setattr(run_mod.notify, "send_message",
                        lambda text, c, **kw: sent.append(text) or True)
    seq = iter([
        ([_bg_item("PoolX", "u", running=2, projects=[
              _bg_proj("id-A", "A"), _bg_proj("id-B", "B")]),
          _bg_item("Launchpool", "v")], []),
        # Same IDs A+B — no alert.
        ([_bg_item("PoolX", "u", running=2, projects=[
              _bg_proj("id-A", "A"), _bg_proj("id-B", "B")]),
          _bg_item("Launchpool", "v")], []),
        # Project A ended, only B left — no NEW ids, must stay silent.
        ([_bg_item("PoolX", "u", running=1, projects=[_bg_proj("id-B", "B")]),
          _bg_item("Launchpool", "v")], []),
    ])
    monkeypatch.setattr(run_mod.bitget_events, "fetch_event_status",
                        lambda *a, **kw: next(seq))
    # First poll: 2 NEW (A,B) → alert
    run_mod.run_announcements(cfg, state_path=state_path)
    assert len(sent) == 1
    sent.clear()
    # Second poll: same IDs → silent
    run_mod.run_announcements(cfg, state_path=state_path)
    assert sent == []
    # Third poll: A ended → silent (no new IDs added)
    run_mod.run_announcements(cfg, state_path=state_path)
    assert sent == []


def test_bitget_events_check_falls_back_to_count_when_list_errored(monkeypatch, cfg, tmp_path):
    # /list failed so projects=[] but running_num jumped — surface a
    # count-only alert (don't lose the signal entirely).
    state_path = tmp_path / "s.json"
    monkeypatch.setattr(run_mod.announcements, "fetch_all", lambda *a, **kw: ([], []))
    sent = []
    monkeypatch.setattr(run_mod.notify, "send_message",
                        lambda text, c, **kw: sent.append(text) or True)
    seq = iter([
        # Baseline: running=0
        ([_bg_item("PoolX", "u")], []),
        # /list errored: projects=[] but running jumped to 3
        ([_bg_item("PoolX", "u", running=3, projects=[])], ["PoolX: list down"]),
    ])
    monkeypatch.setattr(run_mod.bitget_events, "fetch_event_status",
                        lambda *a, **kw: next(seq))
    run_mod.run_announcements(cfg, state_path=state_path)
    assert sent == []
    run_mod.run_announcements(cfg, state_path=state_path)
    assert len(sent) == 1
    assert "3 個項目" in sent[0]


def test_run_announcements_headsup_batches_promos(monkeypatch, cfg, tmp_path):
    # default cfg has no announcement_llm -> deterministic heads-up path (no LLM)
    anns = [
        {"_exchange": "okx", "annId": "O1", "annTitle": "OKX Flash Earn is Now Live", "annUrl": "u1"},
        {"_exchange": "bitget", "annId": "B9", "annTitle": "Scheduled Maintenance: Email", "annUrl": "u2"},
    ]
    monkeypatch.setattr(run_mod.announcements, "fetch_all", lambda *a, **kw: (anns, []))
    monkeypatch.setattr(run_mod.llm, "extract_promo",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no LLM in heads-up mode")))
    # Bitget events check is wired into the heads-up path now (commit 20de6f7+).
    # Stub it to a no-op so this test stays focused on the announcement filter.
    monkeypatch.setattr(run_mod.bitget_events, "fetch_event_status",
                        lambda *a, **kw: ([], []))
    sent = []
    monkeypatch.setattr(run_mod.notify, "send_message", lambda text, c, **kw: sent.append(text) or True)
    n = run_mod.run_announcements(cfg, state_path=tmp_path / "s.json")
    assert n == 1 and len(sent) == 1
    assert "Flash Earn" in sent[0] and "Maintenance" not in sent[0]   # only the promo batched
