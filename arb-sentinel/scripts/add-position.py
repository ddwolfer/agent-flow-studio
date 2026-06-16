#!/usr/bin/env python3
"""Register an entered position for exit monitoring.
Usage: .venv/bin/python scripts/add-position.py '<json>'   (or pipe JSON on stdin)
JSON fields: exchange, asset, entry_date, min_hold_until, activity_end_date,
             entry_price, entry_apr, ref_amount"""
import json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from arb_sentinel import run

def main(argv):
    raw = argv[1] if len(argv) > 1 else sys.stdin.read()
    pos = json.loads(raw)
    n = run.add_position(pos)
    print(f"added position; active_positions now {n}")

if __name__ == "__main__":
    main(sys.argv)
