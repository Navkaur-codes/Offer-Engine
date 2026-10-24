from datetime import datetime

from app import ports, stubs
from app.config import IST
from app.contracts import DecisionLight

NOW = datetime(2026, 10, 23, 19, 40, tzinfo=IST)


def test_every_port_resolves():
    status = ports.status()
    assert set(status) == set(ports._PORTS)
    assert set(status.values()) <= {"real", "stub"}


# The stub tests call `stubs` directly: once a session merges, `ports` route to its real module instead.
def test_stub_decide_covers_sent_no_offer_and_blocked():
    sent = stubs.decide("C000001", "cart_abandoned", now=NOW)
    assert sent.status == "SENT" and sent.coupon_code and sent.message
    assert stubs.decide("C000003", "browse_interest", now=NOW).status == "NO_OFFER"
    assert stubs.decide("C000002", "manual", now=NOW).status == "BLOCKED"


def test_stub_dry_run_has_no_coupon():
    d = stubs.decide("C000004", "inactivity", dry_run=True, now=NOW)
    assert d.status == "DRY_RUN" and d.coupon_code is None


def test_stub_unknown_customer_falls_back_to_fixture():
    d = stubs.decide("TG999", "welcome", now=NOW)
    assert d.customer_id == "TG999" and d.profile_snapshot.first_name == "Friend"


def test_light_decision_and_roundtrip_json():
    for cid in stubs.PROFILES:
        d = stubs.decide(cid, "cart_abandoned", now=NOW)
        assert DecisionLight.from_decision(d).explanation_title == d.explanation.title
        assert type(d).model_validate_json(d.model_dump_json()) == d


def test_evaluate_flags_over_limit_discount():
    p = stubs.PROFILES["C000002"]  # the deal-hunter fixture; this test is about the real evaluate()
    ctx = stubs.get_context(NOW)
    assert ports.evaluate(p, ctx, "OF_PCT_CAT", {"pct": 50}).ok is False
    # deal hunters need a ₹999 minimum basket (real rules engine, P_DEAL_CAP)
    assert ports.evaluate(p, ctx, "OF_PCT_CAT", {"pct": 10, "min_basket": 999}).ok is True
