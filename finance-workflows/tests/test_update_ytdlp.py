"""scripts/update_ytdlp.py: upgrade when possible, never break the pipeline."""
import importlib.util, pathlib


def _load():
    p = pathlib.Path(__file__).parents[1] / "scripts" / "update_ytdlp.py"
    spec = importlib.util.spec_from_file_location("update_ytdlp", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


class FakeRunner:
    """Scripted subprocess: health checks return versions from `versions`
    (None = import fails); pip calls return `pip_rc`."""
    def __init__(self, versions, pip_rc=0, pip_out=""):
        self.versions = list(versions)
        self.pip_rc, self.pip_out = pip_rc, pip_out
        self.calls = []

    def __call__(self, cmd, timeout):
        self.calls.append(cmd)
        if cmd[1] == "-c":                                  # health check
            v = self.versions.pop(0)
            return (0, f"{v}\n") if v else (1, "ModuleNotFoundError: yt_dlp")
        return self.pip_rc, self.pip_out

    def pip_calls(self):
        return [c for c in self.calls if c[1:3] == ["-m", "pip"]]


def test_upgrade_reports_version_change(capsys):
    m = _load()
    run = FakeRunner(["2026.03.17", "2026.08.19"])
    assert m.update(run, channel="stable") == 0
    assert "2026.03.17 → 2026.08.19" in capsys.readouterr().out
    pip = run.pip_calls()[0]
    assert "-U" in pip and m.SPEC in pip and "--pre" not in pip


def test_nightly_channel_adds_pre():
    m = _load()
    run = FakeRunner(["a", "b"])
    m.update(run, channel="nightly")
    assert "--pre" in run.pip_calls()[0]


def test_offline_pip_failure_keeps_installed_version_and_is_ok(capsys):
    m = _load()
    run = FakeRunner(["2026.08.19", "2026.08.19"], pip_rc=1,
                     pip_out="ERROR: Could not find a version (network)")
    assert m.update(run, channel="stable") == 0          # non-fatal: still healthy
    assert "keeping 2026.08.19" in capsys.readouterr().err


def test_broken_upgrade_is_rolled_back(capsys):
    m = _load()
    run = FakeRunner(["2026.08.19", None, "2026.08.19"])
    assert m.update(run, channel="stable") == 1
    pins = [c for c in run.pip_calls() if "yt-dlp==2026.08.19" in c]
    assert pins, "must reinstall the previous version"
    assert "rolled back to 2026.08.19 → ok" in capsys.readouterr().err


def test_pip_timeout_is_bounded():
    m = _load()
    seen = []
    def run(cmd, timeout):
        seen.append(timeout)
        return (0, "x\n") if cmd[1] == "-c" else (124, "timed out")
    m.update(run, channel="stable")
    assert max(seen) == m.PIP_TIMEOUT_SEC
