"""LLM extraction for announcement promos.

Off BOTH Claude pools by design — uses Groq (GROQ_API_KEY), an OpenAI-compatible
chat endpoint, with JSON mode. Called only on NEW announcements (a few/day), so
cost is bounded. Never raises; returns None on any failure (collector contract)."""
import json, os, sys
import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"   # verified live 2026-06-16, supports JSON mode

_SCHEMA_HINT = (
    '只回一個 JSON 物件,不要任何其他文字。欄位:'
    '{"is_promotion": true/false (是否為「補貼/高息/活動」類促銷,純上架/維護/下架公告為 false),'
    '"activity_name": "字串",'
    '"start_date": "YYYY-MM-DD 或 null",'
    '"end_date": "YYYY-MM-DD 或 null",'
    '"apr_percent": 數字或 null (年化「百分比數值」,例如 12 代表 12%),'
    '"min_hold_days": 整數 (無則 0),'
    '"entry_asset": "入場幣種代號或 null",'
    '"subsidy_note": "補貼/活動條件原文摘要或 null",'
    '"directional_risk": true/false (雙幣投資等有方向性風險為 true)}'
)


def _extract_json(text):
    """Brace-balanced JSON extraction (never bare-line match). Returns dict or None."""
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:
                    return None
    return None


def extract_promo(title, body, api_key=None, model=DEFAULT_MODEL, timeout=40.0):
    """Extract structured promo fields from an announcement. Never raises.
    Returns a dict with `apr` normalised to a DECIMAL (0.12), or None on failure."""
    key = api_key or os.environ.get("GROQ_API_KEY", "")
    if not key:
        return None
    prompt = (f"你是加密貨幣交易所活動公告解析器。{_SCHEMA_HINT}\n\n"
              f"公告標題: {title}\n公告內文: {body or '(無內文)'}")
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(GROQ_URL, headers={"Authorization": f"Bearer {key}"},
                       json={"model": model, "temperature": 0,
                             "response_format": {"type": "json_object"},
                             "messages": [{"role": "user", "content": prompt}]})
        if r.status_code != 200:
            print(f"[llm] groq {r.status_code}: {r.text[:160]}", file=sys.stderr)
            return None
        content = r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[llm] groq failed: {e}", file=sys.stderr)
        return None
    obj = _extract_json(content)
    if not isinstance(obj, dict):
        return None
    apr_pct = obj.get("apr_percent")
    try:
        obj["apr"] = (float(apr_pct) / 100.0) if apr_pct is not None else None
    except (ValueError, TypeError):
        obj["apr"] = None
    return obj
