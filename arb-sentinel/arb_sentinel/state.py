import datetime, json, os, pathlib, tempfile
from .models import Opportunity, stable_id

_TIER_RANK = {"LOG_ONLY": 0, "WATCH": 1, "GOOD": 2, "ACT_NOW": 3}

# Absolute default path under the package's repo root. Used when callers don't
# pass an explicit path. Previously every run.py entry defaulted to the
# cwd-relative "state/state.json", which silently diverged whenever a harness
# (CLI test, REPL, alternate scheduler) ran without `cd $ROOT` first —
# producing an empty state and re-broadcasting every alert.
_DEFAULT_STATE_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "state" / "state.json"
)


class State:
    """JSON dedup store for opportunities + announcements.

    Two independent tables:
      - `seen_opportunities`: tier-graded opportunity dedup (rates path + LLM
        announcement path). Keyed by `stable_id(opportunity)`. Stores tier,
        last_apr, last_collected for renotify-delta and tier-upgrade logic.
      - `seen_announcements`: lightweight announcement dedup (BOTH heads-up
        AND LLM announcement paths). Keyed by `"{exchange}:{annId}"`. Stores
        minimal meta (title, is_promo, exchange).

    The heads-up announcement path writes only to `seen_announcements`; the
    LLM path writes both tables. So `bitget-promotion-*` / `okx-promotion-*` /
    `binance-promotion-*` entries in `seen_opportunities` freeze in time once
    `announcement_llm` is flipped to false — by design, not a bug. Dedup
    continuity across path-switches works via the shared `seen_announcements`
    table. See run.py::run_announcements docstring.

    Persistence guarantees:
    - Default `path` is absolute (under the package repo), not cwd-relative.
    - `_save()` is atomic via tempfile+os.replace, so a kill mid-write cannot
      corrupt the file.
    - On parse failure, the broken file is backed up as
      `state.json.corrupt-<UTC>` before reset — recoverable, not silently
      forgotten."""

    def __init__(self, path=None):
        self.path = pathlib.Path(path) if path is not None else _DEFAULT_STATE_PATH
        self.data = {"seen_opportunities": {}, "active_positions": []}
        if self.path.exists():
            raw = None
            try:
                raw = self.path.read_text("utf-8")
                self.data = json.loads(raw)
            except Exception:
                # Back up the broken file before resetting so we can recover
                # the seen-set after the fact (otherwise a partial write +
                # silent reset re-broadcasts every alert).
                if raw is not None:
                    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                    try:
                        backup = self.path.with_name(f"{self.path.name}.corrupt-{ts}")
                        backup.write_text(raw, "utf-8")
                    except Exception:
                        pass        # last-ditch: drop the backup, still reset
                self.data = {"seen_opportunities": {}, "active_positions": []}
        if not isinstance(self.data, dict):          # corrupt/wrong-shape JSON → reset
            self.data = {"seen_opportunities": {}, "active_positions": []}
        self.data.setdefault("seen_opportunities", {})
        self.data.setdefault("active_positions", [])
        self.data.setdefault("seen_announcements", {})

    def should_notify(self, o: Opportunity, tier: str, cfg) -> bool:
        prev = self.data["seen_opportunities"].get(stable_id(o))
        if prev is None:
            return tier in ("ACT_NOW", "GOOD")          # first sighting: alert if actionable
        if _TIER_RANK.get(tier, 0) > _TIER_RANK.get(prev.get("tier", "LOG_ONLY"), 0):
            return True                                  # tier upgraded
        if o.apr is not None and prev.get("last_apr") is not None:
            if abs(o.apr - prev["last_apr"]) >= cfg.renotify_delta:
                return True                              # APR jumped beyond delta
        return False

    def record(self, o: Opportunity, tier: str) -> None:
        self.data["seen_opportunities"][stable_id(o)] = {
            "last_apr": o.apr, "tier": tier, "last_collected": o.collected_at}
        self._save()

    def is_new_announcement(self, ann_id) -> bool:
        return ann_id not in self.data.setdefault("seen_announcements", {})

    def mark_announcement(self, ann_id, meta=None) -> None:
        self.data.setdefault("seen_announcements", {})[ann_id] = meta or {}
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: stage in a sibling temp file, fsync, then os.replace.
        # Path.write_text used to leave a half-written state.json on kill,
        # which __init__ then silently reset → every alert re-broadcast.
        payload = json.dumps(self.data, ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(
            prefix=f"{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except Exception:
            # Best-effort cleanup of the staged temp file; never raise out.
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
