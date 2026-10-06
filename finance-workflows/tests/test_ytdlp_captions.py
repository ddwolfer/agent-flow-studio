"""_fetch_captions must only use directly-downloadable VTT subtitle tracks.

Regression 1: a source returned ONLY an HLS/m3u8 subtitle variant whose "url" is
an .m3u8 manifest; a plain GET fetched the manifest text and it was treated as a
transcript (corrupting the source). Now m3u8 tracks are skipped; if none are
plain VTT, _fetch_captions returns None so the caller falls back to ASR.

Regression 2 (2026-10-07): the caption URL was fetched with a bare
requests.get (no cookies/UA) → HTTP 429 + Google "Sorry..." bot-check HTML,
which was accepted as captions so whisper never ran. Now the URL is fetched
through the YoutubeDL session (ydl.urlopen) and anything that isn't WEBVTT is
rejected."""
import importlib.util, io, pathlib, types

import pytest

SORRY_PAGE = ('<html><head><meta http-equiv="content-type" content="text/html; '
              'charset=utf-8"/><title>Sorry...</title></head><body>unusual traffic'
              '</body></html>')
VTT = "WEBVTT\n\n00:00.000 --> 00:01.000\n你好\n"


def _load():
    p = pathlib.Path(__file__).parents[1] / "mcp" / "servers" / "ytdlp_server.py"
    spec = importlib.util.spec_from_file_location("ytdlp_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def _fake_ydl(info, bodies=None, seen=None, requests_seen=None):
    """FakeYDL whose urlopen serves `bodies[url]` (str or Exception)."""
    bodies = bodies or {}
    seen = seen if seen is not None else []
    requests_seen = requests_seen if requests_seen is not None else []

    class FakeYDL:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, url, download=False): return info
        def urlopen(self, req):
            url = getattr(req, "url", req)       # yt-dlp Request or plain str
            seen.append(url)
            requests_seen.append(req)
            body = bodies[url]
            if isinstance(body, Exception):
                raise body
            return io.BytesIO(body.encode("utf-8"))
    return FakeYDL


def _forbid_requests(monkeypatch):
    """The bare requests path is the bug; fail loudly if anything uses it."""
    import requests
    def boom(*a, **k):
        raise AssertionError("captions must be fetched via ydl.urlopen, not requests")
    monkeypatch.setattr(requests, "get", boom)


def test_skips_m3u8_and_picks_direct_vtt(monkeypatch):
    m = _load(); m._MIN_GAP = 0
    info = {"subtitles": {"zh": [
        {"ext": "vtt", "protocol": "m3u8_native",
         "url": "https://manifest.googlevideo.com/api/manifest/hls_x.m3u8"},
        {"ext": "vtt", "protocol": "https", "url": "https://real/captions.vtt"},
    ]}, "automatic_captions": {}}
    seen = []
    monkeypatch.setattr(m.yt_dlp, "YoutubeDL",
                        _fake_ydl(info, {"https://real/captions.vtt": VTT}, seen))
    _forbid_requests(monkeypatch)
    out = m._fetch_captions("https://youtu.be/x", ["zh"])
    assert seen == ["https://real/captions.vtt"]  # skipped the m3u8 variant
    assert "你好" in out


def test_m3u8_only_returns_none_without_fetching(monkeypatch):
    m = _load(); m._MIN_GAP = 0
    info = {"subtitles": {"zh": [
        {"ext": "vtt", "protocol": "m3u8_native",
         "url": "https://manifest.googlevideo.com/api/manifest/hls_x.m3u8"},
    ]}, "automatic_captions": {}}
    seen = []
    monkeypatch.setattr(m.yt_dlp, "YoutubeDL", _fake_ydl(info, {}, seen))
    assert m._fetch_captions("https://youtu.be/x", ["zh"]) is None
    assert seen == []  # never GET an m3u8 manifest


def test_bot_check_page_is_rejected_not_returned(monkeypatch):
    m = _load(); m._MIN_GAP = 0
    info = {"subtitles": {}, "automatic_captions": {"en": [
        {"ext": "vtt", "protocol": "https", "url": "https://tt/en.vtt"}]}}
    monkeypatch.setattr(m.yt_dlp, "YoutubeDL",
                        _fake_ydl(info, {"https://tt/en.vtt": SORRY_PAGE}))
    with pytest.raises(RuntimeError, match="bot-check"):
        m._fetch_captions("https://youtu.be/x", ["en"])


def test_bot_page_on_first_lang_falls_through_to_next_lang(monkeypatch):
    m = _load(); m._MIN_GAP = 0
    info = {"subtitles": {}, "automatic_captions": {
        "zh-Hant": [{"ext": "vtt", "protocol": "https", "url": "https://tt/zh.vtt"}],
        "en": [{"ext": "vtt", "protocol": "https", "url": "https://tt/en.vtt"}]}}
    monkeypatch.setattr(m.yt_dlp, "YoutubeDL", _fake_ydl(info, {
        "https://tt/zh.vtt": SORRY_PAGE, "https://tt/en.vtt": VTT}))
    assert "你好" in m._fetch_captions("https://youtu.be/x", ["zh-Hant", "en"])


def test_urlopen_http_error_is_recorded(monkeypatch):
    m = _load(); m._MIN_GAP = 0
    info = {"subtitles": {}, "automatic_captions": {"en": [
        {"ext": "vtt", "protocol": "https", "url": "https://tt/en.vtt"}]}}
    monkeypatch.setattr(m.yt_dlp, "YoutubeDL", _fake_ydl(
        info, {"https://tt/en.vtt": OSError("HTTP Error 429: Too Many Requests")}))
    with pytest.raises(RuntimeError, match="429"):
        m._fetch_captions("https://youtu.be/x", ["en"])


