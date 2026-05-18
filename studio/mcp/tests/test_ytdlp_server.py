import importlib.util, pathlib
def _load():
    p = pathlib.Path(__file__).parents[1] / "servers" / "ytdlp_server.py"
    spec = importlib.util.spec_from_file_location("ytdlp_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_map_search_entries():
    m = _load()
    raw = {"entries": [{"id": "abc", "title": "T1", "upload_date": "20260518",
                        "webpage_url": "https://youtu.be/abc"}]}
    assert m._map_search(raw, 1) == [{"video_id": "abc", "title": "T1",
        "upload_date": "2026-05-18", "url": "https://youtu.be/abc"}]

# ── _clean_transcript tests ────────────────────────────────────────────────────

def test_clean_transcript_strips_webvtt_header():
    m = _load()
    raw = "WEBVTT\n\n00:00:00.000 --> 00:00:03.000\n你好\n"
    result = m._clean_transcript(raw)
    assert "WEBVTT" not in result
    assert "00:00:00.000" not in result
    assert "你好" in result

def test_clean_transcript_strips_inline_tags():
    m = _load()
    raw = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<00:00:01.200><c>台股</c>上漲\n"
    result = m._clean_transcript(raw)
    assert "<" not in result
    assert "台股" in result
    assert "上漲" in result

def test_clean_transcript_dedupes_consecutive_lines():
    m = _load()
    # Auto-captions often repeat the same line 2–3 times
    raw = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n今天台股大漲\n\n00:00:02.000 --> 00:00:03.000\n今天台股大漲\n\n00:00:03.000 --> 00:00:04.000\n外資買超\n"
    result = m._clean_transcript(raw)
    lines = [l for l in result.splitlines() if l.strip()]
    assert lines.count("今天台股大漲") == 1
    assert "外資買超" in result

def test_clean_transcript_strips_srt_sequence_numbers():
    m = _load()
    raw = "1\n00:00:00,000 --> 00:00:02,000\n台積電\n\n2\n00:00:02,000 --> 00:00:04,000\n大漲\n"
    result = m._clean_transcript(raw)
    assert "台積電" in result
    assert "大漲" in result
    # Bare numeric lines should be gone
    lines = [l.strip() for l in result.splitlines() if l.strip()]
    assert "1" not in lines
    assert "2" not in lines

# ── _bound_transcript tests ────────────────────────────────────────────────────

def test_bound_under_limit_returns_whole():
    m = _load()
    text = "A" * 100
    result = m._bound_transcript(text, max_chars=200)
    assert result["text"] == text
    assert result["full_chars"] == 100
    assert result["truncated"] is False

def test_bound_at_exact_limit_returns_whole():
    m = _load()
    text = "X" * 48000
    result = m._bound_transcript(text, max_chars=48000)
    assert result["truncated"] is False
    assert result["full_chars"] == 48000

def test_bound_over_limit_returns_head_tail_with_marker():
    m = _load()
    # 100-char text with max 40
    text = "A" * 60 + "B" * 40
    result = m._bound_transcript(text, max_chars=40)
    assert result["truncated"] is True
    assert result["full_chars"] == 100
    assert "[...middle elided" in result["text"]
    # head portion from start of text
    assert result["text"].startswith("A")
    # tail portion from end of text
    assert result["text"].endswith("B" * 16)  # tail_len = 40 * 0.4 = 16

def test_bound_elision_marker_contains_correct_count():
    m = _load()
    text = "S" * 1000
    max_c = 400
    result = m._bound_transcript(text, max_chars=max_c)
    head_len = int(max_c * 0.60)   # 240
    tail_len = max_c - head_len     # 160
    elided = 1000 - head_len - tail_len  # 600
    assert f"elided {elided} chars" in result["text"]

# ── _clean_transcript + _bound_transcript integration ─────────────────────────

def test_clean_and_bound_integration():
    """A realistic VTT blob that exceeds limit after cleaning."""
    m = _load()
    # Build a VTT with 2000 unique lines (well above any limit we test with)
    lines = ["WEBVTT", ""]
    for i in range(500):
        lines += [f"00:0{i//60:01d}:{i%60:02d}.000 --> 00:0{i//60:01d}:{i%60:02d}.999",
                  f"<c>台股分析第{i}段</c> 季線站穩", ""]
    raw = "\n".join(lines)
    cleaned = m._clean_transcript(raw)
    assert "WEBVTT" not in cleaned
    assert "<c>" not in cleaned
    assert "台股分析第0段" in cleaned
    # Now bound with small limit to trigger truncation
    bounded = m._bound_transcript(cleaned, max_chars=500)
    assert bounded["truncated"] is True
    assert "[...middle elided" in bounded["text"]
    assert bounded["full_chars"] > 500

# ── return-shape tests for ytdlp_download_transcript ──────────────────────────

def test_ytdlp_download_transcript_none_source_has_all_keys():
    """When no transcript is available, result must have all expected keys."""
    m = _load()
    # Monkeypatch _fetch_captions to return None and disable gemma
    original_fetch = m._fetch_captions
    original_gemma = m._gemma
    m._fetch_captions = lambda *a, **kw: None
    m._gemma = None
    try:
        result = m.ytdlp_download_transcript("https://youtu.be/fakeid")
        assert result["source"] == "none"
        assert "text" in result
        assert "full_chars" in result
        assert "truncated" in result
        assert result["full_chars"] == 0
        assert result["truncated"] is False
    finally:
        m._fetch_captions = original_fetch
        m._gemma = original_gemma

def test_ytdlp_download_transcript_captions_shape():
    """When captions are returned, result has source=captions + all keys."""
    m = _load()
    original_fetch = m._fetch_captions
    m._fetch_captions = lambda *a, **kw: "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n台股\n"
    try:
        result = m.ytdlp_download_transcript("https://youtu.be/fakeid")
        assert result["source"] == "captions"
        assert "台股" in result["text"]
        assert isinstance(result["full_chars"], int)
        assert result["full_chars"] > 0
        assert isinstance(result["truncated"], bool)
    finally:
        m._fetch_captions = original_fetch

def test_ytdlp_download_transcript_exception_returns_structured_error():
    """If _fetch_captions raises, result is a structured error dict (never raises)."""
    m = _load()
    original_fetch = m._fetch_captions
    m._fetch_captions = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("network error"))
    try:
        result = m.ytdlp_download_transcript("https://youtu.be/fakeid")
        assert result["source"] == "none"
        assert "error" in result
        assert "network error" in result["error"]
    finally:
        m._fetch_captions = original_fetch
