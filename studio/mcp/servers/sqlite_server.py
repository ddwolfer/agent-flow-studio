import os, sqlite3, pathlib
from mcp.server.fastmcp import FastMCP

DB = os.environ.get("STUDIO_DB_PATH", "")
SCHEMA = pathlib.Path(__file__).parents[3] / "financial-report-system" / "db" / "schema.sql"

def _conn():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def _ensure_schema():
    pathlib.Path(DB).parent.mkdir(parents=True, exist_ok=True)
    con = _conn()
    have = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {"eason_training", "eason_daily", "eason_picks"}.issubset(have) and SCHEMA.exists():
        con.executescript(SCHEMA.read_text())
        con.commit()
    con.close()

def _query(sql, params=None):
    con = _conn()
    cur = con.execute(sql, params or [])
    if cur.description:
        out = [dict(r) for r in cur.fetchall()]
    else:
        con.commit(); out = {"rowcount": cur.rowcount}
    con.close()
    return out

def _create_record(table, values: dict):
    cols = ",".join(values.keys())
    ph = ",".join("?" for _ in values)
    con = _conn()
    cur = con.execute(f"INSERT INTO {table} ({cols}) VALUES ({ph})", list(values.values()))
    con.commit(); rid = cur.lastrowid; con.close()
    return {"inserted_id": rid}

def _update_records(table, values: dict, where: dict):
    setc = ",".join(f"{k}=?" for k in values)
    wherec = " AND ".join(f"{k}=?" for k in where)
    con = _conn()
    cur = con.execute(f"UPDATE {table} SET {setc} WHERE {wherec}",
                      list(values.values()) + list(where.values()))
    con.commit(); n = cur.rowcount; con.close()
    return {"updated": n}

mcp = FastMCP("sqlite")

@mcp.tool()
def query(sql: str, params: list | None = None):
    """Run any SQL. SELECT returns rows (list of dict); else returns {rowcount}."""
    _ensure_schema(); return _query(sql, params)

@mcp.tool()
def create_record(table: str, values: dict):
    """INSERT one record (dict of column->value) into table."""
    _ensure_schema(); return _create_record(table, values)

@mcp.tool()
def update_records(table: str, values: dict, where: dict):
    """UPDATE rows in table; set `values` where all `where` equalities match."""
    _ensure_schema(); return _update_records(table, values, where)

if __name__ == "__main__":
    mcp.run()
