"""幣安廣場配圖 — 產生「當日結構卡」PNG 並上傳,回傳 imageUrl。

為什麼要有這個:2026-08-04 的 Day 21 回看顯示,連續 21 天純文字貼文
換到 0 粉絲、每篇瀏覽固定卡在 130–356 —— 瓶頸不在內容而在分發。
User 選擇「攻分發」,配圖是第一個可完全自動化的槓桿。

圖怎麼來:沒有 matplotlib,但 headless Chrome 已是既有依賴
(deep-research 用它出 PDF)。所以走 HTML → Chrome 截圖 → PNG,
不新增任何套件。卡片內容一律取自 zone JSON / _extras 的確定性數字,
和貼文同源,不另外計算(否則圖文會對不上,那比沒有圖更糟)。

上傳協定(取自 binance-skills-hub/square-post/scripts/lib.mjs):
  1. POST  v2 /image/presignedUrl   {imageName}   → {presignedUrl, fileTicket}
  2. PUT   <presignedUrl>            檔案 + Content-Type
  3. POST  v2 /image/imageStatus     {fileTicket}  → 輪詢 status==1 → {imageUrl}
  4. 呼叫端把 imageUrl 放進 content/add 的 imageList(最多 4 張)
注意 image 端點是 **v2**、content/add 是 **v1** — 混用會 404。

用法(通常由發文腳本 import,也可單獨測試):
  python square_image.py --demo            # 產圖 + 上傳,印出 imageUrl
  python square_image.py --demo --no-upload # 只產圖,不碰網路
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

import httpx

V1 = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi"
V2 = "https://www.binance.com/bapi/composite/v2/public/pgc/openApi"

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
]

CARD_W, CARD_H = 1200, 675          # 16:9 — 廣場動態牆的標準比例

_POLL_INTERVAL_S = 3
_MAX_POLLS = 10


# ── 卡片 HTML ────────────────────────────────────────────────────────────────
def build_card_html(title: str, subtitle: str, rows: list[tuple[str, str, str]],
                    footer: str) -> str:
    """rows = [(label, value, tone)] where tone ∈ {"", "up", "down", "warn"}."""
    tone_css = {"up": "#26a69a", "down": "#ef5350", "warn": "#f0b90b", "": "#e6edf3"}
    items = "".join(
        f'<div class="row"><span class="lb">{lb}</span>'
        f'<span class="vl" style="color:{tone_css.get(tone, tone_css[""])}">{vl}</span></div>'
        for lb, vl, tone in rows
    )
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{CARD_W}px;height:{CARD_H}px;background:linear-gradient(150deg,#0d1117,#161b22 60%,#1c2128);
color:#e6edf3;font-family:-apple-system,"PingFang TC","Noto Sans TC",system-ui,sans-serif;
padding:56px 64px;display:flex;flex-direction:column;justify-content:space-between}}
.hd{{border-left:6px solid #f0b90b;padding-left:20px}}
h1{{font-size:52px;font-weight:700;line-height:1.15;letter-spacing:-0.5px}}
.sub{{font-size:24px;color:#8b949e;margin-top:12px}}
.rows{{display:flex;flex-direction:column;gap:18px;margin:8px 0}}
.row{{display:flex;justify-content:space-between;align-items:baseline;
border-bottom:1px solid #30363d;padding-bottom:14px}}
.lb{{font-size:28px;color:#8b949e}}
.vl{{font-size:40px;font-weight:600;font-variant-numeric:tabular-nums}}
.ft{{font-size:20px;color:#6e7681;display:flex;justify-content:space-between;align-items:center}}
.tag{{color:#f0b90b;font-weight:600}}
</style></head><body>
<div class="hd"><h1>{title}</h1><div class="sub">{subtitle}</div></div>
<div class="rows">{items}</div>
<div class="ft"><span>{footer}</span><span class="tag">@hamster_crypto</span></div>
</body></html>"""


