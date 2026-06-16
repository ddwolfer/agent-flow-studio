import datetime
from arb_sentinel.models import Opportunity, stable_id

def test_stable_id_no_deadline_is_date_independent():
    o = Opportunity(exchange="okx", category="flexible_earn", asset="USDC",
                    apr=0.025, apr_source="api")
    assert stable_id(o) == "okx-flexible_earn-USDC"

def test_stable_id_with_deadline_keys_on_end_date():
    o = Opportunity(exchange="bitget", category="promotion", asset="USDGO",
                    apr=0.12, apr_source="announcement",
                    end_date=datetime.date(2026, 6, 30))
    assert stable_id(o) == "bitget-promotion-USDGO-2026-06-30"
