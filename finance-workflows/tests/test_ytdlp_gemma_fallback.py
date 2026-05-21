"""Regression tests for the captions→gemma fallback in _get_full_transcript.

Bug being guarded: a caption-fetch exception (YouTube rate-limit) used to abort
the whole try block, so the gemma fallback never ran. These tests prove that a
captions failure now falls through to gemma."""
import importlib.util, pathlib, types


def _load():
    p = pathlib.Path(__file__).parents[1] / "mcp" / "servers" / "ytdlp_server.py"
    spec = importlib.util.spec_from_file_location("ytdlp_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def test_captions_exception_falls_through_to_gemma(monkeypatch):
    m = _load()
    m._TRANSCRIPT_CACHE.clear()
    # captions raise (simulating YouTube rate-limit during extract_info)
    def boom(url, langs):
        raise RuntimeError("HTTP Error 429: Too Many Requests")
    monkeypatch.setattr(m, "_fetch_captions", boom)
    # gemma available and returns text
    monkeypatch.setattr(m, "_gemma", types.SimpleNamespace(
        transcribe=lambda url: "各位朋友大家好 這裡是測試逐字稿"))
    r = m._get_full_transcript("https://youtu.be/x")
    assert r["source"] == "gemma4:e4b"
    assert "測試逐字稿" in r["text"]


def test_no_captions_uses_gemma(monkeypatch):
    m = _load()
    m._TRANSCRIPT_CACHE.clear()
    monkeypatch.setattr(m, "_fetch_captions", lambda url, langs: None)  # no captions
    monkeypatch.setattr(m, "_gemma", types.SimpleNamespace(
        transcribe=lambda url: "audio transcription text"))
    r = m._get_full_transcript("https://youtu.be/y")
    assert r["source"] == "gemma4:e4b"
    assert "audio transcription" in r["text"]


def test_captions_win_when_present(monkeypatch):
    m = _load()
    m._TRANSCRIPT_CACHE.clear()
    monkeypatch.setattr(m, "_fetch_captions",
                        lambda url, langs: "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n有字幕\n")
    # gemma should NOT be called when captions exist
    called = {"n": 0}
    def g(url): called["n"] += 1; return "should not run"
    monkeypatch.setattr(m, "_gemma", types.SimpleNamespace(transcribe=g))
    r = m._get_full_transcript("https://youtu.be/z")
    assert r["source"] == "captions"
    assert "有字幕" in r["text"]
    assert called["n"] == 0


def test_both_fail_reports_both_errors(monkeypatch):
    m = _load()
    m._TRANSCRIPT_CACHE.clear()
    def boom(url, langs): raise RuntimeError("429 rate limit")
    monkeypatch.setattr(m, "_fetch_captions", boom)
    def gboom(url): raise RuntimeError("ollama down")
    monkeypatch.setattr(m, "_gemma", types.SimpleNamespace(transcribe=gboom))
    r = m._get_full_transcript("https://youtu.be/w")
    assert r["source"] == "none"
    assert "captions: 429 rate limit" in r["error"]
    assert "gemma: ollama down" in r["error"]


def test_gemma_disabled_only_captions_error(monkeypatch):
    m = _load()
    m._TRANSCRIPT_CACHE.clear()
    def boom(url, langs): raise RuntimeError("429")
    monkeypatch.setattr(m, "_fetch_captions", boom)
    monkeypatch.setattr(m, "_gemma", None)  # gemma not installed
    r = m._get_full_transcript("https://youtu.be/v")
    assert r["source"] == "none"
    assert "captions: 429" in r["error"]
