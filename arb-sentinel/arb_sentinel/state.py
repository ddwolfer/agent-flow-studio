import json, pathlib
from .models import Opportunity, stable_id

_TIER_RANK = {"LOG_ONLY": 0, "WATCH": 1, "GOOD": 2, "ACT_NOW": 3}


class State:
    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.data = {"seen_opportunities": {}, "active_positions": []}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text("utf-8"))
            except Exception:
                pass
        self.data.setdefault("seen_opportunities", {})
        self.data.setdefault("active_positions", [])

    def should_notify(self, o: Opportunity, tier: str, cfg) -> bool:
        prev = self.data["seen_opportunities"].get(stable_id(o))
        if prev is None:
            return tier in ("ACT_NOW", "GOOD")          # first sighting: alert if actionable
        if _TIER_RANK[tier] > _TIER_RANK.get(prev.get("tier", "LOG_ONLY"), 0):
            return True                                  # tier upgraded
        if o.apr is not None and prev.get("last_apr") is not None:
            if abs(o.apr - prev["last_apr"]) >= cfg.renotify_delta:
                return True                              # APR jumped beyond delta
        return False

    def record(self, o: Opportunity, tier: str) -> None:
        self.data["seen_opportunities"][stable_id(o)] = {
            "last_apr": o.apr, "tier": tier, "last_collected": o.collected_at}
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), "utf-8")
