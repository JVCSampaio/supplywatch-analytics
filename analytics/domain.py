"""Purchase-order-line metrics, evaluated at a fixed and explicit snapshot date."""

import pandas as pd
from analytics.io import require_columns
from analytics.quality import Gate

AS_OF = "2025-12-31"
TITLE = "SupplyWatch"
SUBTITLE = "Compras e fornecedores para operações de Óleo e Gás"
AMOUNT = "amount_cents"
AMOUNT_LABEL = "Valor contratado"
PARTNER_LABEL = "Fornecedor"


def transform(orders, events, partners, products):
    require_columns(
        orders,
        [
            "line_id",
            "order_id",
            "order_date",
            "due_date",
            "partner_id",
            "product_id",
            "quantity",
            "unit_price_cents",
            "status",
        ],
        "orders",
    )
    require_columns(events, ["event_id", "line_id", "event_date", "quantity"], "events")
    gate = Gate(orders, "orders")
    gate.key("line_id")
    clean = gate.frame.copy()
    clean["quantity"] = gate.number("quantity", lower=1, integer=True)
    clean["unit_price_cents"] = gate.number("unit_price_cents", lower=1, integer=True)
    ordered, due = gate.date("order_date"), gate.date("due_date")
    gate.reject((ordered > AS_OF) | (ordered < "2024-01-01") | (due < ordered), "date_sequence")
    gate.reject(~clean.status.isin(["ordered", "cancelled"]), "invalid_status")
    gate.reject(clean.order_id.astype(str).str.strip().eq(""), "missing_order_id")
    gate.reject(~clean.partner_id.isin(partners.partner_id), "unknown_partner")
    gate.reject(~clean.product_id.isin(products.product_id), "unknown_product")
    good, _ = gate.finish(clean)
    event_gate = Gate(events, "events")
    event_gate.key("event_id")
    received = event_gate.frame.copy()
    received["quantity"] = event_gate.number("quantity", lower=1, integer=True)
    event_date = event_gate.date("event_date")
    mapped_dates = pd.to_datetime(received.line_id.map(good.set_index("line_id").order_date))
    event_gate.reject(~received.line_id.isin(good.line_id), "unknown_or_invalid_line")
    event_gate.reject((event_date > AS_OF) | (event_date < mapped_dates), "event_date_sequence")
    cancelled = good.loc[good.status.eq("cancelled"), "line_id"]
    event_gate.reject(received.line_id.isin(cancelled), "receipt_on_cancelled_line")
    valid_events, _ = event_gate.finish(received)
    totals = valid_events.groupby("line_id").quantity.sum()
    over = good.line_id.map(totals).fillna(0) > good.quantity
    over_ids = good.loc[over, "line_id"]
    event_gate.reject(received.line_id.isin(over_ids), "over_receipt")
    bad_parents = received.loc[event_gate.reasons.ne(""), "line_id"]
    gate.reject(clean.line_id.isin(bad_parents), "invalid_event_dependency")
    good, rejected_orders = gate.finish(clean)
    event_gate.reject(~received.line_id.isin(good.line_id), "invalid_order_dependency")
    valid_events, rejected_events = event_gate.finish(received)
    joined = valid_events.merge(good[["line_id", "due_date"]], on="line_id", validate="many_to_one")
    joined["on_time_quantity"] = joined.quantity.where(joined.event_date <= joined.due_date, 0)
    agg = joined.groupby("line_id").agg(
        received_quantity=("quantity", "sum"),
        on_time_quantity=("on_time_quantity", "sum"),
        last_received_date=("event_date", "max"),
    )
    fact = good.merge(agg, on="line_id", how="left", validate="one_to_one")
    for col in ["quantity", "unit_price_cents", "received_quantity", "on_time_quantity"]:
        fact[col] = fact[col].fillna(0).astype("int64")
    active = fact.status.ne("cancelled")
    fact["amount_cents"] = (fact.quantity * fact.unit_price_cents).where(active, 0)
    fact["open_quantity"] = (fact.quantity - fact.received_quantity).where(active, 0)
    fact["open_cents"] = fact.open_quantity * fact.unit_price_cents
    fact["due_eligible"] = (active & fact.due_date.le(AS_OF)).astype(int)
    fact["otif"] = (fact.on_time_quantity.ge(fact.quantity) & fact.due_eligible.eq(1)).astype(int)
    complete = active & fact.received_quantity.eq(fact.quantity)
    fact["lead_days"] = (
        pd.to_datetime(fact.last_received_date) - pd.to_datetime(fact.order_date)
    ).dt.days.where(complete)
    fact["overdue_cents"] = fact.open_cents.where(fact.due_eligible.eq(1), 0)
    return fact, [rejected_orders, rejected_events]


def kpis(frame):
    eligible = frame.due_eligible.sum()
    return {
        "amount": frame.amount_cents.sum() / 100,
        "rate": frame.otif.sum() / eligible if eligible else None,
        "secondary": frame.overdue_cents.sum() / 100,
        "orders": frame.loc[frame.status.ne("cancelled"), "order_id"].nunique(),
    }


def describe(fact, partners, monthly, output):
    k = kpis(fact)
    worst = partners.sort_values("overdue_cents", ascending=False).iloc[0]
    return f"""# Parecer de suprimentos

Dados inteiramente simulados. Posição em {AS_OF}; coorte pela data do pedido.

- Valor contratado: R$ {k["amount"]:,.2f} (cancelados excluídos).
- OTIF por linha vencida: {k["rate"]:.1%}; inclui linhas ainda não entregues no denominador.
- Saldo vencido em aberto: R$ {k["secondary"]:,.2f}.
- Maior saldo vencido: {worst["partner_name"]}, R$ {worst["overdue_cents"] / 100:,.2f}.

## Recomendação e plano de ação proposto

1. Compras: revisar as linhas vencidas do fornecedor acima em até 5 dias úteis e solicitar datas de regularização.
2. Operações: classificar criticidade dos itens antes de priorizar expedição. O cadastro atual não mede impacto na produção.
3. Produto/Dados: revisar rejeições da carga a cada execução. Não substituir ausência de informação por zero.
4. Em 30 dias, comparar saldo vencido e OTIF com esta linha de base e registrar as ações executadas.

O saldo em aberto é exposição contratual, não perda realizada. Este estudo não demonstra economia obtida.
OTIF é calculado por linha, não por pedido. Lead time é observado somente em linhas completas e sofre viés de sobrevivência.
"""
