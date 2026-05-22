"""_fetch_captions must only use directly-downloadable VTT subtitle tracks.

Regression: a source returned ONLY an HLS/m3u8 subtitle variant whose "url" is
an .m3u8 manifest; a plain GET fetched the manifest text and it was treated as a
transcript (corrupting the source). Now m3u8 tracks are skipped; if none are
plain VTT, _fetch_captions returns None so the caller falls back to ASR."""
import importlib.util, pathlib


def _load():
    p = pathlib.Path(__file__).parents[1] / "mcp" / "servers" / "ytdlp_server.py"
    spec = importlib.util.spec_from_file_location("ytdlp_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def _fake_ydl(info):
    class FakeYDL:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, url, download=False): return info
    return FakeYDL


def test_skips_m3u8_and_picks_direct_vtt(monkeypatch):
    m = _load(); m._MIN_GAP = 0
    info = {"subtitles": {"zh": [
        {"ext": "vtt", "protocol": "m3u8_native",
         "url": "https://manifest.googlevideo.com/api/manifest/hls_x.m3u8"},
        {"ext": "vtt", "protocol": "https", "url": "https://real/captions.vtt"},
    ]}, "automatic_captions": {}}
    monkeypatch.setattr(m.yt_dlp, "YoutubeDL", _fake_ydl(info))
    import requests
    seen = {}
    def fake_get(url, timeout=30):
        seen["url"] = url
        return type("R", (), {"text": "WEBVTT\n\n00:00.000 --> 00:01.000\n你好\n"})()
    monkeypatch.setattr(requests, "get", fake_get)
    out = m._fetch_captions("https://youtu.be/x", ["zh"])
    assert seen["url"] == "https://real/captions.vtt"  # skipped the m3u8 variant
    assert "你好" in out


def test_m3u8_only_returns_none_without_fetching(monkeypatch):
    m = _load(); m._MIN_GAP = 0
    info = {"subtitles": {"zh": [
        {"ext": "vtt", "protocol": "m3u8_native",
         "url": "https://manifest.googlevideo.com/api/manifest/hls_x.m3u8"},
    ]}, "automatic_captions": {}}
    monkeypatch.setattr(m.yt_dlp, "YoutubeDL", _fake_ydl(info))
    import requests
    called = {"n": 0}
    monkeypatch.setattr(requests, "get",
                        lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    assert m._fetch_captions("https://youtu.be/x", ["zh"]) is None
    assert called["n"] == 0  # never GET an m3u8 manifest
