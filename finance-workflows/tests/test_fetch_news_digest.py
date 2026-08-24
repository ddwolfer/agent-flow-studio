"""Unit tests for fetch_news_digest — dedup + window logic only.

We do NOT hit the network here — the RSS live-check is a probe run in the
shell driver, not a unit test. This suite pins:

- canonical URL normalization
- title fuzzy-key normalization
- two-pass dedupe keeps newest of duplicates
- window falls back to DEFAULT_WINDOW_HOURS when no history exists
- window uses last briefing timestamp when history is present
- window respects MAX_WINDOW_HOURS ceiling
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

TESTS_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "scripts"))

import fetch_news_digest as nd


def _tpe(y, m, d, hh=0, mm=0):
    return dt.datetime(y, m, d, hh, mm, tzinfo=nd.TPE)


def test_canonical_url_strips_query_and_fragment():
    assert nd._canonical_url("https://x.com/a/?utm=foo") == "https://x.com/a"
    assert nd._canonical_url("https://x.com/a#top") == "https://x.com/a"
    assert nd._canonical_url("https://X.com/a/") == "https://x.com/a"


def test_title_key_alnum_lowercase_prefix():
    a = nd._title_key("Fed's Powell: 'inflation is falling'")
    b = nd._title_key("FED'S POWELL — inflation is falling!!!")
    assert a == b, f"{a!r} != {b!r}"


def test_title_key_collapses_digit_letter_spacing():
    # "25bp" vs "25 bp" is the real case that motivated whitespace stripping.
    a = nd._title_key("Fed cuts rates by 25bp")
    b = nd._title_key("Fed Cuts Rates by 25 bp!")
    assert a == b, f"{a!r} != {b!r}"


def test_dedupe_url_pass_keeps_newest():
    old = {"_ts_dt": _tpe(2026, 8, 24, 5), "url": "https://a.com/x?utm=1",
           "title": "A", "ts": "old", "feed": "f1", "summary": ""}
    new = {"_ts_dt": _tpe(2026, 8, 24, 8), "url": "https://a.com/x",
           "title": "A", "ts": "new", "feed": "f2", "summary": ""}
    out = nd.dedupe([old, new])
    assert len(out) == 1
    assert out[0]["ts"] == "new"


def test_dedupe_title_pass_across_feeds():
    a = {"_ts_dt": _tpe(2026, 8, 24, 5), "url": "https://bbg.com/x",
         "title": "Fed cuts rates by 25bp", "ts": "old", "feed": "bbg", "summary": ""}
    b = {"_ts_dt": _tpe(2026, 8, 24, 6), "url": "https://cnbc.com/y",
         "title": "Fed Cuts Rates by 25 bp!", "ts": "new", "feed": "cnbc", "summary": ""}
    out = nd.dedupe([a, b])
    assert len(out) == 1
    assert out[0]["ts"] == "new"


def test_window_no_history_uses_default(tmp_path):
    now = _tpe(2026, 8, 24, 7)
    ws, we = nd.compute_window(tmp_path, now=now)
    assert we == now
    assert ws == now - dt.timedelta(hours=nd.DEFAULT_WINDOW_HOURS)


def test_window_uses_last_briefing_from_history(tmp_path):
    hist_dir = tmp_path / "reports" / "morning-briefing"
    hist_dir.mkdir(parents=True)
    (hist_dir / "_history.jsonl").write_text(
        json.dumps({"date": "2026-08-22"}) + "\n"
        + json.dumps({"date": "2026-08-23"}) + "\n"
    )
    now = _tpe(2026, 8, 24, 7)
    ws, we = nd.compute_window(tmp_path, now=now)
    assert we == now
    assert ws == _tpe(2026, 8, 23, 8)  # 8/23 08:00 anchor


def test_window_respects_max_ceiling(tmp_path):
    hist_dir = tmp_path / "reports" / "morning-briefing"
    hist_dir.mkdir(parents=True)
    # A stale last briefing 10 days ago should get clamped to MAX_WINDOW_HOURS.
    (hist_dir / "_history.jsonl").write_text(
        json.dumps({"date": "2026-08-14"}) + "\n"
    )
    now = _tpe(2026, 8, 24, 7)
    ws, we = nd.compute_window(tmp_path, now=now)
    assert we - ws == dt.timedelta(hours=nd.MAX_WINDOW_HOURS)


def test_window_history_without_date_falls_back(tmp_path):
    hist_dir = tmp_path / "reports" / "morning-briefing"
    hist_dir.mkdir(parents=True)
    (hist_dir / "_history.jsonl").write_text(json.dumps({"mood": "x"}) + "\n")
    now = _tpe(2026, 8, 24, 7)
    ws, we = nd.compute_window(tmp_path, now=now)
    assert ws == now - dt.timedelta(hours=nd.DEFAULT_WINDOW_HOURS)
