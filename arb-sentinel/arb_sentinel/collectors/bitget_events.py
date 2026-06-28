"""Bitget event-page scraper for PoolX + Launchpool.

These two products are NOT exposed via Bitget's public announcement API and
NOT in the community wrapper (verified 2026-06-28). They're UI-only products
on /events/{poolx,launchpool} backed by XHR endpoints that require browser-
class JS execution (CloudFlare 16-byte challenge tokens block direct curl on
the chunk URLs).

Pragmatic approach: scrape the SSR HTML — Bitget server-renders the
「進行中(N) 即將開始(N) 已結束」 counts (both ASCII and full-width parens
observed). When N transitions upward, fire a heads-up directing the user
back to the page for details (which token / which pool — too dynamic to
scrape reliably). Never raises."""
import re
import httpx

PAGES = (
    ("PoolX",      "https://www.bitget.com/zh-TC/events/poolx"),
    ("Launchpool", "https://www.bitget.com/zh-TC/events/launchpool"),
)

# Two ASCII or full-width brackets after 進行中 / 即將開始. Brackets must match
# (open and close same width) — defends against the pattern being spliced.
_ACTIVE_RE   = re.compile(r"進行中\s*[（(](\d+)[）)]")
_UPCOMING_RE = re.compile(r"即將開始\s*[（(](\d+)[）)]")

# Browser-shape UA — without it Bitget sometimes serves a stub HTML.
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def fetch_event_status(timeout: float = 20.0):
    """Return ([{page, url, active, upcoming}], errors). Never raises.

    `page` ∈ {"PoolX", "Launchpool"}; `active` / `upcoming` are ints.
    A page whose HTML doesn't yield BOTH counts is reported via `errors`
    and omitted from the item list — better to alert "我看不懂這頁了" than
    silently default to 0 (which would suppress real alerts forever)."""
    items, errors = [], []
    for page, url in PAGES:
        try:
            with httpx.Client(timeout=timeout, headers={"User-Agent": _UA},
                              follow_redirects=True) as c:
                r = c.get(url)
            if r.status_code != 200:
                errors.append(f"bitget-events {page} HTTP {r.status_code}")
                continue
            text = r.text
            a = _ACTIVE_RE.search(text)
            u = _UPCOMING_RE.search(text)
            if not a or not u:
                errors.append(
                    f"bitget-events {page}: pattern not found "
                    f"(SSR layout may have changed)")
                continue
            items.append({
                "page": page,
                "url": url,
                "active": int(a.group(1)),
                "upcoming": int(u.group(1)),
            })
        except Exception as e:
            errors.append(f"bitget-events {page} {type(e).__name__}: {e}")
    return items, errors