def test_bom_prefixed_vtt_is_accepted():
    m = _load()
    assert m._looks_like_vtt("﻿WEBVTT\n\n")
    assert not m._looks_like_vtt(SORRY_PAGE)
    assert not m._looks_like_vtt("")


def test_bot_page_end_to_end_falls_back_to_whisper(monkeypatch):
    """The exact 2026-10-06 failure: bot page on captions must reach whisper."""
    m = _load(); m._MIN_GAP = 0
    m._TRANSCRIPT_CACHE.clear()
    info = {"subtitles": {}, "automatic_captions": {"en": [
        {"ext": "vtt", "protocol": "https", "url": "https://tt/en.vtt"}]}}
    monkeypatch.setattr(m.yt_dlp, "YoutubeDL",
                        _fake_ydl(info, {"https://tt/en.vtt": SORRY_PAGE}))
    # The old bare-requests path also gets the bot page (as it did in prod).
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: types.SimpleNamespace(
        text=SORRY_PAGE, status_code=429))
    monkeypatch.setattr(m, "_asr", types.SimpleNamespace(
        transcribe=lambda url, **kw: "whisper got the real speech"))
    r = m.ytdlp_transcript_page("https://youtu.be/bot")
    assert r["source"] == "whisper"
    assert "real speech" in r["text"]
    assert "Sorry" not in r["text"]


# ── verbatim-only track selection (2026-10-07) ──────────────────────────────
def _tt(lang, tlang=None):
    q = f"v=x&lang={lang}&kind=asr" + (f"&tlang={tlang}" if tlang else "")
    return {"ext": "vtt", "protocol": "https",
            "url": f"https://www.youtube.com/api/timedtext?{q}"}


DUBBED_EN_VIDEO = {
    # Shape observed live on an auto-dubbed Altcoin Daily upload: the first
    # "zh-Hant" track is the ARABIC dub's ASR machine-translated to Chinese.
    "language": "en",
    "subtitles": {},
    "automatic_captions": {
        "zh-Hant": [_tt("ar", "zh-Hant"), _tt("en", "zh-Hant")],
        "en": [_tt("pt", "en"), _tt("es", "en")],
        "ar-orig": [_tt("ar")],
        "en-orig": [_tt("en")],
    },
}


def test_machine_translations_and_dub_asr_are_never_candidates():
    m = _load()
    cands = m._caption_candidates(DUBBED_EN_VIDEO, ["zh-Hant", "zh-TW", "zh", "en"])
    assert [label for label, _ in cands] == ["auto:en-orig"]
    assert "tlang" not in cands[0][1]["url"]


def test_original_language_chinese_auto_caption_is_kept():
    m = _load()
    info = {"language": "zh-TW", "subtitles": {},
            "automatic_captions": {"zh-TW": [_tt("zh-TW")],
                                   "en": [_tt("zh-TW", "en")]}}
    assert [l for l, _ in m._caption_candidates(info, ["zh-Hant", "zh-TW", "en"])] \
        == ["auto:zh-TW"]


def test_uploader_subtitles_come_first():
    m = _load()
    info = dict(DUBBED_EN_VIDEO, subtitles={"en": [
        {"ext": "vtt", "protocol": "https", "url": "https://human/en.vtt"}]})
    labels = [l for l, _ in m._caption_candidates(info, ["zh-Hant", "en"])]
    assert labels == ["subtitles:en", "auto:en-orig"]


def test_unknown_language_falls_back_to_requested_untranslated_keys():
    m = _load()
    info = {"subtitles": {}, "automatic_captions": {
        "en": [_tt("en")], "ja-orig": [_tt("ja")], "zh-Hant": [_tt("en", "zh-Hant")]}}
    assert [l for l, _ in m._caption_candidates(info, ["zh-Hant", "en"])] == ["auto:en"]


def test_only_translations_available_returns_none_so_whisper_runs(monkeypatch):
    m = _load(); m._MIN_GAP = 0
    info = {"language": "en", "subtitles": {},
            "automatic_captions": {"zh-Hant": [_tt("en", "zh-Hant")]}}
    seen = []
    monkeypatch.setattr(m.yt_dlp, "YoutubeDL", _fake_ydl(info, {}, seen))
    assert m._fetch_captions("https://youtu.be/tr", ["zh-Hant", "en"]) is None
    assert seen == []                                # never fetched a translation
    assert m._VIDEO_LANG["https://youtu.be/tr"] == "en"   # hint kept for whisper


def test_whisper_receives_spoken_language_hint(monkeypatch):
    m = _load(); m._MIN_GAP = 0
    m._TRANSCRIPT_CACHE.clear()
    info = {"language": "en", "subtitles": {}, "automatic_captions": {}}
    monkeypatch.setattr(m.yt_dlp, "YoutubeDL", _fake_ydl(info))
    got = {}
    def fake_transcribe(url, language=None):
        got["language"] = language
        return "spoken english"
    monkeypatch.setattr(m, "_asr", types.SimpleNamespace(transcribe=fake_transcribe))
    r = m.ytdlp_transcript_page("https://youtu.be/en-nocaps")
    assert r["source"] == "whisper" and got["language"] == "en"
