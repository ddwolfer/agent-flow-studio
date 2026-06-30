"""Bitget event scraper for PoolX + Launchpool.

These two products are NOT in Bitget's documented announcements API and NOT
in the community wrapper, but the **real** XHR endpoints used by the
events pages ARE keyless. Captured via Chrome DevTools 2026-06-30:

  POST /v1/finance/poolx/product/count             body {}
  POST /v1/finance/poolx/product/page/list/new     body {myProjects:false,status:2,pageSize:900,pre:false}
  POST /v1/finance/launchpool/product/count        body {}
  POST /v1/finance/launchpool/product/list/v2      body {matchType:0,sortType:1,status:2,pageSize:10}

`/count` returns running / waiting / ended numbers — exact match to the
DOM's "進行中(N) 即將開始(N)" once JS has hydrated.
`/list` returns full project rows with reward coin + stake coin + APR +
total rewards + project IDs. The IDs let us state-track at the
**per-project** level rather than relying on a rising-edge of a count,
which is far more robust (a project ending and a new one starting in the
same poll window won't be missed).

NOTE: this REPLACES the earlier SSR-scraping approach (commit 20de6f7) which
was always reading the static "(0)(0) 暫無項目" placeholder Bitget renders
server-side before JS hydration. That code never fired an alert.

Never raises."""
import httpx

_BASE = "https://www.bitget.com"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_HEADERS_TPL = {
    "User-Agent": _UA,
    "Content-Type": "application/json;charset=UTF-8",
    "language": "zh_TW",
    "Accept": "application/json, text/plain, */*",
}

_POOLX_COUNT = "/v1/finance/poolx/product/count"
_POOLX_LIST  = "/v1/finance/poolx/product/page/list/new"
_LAUNCH_COUNT = "/v1/finance/launchpool/product/count"
_LAUNCH_LIST  = "/v1/finance/launchpool/product/list/v2"

PAGES = (
    {
        "page": "PoolX",
        "url": "https://www.bitget.com/zh-TC/events/poolx",
        "count_path": _POOLX_COUNT,
        "list_path": _POOLX_LIST,
        "list_body": {"myProjects": False, "status": 2,
                      "pageSize": 900, "pre": False},
    },
    {
        "page": "Launchpool",
        "url": "https://www.bitget.com/zh-TC/events/launchpool",
        "count_path": _LAUNCH_COUNT,
        "list_path": _LAUNCH_LIST,
        "list_body": {"matchType": 0, "sortType": 1, "status": 2, "pageSize": 10},
    },
)


def _post_json(path: str, body: dict, timeout: float) -> dict:
    """Plain JSON POST to Bitget. Browser-shape headers; no CF cookies needed.
    Returns the parsed response dict or raises (caught by caller)."""
    headers = dict(_HEADERS_TPL)
    # The actual page would set referer to the corresponding events page; we
    # use a generic one. Bitget doesn't enforce path-match.
    headers["referer"] = f"{_BASE}/zh-TC/events/"
    with httpx.Client(timeout=timeout) as c:
        r = c.post(_BASE + path, headers=headers, json=body)
    if r.status_code != 200:
        raise httpx.HTTPStatusError(
            f"HTTP {r.status_code}", request=r.request, response=r)
    return r.json()


def _parse_project_row(row: dict) -> dict:
    """Extract the user-facing fields from a Bitget pool product row.
    `productCoinName` = reward token; `productSubList[0].productSubCoinName`
    = stake token; APR is on the sub-list. End time is unix ms."""
    sub_list = row.get("productSubList") or []
    sub = sub_list[0] if sub_list else {}
    return {
        "id": str(row.get("id") or ""),
        "reward_coin": row.get("productCoinName") or "?",
        "stake_coin": sub.get("productSubCoinName") or "?",
        "apr_percent": sub.get("apr"),                   # string like "20.88"
        "total_rewards": row.get("totalRewards"),        # string
        "end_time_ms": row.get("endTime"),               # string ms epoch
        "detail_url": row.get("productDetailLinkUrl"),
    }


def fetch_pool_page(page_cfg: dict, timeout: float = 20.0) -> dict:
    """Fetch one page (PoolX or Launchpool). Returns:
      {page, url, running_num, wait_start_num, projects: [{...}], error?: str}
    Never raises."""
    try:
        c = _post_json(page_cfg["count_path"], {}, timeout)
    except Exception as e:
        return {"page": page_cfg["page"], "url": page_cfg["url"],
                "error": f"count {type(e).__name__}: {e}"}
    if str(c.get("code")) != "200":
        return {"page": page_cfg["page"], "url": page_cfg["url"],
                "error": f"count code {c.get('code')}: {c.get('msg')}"}
    cdata = c.get("data") or {}
    try:
        running_num = int(cdata.get("runningNum") or 0)
        wait_start_num = int(cdata.get("waitStartNum") or 0)
    except (ValueError, TypeError):
        return {"page": page_cfg["page"], "url": page_cfg["url"],
                "error": "count: non-numeric runningNum/waitStartNum"}

    # If there is no active project, skip the list call — it's a wasted RTT.
    projects = []
    if running_num > 0:
        try:
            lst = _post_json(page_cfg["list_path"], page_cfg["list_body"], timeout)
        except Exception as e:
            # Surface as a partial result — we still have the counts.
            return {"page": page_cfg["page"], "url": page_cfg["url"],
                    "running_num": running_num,
                    "wait_start_num": wait_start_num,
                    "projects": [],
                    "error": f"list {type(e).__name__}: {e}"}
        if str(lst.get("code")) == "200":
            items = (lst.get("data") or {}).get("items") or \
                    (lst.get("data") or {}).get("data") or []
            for row in items:
                if isinstance(row, dict):
                    p = _parse_project_row(row)
                    if p["id"]:
                        projects.append(p)
    return {
        "page": page_cfg["page"],
        "url": page_cfg["url"],
        "running_num": running_num,
        "wait_start_num": wait_start_num,
        "projects": projects,
    }


def fetch_event_status(timeout: float = 20.0):
    """Return ([per_page_status], errors). Never raises. Each item:
      {page, url, running_num, wait_start_num, projects: [{...}]}
    Errors land in the second list as 'page: msg' strings."""
    items, errors = [], []
    for cfg in PAGES:
        result = fetch_pool_page(cfg, timeout=timeout)
        if "error" in result:
            errors.append(f"{result['page']}: {result['error']}")
        # Always surface the result if we have at least the counts; otherwise drop.
        if "running_num" in result:
            items.append(result)
    return items, errors
