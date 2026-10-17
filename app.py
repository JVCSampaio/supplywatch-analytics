"""Interactive self-service analytics using the same curated fact as Power BI."""

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import date
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st
from analytics.domain import TITLE, SUBTITLE, AMOUNT, AMOUNT_LABEL, PARTNER_LABEL, AS_OF, kpis
from analytics.pipeline import run
from analytics.query import load, csv_download
from analytics.telemetry import record, summary

ROOT = Path(__file__).resolve().parent
SUPPLY = True
st.set_page_config(page_title=TITLE, page_icon="📊", layout="wide")
st.markdown(
    """<style>
  .block-container {padding-top:4rem; padding-bottom:2rem; max-width:1500px;}
  h1 {letter-spacing:-1.5px; font-weight:750;}
  [data-testid="stMetric"] {background:white; border:1px solid #dde5ed; border-top:3px solid #00857c;
    border-radius:10px; padding:18px 20px;}
  [data-testid="stMetricValue"] {font-size:1.8rem;}
</style>""",
    unsafe_allow_html=True,
)
st.caption("PORTFÓLIO DE DADOS  /  ESTUDO COM DADOS SIMULADOS")
st.title(TITLE)
st.write(SUBTITLE)
db_path = ROOT / "data/warehouse/analytics.db"
if not db_path.exists():
    with st.spinner("Preparando dados e controles de qualidade…"):
        run(ROOT)
with closing(sqlite3.connect(db_path)) as db:
    manifest = json.loads(db.execute("SELECT payload FROM build_manifest").fetchone()[0])
    regions = [x[0] for x in db.execute("SELECT DISTINCT region FROM dim_partner ORDER BY region")]
    categories = [
        x[0] for x in db.execute("SELECT DISTINCT category FROM dim_product ORDER BY category")
    ]
st.caption(
    f"Posição em {AS_OF} · Pedidos de 2024–2025 · Atualização: {manifest['built_at_utc'][:19]} UTC"
)
quality_path = ROOT / "reports/runtime/quality.json"
latest_quality = (
    json.loads(quality_path.read_text()) if quality_path.exists() else manifest["quality"]
)
if latest_quality["status"] == "failed":
    st.warning(
        "A última tentativa de carga foi rejeitada. Este painel mantém a última base aprovada."
    )

with st.sidebar:
    st.subheader("Recorte da análise")
    period = st.date_input(
        "Data do pedido",
        (date(2024, 1, 1), date(2025, 12, 31)),
        min_value=date(2024, 1, 1),
        max_value=date(2025, 12, 31),
    )
    selected_regions = st.multiselect("UF", regions)
    selected_categories = st.multiselect("Categoria", categories)
    st.caption(
        "Sem seleção = todas as opções. Os filtros afetam indicadores, gráficos e exportação."
    )
    st.divider()
    telemetry = st.checkbox("Registrar uso nesta instalação", value=False)
    st.caption("Opcional. Registra sessão aleatória e ações em banco local, sem nome ou IP.")

if len(period) != 2:
    st.info("Selecione a data inicial e a data final.")
    st.stop()
frame = load(db_path, *period, selected_regions, selected_categories)
session = st.session_state.setdefault("session_id", str(uuid.uuid4()))
usage_path = ROOT / "reports/runtime/usage.db"
signature = str((period, selected_regions, selected_categories))
if telemetry:
    if not st.session_state.get("view_recorded"):
        record(usage_path, session, "view")
        st.session_state["view_recorded"] = True
    if st.session_state.get("filter_signature") not in (None, signature):
        record(usage_path, session, "filter")
st.session_state["filter_signature"] = signature


def export_event():
    if telemetry:
        record(usage_path, session, "export")


def money(value):
    return (
        ("R$ " + f"{value / 1_000_000:.2f}".replace(".", ",") + " mi")
        if abs(value) >= 1_000_000
        else ("R$ " + f"{value:,.0f}").replace(",", ".")
    )


