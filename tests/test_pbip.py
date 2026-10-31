import json
from pathlib import Path

import pandas as pd
import pytest
from analytics.pbi_export import build_inventory, inventory_kpis, order_kpis, warehouse_id
from powerbi.validate_structure import schema_errors, structural_errors

ROOT = Path(__file__).resolve().parents[1]


def test_pbip_structure_and_relative_path():
    assert structural_errors() == []
    expression = (ROOT / "SupplyWatch.SemanticModel/definition/expressions.tmdl").read_text(encoding="utf-8")
    assert 'DataFolder = "data/pbi"' in expression


def test_pbip_schema_when_schemas_can_be_downloaded():
    errors = schema_errors()
    if errors and errors[0].startswith("skipped:"):
        pytest.skip(errors[0])
    assert errors == []


def test_order_totals_match_the_reference_sample():
    fact = pd.read_csv(ROOT / "data/pbi/fact_orders.csv")
    partners = pd.read_csv(ROOT / "data/pbi/dim_partner.csv", dtype=str)
    kpis = order_kpis(fact)
    reference = json.loads((ROOT / "reports/sample/metrics.json").read_text(encoding="utf-8"))
    assert kpis["valor_contratado"] == pytest.approx(reference["contracted_brl"], abs=0.01)
    assert kpis["otif"] == pytest.approx(reference["otif_rate"], abs=1e-12)
    assert kpis["saldo_vencido"] == pytest.approx(reference["overdue_brl"], abs=0.01)
    assert kpis["pedidos_ativos"] == reference["active_orders"]

    rio = fact.merge(partners, on="partner_id")
    rio = rio.loc[rio.region.eq("RJ")]
    rio_kpis = order_kpis(rio)
    rio_reference = json.loads((ROOT / "reports/sample/metrics_RJ.json").read_text(encoding="utf-8"))
    assert rio_kpis["valor_contratado"] == pytest.approx(rio_reference["contracted_brl"], abs=0.01)
    assert rio_kpis["otif"] == pytest.approx(rio_reference["otif_rate"], abs=1e-12)
    assert rio_kpis["saldo_vencido"] == pytest.approx(rio_reference["overdue_brl"], abs=0.01)
    assert rio_kpis["pedidos_ativos"] == rio_reference["active_orders"]


def test_manifest_matches_recomputed_measures():
    fact = pd.read_csv(ROOT / "data/pbi/fact_orders.csv")
    inventory = pd.read_csv(ROOT / "data/pbi/fact_inventory.csv")
    manifest = json.loads((ROOT / "data/pbi/manifest.json").read_text(encoding="utf-8"))
    assert manifest["synthetic"] is True
    assert manifest["seed"] == 42
    assert order_kpis(fact)["fill_rate"] == pytest.approx(manifest["orders"]["fill_rate"])
    assert inventory_kpis(inventory)["taxa_ruptura"] == pytest.approx(manifest["inventory"]["taxa_ruptura"])
    assert fact.groupby("order_id").warehouse_id.nunique().max() == 1
    assert set(fact.warehouse_id).issubset({"W01", "W02", "W03", "W04"})


def test_warehouse_and_inventory_depend_on_the_seed():
    assert warehouse_id("O00001", seed=42) == warehouse_id("O00001", seed=42)
    assigned_42 = [warehouse_id(f"O{i:05}", seed=42) for i in range(1, 40)]
    assigned_99 = [warehouse_id(f"O{i:05}", seed=99) for i in range(1, 40)]
    assert assigned_42 != assigned_99
    first = build_inventory(["P001"], seed=42, start="2024-01-01", end="2024-01-31")
    second = build_inventory(["P001"], seed=42, start="2024-01-01", end="2024-01-31")
    other = build_inventory(["P001"], seed=99, start="2024-01-01", end="2024-01-31")
    pd.testing.assert_frame_equal(first, second)
    assert not first.equals(other)


def test_portfolio_text_has_no_em_dash():
    paths = [
        ROOT / "README.md",
        ROOT / "powerbi/README.md",
        ROOT / "docs/dicionario_medidas.md",
        ROOT / "data/pbi/README.md",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "\u2014" not in text, path.name
        assert "\u2013" not in text, path.name
