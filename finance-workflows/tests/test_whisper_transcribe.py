"""Engine-selection tests for whisper_transcribe.transcribe().

Groq is preferred when GROQ_API_KEY is set; local faster-whisper is the offline
fallback when there's no key or Groq errors out. Network/model calls are
monkeypatched — these tests assert routing, not real transcription."""
import importlib.util, pathlib, types


def _load():
    p = pathlib.Path(__file__).parents[1] / "mcp" / "lib" / "whisper_transcribe.py"
    spec = importlib.util.spec_from_file_location("whisper_transcribe", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def _stub_download(m, monkeypatch):
    monkeypatch.setattr(m, "_download_wav", lambda url, dp: pathlib.Path(dp) / "norm.wav")


def test_prefers_groq_when_key_set(monkeypatch):
    m = _load(); _stub_download(m, monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setattr(m, "_groq_transcribe", lambda wav, dp, key: "groq text")
    called = {"local": 0}
    monkeypatch.setattr(m, "_local_transcribe",
                        lambda wav: called.__setitem__("local", called["local"] + 1) or "local text")
    assert m.transcribe("https://youtu.be/x") == "groq text"
    assert called["local"] == 0  # local must NOT run when groq succeeds


def test_falls_back_to_local_on_groq_error(monkeypatch):
    m = _load(); _stub_download(m, monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    def boom(wav, dp, key): raise RuntimeError("groq 500")
    monkeypatch.setattr(m, "_groq_transcribe", boom)
    monkeypatch.setattr(m, "_local_transcribe", lambda wav: "local text")
    assert m.transcribe("https://youtu.be/x") == "local text"


def test_groq_empty_falls_back_to_local(monkeypatch):
    m = _load(); _stub_download(m, monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setattr(m, "_groq_transcribe", lambda wav, dp, key: "   ")
    monkeypatch.setattr(m, "_local_transcribe", lambda wav: "local text")
    assert m.transcribe("https://youtu.be/x") == "local text"


def test_no_key_uses_local(monkeypatch):
    m = _load(); _stub_download(m, monkeypatch)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    called = {"groq": 0}
    monkeypatch.setattr(m, "_groq_transcribe",
                        lambda wav, dp, key: called.__setitem__("groq", 1) or "groq")
    monkeypatch.setattr(m, "_local_transcribe", lambda wav: "local text")
    assert m.transcribe("https://youtu.be/x") == "local text"
    assert called["groq"] == 0  # groq must NOT run without a key
