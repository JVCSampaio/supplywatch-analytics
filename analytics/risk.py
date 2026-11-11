"""Supplier review index for the synthetic purchase fact.

The index ranks suppliers for a purchasing review. It is not a probability of
failure, a credit score, or a material-criticality rating: those attributes are
not in the source data.

Two components, each on [0, 1], with equal weights:

* falha_otif = 1 - (OTIF lines / eligible lines)
* exposicao_vencida = overdue cents / contracted cents

Both denominators are required. If either is zero the score is blank, so a
supplier whose lines are not yet due is not presented as low risk. Cancelled
lines contribute zero to the contracted value, the OTIF counts and the overdue
balance, which is the same rule as the rest of the fact.

The weights sum to 1 and are an explicit choice for this sample, not a fitted
model. With both components inside [0, 1], the score stays inside [0, 100].
Overdue cents cannot exceed contracted cents in this fact; the function rejects
that input rather than publishing a score above 100.
"""

import pandas as pd

WEIGHT_OTIF_MISS = 0.5
WEIGHT_OVERDUE_EXPOSURE = 0.5

COLUMNS = [
    "partner_id",
    "partner_name",
    "region",
    "segment",
    "amount_cents",
    "overdue_cents",
    "otif_lines",
    "eligible_lines",
    "falha_otif",
    "exposicao_vencida",
    "risk_score",
]


def dax_expression():
    """DAX for the PBIP measure. The weights are the constants above."""
    otif_weight = format(WEIGHT_OTIF_MISS, "g")
    exposure_weight = format(WEIGHT_OVERDUE_EXPOSURE, "g")
    return (
        "VAR Falha = IF(ISBLANK([OTIF %]), BLANK(), 1 - [OTIF %]) "
        "VAR Exposicao = DIVIDE([Saldo vencido], [Valor contratado]) "
        "RETURN IF(OR(ISBLANK(Falha), ISBLANK(Exposicao)), BLANK(), "
        f"100 * ({otif_weight} * Falha + {exposure_weight} * Exposicao))"
    )


def _whole(name, value):
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{name} must be a non-negative integer")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a non-negative integer") from exc
    if number != number or number < 0 or not number.is_integer():
        raise ValueError(f"{name} must be a non-negative integer")
    return int(number)


def risk_components(otif_lines, eligible_lines, overdue_cents, amount_cents):
    if WEIGHT_OTIF_MISS < 0 or WEIGHT_OVERDUE_EXPOSURE < 0:
        raise ValueError("risk weights cannot be negative")
    if abs((WEIGHT_OTIF_MISS + WEIGHT_OVERDUE_EXPOSURE) - 1) > 1e-9:
        raise ValueError("risk weights must sum to 1")
    otif = _whole("otif_lines", otif_lines)
    eligible = _whole("eligible_lines", eligible_lines)
    overdue = _whole("overdue_cents", overdue_cents)
    amount = _whole("amount_cents", amount_cents)
    if otif > eligible:
        raise ValueError("otif_lines cannot exceed eligible_lines")
    if overdue > amount:
        raise ValueError("overdue_cents cannot exceed amount_cents")
    falha = None if eligible == 0 else 1 - otif / eligible
    exposure = None if amount == 0 else overdue / amount
    if falha is None or exposure is None:
        score = None
    else:
        score = 100 * (WEIGHT_OTIF_MISS * falha + WEIGHT_OVERDUE_EXPOSURE * exposure)
    return {"falha_otif": falha, "exposicao_vencida": exposure, "risk_score": score}


def supplier_risk_table(fact, partners):
    """One row per partner. Partners with no published lines stay in the table with a blank score."""
    required = ["partner_id", "otif", "due_eligible", "overdue_cents", "amount_cents"]
    missing = [column for column in required if column not in fact.columns]
    if missing:
        raise ValueError("fact missing columns: " + ", ".join(missing))
    partner_cols = ["partner_id", "partner_name", "region", "segment"]
    missing_partners = [column for column in partner_cols if column not in partners.columns]
    if missing_partners:
        raise ValueError("partners missing columns: " + ", ".join(missing_partners))
    rows = []
    if not fact.empty:
        grouped = fact.copy()
        grouped["partner_id"] = grouped["partner_id"].astype(str)
        for partner_id, group in grouped.groupby("partner_id", sort=False):
            otif_lines = int(group.otif.sum())
            eligible = int(group.due_eligible.sum())
            overdue = int(group.overdue_cents.sum())
            amount = int(group.amount_cents.sum())
            components = risk_components(otif_lines, eligible, overdue, amount)
            rows.append(
                {
                    "partner_id": partner_id,
                    "amount_cents": amount,
                    "overdue_cents": overdue,
                    "otif_lines": otif_lines,
                    "eligible_lines": eligible,
                    **components,
                }
            )
    measured = pd.DataFrame(rows)
    directory = partners.loc[:, partner_cols].copy()
    directory["partner_id"] = directory["partner_id"].astype(str)
    if measured.empty:
        measured = pd.DataFrame(
            columns=[
                "partner_id",
                "amount_cents",
                "overdue_cents",
                "otif_lines",
                "eligible_lines",
                "falha_otif",
                "exposicao_vencida",
                "risk_score",
            ]
        )
    table = directory.merge(measured, on="partner_id", how="left")
    for column in ["amount_cents", "overdue_cents", "otif_lines", "eligible_lines"]:
        table[column] = table[column].fillna(0).astype(int)
    table = table.sort_values(
        ["risk_score", "overdue_cents", "partner_id"],
        ascending=[False, False, True],
        na_position="last",
    ).reset_index(drop=True)
    return table.loc[:, COLUMNS]


def write_supplier_risk(root, fact, partners):
    """Publish the same table to the warehouse export folder and to data/pbi."""
    from pathlib import Path

    table = supplier_risk_table(fact, partners)
    root = Path(root)
    destinations = [root / "data" / "exports", root / "data" / "pbi"]
    for folder in destinations:
        folder.mkdir(parents=True, exist_ok=True)
    table.to_csv(
        destinations[0] / "mart_supplier_risk.csv",
        index=False,
        encoding="utf-8",
        lineterminator="\n",
    )
    table.to_csv(
        destinations[1] / "supplier_risk.csv",
        index=False,
        encoding="utf-8",
        lineterminator="\n",
    )
    return table
