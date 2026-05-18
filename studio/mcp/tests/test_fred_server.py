import importlib.util, pathlib
def _load():
    p = pathlib.Path(__file__).parents[1] / "servers" / "fred_server.py"
    spec = importlib.util.spec_from_file_location("fred_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_pick_latest_and_prev():
    m = _load()
    obs = {"observations": [
        {"date": "2026-03-01", "value": "4.1"},
        {"date": "2026-04-01", "value": "4.3"},
        {"date": "2026-05-01", "value": "."},
    ]}
    assert m._latest(obs) == {"date": "2026-04-01", "value": 4.3,
                              "prev_date": "2026-03-01", "prev_value": 4.1}
