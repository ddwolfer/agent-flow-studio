from dataclasses import dataclass, field
from datetime import date

# Tiers (spec section 5.4)
ACT_NOW, GOOD, WATCH, LOG_ONLY = "ACT_NOW", "GOOD", "WATCH", "LOG_ONLY"
# Time flags (spec section 5.2)
OK_TIME, TIGHT, TOO_LATE, NO_DEADLINE = "OK_TIME", "TIGHT", "TOO_LATE", "NO_DEADLINE"


@dataclass
class Opportunity:
    exchange: str                       # okx | binance | bitget
    category: str                       # flexible_earn | borrow | launchpool |
                                        # new_listing_earn | dual_investment |
                                        # promotion | stable_depeg
    asset: str
    apr: float | None                   # annualised decimal (0.123 = 12.3%); None if unknown
    apr_source: str                     # api | announcement | app_display
    apr_is_promotional: bool = False
    tier_info: str | None = None
    borrow_apr_same_asset: float | None = None
    min_hold_days: int = 0
    start_date: date | None = None
    end_date: date | None = None
    entry_asset_required: str | None = None
    subsidy_note: str | None = None
    directional_risk: bool = False
    source_url: str | None = None
    raw_snapshot: dict = field(default_factory=dict)
    collected_at: str = ""              # ISO8601 UTC


def stable_id(o: "Opportunity") -> str:
    base = f"{o.exchange}-{o.category}-{o.asset}"
    return f"{base}-{o.end_date.isoformat()}" if o.end_date else base
