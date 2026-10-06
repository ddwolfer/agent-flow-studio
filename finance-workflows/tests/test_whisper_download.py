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
    assert m._lang_and_prompt(None) == ("zh", m.INITIAL_PROMPT)       # historical default
    assert m._lang_and_prompt("zh-TW") == ("zh", m.INITIAL_PROMPT)
    assert m._lang_and_prompt("en") == ("en", m.INITIAL_PROMPT_EN)
    assert m._lang_and_prompt("en-US")[0] == "en"
