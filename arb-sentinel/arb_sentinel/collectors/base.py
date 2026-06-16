import httpx


def get_json(url: str, params: dict | None = None, timeout: float = 15.0):
    """GET -> (json, None) on success, (None, error_str) on any failure. Never raises."""
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.get(url, params=params)
        if r.status_code != 200:
            return None, f"{url} HTTP {r.status_code}"
        return r.json(), None
    except Exception as e:
        return None, f"{url} {type(e).__name__}: {e}"
