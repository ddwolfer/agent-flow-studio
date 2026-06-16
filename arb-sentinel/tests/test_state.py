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
