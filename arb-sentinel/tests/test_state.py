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

def test_corrupt_non_dict_state_recovers(tmp_path, cfg):
    p = tmp_path / "state.json"
    p.write_text("[1, 2, 3]", "utf-8")          # valid JSON but wrong shape
    st = State(p)                                # must not raise
    assert st.should_notify(_opp(0.06), ACT_NOW, cfg) is True


def test_save_is_atomic_no_partial_files(tmp_path, cfg):
    # Non-atomic Path.write_text leaves a half-written state.json if killed
    # mid-write — __init__ then resets silently and re-broadcasts every alert.
    # Atomic save writes to a temp sibling, fsync, then os.replace.
    import os
    p = tmp_path / "state.json"
    st = State(p)
    st.record(_opp(0.06), ACT_NOW)
    siblings = [f.name for f in tmp_path.iterdir()]
    # No leftover .tmp / .partial — replace happened atomically.
    assert all(not name.startswith("state.json.") or name == "state.json"
               for name in siblings), f"unexpected leftover sibling: {siblings}"
    assert os.path.exists(p)


def test_corrupt_state_is_backed_up_before_reset(tmp_path, cfg):
    # When the on-disk JSON is unparseable (mid-write kill, disk error), the
    # reset must back up the broken file as state.json.corrupt-<ts> so we can
    # recover seen-set context after the fact instead of losing it forever.
    p = tmp_path / "state.json"
    p.write_text("{not-valid-json", "utf-8")
    st = State(p)                                # must not raise
    backups = [f for f in tmp_path.iterdir() if "corrupt" in f.name]
    assert len(backups) == 1, f"expected one backup, got {[b.name for b in tmp_path.iterdir()]}"
    assert backups[0].read_text("utf-8") == "{not-valid-json"
    # Fresh state behaves like an empty store
    assert st.should_notify(_opp(0.06), ACT_NOW, cfg) is True


def test_default_state_path_is_absolute(tmp_path, monkeypatch):
    # Calling State() with no path should default to an absolute path under
    # the package's parent dir, NOT cwd-relative "state/state.json". Otherwise
    # any harness that invokes run_rates without `cd $ROOT` writes to a
    # different state and re-broadcasts every alert.
    monkeypatch.chdir(tmp_path)                 # cwd is now a clean temp dir
    st = State()                                 # default path
    import pathlib
    assert pathlib.Path(st.path).is_absolute()
    # And it should not resolve under our temp cwd — proving cwd-independence.
    assert tmp_path not in pathlib.Path(st.path).parents
