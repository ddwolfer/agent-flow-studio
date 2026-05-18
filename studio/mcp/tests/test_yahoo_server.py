import importlib.util, pathlib
def _load():
    p = pathlib.Path(__file__).parents[1] / "servers" / "yahoo_server.py"
    spec = importlib.util.spec_from_file_location("yahoo_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_select_info_fields():
    m = _load()
    raw = {"regularMarketPrice": 950.0, "trailingPE": 25.4, "shortName": "TSMC", "junk": 1}
    assert m._info(raw, "2330.TW") == {"ticker": "2330.TW", "price": 950.0,
                                       "pe": 25.4, "name": "TSMC"}