if frame.empty:
    st.warning("Nenhum pedido encontrado para este recorte. Amplie as datas ou remova filtros.")
    st.stop()

k = kpis(frame)
cards = st.columns(4)
cards[0].metric(AMOUNT_LABEL, money(k["amount"]))
cards[1].metric(
    "OTIF por linha" if SUPPLY else "Margem bruta",
    f"{k['rate']:.1%}" if k["rate"] is not None else "Não disponível",
)
cards[2].metric("Saldo vencido" if SUPPLY else "Devoluções", money(k["secondary"]))
cards[3].metric(
    "Pedidos ativos" if SUPPLY else "Pedidos faturados", f"{k['orders']:,}".replace(",", ".")
)
st.caption(
    "OTIF: quantidade integral recebida até o prazo / linhas com prazo vencido. Cancelados excluídos."
    if SUPPLY
    else "Receita após descontos e devoluções. Margem = soma das margens / soma das receitas. Sem impostos e frete."
)

tabs = st.tabs(
    [
        "Visão gerencial",
        "Explorar e exportar",
        "Qualidade e uso",
        "Método e decisões" if SUPPLY else "Estudo estatístico",
    ]
)
chart_style = dict(
    template="plotly_white", color_discrete_sequence=["#00857c", "#f0a23b", "#274e73"]
)
with tabs[0]:
    left, right = st.columns([1.65, 1])
    plot = frame.copy()
    plot["month"] = plot.order_date.str[:7]
    monthly = plot.groupby("month", as_index=False)[AMOUNT].sum()
    monthly["value"] = monthly[AMOUNT] / 100
    with left:
        st.subheader("Evolução por mês do pedido")
        fig = px.area(
            monthly, x="month", y="value", labels={"month": "Mês", "value": "R$"}, **chart_style
        )
        fig.update_layout(height=320, margin=dict(t=15, b=20, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})
    with right:
        st.subheader("Distribuição por categoria")
        category = frame.groupby("category", as_index=False)[AMOUNT].sum().sort_values(AMOUNT)
        category["value"] = category[AMOUNT] / 100
        fig = px.bar(
            category,
            y="category",
            x="value",
            orientation="h",
            labels={"category": "", "value": "R$"},
            **chart_style,
        )
        fig.update_layout(height=320, margin=dict(t=15, b=20, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})
    if SUPPLY:
        st.subheader("Fornecedores que precisam de atenção")
        ranking = frame.groupby("partner_name", as_index=False).agg(
            saldo_vencido=("overdue_cents", "sum"),
            elegiveis=("due_eligible", "sum"),
            completas_no_prazo=("otif", "sum"),
        )
        ranking["OTIF"] = ranking.completas_no_prazo.div(ranking.elegiveis.replace(0, float("nan")))
        ranking["Saldo vencido (R$)"] = ranking.saldo_vencido / 100
        ranking = ranking.sort_values("saldo_vencido", ascending=False)
        st.dataframe(
            ranking[["partner_name", "Saldo vencido (R$)", "OTIF", "elegiveis"]].rename(
                columns={"partner_name": "Fornecedor", "elegiveis": "Linhas elegíveis"}
            ),
            hide_index=True,
            column_config={"OTIF": st.column_config.NumberColumn(format="percent")},
            width="stretch",
        )
    else:
        st.subheader("Receita e margem por cliente")
        ranking = frame.groupby("partner_name", as_index=False).agg(
            receita=("net_revenue_cents", "sum"),
            margem=("margin_cents", "sum"),
            devolucoes=("return_cents", "sum"),
        )
        ranking["Margem (%)"] = 100 * ranking.margem.div(ranking.receita.replace(0, float("nan")))
        ranking["Receita (R$)"] = ranking.receita / 100
        fig = px.scatter(
            ranking, x="Receita (R$)", y="Margem (%)", hover_name="partner_name", **chart_style
        )
        fig.add_hline(y=20, line_dash="dot", annotation_text="Referência hipotética: 20%")
        fig.update_layout(height=320, margin=dict(t=20, b=20))
        st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})

