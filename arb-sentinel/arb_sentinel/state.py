import json, pathlib
from .models import Opportunity, stable_id

_TIER_RANK = {"LOG_ONLY": 0, "WATCH": 1, "GOOD": 2, "ACT_NOW": 3}


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
    table. See run.py::run_announcements docstring."""

    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.data = {"seen_opportunities": {}, "active_positions": []}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text("utf-8"))
            except Exception:
                pass
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
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), "utf-8")
