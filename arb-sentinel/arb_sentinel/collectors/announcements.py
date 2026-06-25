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

# Deterministic promo detector for heads-up mode (no LLM). Biased to surface.
# Chinese keywords cover both Traditional (OKX/Bitget zh_TW) and Simplified
# (Bitget zh_CN default) — codepoint-exact `in` matching, so 理財 ≠ 理财.
PROMO_KEYWORDS = (
    "earn", "cedefi", "launchpool", "launchpad", "jumpstart", "staking", "stake",
    "savings", "airdrop", "bonus", "reward", "campaign", "trade-to-earn",
    "trade to earn", "boost", "apr", "apy", "yield", "dual investment", "giveaway",
    # Traditional
    "理財", "補貼", "雙幣", "賺幣", "質押", "獎勵", "回饋", "活動",
    # Simplified (Bitget zh_CN returns these)
    "理财", "补贴", "双币", "赚币", "质押", "奖励", "回馈", "活动",
    # Script-identical between Trad/Simp — listed once
    "活期", "空投", "瓜分", "高息",
)


def looks_like_promo(title, ann_type=None) -> bool:
    """Cheap keyword check: does this announcement look like an Earn/yield/reward
    activity worth a heads-up? Biased to surface (you confirm details in the App)."""
    t = (title or "").lower()
    return any(k in t for k in PROMO_KEYWORDS)


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
