"""Announcement collector.

M3 source: Bitget public announcements API (no key, verified path — the 'annoucements'
typo is real). Returns raw announcement dicts; the LLM (llm.py) does the structured
extraction downstream. OKX/Binance announcement HTML scraping is deferred (fragile) —
TODO M3-proper. Never raises."""
import httpx

BITGET_ANN = "https://api.bitget.com/api/v2/public/annoucements"   # typo path is real
PROMO_TYPES = ("latest_news", "product_updates")                  # Bitget promo types

OKX_ANN = "https://www.okx.com/api/v5/support/announcements"       # official public, keyless
OKX_PROMO_TYPES = ("latest-events", "announcements-others")        # OKX promo/event types


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


def fetch_okx(timeout=20.0):
    """OKX official public announcements (keyless), promo/event types only. Normalised
    to the Bitget shape (annId/annTitle/annDesc/annUrl/annType/cTime). OKX's list has no
    body, so annDesc is empty and the LLM classifies from the title. Never raises."""
    anns, errors = [], []
    for ann_type in OKX_PROMO_TYPES:
        try:
            with httpx.Client(timeout=timeout) as c:
                r = c.get(OKX_ANN, params={"annType": ann_type})
            if r.status_code != 200:
                errors.append(f"okx ann {ann_type} HTTP {r.status_code}"); continue
            j = r.json()
            if str(j.get("code")) != "0":
                errors.append(f"okx ann {ann_type} code {j.get('code')}: {j.get('msg')}")
                continue
            for page in (j.get("data") or []):
                for d in (page.get("details") or []):
                    anns.append({"_exchange": "okx", "annId": d.get("url"),
                                 "annTitle": d.get("title"), "annDesc": "",
                                 "annUrl": d.get("url"), "annType": d.get("annType"),
                                 "cTime": d.get("pTime")})
        except Exception as e:
            errors.append(f"okx ann {ann_type} {type(e).__name__}: {e}")
    return anns, errors


def fetch_all(cfg=None, language="zh_CN"):
    """All exchange announcements, each tagged with `_exchange`. Bitget + OKX (both
    official public APIs). Binance has no official announcements API (only an unofficial
    bapi the spec warns against) — deferred. Never raises."""
    anns, errors = [], []
    b, e1 = fetch_bitget(language=language)
    for a in b:
        a["_exchange"] = "bitget"
    o, e2 = fetch_okx()
    return b + o, e1 + e2