with tabs[1]:
    st.subheader("Consulta de autosserviço")
    st.write(
        "Escolha uma dimensão para resumir o recorte atual. Baixe os registros para investigar a origem dos valores."
    )
    dimension = st.selectbox(
        "Agrupar por",
        ["category", "region", "segment", "partner_name"],
        format_func=lambda x: {
            "category": "Categoria",
            "region": "UF",
            "segment": "Segmento",
            "partner_name": PARTNER_LABEL,
        }[x],
    )
    grouped = frame.groupby(dimension, as_index=False)[AMOUNT].sum()
    grouped[AMOUNT_LABEL + " (R$)"] = grouped.pop(AMOUNT) / 100
    st.dataframe(grouped, hide_index=True, width="stretch")
    st.download_button(
        "Baixar dados filtrados (CSV)",
        csv_download(frame),
        "dados_filtrados.csv",
        mime="text/csv",
        on_click=export_event,
    )
    with st.expander("Ver linhas e campos de auditoria"):
        st.caption(
            "Campos terminados em _cents estão em centavos. Uma linha representa um item de pedido."
        )
        st.dataframe(frame, hide_index=True, width="stretch")

with tabs[2]:
    st.subheader("Qualidade da base publicada")
    quality = manifest["quality"]
    qcols = st.columns(3)
    qcols[0].metric("Linhas de origem", quality["source_rows"])
    qcols[1].metric("Linhas rejeitadas", quality["rejected_rows"])
    qcols[2].metric("Taxa de rejeição", f"{quality['rejected_rate']:.2%}")
    st.caption(
        "Indicadores de qualidade e uso abrangem toda a instalação e não recebem os filtros de negócio."
    )
    st.write(
        "Chaves duplicadas, datas inválidas, referências inexistentes e quantidades inconsistentes são isoladas. "
        "Acima de 3% de rejeição, a publicação é bloqueada. Limite hipotético, ajustável pela CLI."
    )
    rejected = pd.concat(
        [pd.read_csv(p) for p in sorted((ROOT / "data/quarantine").glob("*.csv"))],
        ignore_index=True,
    )
    st.dataframe(
        rejected[["source", "source_row", "line_id", "reason"]], hide_index=True, width="stretch"
    )
    st.caption(
        "A tabela de rejeições corresponde à última tentativa de carga, inclusive se ela falhou."
    )
    with st.expander("Rastreabilidade da base publicada"):
        st.json(quality)
    st.subheader("Adoção do produto de dados")
    usage = summary(usage_path)
    st.write(
        f"{usage['sessions']} sessões locais · {usage['views']} aberturas · {usage['exports']} exportações"
    )
    st.caption(
        "Cliques de exportação são um sinal de uso, não prova de decisão melhor. "
        "Combine com entrevistas, tempo para responder perguntas e redução de retrabalho."
    )

with tabs[3]:
    if not SUPPLY:
        st.caption("Estudo sobre a base completa; não recebe os filtros da barra lateral.")
        metrics = json.loads((ROOT / "reports/runtime/regression.json").read_text())
        if metrics["status"] == "evaluated":
            predictions = pd.read_csv(ROOT / "reports/runtime/backtest.csv")
            fig = px.line(
                predictions,
                x="month",
                y=["actual", "regression", "seasonal_baseline"],
                markers=True,
                labels={"value": "Receita (R$)", "month": "Mês", "variable": "Série"},
                **chart_style,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})
            st.json(metrics)
    st.markdown(
        (ROOT / "reports/runtime/executive_summary.md")
        .read_text(encoding="utf-8")
        .replace("$", r"\$")
    )
