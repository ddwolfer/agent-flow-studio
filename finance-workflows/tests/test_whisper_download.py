"""_download_wav must use THIS interpreter's yt_dlp and surface its stderr.

Regression 2026-10-07: the bare `yt-dlp` on PATH was a stale Homebrew copy
(2026.03.17) that got HTTP 403 on every audio download; reports only showed
"exit status 1"."""
import importlib.util, pathlib, subprocess, sys, types

import pytest


def _load():
    p = pathlib.Path(__file__).parents[1] / "mcp" / "lib" / "whisper_transcribe.py"
    spec = importlib.util.spec_from_file_location("whisper_transcribe", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def test_uses_current_interpreter_module(monkeypatch, tmp_path):
    m = _load()
    seen = {}
    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return types.SimpleNamespace(returncode=1, stderr="ERROR: boom", stdout="")
    monkeypatch.setattr(m.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError):
        m._download_wav("https://youtu.be/x", tmp_path)
    assert seen["cmd"][:3] == [sys.executable, "-m", "yt_dlp"]


def test_failure_message_carries_yt_dlp_error_line(monkeypatch, tmp_path):
    m = _load()
    stderr = ("WARNING: something benign\n"
              "ERROR: unable to download video data: HTTP Error 403: Forbidden\n")
    monkeypatch.setattr(m.subprocess, "run", lambda cmd, **kw: types.SimpleNamespace(
        returncode=1, stderr=stderr, stdout=""))
    with pytest.raises(RuntimeError, match="HTTP Error 403"):
        m._download_wav("https://youtu.be/x", tmp_path)


def test_download_is_bounded_by_timeout(monkeypatch, tmp_path):
    m = _load()
    def fake_run(cmd, **kw):
        assert kw.get("timeout") == m.DOWNLOAD_TIMEOUT_SEC
        raise subprocess.TimeoutExpired(cmd, kw["timeout"])
    monkeypatch.setattr(m.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="timed out"):
        m._download_wav("https://youtu.be/x", tmp_path)


def test_language_and_prompt_selection():
    m = _load()
    # Unknown → auto-detect with NO prompt. Never guess zh: forcing zh + a
    # Chinese prompt onto English audio makes Whisper translate it.
    assert m._lang_and_prompt(None) == (None, None)
    assert m._lang_and_prompt("zh-TW") == ("zh", m.INITIAL_PROMPT)
    assert m._lang_and_prompt("en") == ("en", m.INITIAL_PROMPT_EN)
    assert m._lang_and_prompt("en-US")[0] == "en"
    assert m._lang_and_prompt("English") == ("en", m.INITIAL_PROMPT_EN)  # Groq name
    assert m._lang_and_prompt("ja") == ("ja", None)


# ── language plumbing (each of these mutations survived the old suite) ─────────
def _stub_download(m, monkeypatch):
    monkeypatch.setattr(m, "_download_wav", lambda url, dp: pathlib.Path(dp) / "n.wav")


def test_known_language_reaches_groq_without_detection(monkeypatch):
    m = _load(); _stub_download(m, monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "k")
    got = {}
    monkeypatch.setattr(m, "_detect_language",
                        lambda *a: (_ for _ in ()).throw(AssertionError("no detect")))
    def groq(wav, dp, key, language=None):
        got["g"] = language
        return "t"
    monkeypatch.setattr(m, "_groq_transcribe", groq)
    assert m.transcribe("u", language="en-US") == "t"
    assert got["g"] == "en"


def test_unknown_language_is_detected_then_passed_to_both_engines(monkeypatch):
    m = _load(); _stub_download(m, monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "k")
    got = {}
    monkeypatch.setattr(m, "_detect_language", lambda wav, dp, key: "en")
    def groq(wav, dp, key, language=None):
        got["groq"] = language; raise RuntimeError("groq down")
    def local(wav, language=None):
        got["local"] = language; return "local text"
    monkeypatch.setattr(m, "_groq_transcribe", groq)
    monkeypatch.setattr(m, "_local_transcribe", local)
    assert m.transcribe("u") == "local text"
    assert got == {"groq": "en", "local": "en"}


def _capture_groq_post(m, monkeypatch, json_body=None):
    import httpx
    sent = []
    class R:
        def raise_for_status(self): pass
        def json(self): return json_body or {"text": "hello"}
    def post(url, headers=None, files=None, data=None, timeout=None):
        sent.append(data); return R()
    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(m, "_audio_duration", lambda wav: 10)
    return sent


def test_groq_request_carries_language_and_matching_prompt(monkeypatch, tmp_path):
    m = _load()
    sent = _capture_groq_post(m, monkeypatch)
    (tmp_path / "n.wav").write_bytes(b"x")
    m._groq_transcribe(tmp_path / "n.wav", tmp_path, "k", "en")
    assert sent[0]["language"] == "en" and sent[0]["prompt"] == m.INITIAL_PROMPT_EN


def test_groq_request_omits_language_and_prompt_when_unknown(monkeypatch, tmp_path):
    m = _load()
    sent = _capture_groq_post(m, monkeypatch)
    (tmp_path / "n.wav").write_bytes(b"x")
    m._groq_transcribe(tmp_path / "n.wav", tmp_path, "k", None)
    assert "language" not in sent[0] and "prompt" not in sent[0]


def test_groq_detection_maps_language_name(monkeypatch, tmp_path):
    m = _load()
    sent = _capture_groq_post(m, monkeypatch, {"language": "English", "text": "hi"})
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: None)   # ffmpeg clip
    (tmp_path / "detect.wav").write_bytes(b"x")
    assert m._groq_detect(tmp_path / "n.wav", tmp_path, "k") == "en"
    assert sent[0]["response_format"] == "verbose_json" and "prompt" not in sent[0]


def test_local_engine_receives_language(monkeypatch, tmp_path):
    m = _load()
    calls = []
    class Model:
        def transcribe(self, path, **kw):
            calls.append(kw)
            return iter([types.SimpleNamespace(text="hi")]), None
    monkeypatch.setattr(m, "_get_model", lambda: Model())
    m._local_transcribe(tmp_path / "n.wav", "en")
    m._local_transcribe(tmp_path / "n.wav", None)
    assert calls[0]["language"] == "en" and calls[0]["initial_prompt"] == m.INITIAL_PROMPT_EN
    assert calls[1]["language"] is None and calls[1]["initial_prompt"] is None
