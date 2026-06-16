"""Announcement collector.

M3 source: Bitget public announcements API (no key, verified path — the 'annoucements'
typo is real). Returns raw announcement dicts; the LLM (llm.py) does the structured
extraction downstream. OKX/Binance announcement HTML scraping is deferred (fragile) —
TODO M3-proper. Never raises."""
import httpx

BITGET_ANN = "https://api.bitget.com/api/v2/public/annoucements"   # typo path is real
PROMO_TYPES = ("latest_news", "product_updates")                  # promos live under these


def fetch_bitget(language="zh_CN", timeout=20.0):
    """Return (announcements, errors). Each ann dict has annId, annTitle, annDesc,
    annUrl, annType, cTime. Never raises."""
    anns, errors = [], []
    for ann_type in PROMO_TYPES:
        try:
            with httpx.Client(timeout=timeout) as c:
                r = c.get(BITGET_ANN, params={"language": language, "annType": ann_type})
            if r.status_code != 200:
                errors.append(f"bitget ann {ann_type} HTTP {r.status_code}"); continue
            j = r.json()
            if str(j.get("code")) != "00000":
                errors.append(f"bitget ann {ann_type} code {j.get('code')}: {j.get('msg')}")
                continue
            for a in (j.get("data") or []):
                anns.append(a)
        except Exception as e:
            errors.append(f"bitget ann {ann_type} {type(e).__name__}: {e}")
    return anns, errors
