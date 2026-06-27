"""Announcement collector.

Bitget + OKX + Binance public announcement feeds (all keyless). Returns raw
announcement dicts; the LLM (llm.py) does the structured extraction downstream
for the LLM path, and looks_like_promo() does it deterministically for the
heads-up path. Never raises."""
import httpx

BITGET_ANN = "https://api.bitget.com/api/v2/public/annoucements"   # typo path is real
# Bitget annTypes — live-probed 2026-06-27. Bitget pushed Earn-style content
# into more than just latest_news + product_updates; `coin_listings` carries
# launch promos / airdrops for new tokens and stock-token products, and
# `trading_competitions_promotions` is the documented promo-only channel
# (currently sparse but emits all real trading-contest activity). Skipping
# `maintenance_system_updates` because it's purely operational.
PROMO_TYPES = (
    "latest_news",
    "product_updates",
    "coin_listings",
    "trading_competitions_promotions",
)

OKX_ANN = "https://www.okx.com/api/v5/support/announcements"       # official public, keyless
OKX_PROMO_TYPES = ("latest-events", "announcements-others")        # OKX promo/event types

# Binance public CMS feed. Verified 2026-06-25: POST /article/list/query is 403
# (WAF), but GET /article/catalog/list/query works without key/UA tricks.
# Catalog IDs (probed live): 49=Latest News (includes Earn campaigns),
# 93=Latest Activities (pure promos), 128=HODLer Airdrops / new-coin airdrops.
BINANCE_ANN = ("https://www.binance.com/bapi/composite/v1/public/cms/"
               "article/catalog/list/query")
BINANCE_PROMO_CATALOGS = ("49", "93", "128")
BINANCE_ARTICLE_URL = "https://www.binance.com/en/support/announcement/{code}"

# Hard cap on pagination per source per launchd cycle. A 24-hour gap rarely
# produces more than a handful of items; cap defends against an infinite
# walk if an upstream API changes its short-page semantics.
_MAX_PAGES = 3

# Deterministic promo detector for heads-up mode (no LLM). Biased to surface.
# Chinese keywords cover both Traditional (OKX/Bitget zh_TW) and Simplified
# (Bitget zh_CN default) — codepoint-exact `in` matching, so 理財 ≠ 理织.
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

# Categories that are 100% promo by definition — every item qualifies, no
# keyword check needed. Catches promos with off-keyword titles like
# "Binance Wallet x Project" (catalog 93) or "Join the Q3 Beautiful Game"
# (OKX latest-events). Bitget's `latest_news` / `product_updates` /
# `coin_listings` are NOT in this set — they mix promos with listing /
# maintenance / 美股 / 合約調整 notices — so they still need the keyword
# filter. `trading_competitions_promotions` IS pure by name and by Bitget's
# own categorisation.
_PURE_PROMO_ANN_TYPES = frozenset({
    "93",                                    # Binance Latest Activities
    "128",                                   # Binance HODLer Airdrops
    "latest-events",                         # OKX promo/event tier
    "trading_competitions_promotions",       # Bitget contest/promo channel
})


def looks_like_promo(title, ann_type=None) -> bool:
    """Cheap promo detector: returns True if either the source category is
    a pure-promo tier (Binance catalog 93/128, OKX latest-events) OR the
    title hits a keyword. Biased to surface (you confirm details in the App)."""
    if ann_type is not None and str(ann_type) in _PURE_PROMO_ANN_TYPES:
        return True
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
    body, so annDesc is empty and the LLM classifies from the title. Walks pages 1..N
    via the `page` query param until a page returns no items or the safety cap fires.
    Never raises."""
    anns, errors = [], []
    for ann_type in OKX_PROMO_TYPES:
        for page in range(1, _MAX_PAGES + 1):
            try:
                with httpx.Client(timeout=timeout) as c:
                    r = c.get(OKX_ANN, params={"annType": ann_type, "page": page})
                if r.status_code != 200:
                    errors.append(f"okx ann {ann_type} HTTP {r.status_code}"); break
                j = r.json()
                if str(j.get("code")) != "0":
                    errors.append(f"okx ann {ann_type} code {j.get('code')}: {j.get('msg')}")
                    break
                page_items = 0
                for page_obj in (j.get("data") or []):
                    for d in (page_obj.get("details") or []):
                        anns.append({"_exchange": "okx", "annId": d.get("url"),
                                     "annTitle": d.get("title"), "annDesc": "",
                                     "annUrl": d.get("url"), "annType": d.get("annType"),
                                     "cTime": d.get("pTime")})
                        page_items += 1
                if page_items == 0:
                    break
            except Exception as e:
                errors.append(f"okx ann {ann_type} {type(e).__name__}: {e}")
                break
    return anns, errors


def fetch_binance(timeout=20.0, page_size=20):
    """Binance public CMS announcements across promo-relevant catalogs. Normalised
    to the Bitget shape (annId/annTitle/annDesc/annUrl/annType/cTime). The catalog
    list endpoint returns titles only — annDesc is empty (LLM/keyword classifies
    from title). Walks pageNo=1..N until a short page (len < page_size) or the
    safety cap fires. Never raises. `annId` is the article `code` (stable hex
    hash; `id` field is also stable but `code` matches the public URL slug)."""
    anns, errors = [], []
    for cat in BINANCE_PROMO_CATALOGS:
        for page_no in range(1, _MAX_PAGES + 1):
            try:
                with httpx.Client(timeout=timeout) as c:
                    r = c.get(BINANCE_ANN, params={
                        "catalogId": cat, "pageNo": page_no, "pageSize": page_size,
                    })
                if r.status_code != 200:
                    errors.append(f"binance ann {cat} HTTP {r.status_code}"); break
                j = r.json()
                if str(j.get("code")) != "000000":
                    errors.append(f"binance ann {cat} code {j.get('code')}: "
                                  f"{j.get('message')}")
                    break
                articles = (j.get("data") or {}).get("articles") or []
                for art in articles:
                    code = art.get("code")
                    if not code:
                        continue
                    anns.append({
                        "_exchange": "binance",
                        "annId": code,
                        "annTitle": art.get("title") or "",
                        "annDesc": "",
                        "annUrl": BINANCE_ARTICLE_URL.format(code=code),
                        "annType": cat,
                        "cTime": str(art.get("releaseDate") or ""),
                    })
                if len(articles) < page_size:
                    break              # short page → no more
            except Exception as e:
                errors.append(f"binance ann {cat} {type(e).__name__}: {e}")
                break
    return anns, errors


def fetch_all(cfg=None, language="zh_CN"):
    """All exchange announcements, each tagged with `_exchange`. ALWAYS
    fetches bitget + okx + binance — every feed is keyless, so there is no
    cost / authentication reason to subset them.

    Deliberately does NOT read `cfg.exchanges` even when cfg is provided:
    that field controls signed RATE collector selection (only the exchanges
    you hold API keys for), which has nothing to do with promo heads-up
    coverage. An operator running `exchanges: [okx]` because OKX is their
    only API key should still receive Binance/Bitget Earn-promo heads-up
    automatically. Never raises."""
    anns, errors = [], []
    b, e1 = fetch_bitget(language=language)
    for a in b:
        a["_exchange"] = "bitget"
    anns.extend(b); errors.extend(e1)
    o, e2 = fetch_okx()
    anns.extend(o); errors.extend(e2)
    bn, e3 = fetch_binance()
    anns.extend(bn); errors.extend(e3)
    return anns, errors
