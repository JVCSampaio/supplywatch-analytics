"""Synthetic Power BI tables on top of the purchase-order fact.

Order lines come from the existing pipeline. Warehouse on those lines is a
deterministic label (seed 42): the source orders have no warehouse. Inventory
snapshots are generated here and are not part of the purchase pipeline.
"""

import hashlib
import random
from datetime import date

import pandas as pd
from analytics.domain import AS_OF
from analytics.io import read_partners
from analytics.pipeline import run

SEED = 42
START = "2024-01-01"
WAREHOUSES = (
    ("W01", "Almoxarifado Macaé", "Macaé", "RJ"),
    ("W02", "Base Santos", "Santos", "SP"),
    ("W03", "Canteiro Camaçari", "Camaçari", "BA"),
    ("W04", "Hub Duque de Caxias", "Duque de Caxias", "RJ"),
)
DEMAND_MEAN = {
    "P001": 2,
    "P002": 1,
    "P003": 4,
    "P004": 3,
    "P005": 8,
    "P006": 6,
    "P007": 5,
    "P008": 2,
}
REPLENISH_EVERY = {"W01": 14, "W02": 14, "W03": 21, "W04": 14}
MISS_REPLENISHMENT = {"W01": 0.06, "W02": 0.12, "W03": 0.42, "W04": 0.20}
MONTHS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def warehouse_id(order_id, seed=SEED):
    digest = hashlib.sha256(f"supplywatch-{seed}|{order_id}".encode()).hexdigest()
    return WAREHOUSES[int(digest[:8], 16) % len(WAREHOUSES)][0]


def build_calendar(start=START, end=AS_OF):
    dates = pd.date_range(start, end, freq="D")
    month_numbers = dates.month
    return pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "year": dates.year.astype(int),
            "quarter": [f"{day.year}-T{(day.month - 1) // 3 + 1}" for day in dates],
            "month": dates.strftime("%Y-%m"),
            "month_name": [f"{MONTHS[day.month - 1]}/{day.year}" for day in dates],
            "month_sort": (dates.year * 100 + month_numbers).astype(int),
        }
    )


def build_inventory(product_ids, seed=SEED, start=START, end=AS_OF):
    """Daily product-warehouse snapshot. stockout_flag is unmet demand that day."""
    rng = random.Random(seed)
    dates = pd.date_range(start, end, freq="D")
    rows = []
    for warehouse, *_rest in WAREHOUSES:
        every = REPLENISH_EVERY[warehouse]
        miss = MISS_REPLENISHMENT[warehouse]
        for product_id in sorted(product_ids):
            mean = DEMAND_MEAN.get(product_id, 2)
            safety = mean * 5
            target = safety + mean * every
            on_hand = target
            for index, day in enumerate(dates):
                demand = rng.randint(0, mean * 2)
                short = max(0, demand - on_hand)
                on_hand -= demand - short
                if index % every == every - 1 and rng.random() >= miss:
                    on_hand += max(0, target - on_hand)
                stamp = day.strftime("%Y-%m-%d")
                rows.append(
                    {
                        "snapshot_id": f"{stamp}|{warehouse}|{product_id}",
                        "snapshot_date": stamp,
                        "warehouse_id": warehouse,
                        "product_id": product_id,
                        "on_hand_qty": on_hand,
                        "safety_qty": safety,
                        "demand_qty": demand,
                        "short_qty": short,
                        "stockout_flag": int(short > 0),
                    }
                )
    frame = pd.DataFrame(rows)
    if frame.snapshot_id.duplicated().any():
        raise ValueError("inventory snapshot key is not unique")
    return frame


def prepare_orders(fact):
    frame = fact.copy()
    frame["warehouse_id"] = frame.order_id.map(lambda value: warehouse_id(value))
    frame["situacao"] = frame.status.map(
        lambda value: "Pedido ativo" if value == "ordered" else "Cancelado"
    )
    for column in ("order_date", "due_date", "last_received_date"):
        parsed = pd.to_datetime(frame[column], errors="coerce")
        frame[column] = parsed.dt.strftime("%Y-%m-%d")
    return frame


