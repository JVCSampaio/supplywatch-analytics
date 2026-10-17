import pandas as pd
import pytest
from analytics.domain import transform, kpis


def calculate(rows, events=()):
    partners = pd.DataFrame({"partner_id": ["S"]})
    products = pd.DataFrame({"product_id": ["P"]})
    base = dict(
        order_id="O",
        order_date="2025-01-01",
        due_date="2025-01-10",
        partner_id="S",
        product_id="P",
        quantity=10,
        unit_price_cents=100,
        status="ordered",
    )
    orders = pd.DataFrame([{**base, "line_id": f"L{i}", **r} for i, r in enumerate(rows)])
    events = pd.DataFrame(events, columns=["event_id", "line_id", "event_date", "quantity"])
    return transform(orders, events, partners, products)


def test_partial_and_late_receipts_do_not_duplicate_spend():
    fact, rejected = calculate([{}], [("E1", "L0", "2025-01-09", 4), ("E2", "L0", "2025-01-11", 6)])
    assert not any(len(x) for x in rejected)
    assert fact.amount_cents.sum() == 1000
    assert fact.received_quantity.iloc[0] == 10
    assert fact.on_time_quantity.iloc[0] == 4
    assert fact.otif.iloc[0] == 0
    assert fact.lead_days.iloc[0] == 10
    assert fact.open_cents.iloc[0] == 0


def test_delivery_on_due_date_is_on_time():
    fact, _ = calculate([{}], [("E1", "L0", "2025-01-10", 10)])
    assert kpis(fact)["rate"] == 1


def test_no_receipts_is_overdue_not_missing():
    fact, _ = calculate([{}])
    assert kpis(fact)["rate"] == 0
    assert fact.overdue_cents.iloc[0] == 1000
    assert pd.isna(fact.lead_days.iloc[0])


def test_future_due_and_cancelled_excluded_from_otif():
    fact, _ = calculate([{"due_date": "2026-01-10"}, {"status": "cancelled"}])
    assert kpis(fact)["rate"] is None
    assert kpis(fact)["amount"] == 10
    assert fact.overdue_cents.sum() == 0


@pytest.mark.parametrize(
    "events",
    [
        [("E", "L0", "2025-01-10", 11)],
        [("E", "L0", "2026-01-10", 10)],
        [("E", "L0", "2024-12-31", 10)],
        [("E", "L0", "2025-01-10", 5), ("E", "L0", "2025-01-10", 5)],
    ],
)
def test_bad_receipt_quarantines_affected_order(events):
    fact, rejected = calculate([{}], events)
    assert fact.empty
    assert len(rejected[0]) == 1
    assert len(rejected[1]) == len(events)


def test_otif_is_ratio_of_components():
    fact, _ = calculate([{}, {}, {}], [("E", "L0", "2025-01-10", 10)])
    assert kpis(fact)["rate"] == pytest.approx(1 / 3)
