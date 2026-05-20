"""Tests for the new ytdlp_latest_from_channel tool — channel-feed-based fetch
that avoids the keyword-search heuristic of ytdlp_search_videos.

We only test the NEW tool here; the rest of ytdlp_server.py is the proven copy
from studio/mcp/servers/ and is exercised in studio's own test suite.
"""
import importlib.util, pathlib


def _load():
    p = pathlib.Path(__file__).parents[1] / "mcp" / "servers" / "ytdlp_server.py"
    spec = importlib.util.spec_from_file_location("ytdlp_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


class _FakeYDL:
    """Mimics yt_dlp.YoutubeDL: context manager exposing extract_info()."""
    def __init__(self, *args, **kwargs): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False
    extract_info_return = None  # set by tests
    def extract_info(self, url, download=False):
        # capture what URL the tool hit so we can assert on it
        _FakeYDL.last_url = url
        return _FakeYDL.extract_info_return


def test_latest_from_channel_hits_videos_url_and_maps_entries(monkeypatch):
    m = _load()
    _FakeYDL.extract_info_return = {"entries": [
        {"id": "AAA", "title": "Today's video", "upload_date": "20260521",
         "webpage_url": "https://youtu.be/AAA"},
        {"id": "BBB", "title": "Yesterday's video", "upload_date": "20260520",
         "webpage_url": "https://youtu.be/BBB"},
    ]}
    monkeypatch.setattr(m, "yt_dlp", type("X", (), {"YoutubeDL": _FakeYDL})())
    out = m.ytdlp_latest_from_channel("@crypto_punks", max_results=2)
    # hit the channel's /videos page directly, NOT a ytsearch URL
    assert _FakeYDL.last_url == "https://www.youtube.com/@crypto_punks/videos"
    assert len(out) == 2
    assert out[0] == {"video_id": "AAA", "title": "Today's video",
                      "upload_date": "2026-05-21", "url": "https://youtu.be/AAA"}


def test_handle_without_at_prefix_works(monkeypatch):
    m = _load()
    _FakeYDL.extract_info_return = {"entries": [
        {"id": "X", "title": "T", "upload_date": "20260520",
         "webpage_url": "https://youtu.be/X"}
    ]}
    monkeypatch.setattr(m, "yt_dlp", type("X", (), {"YoutubeDL": _FakeYDL})())
    m.ytdlp_latest_from_channel("crypto_punks", max_results=1)  # no @
    assert _FakeYDL.last_url == "https://www.youtube.com/@crypto_punks/videos"


def test_extract_info_exception_returns_empty(monkeypatch):
    m = _load()
    class Boom(_FakeYDL):
        def extract_info(self, url, download=False):
            raise RuntimeError("network down")
    monkeypatch.setattr(m, "yt_dlp", type("X", (), {"YoutubeDL": Boom})())
    assert m.ytdlp_latest_from_channel("@x", max_results=3) == []


def test_empty_handle_returns_empty():
    m = _load()
    assert m.ytdlp_latest_from_channel("", max_results=5) == []
    assert m.ytdlp_latest_from_channel("@", max_results=5) == []