def load_model_frames(root):
    """Run the purchase pipeline, then add the synthetic warehouse and inventory."""
    run(root)
    root_path = root if hasattr(root, "joinpath") else __import__("pathlib").Path(root)
    exports = root_path / "data" / "exports"
    partners = read_partners(root_path / "data" / "source" / "partners.xlsx")
    products = pd.read_csv(exports / "dim_product.csv", dtype=str)
    orders = pd.read_csv(exports / "fact_orders.csv")
    calendar = build_calendar()
    inventory = build_inventory(products.product_id.tolist())
    warehouses = pd.DataFrame(
        WAREHOUSES, columns=["warehouse_id", "warehouse_name", "city", "state"]
    )
    prepared = prepare_orders(orders)
    _assert_keys(prepared, partners, products, warehouses, calendar, inventory)
    return {
        "dim_partner": partners,
        "dim_product": products,
        "dim_warehouse": warehouses,
        "dim_date": calendar,
        "fact_orders": prepared,
        "fact_inventory": inventory,
    }


def _assert_keys(orders, partners, products, warehouses, calendar, inventory):
    if not set(orders.partner_id).issubset(set(partners.partner_id)):
        raise ValueError("order partner_id missing from dim_partner")
    if not set(orders.product_id).issubset(set(products.product_id)):
        raise ValueError("order product_id missing from dim_product")
    if not set(orders.warehouse_id).issubset(set(warehouses.warehouse_id)):
        raise ValueError("order warehouse_id missing from dim_warehouse")
    if not set(orders.order_date).issubset(set(calendar.date)):
        raise ValueError("order_date missing from dim_date")
    if not set(inventory.product_id).issubset(set(products.product_id)):
        raise ValueError("inventory product_id missing from dim_product")
    if not set(inventory.warehouse_id).issubset(set(warehouses.warehouse_id)):
        raise ValueError("inventory warehouse_id missing from dim_warehouse")
    if not set(inventory.snapshot_date).issubset(set(calendar.date)):
        raise ValueError("snapshot_date missing from dim_date")
    if orders.groupby("order_id").warehouse_id.nunique().max() != 1:
        raise ValueError("one order was assigned to more than one warehouse")


def order_kpis(fact):
    active = fact.loc[fact.status.eq("ordered")]
    eligible = int(fact.due_eligible.sum())
    ordered_qty = int(active.quantity.sum())
    received_qty = int(active.received_quantity.sum())
    return {
        "valor_contratado": fact.amount_cents.sum() / 100,
        "saldo_aberto": fact.open_cents.sum() / 100,
        "saldo_vencido": fact.overdue_cents.sum() / 100,
        "linhas_elegiveis": eligible,
        "linhas_otif": int(fact.otif.sum()),
        "otif": (fact.otif.sum() / eligible) if eligible else None,
        "quantidade_pedida": ordered_qty,
        "quantidade_recebida": received_qty,
        "fill_rate": (received_qty / ordered_qty) if ordered_qty else None,
        "lead_time": float(fact.lead_days.mean()) if fact.lead_days.notna().any() else None,
        "pedidos_ativos": int(active.order_id.nunique()),
    }


def inventory_kpis(inventory):
    observed = len(inventory)
    stockout_days = int(inventory.stockout_flag.sum())
    last = inventory.snapshot_date.max()
    position = inventory.loc[inventory.snapshot_date.eq(last)]
    daily = inventory.groupby("snapshot_date").demand_qty.sum()
    demand_mean = float(daily.mean()) if len(daily) else None
    stock = int(position.on_hand_qty.sum())
    return {
        "as_of": last,
        "dias_observados": observed,
        "dias_em_ruptura": stockout_days,
        "taxa_ruptura": (stockout_days / observed) if observed else None,
        "quantidade_nao_atendida": int(inventory.short_qty.sum()),
        "estoque_na_posicao": stock,
        "demanda_na_posicao": int(position.demand_qty.sum()),
        "combinacoes_em_ruptura": int(position.stockout_flag.sum()),
        "cobertura_dias": (stock / demand_mean) if demand_mean else None,
        "seguranca_na_posicao": int(position.safety_qty.sum()),
    }


