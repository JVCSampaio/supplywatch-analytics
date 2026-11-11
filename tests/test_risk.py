import pandas as pd
import pytest
from analytics.risk import (
    WEIGHT_OTIF_MISS,
    WEIGHT_OVERDUE_EXPOSURE,
    dax_expression,
    risk_components,
    supplier_risk_table,
)


def test_weights_are_equal_and_sum_to_one():
    assert WEIGHT_OTIF_MISS == 0.5
    assert WEIGHT_OVERDUE_EXPOSURE == 0.5
    assert WEIGHT_OTIF_MISS + WEIGHT_OVERDUE_EXPOSURE == 1


def test_perfect_delivery_and_no_overdue_scores_zero():
    result = risk_components(10, 10, 0, 1000)
    assert result["falha_otif"] == 0
    assert result["exposicao_vencida"] == 0
    assert result["risk_score"] == 0


def test_total_otif_miss_and_full_overdue_scores_one_hundred():
    result = risk_components(0, 4, 500, 500)
    assert result["falha_otif"] == 1
    assert result["exposicao_vencida"] == 1
    assert result["risk_score"] == 100


def test_equal_weights_match_a_hand_calculation():
    # OTIF 8/10, overdue 250 of 1000 cents.
    result = risk_components(8, 10, 250, 1000)
    assert result["falha_otif"] == pytest.approx(0.2)
    assert result["exposicao_vencida"] == pytest.approx(0.25)
    assert result["risk_score"] == pytest.approx(100 * (0.5 * 0.2 + 0.5 * 0.25))


def test_lines_not_yet_due_do_not_score_as_low_risk():
    result = risk_components(0, 0, 0, 1000)
    assert result["falha_otif"] is None
    assert result["exposicao_vencida"] == 0
    assert result["risk_score"] is None


def test_cancelled_only_supplier_is_blank():
    result = risk_components(0, 0, 0, 0)
    assert result["risk_score"] is None
    assert result["falha_otif"] is None
    assert result["exposicao_vencida"] is None


def test_otif_miss_without_overdue_is_fifty():
    result = risk_components(0, 10, 0, 800)
    assert result["risk_score"] == 50


@pytest.mark.parametrize(
    "args",
    [
        (11, 10, 0, 100),
        (-1, 10, 0, 100),
        (1, 1, 5, 4),
        (1.5, 2, 0, 10),
        (True, 1, 0, 10),
    ],
)
def test_invalid_components_are_rejected(args):
    with pytest.raises(ValueError):
        risk_components(*args)


def test_table_keeps_a_partner_with_no_lines_and_sorts_by_score():
    fact = pd.DataFrame(
        [
            {
                "partner_id": "B",
                "otif": 0,
                "due_eligible": 1,
                "overdue_cents": 100,
                "amount_cents": 100,
            },
            {
                "partner_id": "A",
                "otif": 1,
                "due_eligible": 1,
                "overdue_cents": 0,
                "amount_cents": 100,
            },
        ]
    )
    partners = pd.DataFrame(
        [
            {"partner_id": "A", "partner_name": "Alpha", "region": "RJ", "segment": "A"},
            {"partner_id": "B", "partner_name": "Beta", "region": "SP", "segment": "B"},
            {"partner_id": "C", "partner_name": "Gamma", "region": "BA", "segment": "C"},
        ]
    )
    table = supplier_risk_table(fact, partners)
    assert list(table.partner_id) == ["B", "A", "C"]
    assert table.loc[0, "risk_score"] == 100
    assert table.loc[1, "risk_score"] == 0
    assert pd.isna(table.loc[2, "risk_score"])
    assert table.loc[2, "amount_cents"] == 0


def test_dax_uses_the_same_weights():
    expression = dax_expression()
    assert "0.5 * Falha + 0.5 * Exposicao" in expression
    assert "OR(ISBLANK(Falha), ISBLANK(Exposicao))" in expression
    assert "[OTIF %]" in expression
    assert "[Saldo vencido]" in expression
    assert "[Valor contratado]" in expression
