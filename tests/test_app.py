from pathlib import Path
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from analytics.pipeline import run
from analytics.risk import supplier_risk_table

ROOT = Path(__file__).resolve().parents[1]


def _risk_ranking(app):
    frames = [block.value for block in app.dataframe]
    return next(frame for frame in frames if "Risco" in list(getattr(frame, "columns", [])))


def test_app_filters_exports_and_empty_state():
    run(ROOT)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert len(app.metric) >= 4
    fact = pd.read_csv(ROOT / "data/exports/fact_orders.csv")
    partners = pd.read_csv(ROOT / "data/exports/dim_partner.csv", dtype=str)
    expected = supplier_risk_table(fact, partners)
    ranking = _risk_ranking(app)
    assert ranking.iloc[0]["Fornecedor"] == expected.iloc[0]["partner_name"]
    assert ranking.iloc[0]["Risco"] == pytest.approx(expected.iloc[0]["risk_score"])
    before = app.metric[0].value
    app.multiselect[0].select("RJ").run()
    assert not app.exception
    assert app.metric[0].value != before
    rio_partners = partners.loc[partners.region.eq("RJ")]
    rio_fact = fact.loc[fact.partner_id.isin(set(rio_partners.partner_id))]
    rio_expected = supplier_risk_table(rio_fact, rio_partners)
    rio_ranking = _risk_ranking(app)
    assert rio_ranking.iloc[0]["Fornecedor"] == rio_expected.iloc[0]["partner_name"]
    assert set(rio_ranking["Fornecedor"]) == set(rio_expected.partner_name)
    app.selectbox[0].select("region").run()
    assert not app.exception
    app.checkbox[0].check().run()
    assert not app.exception
    # All synthetic suppliers/customers in RJ are never in every possible segment,
    # but an impossible date/category slice is tested independently in SQL tests.
