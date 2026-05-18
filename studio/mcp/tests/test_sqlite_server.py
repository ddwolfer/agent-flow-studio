import os, sqlite3, tempfile, importlib.util, pathlib

def _load(db):
    os.environ["STUDIO_DB_PATH"] = db
    p = pathlib.Path(__file__).parents[1] / "servers" / "sqlite_server.py"
    spec = importlib.util.spec_from_file_location("sqlite_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def test_query_create_update_roundtrip(tmp_path):
    db = str(tmp_path / "f.db")
    m = _load(db)
    m._ensure_schema()
    m._create_record("eason_picks", {"ticker": "2330", "pick_date": "2026-05-18", "name": "TSMC", "status": "active"})
    rows = m._query("SELECT ticker,status FROM eason_picks WHERE pick_date=?", ["2026-05-18"])
    assert rows == [{"ticker": "2330", "status": "active"}]
    m._update_records("eason_picks", {"status": "closed"}, {"ticker": "2330"})
    rows = m._query("SELECT status FROM eason_picks WHERE ticker=?", ["2330"])
    assert rows == [{"status": "closed"}]

def test_schema_autoinit_creates_three_tables(tmp_path):
    db = str(tmp_path / "g.db")
    m = _load(db); m._ensure_schema()
    con = sqlite3.connect(db)
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"eason_training", "eason_daily", "eason_picks"}.issubset(names)