def monthly_orders(fact):
    frame = fact.copy()
    frame["month"] = frame.order_date.str.slice(0, 7)
    rows = []
    for month, group in frame.groupby("month", sort=True):
        kpis = order_kpis(group)
        rows.append({"month": month, **kpis})
    return pd.DataFrame(rows)


def supplier_summary(fact, partners):
    rows = []
    for partner_id, group in fact.groupby("partner_id", sort=False):
        kpis = order_kpis(group)
        kpis["partner_id"] = partner_id
        rows.append(kpis)
    summary = pd.DataFrame(rows).merge(partners, on="partner_id", how="left")
    total = summary.valor_contratado.sum()
    summary["participacao"] = summary.valor_contratado / total if total else 0
    return summary.sort_values("saldo_vencido", ascending=False)


def category_summary(fact, products):
    rows = []
    for product_id, group in fact.groupby("product_id", sort=False):
        kpis = order_kpis(group)
        kpis["product_id"] = product_id
        rows.append(kpis)
    summary = pd.DataFrame(rows).merge(products, on="product_id", how="left")
    return (
        summary.groupby("category", as_index=False)
        .agg(valor_contratado=("valor_contratado", "sum"), saldo_vencido=("saldo_vencido", "sum"))
        .sort_values("valor_contratado", ascending=False)
    )


def monthly_stockout(inventory):
    frame = inventory.copy()
    frame["month"] = frame.snapshot_date.str.slice(0, 7)
    grouped = frame.groupby("month", sort=True).stockout_flag.agg(taxa_ruptura="mean", dias_em_ruptura="sum")
    return grouped.reset_index()


def stockout_by_warehouse(inventory, warehouses):
    grouped = inventory.groupby("warehouse_id").stockout_flag.agg(
        taxa_ruptura="mean", dias_em_ruptura="sum"
    )
    summary = grouped.reset_index().merge(warehouses, on="warehouse_id")
    return summary.sort_values("taxa_ruptura", ascending=False)


def position_rows(inventory, products, warehouses):
    last = inventory.snapshot_date.max()
    position = inventory.loc[inventory.snapshot_date.eq(last)].copy()
    daily = (
        inventory.groupby(["warehouse_id", "product_id"])
        .agg(demanda_media=("demand_qty", "mean"), dias_em_ruptura=("stockout_flag", "sum"), dias=("stockout_flag", "size"))
        .reset_index()
    )
    daily["taxa_ruptura"] = daily.dias_em_ruptura / daily.dias
    merged = position.merge(daily, on=["warehouse_id", "product_id"])
    merged = merged.merge(products, on="product_id").merge(warehouses, on="warehouse_id")
    merged["cobertura_dias"] = merged.on_hand_qty / merged.demanda_media.replace(0, pd.NA)
    return merged.sort_values(["taxa_ruptura", "warehouse_name"], ascending=[False, True])


def format_brl(value):
    sign = "-" if value < 0 else ""
    whole, frac = f"{abs(value):.2f}".split(".")
    parts = []
    while whole:
        parts.append(whole[-3:])
        whole = whole[:-3]
    return f"{sign}R$ {'.'.join(reversed(parts))},{frac}"


def format_pct(value):
    if value is None:
        return "branco"
    return f"{value * 100:.1f}".replace(".", ",") + "%"


def format_num(value, digits=1):
    if value is None:
        return "branco"
    return f"{value:.{digits}f}".replace(".", ",")


def as_of_label():
    year, month, day = (int(part) for part in AS_OF.split("-"))
    return date(year, month, day).strftime("%d/%m/%Y")
