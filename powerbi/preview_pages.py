"""Static page previews from the same CSV files and measure rules as the PBIP.

These images are not Power BI Desktop screenshots.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.pbi_export import (  # noqa: E402
    as_of_label,
    category_summary,
    format_brl,
    format_num,
    format_pct,
    inventory_kpis,
    monthly_orders,
    monthly_stockout,
    order_kpis,
    stockout_by_warehouse,
    supplier_summary,
)

OUT = ROOT / "docs" / "powerbi"
BG = "#F7F9FC"
INK = "#142D46"
MUTED = "#5C6B7A"
TEAL = "#00857C"
NAVY = "#274E73"
AMBER = "#F0A23B"
RED = "#B65555"
CAPTION = "Pré-visualização gerada por script. Não é captura do Power BI Desktop."


def load(root):
    data = Path(root) / "data" / "pbi"
    return {
        "orders": pd.read_csv(data / "fact_orders.csv"),
        "partners": pd.read_csv(data / "dim_partner.csv", dtype=str),
        "products": pd.read_csv(data / "dim_product.csv", dtype=str),
        "warehouses": pd.read_csv(data / "dim_warehouse.csv", dtype=str),
        "inventory": pd.read_csv(data / "fact_inventory.csv"),
    }


def new_figure(title, subtitle):
    fig = plt.figure(figsize=(12.8, 7.2), dpi=120)
    fig.patch.set_facecolor(BG)
    fig.suptitle(title, x=0.035, ha="left", fontsize=16, color=INK, fontweight="bold")
    fig.text(0.035, 0.935, subtitle, color=MUTED, fontsize=9)
    fig.text(0.035, 0.012, CAPTION, color=RED, fontsize=8)
    return fig


def brl_card(value):
    if abs(value) >= 1_000_000:
        return "R$ " + f"{value / 1_000_000:.1f}".replace(".", ",") + " mi"
    return format_brl(value)


def kpi_box(ax, label, value):
    ax.set_axis_off()
    ax.set_facecolor("white")
    ax.add_patch(
        plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes, facecolor="white", edgecolor="#E2E8F0", lw=1)
    )
    ax.text(0.08, 0.68, label, color=MUTED, fontsize=8, transform=ax.transAxes, va="center")
    ax.text(0.08, 0.30, value, color=INK, fontsize=12, fontweight="bold", transform=ax.transAxes, va="center")


def thin_months(ax):
    labels = ax.get_xticklabels()
    for index, label in enumerate(labels):
        label.set_visible(index % 3 == 0)
    ax.tick_params(axis="x", labelrotation=0, labelsize=7)


def style_ax(ax, title):
    ax.set_facecolor("white")
    ax.set_title(title, loc="left", color=INK, fontsize=11, pad=8)
    ax.tick_params(colors=MUTED, labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#E2E8F0")
    ax.grid(axis="y", color="#EEF2F6", lw=0.8)
    ax.set_axisbelow(True)


def render(root=ROOT):
    frames = load(root)
    orders = order_kpis(frames["orders"])
    inventory = inventory_kpis(frames["inventory"])
    OUT.mkdir(parents=True, exist_ok=True)
    _executive(frames, orders, inventory)
    _suppliers(frames, orders)
    _inventory(frames, inventory)
    worst = supplier_summary(frames["orders"], frames["partners"]).iloc[0]
    _detail(frames, worst)
    plt.close("all")


def _executive(frames, orders, inventory):
    fig = new_figure(
        "SupplyWatch  |  Visão executiva",
        f"Dados sintéticos, semente 42. Sem segmentador. Posição {as_of_label()}.",
    )
    gs = fig.add_gridspec(
        3, 6, height_ratios=[0.62, 1.35, 1.35], left=0.05, right=0.98, top=0.88, bottom=0.08, hspace=0.55, wspace=0.4
    )
    cards = [
        ("OTIF %", format_pct(orders["otif"])),
        ("Fill rate %", format_pct(orders["fill_rate"])),
        ("Lead time", format_num(orders["lead_time"]) + " d"),
        ("Taxa de ruptura %", format_pct(inventory["taxa_ruptura"])),
        ("Valor contratado", brl_card(orders["valor_contratado"])),
        ("Saldo vencido", brl_card(orders["saldo_vencido"])),
    ]
    for index, (label, value) in enumerate(cards):
        kpi_box(fig.add_subplot(gs[0, index]), label, value)
    monthly = monthly_orders(frames["orders"])
    ax = fig.add_subplot(gs[1, 0:4])
    style_ax(ax, "OTIF % e fill rate % por mês do pedido")
    ax.plot(monthly["month"], monthly["otif"] * 100, color=TEAL, marker="o", ms=3, label="OTIF %")
    ax.plot(monthly["month"], monthly["fill_rate"] * 100, color=NAVY, marker="o", ms=3, label="Fill rate %")
    thin_months(ax)
    ax.set_ylabel("%", color=MUTED)
    ax.legend(frameon=False, fontsize=8)
    categories = category_summary(frames["orders"], frames["products"])
    ax = fig.add_subplot(gs[1, 4:6])
    style_ax(ax, "Valor contratado por categoria")
    ax.bar(categories["category"], categories["valor_contratado"] / 1e6, color=TEAL)
    ax.set_ylabel("R$ milhões", color=MUTED)
    ax.tick_params(axis="x", labelrotation=25)
    ax = fig.add_subplot(gs[2, 0:3])
    style_ax(ax, "Lead time completo por mês do pedido")
    ax.plot(monthly["month"], monthly["lead_time"], color=AMBER, marker="o", ms=3)
    thin_months(ax)
    ax.set_ylabel("dias", color=MUTED)
    suppliers = supplier_summary(frames["orders"], frames["partners"]).sort_values("saldo_vencido")
    ax = fig.add_subplot(gs[2, 3:6])
    style_ax(ax, "Saldo vencido por fornecedor")
    ax.barh(suppliers["partner_name"], suppliers["saldo_vencido"] / 1e3, color=RED)
    ax.set_xlabel("R$ mil", color=MUTED)
    fig.savefig(OUT / "01-visao-executiva.png", facecolor=fig.get_facecolor())


def _suppliers(frames, orders):
    fig = new_figure(
        "SupplyWatch  |  Fornecedores",
        "Sem segmentador. OTIF inclui linha vencida sem entrega. Saldo vencido não é perda realizada.",
    )
    summary = supplier_summary(frames["orders"], frames["partners"])
    gs = fig.add_gridspec(2, 2, height_ratios=[1.2, 1], left=0.12, right=0.98, top=0.88, bottom=0.08, hspace=0.35, wspace=0.25)
    by_otif = summary.sort_values("otif")
    ax = fig.add_subplot(gs[0, 0])
    style_ax(ax, "OTIF % por fornecedor")
    ax.barh(by_otif["partner_name"], by_otif["otif"] * 100, color=TEAL)
    ax.set_xlabel("%", color=MUTED)
    by_lead = summary.sort_values("lead_time")
    ax = fig.add_subplot(gs[0, 1])
    style_ax(ax, "Lead time completo por fornecedor")
    ax.barh(by_lead["partner_name"], by_lead["lead_time"], color=NAVY)
    ax.set_xlabel("dias", color=MUTED)
    ax = fig.add_subplot(gs[1, :])
    ax.set_axis_off()
    ax.set_title("Fila de ação por saldo vencido", loc="left", color=INK, fontsize=11)
    shown = summary.head(8)
    cells = []
    for row in shown.itertuples(index=False):
        cells.append(
            [
                row.partner_name,
                row.region,
                format_pct(row.otif),
                format_pct(row.fill_rate),
                format_num(row.lead_time),
                format_brl(row.saldo_vencido),
                format_pct(row.participacao),
            ]
        )
    table = ax.table(
        cellText=cells,
        colLabels=["Fornecedor", "UF", "OTIF %", "Fill rate %", "Lead time", "Saldo vencido", "Participação"],
        loc="upper center",
        cellLoc="left",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.25)
    fig.savefig(OUT / "02-fornecedores.png", facecolor=fig.get_facecolor())


def _inventory(frames, inventory):
    fig = new_figure(
        "SupplyWatch  |  Estoque e rupturas",
        "Série sintética. Ruptura é demanda do dia não atendida. O fornecedor não altera este recorte.",
    )
    cards = [
        ("Taxa de ruptura %", format_pct(inventory["taxa_ruptura"])),
        ("Combinações em ruptura", str(inventory["combinacoes_em_ruptura"])),
        ("Estoque na posição", format_num(inventory["estoque_na_posicao"], 0)),
        ("Cobertura em dias", format_num(inventory["cobertura_dias"])),
    ]
    outer = fig.add_gridspec(2, 1, height_ratios=[0.38, 1.6], left=0.06, right=0.98, top=0.88, bottom=0.12, hspace=0.35)
    top = outer[0].subgridspec(1, 4, wspace=0.25)
    for index, (label, value) in enumerate(cards):
        kpi_box(fig.add_subplot(top[0, index]), label, value)
    bottom = outer[1].subgridspec(1, 2, wspace=0.28)
    monthly = monthly_stockout(frames["inventory"])
    ax = fig.add_subplot(bottom[0, 0])
    style_ax(ax, "Taxa de ruptura % por mês")
    ax.plot(monthly["month"], monthly["taxa_ruptura"] * 100, color=RED, marker="o", ms=3)
    thin_months(ax)
    ax.set_ylabel("%", color=MUTED)
    by_wh = stockout_by_warehouse(frames["inventory"], frames["warehouses"]).sort_values("taxa_ruptura")
    ax = fig.add_subplot(bottom[0, 1])
    style_ax(ax, "Taxa de ruptura % por almoxarifado")
    ax.barh(by_wh["warehouse_name"], by_wh["taxa_ruptura"] * 100, color=AMBER)
    ax.set_xlabel("%", color=MUTED)
    fig.savefig(OUT / "03-estoque-rupturas.png", facecolor=fig.get_facecolor())


def _detail(frames, worst):
    name = worst.partner_name
    subset = frames["orders"].merge(frames["partners"], on="partner_id")
    subset = subset.loc[subset.partner_name.eq(name)].merge(frames["products"], on="product_id")
    subset = subset.merge(frames["warehouses"], on="warehouse_id")
    kpis = order_kpis(subset)
    fig = new_figure(
        "SupplyWatch  |  Detalhe do pedido",
        f"Exemplo de drill-through no fornecedor de maior saldo vencido: {name}.",
    )
    outer = fig.add_gridspec(2, 1, height_ratios=[0.38, 1.7], left=0.04, right=0.98, top=0.88, bottom=0.08, hspace=0.28)
    top = outer[0].subgridspec(1, 5, wspace=0.25)
    cards = [
        ("Valor contratado", brl_card(kpis["valor_contratado"])),
        ("OTIF %", format_pct(kpis["otif"])),
        ("Fill rate %", format_pct(kpis["fill_rate"])),
        ("Lead time", format_num(kpis["lead_time"]) + " d"),
        ("Saldo vencido", brl_card(kpis["saldo_vencido"])),
    ]
    for index, (label, value) in enumerate(cards):
        kpi_box(fig.add_subplot(top[0, index]), label, value)
    ax = fig.add_subplot(outer[1])
    ax.set_axis_off()
    ax.set_title("Linhas com maior saldo vencido", loc="left", color=INK, fontsize=11)
    shown = subset.sort_values("overdue_cents", ascending=False).head(8)
    cells = []
    for row in shown.itertuples(index=False):
        cells.append(
            [
                row.order_id,
                row.line_id,
                row.product_name,
                row.city,
                row.order_date,
                row.due_date,
                row.situacao,
                f"{int(row.quantity)}",
                f"{int(row.received_quantity)}",
                format_brl(row.overdue_cents / 100),
            ]
        )
    table = ax.table(
        cellText=cells,
        colLabels=["Pedido", "Linha", "Produto", "Cidade", "Pedido em", "Prazo", "Situação", "Qtd", "Recebida", "Saldo vencido"],
        colWidths=[0.08, 0.08, 0.15, 0.13, 0.10, 0.10, 0.11, 0.06, 0.08, 0.11],
        loc="upper center",
        cellLoc="left",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7.5)
    table.scale(1, 1.35)
    fig.savefig(OUT / "04-detalhe.png", facecolor=fig.get_facecolor())


if __name__ == "__main__":
    render()
