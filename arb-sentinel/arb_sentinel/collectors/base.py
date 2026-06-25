import time
import httpx

# Retry only transient classes: HTTP 5xx, 429 (rate limit), and TransportError
# subclasses (ConnectError / ReadTimeout / NetworkError). Deterministic 4xx
# (400/401/403/404) burn the retry budget for no benefit and should fail fast.
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
# Backoff sleeps BEFORE retries [1] and [2]. Total wall-clock cap = 1.5s,
# small enough that a 2h job doesn't notice but enough to clear a typical
# network blip / single 5xx bounce.
_BACKOFF_SECONDS = (0, 0.5, 1.0)


def get_json(url: str, params: dict | None = None, timeout: float = 15.0):
    """GET -> (json, None) on success, (None, error_str) on persistent failure.
    Never raises. Retries up to 2 times (3 total attempts) on transient
    failures only (5xx, 429, httpx.TransportError); 4xx responses fail fast."""
    last_err = None
    for attempt, backoff in enumerate(_BACKOFF_SECONDS):
        if backoff:
            time.sleep(backoff)
        try:
            with httpx.Client(timeout=timeout) as c:
                r = c.get(url, params=params)
            if r.status_code == 200:
                return r.json(), None
            if r.status_code not in _RETRYABLE_STATUS:
                return None, f"{url} HTTP {r.status_code}"
            last_err = f"{url} HTTP {r.status_code}"
        except httpx.TransportError as e:
            last_err = f"{url} {type(e).__name__}: {e}"
        except Exception as e:
            # Non-transport (JSON decode, etc.): fail fast, retrying won't help.
            return None, f"{url} {type(e).__name__}: {e}"
    return None, last_err
