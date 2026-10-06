"""Keep the venv's yt-dlp current before each YouTube-reading run.

Why: YouTube breaks yt-dlp's clients every few months and the fix ships as a
new yt-dlp release. On 2026-10-07 the venv was still on 2026.03.17 (7 months
stale): every audio download got HTTP 403 and reports only said "exit status
1". yt-dlp's own README calls a stale stable install "prone to external
breakage", so updating is a routine pre-step, not a one-time fix.

Run by scripts/crypto_daily.sh before run-workflow.py. NON-FATAL by design:
if PyPI is unreachable we keep the installed version and the report still
runs. If an upgrade installs but the import health check fails, roll back to
the previous version so a bad release can't take the pipeline down.

    mcp/.venv/bin/python scripts/update_ytdlp.py            # stable channel
    STUDIO_YTDLP_CHANNEL=nightly ... update_ytdlp.py         # --pre (nightly)
"""
import os
import subprocess
import sys

PY = sys.executable
SPEC = "yt-dlp[default,curl-cffi]"
PIP_TIMEOUT_SEC = 240          # whole pip run; pip's own --timeout is per request
# Import what actually breaks across releases: yt-dlp loads its YouTube
# extractor lazily, so `import yt_dlp` alone proves little. Report the
# DISTRIBUTION version (importlib.metadata) — for nightlies it differs from
# yt_dlp.version.__version__ (".dev0" suffix) and only it can be pinned back.
_HEALTH = ("import yt_dlp, yt_dlp_ejs, yt_dlp.extractor.youtube; "
           "from importlib.metadata import version; print(version('yt-dlp'))")


def _run(cmd, timeout):
    """subprocess.run that never raises; returns (rc, combined output)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except Exception as e:                                   # pragma: no cover
        return 1, f"{type(e).__name__}: {e}"


def installed_version(run=_run):
    rc, out = run([PY, "-c", _HEALTH], 60)
    lines = out.strip().splitlines()
    return lines[-1].strip() if rc == 0 and lines else None


def update(run=_run, channel=None) -> int:
    """Returns 0 when yt-dlp is healthy afterwards (updated or unchanged)."""
    channel = channel or os.environ.get("STUDIO_YTDLP_CHANNEL", "stable")
    prev = installed_version(run)
    cmd = [PY, "-m", "pip", "install", "-U", "-q", "--disable-pip-version-check",
           "--timeout", "30", "--retries", "2", SPEC]
    if channel == "nightly":
        cmd.insert(5, "--pre")
    rc, out = run(cmd, PIP_TIMEOUT_SEC)
    now = installed_version(run)

    if now is None and prev:
        # Upgrade (or a half-finished one) left yt-dlp unimportable → roll back.
        run([PY, "-m", "pip", "install", "-q", "--disable-pip-version-check",
             f"{SPEC}=={prev}"], PIP_TIMEOUT_SEC)
        restored = installed_version(run)
        print(f"[update_ytdlp] ERROR: post-upgrade health check failed; rolled "
              f"back to {prev} → {'ok' if restored else 'STILL BROKEN'}",
              file=sys.stderr)
        return 1
    if rc != 0:
        tail = out.strip().splitlines()[-1:] or [""]
        print(f"[update_ytdlp] WARN: pip exit {rc} ({tail[0][:200]}); "
              f"keeping {now}", file=sys.stderr)
        return 0 if now else 1
    change = f"{prev} → {now}" if prev != now else f"{now} (already latest)"
    print(f"[update_ytdlp] yt-dlp {change} [{channel}]")
    return 0 if now else 1


if __name__ == "__main__":
    raise SystemExit(update())
