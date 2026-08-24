"""Aggregate + dedupe overnight financial news RSS for morning-briefing.

Why exists: `morning-briefing` has always been数字 only (FRED/Yahoo/TWSE).
Adding a news source directly to the workflow would flood Claude with ~135
raw headlines per day — expensive and noisy. This script does the
deterministic pre-processing (fetch → normalize → dedupe → time-window) so
the prompt receives a curated ≤80-item list, tagged by feed.

Design constraints:
- Free public RSS only (FJ paid feed not available, and their free feed
  is empty — verified 2026-08-24).
- Window is dynamic: from `last_briefing_ts` (parsed from
  `reports/morning-briefing/_history.jsonl`) to now. Weekends and holidays
  therefore auto-widen the window, no special-casing needed.
- Dedup is two-pass: (1) canonical URL match; (2) title fuzzy match
  (lowercased alnum-only, prefix 60 chars). This is intentionally simple —
  a false-negative here just leaves a dup for Claude to merge, which is
  cheap. A false-positive would silently drop news, which is expensive.
- No LLM. Ranking is done later by the prompt.

Output: JSON on stdout (or --out) with shape:
  {
    "window_start": "2026-08-23T22:00:00+08:00",
    "window_end":   "2026-08-24T05:30:00+08:00",
    "counts": {"feed_name": <items after dedup>, ...},
    "items": [
      {"ts": iso, "feed": name, "title": str, "url": str, "summary": str},
      ...
    ]
  }
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
from zoneinfo import ZoneInfo

import feedparser
import httpx

# Verified live + fresh 2026-08-24. See probe in fetch_news_digest tests.
FEEDS = [
    ("marketwatch",  "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("cnbc",         "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("coindesk",     "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("bloomberg",    "https://feeds.bloomberg.com/markets/news.rss"),
    ("yahoo",        "https://finance.yahoo.com/news/rssindex"),
    ("investing",    "https://www.investing.com/rss/news_25.rss"),
]

TPE = ZoneInfo("Asia/Taipei")
UTC = ZoneInfo("UTC")

# Default window (used when no _history.jsonl is available): 18h back.
DEFAULT_WINDOW_HOURS = 18
# Hard ceiling — never look further back than this even if history says so.
MAX_WINDOW_HOURS = 72

UA = "Mozilla/5.0 finance-workflows/morning-briefing"


def _now_tpe() -> dt.datetime:
    return dt.datetime.now(TPE)


def _fetch(url: str, timeout: int = 15) -> bytes:
    r = httpx.get(url, timeout=timeout, follow_redirects=True,
                  headers={"User-Agent": UA})
    r.raise_for_status()
    return r.content


def _entry_ts(entry) -> dt.datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        v = entry.get(key)
        if v:
            try:
                return dt.datetime(*v[:6], tzinfo=UTC).astimezone(TPE)
            except Exception:
                continue
    return None


_TITLE_STRIP = re.compile(r"[^a-z0-9]+")


def _canonical_url(url: str) -> str:
    """Strip query strings + fragments so tracking URLs collide with clean ones."""
    if not url:
        return ""
    u = url.split("#", 1)[0].split("?", 1)[0].rstrip("/")
    return u.lower()


def _title_key(title: str) -> str:
    """Lowercased alnum-only, whitespace stripped, first 60 chars.

    Whitespace is stripped (not just collapsed) so "25bp" and "25 bp" —
    the same story typeset differently across feeds — produce the same key.
    False-positive risk of over-collapsing is low at 60-char prefix and
    much cheaper than the false-negative of leaving syndicated dupes.
    """
    s = _TITLE_STRIP.sub(" ", (title or "").lower())
    return "".join(s.split())[:60]


def _summary_from_entry(entry) -> str:
    """Best-effort short summary — strip HTML, cap at 240 chars."""
    raw = entry.get("summary") or entry.get("description") or ""
    txt = re.sub(r"<[^>]+>", " ", raw)
    txt = " ".join(txt.split())
    return txt[:240]


def _read_last_briefing_ts(root: pathlib.Path) -> dt.datetime | None:
    """Parse the most recent morning-briefing history entry's date, if any.

    History is jsonl; the last non-blank line is the newest. We use the file's
    mtime as a fallback because the date field is a bare 'YYYY-MM-DD' — we
    interpret it as "briefing generated during that TPE morning ~06:00" and
    take 08:00 TPE that day as the window anchor.
    """
    hist = root / "reports" / "morning-briefing" / "_history.jsonl"
    if not hist.exists():
        return None
    try:
        last = None
        for line in hist.read_text().splitlines():
            line = line.strip()
            if line:
                last = line
        if not last:
            return None
        obj = json.loads(last)
        d = obj.get("date")
        if not d:
            return None
        return dt.datetime.fromisoformat(d + "T08:00:00").replace(tzinfo=TPE)
    except Exception:
        return None


def compute_window(root: pathlib.Path,
                   now: dt.datetime | None = None) -> tuple[dt.datetime, dt.datetime]:
    """Window = [last_briefing_ts .. now], clamped to MAX_WINDOW_HOURS."""
    now = now or _now_tpe()
    last = _read_last_briefing_ts(root)
    if last is None:
        start = now - dt.timedelta(hours=DEFAULT_WINDOW_HOURS)
    else:
        start = last
    floor = now - dt.timedelta(hours=MAX_WINDOW_HOURS)
    if start < floor:
        start = floor
    return start, now


def fetch_all(window_start: dt.datetime,
              window_end: dt.datetime) -> list[dict]:
    """Fetch all feeds, keep only entries inside the window, return raw items."""
    out = []
    for name, url in FEEDS:
        try:
            raw = _fetch(url)
        except Exception as e:
            print(f"[news_digest] {name}: fetch failed — {e}", file=sys.stderr)
            continue
        f = feedparser.parse(raw)
        for entry in f.entries:
            ts = _entry_ts(entry)
            if ts is None or not (window_start <= ts <= window_end):
                continue
            out.append({
                "ts": ts.isoformat(timespec="minutes"),
                "_ts_dt": ts,
                "feed": name,
                "title": (entry.get("title") or "").strip(),
                "url": (entry.get("link") or "").strip(),
                "summary": _summary_from_entry(entry),
            })
    return out


def dedupe(items: list[dict]) -> list[dict]:
    """Two-pass dedupe. Later items win only if strictly newer.

    Pass 1: exact canonical URL match.
    Pass 2: title fuzzy key match (in case the same story got syndicated with
    a different URL structure).
    """
    by_url: dict[str, dict] = {}
    for it in items:
        key = _canonical_url(it["url"])
        if not key:
            key = f"_notitle_{it['title']}"
        cur = by_url.get(key)
        if cur is None or it["_ts_dt"] > cur["_ts_dt"]:
            by_url[key] = it
    stage1 = list(by_url.values())

    by_title: dict[str, dict] = {}
    for it in stage1:
        key = _title_key(it["title"])
        if not key:
            key = it["url"]
        cur = by_title.get(key)
        if cur is None or it["_ts_dt"] > cur["_ts_dt"]:
            by_title[key] = it
    return list(by_title.values())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, help="write JSON here (default: stdout)")
    ap.add_argument("--root", type=pathlib.Path,
                    default=pathlib.Path(__file__).resolve().parent.parent,
                    help="finance-workflows/ root")
    args = ap.parse_args(argv)

    ws, we = compute_window(args.root)
    raw = fetch_all(ws, we)
    deduped = dedupe(raw)
    deduped.sort(key=lambda x: x["_ts_dt"], reverse=True)

    counts: dict[str, int] = {}
    for it in deduped:
        counts[it["feed"]] = counts.get(it["feed"], 0) + 1

    payload = {
        "window_start": ws.isoformat(timespec="minutes"),
        "window_end": we.isoformat(timespec="minutes"),
        "counts": counts,
        "items": [{k: v for k, v in it.items() if not k.startswith("_")}
                  for it in deduped],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
        print(f"[news_digest] wrote {len(deduped)} items to {args.out}",
              file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
