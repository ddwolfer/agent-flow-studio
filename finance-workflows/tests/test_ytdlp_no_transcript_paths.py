"""What happens when a video's speech can't be read (2026-10-07).

- Channel listings skip members-only / upcoming / live uploads (Coin Bureau
  interleaves "Coin Bureau Club" videos into its /videos tab: 4 of 8 newest).
- Caption tracks flagged `impersonate` are fetched with impersonation, like
  yt-dlp's own subtitle downloader, falling back to a plain session request
  only if no impersonation handler is installed.
- With no captions AND no audio, the creator's title/chapters/description is
  returned as source="description" — labelled, never passed off as speech.
"""
import importlib.util, io, pathlib, types


def _load():
    p = pathlib.Path(__file__).parents[1] / "mcp" / "servers" / "ytdlp_server.py"
    spec = importlib.util.spec_from_file_location("ytdlp_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    m._MIN_GAP = 0
    m._TRANSCRIPT_CACHE.clear()
    return m


VTT = "WEBVTT\n\n00:00.000 --> 00:01.000\nhello\n"


def _ydl(info, bodies=None, calls=None, opts_seen=None):
    bodies = bodies or {}
    calls = calls if calls is not None else []

    class FakeYDL:
        def __init__(self, opts=None, *a, **k):
            if opts_seen is not None:
                opts_seen.append(opts or {})
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def extract_info(self, url, download=False): return info
        def urlopen(self, req):
            calls.append(req)
            return io.BytesIO(bodies[getattr(req, "url", req)].encode("utf-8"))
    return FakeYDL


def _entry(vid, availability=None, live_status=None):
    return {"id": vid, "title": vid, "upload_date": "20261006",
            "webpage_url": f"https://youtu.be/{vid}",
            "availability": availability, "live_status": live_status}


# ── listing ─────────────────────────────────────────────────────────────────
def test_members_only_and_live_entries_are_skipped(monkeypatch):
    m = _load()
    opts = []
    info = {"entries": [
        _entry("club1", "subscriber_only"), _entry("public1"),
        _entry("live1", live_status="is_upcoming"), _entry("club2", "subscriber_only"),
        _entry("public2", "public"),
    ]}
    monkeypatch.setattr(m.yt_dlp, "YoutubeDL", _ydl(info, opts_seen=opts))
    out = m.ytdlp_latest_from_channel("@CoinBureau", max_results=2)
    assert [e["video_id"] for e in out] == ["public1", "public2"]
    assert opts[0]["playlistend"] >= 2 + 8          # over-fetch in ONE request


def test_all_unreadable_are_returned_with_reason_not_empty(monkeypatch):
    m = _load()
    info = {"entries": [_entry("club1", "subscriber_only"),
                        _entry("club2", "subscriber_only")]}
    monkeypatch.setattr(m.yt_dlp, "YoutubeDL", _ydl(info))
    out = m.ytdlp_latest_from_channel("@CoinBureau", max_results=1)
    assert [e["video_id"] for e in out] == ["club1"]
    assert out[0]["availability"] == "subscriber_only"


def test_none_availability_counts_as_public():
    m = _load()
    assert m._is_readable({"availability": None, "live_status": None})
    assert m._is_readable({"availability": "unlisted"})
    assert not m._is_readable({"availability": "premium_only"})
    assert not m._is_readable({"live_status": "is_live"})


# ── impersonated caption request ────────────────────────────────────────────
def _caption_info(track):
    return {"language": "en", "subtitles": {}, "automatic_captions": {"en": [track]}}


def test_impersonate_flagged_track_is_fetched_with_impersonation(monkeypatch):
    m = _load()
    track = {"ext": "vtt", "protocol": "https", "url": "https://tt/en?lang=en",
             "impersonate": True, "http_headers": {"Referer": "r"}}
    calls = []
    monkeypatch.setattr(m.yt_dlp, "YoutubeDL",
                        _ydl(_caption_info(track), {track["url"]: VTT}, calls))
    assert "hello" in m._fetch_captions("https://youtu.be/imp", ["en"])
    assert "impersonate" in calls[0].extensions
    assert calls[0].headers.get("Referer") == "r"


def test_unflagged_track_uses_plain_session_request(monkeypatch):
    m = _load()
    track = {"ext": "vtt", "protocol": "https", "url": "https://tt/en?lang=en"}
    calls = []
    monkeypatch.setattr(m.yt_dlp, "YoutubeDL",
                        _ydl(_caption_info(track), {track["url"]: VTT}, calls))
    m._fetch_captions("https://youtu.be/plain", ["en"])
    assert "impersonate" not in calls[0].extensions


def test_missing_impersonation_handler_falls_back_to_plain(monkeypatch):
    m = _load()
    from yt_dlp.networking.exceptions import NoSupportingHandlers
    track = {"ext": "vtt", "protocol": "https", "url": "https://tt/en?lang=en",
             "impersonate": True}
    calls = []
    Base = _ydl(_caption_info(track), {track["url"]: VTT}, calls)

    class NoCurl(Base):
        def urlopen(self, req):
            if "impersonate" in req.extensions:
                calls.append(req)
                raise NoSupportingHandlers([], [])
            return super().urlopen(req)
    monkeypatch.setattr(m.yt_dlp, "YoutubeDL", NoCurl)
    assert "hello" in m._fetch_captions("https://youtu.be/nocurl", ["en"])
    assert ["impersonate" in c.extensions for c in calls] == [True, False]


# ── last-resort "description" source ────────────────────────────────────────
DESC_INFO = {
    "language": "en", "subtitles": {}, "automatic_captions": {},
    "title": "Bitcoin Knocking On $87K",
    "description": ("Today we cover the $87K level.\n\n"
                    "Join: https://x.co/aff?ref=1\n------\nhttps://only.a/link\n"),
    "chapters": [{"start_time": 0, "title": "Intro"},
                 {"start_time": 95, "title": "BTC levels"}],
}


def _whisper_fails(url, **kw):
    raise RuntimeError("yt-dlp audio download failed (exit 1): HTTP Error 403")


def test_no_speech_falls_back_to_labelled_description(monkeypatch):
    m = _load()
    monkeypatch.setattr(m.yt_dlp, "YoutubeDL", _ydl(DESC_INFO))
    monkeypatch.setattr(m, "_asr", types.SimpleNamespace(transcribe=_whisper_fails))
    r = m.ytdlp_transcript_page("https://youtu.be/desc")
    assert r["source"] == "description"
    assert "Bitcoin Knocking On $87K" in r["text"]
    assert "01:35 BTC levels" in r["text"]
    assert "Today we cover the $87K level." in r["text"]
    assert "Join:" in r["text"] and "http" not in r["text"]   # URLs stripped
    assert "------" not in r["text"]                           # separator lines dropped
    assert "HTTP Error 403" in r["error"]                      # why speech failed


def test_description_never_beats_real_speech(monkeypatch):
    m = _load()
    monkeypatch.setattr(m.yt_dlp, "YoutubeDL", _ydl(DESC_INFO))
    monkeypatch.setattr(m, "_asr", types.SimpleNamespace(
        transcribe=lambda url, **kw: "actual spoken words"))
    assert m.ytdlp_transcript_page("https://youtu.be/desc2")["source"] == "whisper"


def test_empty_metadata_stays_none(monkeypatch):
    m = _load()
    monkeypatch.setattr(m.yt_dlp, "YoutubeDL", _ydl(
        {"subtitles": {}, "automatic_captions": {}, "title": "t", "description": ""}))
    monkeypatch.setattr(m, "_asr", None)
    assert m.ytdlp_transcript_page("https://youtu.be/empty")["source"] == "none"


def test_download_tool_returns_description_with_error(monkeypatch):
    m = _load()
    monkeypatch.setattr(m.yt_dlp, "YoutubeDL", _ydl(DESC_INFO))
    monkeypatch.setattr(m, "_asr", types.SimpleNamespace(transcribe=_whisper_fails))
    r = m.ytdlp_download_transcript("https://youtu.be/desc3")
    assert r["source"] == "description" and "BTC levels" in r["text"]
    assert "HTTP Error 403" in r["error"]
