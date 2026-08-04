"""Tests for scripts/square_image.py — 廣場配圖產生與上傳。

最重要的契約在最後一段:**配圖失敗必須降級成純文字發文,絕不能拋例外**。
貼文是交付物,圖只是加分項 —— 如果哪天 Chrome 不在、S3 掛掉或圖片
審核不過,結果應該是「今天那篇沒有圖」,而不是「今天沒發文」。
"""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import square_image as si                                       # noqa: E402


# ── 卡片 HTML ────────────────────────────────────────────────────────────────
def test_card_contains_all_rows_and_headings():
    html = si.build_card_html("標題", "副標", [("BTC", "$63,705", "up")], "註腳")
    for expect in ("標題", "副標", "BTC", "$63,705", "註腳", "@hamster_crypto"):
        assert expect in html


def test_card_tone_colours():
    up = si.build_card_html("t", "s", [("x", "1", "up")], "f")
    down = si.build_card_html("t", "s", [("x", "1", "down")], "f")
    warn = si.build_card_html("t", "s", [("x", "1", "warn")], "f")
    assert "#26a69a" in up and "#ef5350" in down and "#f0b90b" in warn


def test_card_unknown_tone_falls_back_to_default():
    """A typo'd tone must not crash or emit an empty colour."""
    html = si.build_card_html("t", "s", [("x", "1", "nonsense")], "f")
    assert "color:#e6edf3" in html


def test_card_dimensions_match_constants():
    html = si.build_card_html("t", "s", [], "f")
    assert f"width:{si.CARD_W}px" in html and f"height:{si.CARD_H}px" in html


def test_card_is_16_by_9():
    assert round(si.CARD_W / si.CARD_H, 2) == pytest.approx(1.78, abs=0.01)


# ── Chrome 偵測 ──────────────────────────────────────────────────────────────
def test_find_chrome_returns_none_when_absent(monkeypatch):
    monkeypatch.setattr(si.os.path, "exists", lambda p: False)
    assert si.find_chrome() is None


def test_render_png_returns_none_without_chrome(monkeypatch, tmp_path):
    monkeypatch.setattr(si, "find_chrome", lambda: None)
    assert si.render_png("<html></html>", tmp_path / "x.png") is None


# ── 上傳錯誤處理 ─────────────────────────────────────────────────────────────
def test_api_raises_on_non_success_code(monkeypatch):
    class R:
        def json(self):
            return {"code": "220003", "message": "bad key"}
    monkeypatch.setattr(si.httpx, "post", lambda *a, **k: R())
    with pytest.raises(RuntimeError, match="220003"):
        si._api("/image/presignedUrl", "k", {})


def test_upload_raises_when_processing_fails(monkeypatch, tmp_path):
    png = tmp_path / "a.png"
    png.write_bytes(b"\x89PNG")
    seq = [
        {"presignedUrl": "https://s3.example/x", "fileTicket": "T1"},
        {"status": 2, "failedReason": "rejected"},
    ]
    monkeypatch.setattr(si, "_api", lambda *a, **k: seq.pop(0))
    monkeypatch.setattr(si.httpx, "put",
                        lambda *a, **k: type("R", (), {"status_code": 200})())
    with pytest.raises(RuntimeError, match="rejected"):
        si.upload_image("k", png)


def test_upload_raises_when_s3_put_fails(monkeypatch, tmp_path):
    png = tmp_path / "a.png"
    png.write_bytes(b"\x89PNG")
    monkeypatch.setattr(si, "_api", lambda *a, **k: {
        "presignedUrl": "https://s3.example/x", "fileTicket": "T1"})
    monkeypatch.setattr(si.httpx, "put",
                        lambda *a, **k: type("R", (), {"status_code": 403})())
    with pytest.raises(RuntimeError, match="403"):
        si.upload_image("k", png)


# ── 降級契約:make_and_upload 永不拋 ─────────────────────────────────────────
def test_make_and_upload_returns_none_when_render_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(si, "render_png", lambda *a, **k: None)
    assert si.make_and_upload("k", "t", "s", [], "f", tmp_path, "n") is None


def test_make_and_upload_swallows_upload_errors(monkeypatch, tmp_path):
    png = tmp_path / "n.png"
    png.write_bytes(b"\x89PNG")
    monkeypatch.setattr(si, "render_png", lambda *a, **k: png)

    def boom(*a, **k):
        raise RuntimeError("S3 down")
    monkeypatch.setattr(si, "upload_image", boom)
    assert si.make_and_upload("k", "t", "s", [], "f", tmp_path, "n") is None


def test_make_and_upload_returns_url_on_success(monkeypatch, tmp_path):
    png = tmp_path / "n.png"
    png.write_bytes(b"\x89PNG")
    monkeypatch.setattr(si, "render_png", lambda *a, **k: png)
    monkeypatch.setattr(si, "upload_image", lambda k, p: "https://cdn/x.png")
    assert si.make_and_upload("k", "t", "s", [], "f", tmp_path, "n") == "https://cdn/x.png"


# ── 端點版本:image 用 v2、content/add 用 v1(混用會 404)──────────────────
def test_image_endpoints_use_v2_base():
    assert si.V2.endswith("/v2/public/pgc/openApi")


def test_content_endpoint_base_is_v1():
    assert si.V1.endswith("/v1/public/pgc/openApi")