def find_chrome() -> str | None:
    for p in CHROME_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def render_png(html: str, out_path: pathlib.Path) -> pathlib.Path | None:
    """HTML → PNG via headless Chrome. Returns None if Chrome is unavailable."""
    chrome = find_chrome()
    if not chrome:
        print("[square_image] Chrome not found — skipping image", file=sys.stderr)
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                     encoding="utf-8") as f:
        f.write(html)
        html_path = f.name
    try:
        subprocess.run(
            [chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
             f"--window-size={CARD_W},{CARD_H}",
             f"--screenshot={out_path}", f"file://{html_path}"],
            check=True, capture_output=True, timeout=90,
        )
    except Exception as e:
        print(f"[square_image] render failed: {e}", file=sys.stderr)
        return None
    finally:
        os.unlink(html_path)
    return out_path if out_path.exists() and out_path.stat().st_size > 0 else None


# ── 上傳 ─────────────────────────────────────────────────────────────────────
def _api(endpoint: str, key: str, body: dict, base: str = V2, timeout: float = 45.0):
    r = httpx.post(f"{base}{endpoint}", headers={
        "X-Square-OpenAPI-Key": key,
        "Content-Type": "application/json",
        "clienttype": "binanceSkill",
    }, json=body, timeout=timeout)
    j = r.json()
    if j.get("code") != "000000":
        raise RuntimeError(f"API error [{j.get('code')}]: {j.get('message')}")
    return j.get("data")


def upload_image(key: str, path: pathlib.Path) -> str:
    """presignedUrl → S3 PUT → poll → imageUrl. Raises on failure."""
    data = _api("/image/presignedUrl", key, {"imageName": path.name})
    presigned, ticket = data["presignedUrl"], data["fileTicket"]

    with open(path, "rb") as f:
        put = httpx.put(presigned, content=f.read(),
                        headers={"Content-Type": "image/png"}, timeout=90.0)
    if put.status_code >= 300:
        raise RuntimeError(f"S3 upload failed: {put.status_code}")

    for i in range(_MAX_POLLS):
        st = _api("/image/imageStatus", key, {"fileTicket": ticket})
        if st.get("status") == 1:
            return st["imageUrl"]
        if st.get("status") == 2:
            raise RuntimeError(f"processing failed: {st.get('failedReason')}")
        time.sleep(_POLL_INTERVAL_S)
    raise RuntimeError("image processing poll timed out")


def make_and_upload(key: str, title: str, subtitle: str,
                    rows: list[tuple[str, str, str]], footer: str,
                    out_dir: pathlib.Path, name: str) -> str | None:
    """Full path: card → PNG → upload. Returns imageUrl, or None on any failure.

    Never raises: a missing image must degrade to a text-only post, never
    block publishing. The post is the deliverable; the image is a bonus.
    """
    try:
        png = render_png(build_card_html(title, subtitle, rows, footer),
                         out_dir / f"{name}.png")
        if png is None:
            return None
        return upload_image(key, png)
    except Exception as e:
        print(f"[square_image] degraded to text-only: {e}", file=sys.stderr)
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    out_dir = pathlib.Path(a.out) if a.out else pathlib.Path(tempfile.gettempdir())
    rows = [("BTC", "$63,705", "up"), ("關鍵位", "63,092", "warn"),
            ("ETH", "$1,861", ""), ("恐懼貪婪", "37 · 恐懼", "down")]
    html = build_card_html("結構每日速報", "2026-08-04 · 週二", rows,
                           "價位來自程式化計算 · 非投資建議")
    png = render_png(html, out_dir / "square_card_demo.png")
    if png is None:
        print("render failed"); return 1
    print(f"rendered {png} ({png.stat().st_size // 1024} KB)")
    if a.no_upload:
        return 0
    key = os.environ.get("BINANCE_SQUARE_API_KEY", "").strip()
    if not key:
        print("BINANCE_SQUARE_API_KEY not set", file=sys.stderr); return 2
    print("imageUrl:", upload_image(key, png))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
