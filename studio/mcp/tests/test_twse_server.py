import importlib.util, pathlib


def _load():
    p = pathlib.Path(__file__).parents[1] / "servers" / "twse_server.py"
    spec = importlib.util.spec_from_file_location("twse_server", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_pick_row_for_stock():
    m = _load()
    rows = [
        {"Code": "2317", "ClosingPrice": "100.0", "TradeVolume": "1000"},
        {"Code": "2408", "ClosingPrice": "55.5", "TradeVolume": "2000"},
    ]
    assert m._row_for(rows, "Code", "2408") == {
        "Code": "2408",
        "ClosingPrice": "55.5",
        "TradeVolume": "2000",
    }
    assert m._row_for(rows, "Code", "9999") == {"error": "stock 9999 not found"}
