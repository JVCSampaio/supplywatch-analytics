"""Write the SupplyWatch PBIP, the synthetic CSV folder and the measure dictionary.

Run from the repository root: python powerbi/build_pbip.py
"""

import hashlib
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.pbi_export import (  # noqa: E402
    SEED,
    as_of_label,
    format_brl,
    format_num,
    format_pct,
    inventory_kpis,
    load_model_frames,
    order_kpis,
)
from analytics.domain import AS_OF  # noqa: E402

PBIP = ROOT / "SupplyWatch.pbip"
MODEL = ROOT / "SupplyWatch.SemanticModel"
REPORT = ROOT / "SupplyWatch.Report"
DATA = ROOT / "data" / "pbi"

VISUAL_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
    "visualContainer/2.9.0/schema.json"
)
PAGE_SCHEMA = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
    "page/2.1.0/schema.json"
)
M_TYPE = {
    "string": "type text",
    "int64": "Int64.Type",
    "double": "type number",
    "dateTime": "type date",
}


def logical_id(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "supplywatch-analytics:" + name))


def visual_name(page, key):
    return hashlib.sha1(f"{page}:{key}".encode()).hexdigest()[:20]


def tmdl_name(name):
    if name.isascii() and name.isidentifier():
        return name
    return "'" + name.replace("'", "''") + "'"


def col(name, source, data_type, hidden=False, key=False, fmt=None, sort=None):
    return {
        "name": name,
        "source": source,
        "data_type": data_type,
        "hidden": hidden,
        "key": key,
        "fmt": fmt,
        "sort": sort,
    }


def measure(table, name, dax, fmt, folder, description):
    return {
        "table": table,
        "name": name,
        "dax": dax,
        "fmt": fmt,
        "folder": folder,
        "description": description,
    }


MEASURES = [
    measure(
        "fact_orders",
        "Valor contratado",
        "DIVIDE(SUM(fact_orders[amount_cents]), 100)",
        "R$ #,##0.00",
        "Pedidos",
        "Soma de quantidade vezes preço unitário, em reais. Cancelados entram como zero. É valor contratado, não valor pago.",
    ),
    measure(
        "fact_orders",
        "Saldo em aberto",
        "DIVIDE(SUM(fact_orders[open_cents]), 100)",
        "R$ #,##0.00",
        "Pedidos",
        "Quantidade ainda não recebida vezes preço, em reais. Cancelados entram como zero. É exposição contratual, não perda realizada.",
    ),
    measure(
        "fact_orders",
        "Saldo vencido",
        "DIVIDE(SUM(fact_orders[overdue_cents]), 100)",
        "R$ #,##0.00",
        "Pedidos",
        "Saldo em aberto das linhas com prazo até 31/12/2025. O corte está gravado na coluna e não acompanha o relógio do computador.",
    ),
    measure(
        "fact_orders",
        "Linhas elegíveis",
        "SUM(fact_orders[due_eligible])",
        "#,##0",
        "Pedidos",
        "Linhas ativas cujo prazo é menor ou igual à posição 31/12/2025. Cancelados ficam de fora.",
    ),
    measure(
        "fact_orders",
        "Linhas OTIF",
        "SUM(fact_orders[otif])",
        "#,##0",
        "Pedidos",
        "Linhas elegíveis recebidas por completo até o prazo.",
    ),
    measure(
        "fact_orders",
        "OTIF %",
        "DIVIDE([Linhas OTIF], [Linhas elegíveis])",
        "0.0%",
        "Pedidos",
        "Linhas OTIF divididas pelas linhas elegíveis. Linha vencida e ainda não entregue entra no denominador. Denominador zero retorna branco.",
    ),
    measure(
        "fact_orders",
        "Lead time completo",
        "AVERAGE(fact_orders[Lead time (dias)])",
        "0.0",
        "Pedidos",
        "Média de dias entre o pedido e o último recebimento. Só entra linha recebida por completo. Há viés de sobrevivência.",
    ),
    measure(
        "fact_orders",
        "Pedidos ativos",
        'CALCULATE(DISTINCTCOUNT(fact_orders[Pedido]), KEEPFILTERS(fact_orders[Status] = "ordered"))',
        "#,##0",
        "Pedidos",
        "Pedidos distintos com status ordered. Cancelados não entram.",
    ),
    measure(
        "fact_orders",
        "Participação fornecedor %",
        "DIVIDE([Valor contratado], CALCULATE([Valor contratado], ALLSELECTED(dim_partner)))",
        "0.0%",
        "Pedidos",
        "Valor do fornecedor dividido pelo valor contratado no universo selecionado de fornecedores.",
    ),
    measure(
        "fact_orders",
        "Quantidade pedida",
        'CALCULATE(SUM(fact_orders[Qtd pedida]), KEEPFILTERS(fact_orders[Status] = "ordered"))',
        "#,##0",
        "Pedidos",
        "Soma da quantidade pedida nas linhas ativas. É o denominador do fill rate.",
    ),
    measure(
        "fact_orders",
        "Quantidade recebida",
        'CALCULATE(SUM(fact_orders[Qtd recebida]), KEEPFILTERS(fact_orders[Status] = "ordered"))',
        "#,##0",
        "Pedidos",
        "Soma da quantidade recebida nas linhas ativas, com ou sem atraso. É o numerador do fill rate.",
    ),
    measure(
        "fact_orders",
        "Fill rate %",
        "DIVIDE([Quantidade recebida], [Quantidade pedida])",
        "0.0%",
        "Pedidos",
        "Quantidade recebida dividida pela quantidade pedida, só em linhas ativas. Não exige pontualidade. É diferente do OTIF, que é por linha e exige o prazo.",
    ),
    measure(
        "fact_inventory",
        "Dias observados",
        "COUNTROWS(fact_inventory)",
        "#,##0",
        "Estoque",
        "Linhas da foto diária no filtro. Cada linha é um dia de um produto em um almoxarifado.",
    ),
    measure(
        "fact_inventory",
        "Dias em ruptura",
        "SUM(fact_inventory[Ruptura])",
        "#,##0",
        "Estoque",
        "Dias em que a demanda do produto no almoxarifado não foi toda atendida.",
    ),
    measure(
        "fact_inventory",
        "Taxa de ruptura %",
        "DIVIDE([Dias em ruptura], [Dias observados])",
        "0.0%",
        "Estoque",
        "Dias em ruptura divididos pelos dias observados. Dia sem demanda não conta como ruptura, mesmo com estoque zerado.",
    ),
    measure(
        "fact_inventory",
        "Quantidade não atendida total",
        "SUM(fact_inventory[Quantidade não atendida])",
        "#,##0",
        "Estoque",
        "Soma das unidades pedidas pelo consumo do dia e não atendidas pelo estoque.",
    ),
    measure(
        "fact_inventory",
        "Estoque na posição",
        "VAR UltimaData = MAX(dim_date[Data]) RETURN CALCULATE(SUM(fact_inventory[Estoque]), dim_date[Data] = UltimaData)",
        "#,##0",
        "Estoque",
        "Soma do estoque no último dia visível do calendário. Sem filtro, a posição é 31/12/2025.",
    ),
    measure(
        "fact_inventory",
        "Demanda na posição",
        "VAR UltimaData = MAX(dim_date[Data]) RETURN CALCULATE(SUM(fact_inventory[Demanda do dia]), dim_date[Data] = UltimaData)",
        "#,##0",
        "Estoque",
        "Demanda do último dia visível do calendário. Serve de contexto da posição, não de média.",
    ),
    measure(
        "fact_inventory",
        "Combinações em ruptura",
        "VAR UltimaData = MAX(dim_date[Data]) RETURN CALCULATE(COUNTROWS(fact_inventory), dim_date[Data] = UltimaData, fact_inventory[Ruptura] = 1)",
        "#,##0",
        "Estoque",
        "Pares produto-almoxarifado em ruptura no último dia visível.",
    ),
    measure(
        "fact_inventory",
        "Cobertura em dias",
        "VAR UltimaData = MAX(dim_date[Data]) VAR Estoque = CALCULATE(SUM(fact_inventory[Estoque]), dim_date[Data] = UltimaData) VAR Media = AVERAGEX(VALUES(dim_date[Data]), CALCULATE(SUM(fact_inventory[Demanda do dia]))) RETURN DIVIDE(Estoque, Media)",
        "0.0",
        "Estoque",
        "Estoque no último dia do filtro dividido pela demanda média diária do período filtrado. Não é meta de cobertura.",
    ),
    measure(
        "fact_inventory",
        "Estoque de segurança na posição",
        "VAR UltimaData = MAX(dim_date[Data]) RETURN CALCULATE(SUM(fact_inventory[Estoque de segurança]), dim_date[Data] = UltimaData)",
        "#,##0",
        "Estoque",
        "Soma do parâmetro de estoque de segurança no último dia do filtro. O parâmetro é constante por produto e almoxarifado.",
    ),
    measure(
        "dim_date",
        "Posição",
        "MAX(dim_date[Data])",
        "dd/MM/yyyy",
        "Calendário",
        "Última data visível no calendário filtrado. Sem filtro, é 31/12/2025.",
    ),
]


def tables():
    orders = [
        col("Linha", "line_id", "string", key=True),
        col("Pedido", "order_id", "string"),
        col("Data do pedido", "order_date", "dateTime", fmt="dd/MM/yyyy"),
        col("partner_id", "partner_id", "string", hidden=True),
        col("product_id", "product_id", "string", hidden=True),
        col("warehouse_id", "warehouse_id", "string", hidden=True),
        col("Qtd pedida", "quantity", "int64"),
        col("unit_price_cents", "unit_price_cents", "int64", hidden=True),
        col("Status", "status", "string", hidden=True),
        col("Situação", "situacao", "string"),
        col("Prazo", "due_date", "dateTime", fmt="dd/MM/yyyy"),
        col("Qtd recebida", "received_quantity", "int64"),
        col("Qtd no prazo", "on_time_quantity", "int64"),
        col("Último recebimento", "last_received_date", "dateTime", fmt="dd/MM/yyyy"),
        col("amount_cents", "amount_cents", "int64", hidden=True),
        col("Qtd em aberto", "open_quantity", "int64"),
        col("open_cents", "open_cents", "int64", hidden=True),
        col("due_eligible", "due_eligible", "int64", hidden=True),
        col("otif", "otif", "int64", hidden=True),
        col("Lead time (dias)", "lead_days", "double", fmt="0.0"),
        col("overdue_cents", "overdue_cents", "int64", hidden=True),
    ]
    inventory = [
        col("snapshot_id", "snapshot_id", "string", hidden=True, key=True),
        col("Data do snapshot", "snapshot_date", "dateTime", hidden=True, fmt="dd/MM/yyyy"),
        col("warehouse_id", "warehouse_id", "string", hidden=True),
        col("product_id", "product_id", "string", hidden=True),
        col("Estoque", "on_hand_qty", "int64", hidden=True),
        col("Estoque de segurança", "safety_qty", "int64", hidden=True),
        col("Demanda do dia", "demand_qty", "int64", hidden=True),
        col("Quantidade não atendida", "short_qty", "int64", hidden=True),
        col("Ruptura", "stockout_flag", "int64", hidden=True),
    ]
    return [
        {
            "name": "dim_date",
            "description": "Calendário diário de 01/01/2024 a 31/12/2025. Tabela de datas do modelo.",
            "data_category": "Time",
            "file": "dim_date.csv",
            "columns": [
                col("Data", "date", "dateTime", key=True, fmt="dd/MM/yyyy"),
                col("Ano", "year", "int64"),
                col("Trimestre", "quarter", "string"),
                col("Ano-mês", "month", "string"),
                col("month_sort", "month_sort", "int64", hidden=True),
                col("Mês", "month_name", "string", sort="month_sort"),
            ],
        },
        {
            "name": "dim_partner",
            "description": "Fornecedor fictício. A UF vem do cadastro Excel do pipeline.",
            "file": "dim_partner.csv",
            "columns": [
                col("partner_id", "partner_id", "string", hidden=True, key=True),
                col("Fornecedor", "partner_name", "string"),
                col("UF", "region", "string"),
                col("Segmento", "segment", "string"),
            ],
        },
        {
            "name": "dim_product",
            "description": "Material industrial fictício do cadastro de produtos.",
            "file": "dim_product.csv",
            "columns": [
                col("product_id", "product_id", "string", hidden=True, key=True),
                col("Produto", "product_name", "string"),
                col("Categoria", "category", "string"),
            ],
        },
        {
            "name": "dim_warehouse",
            "description": "Almoxarifado fictício. Não existe na fonte de pedidos.",
            "file": "dim_warehouse.csv",
            "columns": [
                col("warehouse_id", "warehouse_id", "string", hidden=True, key=True),
                col("Almoxarifado", "warehouse_name", "string"),
                col("Cidade", "city", "string"),
                col("UF do almoxarifado", "state", "string"),
            ],
        },
        {
            "name": "fact_orders",
            "description": "Uma linha por item de pedido, vinda do pipeline. O almoxarifado é atribuição sintética da semente 42.",
            "file": "fact_orders.csv",
            "columns": orders,
        },
        {
            "name": "fact_inventory",
            "description": "Foto diária sintética de estoque por produto e almoxarifado. Não faz parte do pipeline de compras.",
            "file": "fact_inventory.csv",
            "columns": inventory,
        },
    ]


def render_column(column):
    lines = [f"\tcolumn {tmdl_name(column['name'])}"]
    lines.append(f"\t\tdataType: {column['data_type']}")
    if column["hidden"]:
        lines.append("\t\tisHidden")
    if column["key"]:
        lines.append("\t\tisKey")
    lines.append("\t\tsummarizeBy: none")
    lines.append(f"\t\tsourceColumn: {column['source']}")
    if column["fmt"]:
        lines.append(f"\t\tformatString: {column['fmt']}")
    if column["sort"]:
        lines.append(f"\t\tsortByColumn: {tmdl_name(column['sort'])}")
    return "\n".join(lines)


def render_measure(item):
    lines = [f"\t/// {item['description']}", f"\tmeasure {tmdl_name(item['name'])} = {item['dax']}"]
    lines.append(f"\t\tformatString: {item['fmt']}")
    lines.append(f"\t\tdisplayFolder: {item['folder']}")
    return "\n".join(lines)


def render_partition(spec):
    pairs = ", ".join(
        '{"' + column["source"] + '", ' + M_TYPE[column["data_type"]] + "}"
        for column in spec["columns"]
    )
    m_lines = [
        "let",
        f'    Nome = "{spec["file"]}",',
        "    Ler = (pasta as text) as table =>",
        "        let",
        '            Bruto = Csv.Document(File.Contents(pasta & "/" & Nome), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
        "            Cabecalho = Table.PromoteHeaders(Bruto, [PromoteAllScalars=true]),",
        '            Nulos = Table.ReplaceValue(Cabecalho, "", null, Replacer.ReplaceValue, Table.ColumnNames(Cabecalho))',
        "        in",
        "            Nulos,",
        '    Fonte = try Ler(DataFolder) otherwise Ler("./" & DataFolder),',
        f'    Tipos = Table.TransformColumnTypes(Fonte, {{{pairs}}}, "en-US")',
        "in",
        "    Tipos",
    ]
    lines = [
        f"\tpartition {spec['name']} = m",
        "\t\tmode: import",
        "\t\tsource =",
    ]
    lines.extend("\t\t\t" + line for line in m_lines)
    return "\n".join(lines)


def render_table(spec):
    by_table = [item for item in MEASURES if item["table"] == spec["name"]]
    parts = [f"/// {spec['description']}", f"table {spec['name']}"]
    if spec.get("data_category"):
        parts.append(f"\tdataCategory: {spec['data_category']}")
    parts.extend(render_column(column) for column in spec["columns"])
    parts.extend(render_measure(item) for item in by_table)
    parts.append(render_partition(spec))
    return "\n".join(parts) + "\n"


def render_model():
    refs = "\n".join(f"ref table {spec['name']}" for spec in tables())
    return (
        "model Model\n"
        "\tculture: pt-BR\n"
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        "\tsourceQueryCulture: en-US\n"
        "\tdataAccessOptions\n"
        "\t\tlegacyRedirects\n"
        "\t\treturnErrorValuesAsNull\n"
        "\tannotation __PBI_TimeIntelligenceEnabled = 0\n"
        f"{refs}\n"
        "ref expression DataFolder\n"
    )


def render_relationships():
    links = [
        ("orders_date", "fact_orders", "Data do pedido", "dim_date", "Data"),
        ("orders_partner", "fact_orders", "partner_id", "dim_partner", "partner_id"),
        ("orders_product", "fact_orders", "product_id", "dim_product", "product_id"),
        ("orders_warehouse", "fact_orders", "warehouse_id", "dim_warehouse", "warehouse_id"),
        ("inventory_date", "fact_inventory", "Data do snapshot", "dim_date", "Data"),
        ("inventory_product", "fact_inventory", "product_id", "dim_product", "product_id"),
        ("inventory_warehouse", "fact_inventory", "warehouse_id", "dim_warehouse", "warehouse_id"),
    ]
    blocks = []
    for name, src, src_col, dst, dst_col in links:
        blocks.append(
            "\n".join(
                [
                    f"relationship {name}",
                    f"\tfromColumn: {src}.{tmdl_name(src_col)}",
                    f"\ttoColumn: {dst}.{tmdl_name(dst_col)}",
                    "\tfromCardinality: many",
                    "\ttoCardinality: one",
                    "\tcrossFilteringBehavior: oneDirection",
                ]
            )
        )
    return "\n\n".join(blocks) + "\n"


def write_tmdl():
    definition = MODEL / "definition"
    table_dir = definition / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    (definition / "database.tmdl").write_text(
        "database SupplyWatch\n\tcompatibilityLevel: 1600\n", encoding="utf-8"
    )
    (definition / "model.tmdl").write_text(render_model(), encoding="utf-8")
    (definition / "relationships.tmdl").write_text(render_relationships(), encoding="utf-8")
    (definition / "expressions.tmdl").write_text(
        "expression DataFolder = \"data/pbi\" meta "
        "[IsParameterQuery=true, Type=\"Text\", IsParameterQueryRequired=true]\n"
        "\tannotation PBI_ResultType = Text\n",
        encoding="utf-8",
    )
    for spec in tables():
        (table_dir / f"{spec['name']}.tmdl").write_text(render_table(spec), encoding="utf-8")


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def lit(value):
    return {"expr": {"Literal": {"Value": value}}}


def quote(text):
    return "'" + text.replace("'", "''") + "'"


def column_field(entity, prop):
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def measure_field(entity, prop):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def projection(entity, prop, kind):
    field = column_field(entity, prop) if kind == "column" else measure_field(entity, prop)
    return {"field": field, "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}


def title_box(text):
    return {"title": [{"properties": {"show": lit("true"), "text": lit(quote(text))}}]}


def hide_title():
    return {"title": [{"properties": {"show": lit("false")}}]}


class Page:
    def __init__(self, name, display, **extra):
        self.name = name
        self.display = display
        self.extra = extra
        self.visuals = []

    def add(self, key, visual, x, y, w, h):
        self.visuals.append((key, visual, x, y, w, h))


def slicer(entity, prop, header, mode, group):
    return {
        "visualType": "slicer",
        "syncGroup": {"groupName": group, "fieldChanges": True, "filterChanges": True},
        "query": {"queryState": {"Values": {"projections": [projection(entity, prop, "column")]}}},
        "objects": {
            "data": [{"properties": {"mode": lit(quote(mode))}}],
            "header": [{"properties": {"show": lit("true"), "text": lit(quote(header))}}],
        },
        "visualContainerObjects": hide_title(),
        "drillFilterOtherVisuals": False,
    }


def textbox(text, size="18px", color="#142D46", bold=True):
    family = "Segoe UI Semibold" if bold else "Segoe UI"
    return {
        "visualType": "textbox",
        "objects": {
            "general": [
                {
                    "properties": {
                        "paragraphs": [
                            {
                                "textRuns": [
                                    {
                                        "value": text,
                                        "textStyle": {"fontFamily": family, "fontSize": size, "color": color},
                                    }
                                ],
                                "horizontalTextAlignment": "left",
                            }
                        ]
                    }
                }
            ]
        },
        "visualContainerObjects": {
            "background": [{"properties": {"show": lit("false")}}],
            "border": [{"properties": {"show": lit("false")}}],
        },
    }


def card(entity, name):
    return {
        "visualType": "cardVisual",
        "query": {"queryState": {"Data": {"projections": [projection(entity, name, "measure")]}}},
        "visualContainerObjects": hide_title(),
        "drillFilterOtherVisuals": True,
    }


def chart(visual_type, title, category, values, sort_kind, sort_entity, sort_prop, direction):
    sort_field = (
        column_field(sort_entity, sort_prop)
        if sort_kind == "column"
        else measure_field(sort_entity, sort_prop)
    )
    return {
        "visualType": visual_type,
        "query": {
            "queryState": {
                "Category": {"projections": [projection(category[0], category[1], "column")]},
                "Y": {"projections": [projection(entity, prop, "measure") for entity, prop in values]},
            },
            "sortDefinition": {
                "sort": [{"field": sort_field, "direction": direction}],
                "isDefaultSort": False,
            },
        },
        "visualContainerObjects": title_box(title),
        "drillFilterOtherVisuals": True,
    }


def table(title, fields, sort_kind, sort_entity, sort_prop, direction):
    sort_field = (
        column_field(sort_entity, sort_prop)
        if sort_kind == "column"
        else measure_field(sort_entity, sort_prop)
    )
    return {
        "visualType": "tableEx",
        "query": {
            "queryState": {
                "Values": {"projections": [projection(entity, prop, kind) for kind, entity, prop in fields]}
            },
            "sortDefinition": {
                "sort": [{"field": sort_field, "direction": direction}],
                "isDefaultSort": False,
            },
        },
        "visualContainerObjects": title_box(title),
        "drillFilterOtherVisuals": True,
    }


def add_slicers(page):
    specs = [
        ("periodo", "dim_date", "Data", "Período", "Between", "Periodo", 12, 340),
        ("fornecedor", "dim_partner", "Fornecedor", "Fornecedor", "Dropdown", "Fornecedor", 360, 300),
        ("categoria", "dim_product", "Categoria", "Categoria", "Dropdown", "Categoria", 668, 300),
        ("almox", "dim_warehouse", "Almoxarifado", "Almoxarifado", "Dropdown", "Almoxarifado", 976, 292),
    ]
    for key, entity, prop, header, mode, group, x, width in specs:
        page.add(key, slicer(entity, prop, header, mode, group), x, 40, width, 88)


def add_cards(page, y, height, items):
    gap = 8
    width = int((1280 - 24 - gap * (len(items) - 1)) / len(items))
    total = width * len(items) + gap * (len(items) - 1)
    x = (1280 - total) // 2
    for index, (entity, name) in enumerate(items):
        page.add(f"kpi-{index}", card(entity, name), x + index * (width + gap), y, width, height)


def build_pages():
    visao = Page("visao", "Visão executiva")
    visao.add("titulo", textbox("SupplyWatch  |  Visão executiva"), 12, 8, 700, 28)
    visao.add(
        "aviso",
        textbox("Dados sintéticos, semente 42. Posição 31/12/2025.", "12px", "#5C6B7A", False),
        720,
        10,
        548,
        24,
    )
    add_slicers(visao)
    add_cards(
        visao,
        136,
        84,
        [
            ("fact_orders", "OTIF %"),
            ("fact_orders", "Fill rate %"),
            ("fact_orders", "Lead time completo"),
            ("fact_inventory", "Taxa de ruptura %"),
            ("fact_orders", "Valor contratado"),
            ("fact_orders", "Saldo vencido"),
        ],
    )
    visao.add(
        "otif-fill",
        chart(
            "lineChart",
            "OTIF % e fill rate % por mês do pedido",
            ("dim_date", "Ano-mês"),
            [("fact_orders", "OTIF %"), ("fact_orders", "Fill rate %")],
            "column",
            "dim_date",
            "Ano-mês",
            "Ascending",
        ),
        12,
        228,
        760,
        236,
    )
    visao.add(
        "valor-categoria",
        chart(
            "columnChart",
            "Valor contratado por categoria",
            ("dim_product", "Categoria"),
            [("fact_orders", "Valor contratado")],
            "measure",
            "fact_orders",
            "Valor contratado",
            "Descending",
        ),
        784,
        228,
        484,
        236,
    )
    visao.add(
        "lead-mes",
        chart(
            "lineChart",
            "Lead time completo por mês do pedido",
            ("dim_date", "Ano-mês"),
            [("fact_orders", "Lead time completo")],
            "column",
            "dim_date",
            "Ano-mês",
            "Ascending",
        ),
        12,
        472,
        624,
        236,
    )
    visao.add(
        "saldo-fornecedor",
        chart(
            "barChart",
            "Saldo vencido por fornecedor",
            ("dim_partner", "Fornecedor"),
            [("fact_orders", "Saldo vencido")],
            "measure",
            "fact_orders",
            "Saldo vencido",
            "Descending",
        ),
        648,
        472,
        620,
        236,
    )

    fornecedores = Page("fornecedores", "Fornecedores")
    fornecedores.add("titulo", textbox("SupplyWatch  |  Fornecedores"), 12, 8, 620, 28)
    fornecedores.add(
        "aviso",
        textbox("OTIF inclui linha vencida sem entrega. Saldo vencido não é perda realizada.", "12px", "#5C6B7A", False),
        640,
        10,
        628,
        24,
    )
    add_slicers(fornecedores)
    fornecedores.add(
        "otif-fornecedor",
        chart(
            "barChart",
            "OTIF % por fornecedor",
            ("dim_partner", "Fornecedor"),
            [("fact_orders", "OTIF %")],
            "measure",
            "fact_orders",
            "OTIF %",
            "Ascending",
        ),
        12,
        136,
        624,
        280,
    )
    fornecedores.add(
        "lead-fornecedor",
        chart(
            "barChart",
            "Lead time completo por fornecedor",
            ("dim_partner", "Fornecedor"),
            [("fact_orders", "Lead time completo")],
            "measure",
            "fact_orders",
            "Lead time completo",
            "Descending",
        ),
        648,
        136,
        620,
        280,
    )
    fornecedores.add(
        "tabela-fornecedor",
        table(
            "Fila de ação por saldo vencido",
            [
                ("column", "dim_partner", "Fornecedor"),
                ("column", "dim_partner", "UF"),
                ("column", "dim_partner", "Segmento"),
                ("measure", "fact_orders", "Valor contratado"),
                ("measure", "fact_orders", "OTIF %"),
                ("measure", "fact_orders", "Fill rate %"),
                ("measure", "fact_orders", "Lead time completo"),
                ("measure", "fact_orders", "Saldo vencido"),
                ("measure", "fact_orders", "Participação fornecedor %"),
                ("measure", "fact_orders", "Linhas elegíveis"),
                ("measure", "fact_orders", "Pedidos ativos"),
            ],
            "measure",
            "fact_orders",
            "Saldo vencido",
            "Descending",
        ),
        12,
        428,
        1256,
        280,
    )

    estoque = Page("estoque", "Estoque e rupturas")
    estoque.add("titulo", textbox("SupplyWatch  |  Estoque e rupturas"), 12, 8, 640, 28)
    estoque.add(
        "aviso",
        textbox("Ruptura é demanda do dia não atendida. Fornecedor não filtra o estoque.", "12px", "#5C6B7A", False),
        660,
        10,
        608,
        24,
    )
    add_slicers(estoque)
    add_cards(
        estoque,
        136,
        80,
        [
            ("fact_inventory", "Taxa de ruptura %"),
            ("fact_inventory", "Combinações em ruptura"),
            ("fact_inventory", "Estoque na posição"),
            ("fact_inventory", "Cobertura em dias"),
        ],
    )
    estoque.add(
        "ruptura-mes",
        chart(
            "lineChart",
            "Taxa de ruptura % por mês",
            ("dim_date", "Ano-mês"),
            [("fact_inventory", "Taxa de ruptura %")],
            "column",
            "dim_date",
            "Ano-mês",
            "Ascending",
        ),
        12,
        228,
        620,
        220,
    )
    estoque.add(
        "ruptura-almox",
        chart(
            "barChart",
            "Taxa de ruptura % por almoxarifado",
            ("dim_warehouse", "Almoxarifado"),
            [("fact_inventory", "Taxa de ruptura %")],
            "measure",
            "fact_inventory",
            "Taxa de ruptura %",
            "Descending",
        ),
        644,
        228,
        624,
        220,
    )
    estoque.add(
        "tabela-estoque",
        table(
            "Posição por almoxarifado e produto",
            [
                ("column", "dim_warehouse", "Almoxarifado"),
                ("column", "dim_product", "Produto"),
                ("column", "dim_product", "Categoria"),
                ("measure", "fact_inventory", "Estoque na posição"),
                ("measure", "fact_inventory", "Demanda na posição"),
                ("measure", "fact_inventory", "Cobertura em dias"),
                ("measure", "fact_inventory", "Estoque de segurança na posição"),
                ("measure", "fact_inventory", "Dias em ruptura"),
                ("measure", "fact_inventory", "Taxa de ruptura %"),
            ],
            "measure",
            "fact_inventory",
            "Taxa de ruptura %",
            "Descending",
        ),
        12,
        460,
        1256,
        248,
    )

    detalhe = Page(
        "detalhe",
        "Detalhe do pedido",
        filterConfig={
            "filters": [
                {
                    "name": "FiltroFornecedor",
                    "field": column_field("dim_partner", "Fornecedor"),
                    "type": "Categorical",
                    "howCreated": "Drillthrough",
                }
            ]
        },
        pageBinding={
            "name": "DrillFornecedor",
            "type": "Drillthrough",
            "parameters": [
                {
                    "name": "ParamFornecedor",
                    "boundFilter": "FiltroFornecedor",
                    "fieldExpr": column_field("dim_partner", "Fornecedor"),
                }
            ],
        },
        visibility="HiddenInViewMode",
    )
    detalhe.add("titulo", textbox("SupplyWatch  |  Detalhe do pedido"), 12, 8, 640, 28)
    detalhe.add(
        "aviso",
        textbox("Drill-through por fornecedor. Use o botão direito nas outras páginas.", "12px", "#5C6B7A", False),
        660,
        10,
        608,
        24,
    )
    add_slicers(detalhe)
    detalhe.add(
        "contexto",
        textbox(
            "A página abre filtrada pelo fornecedor. O botão voltar do Desktop retorna à página de origem.",
            "12px",
            "#142D46",
            False,
        ),
        12,
        136,
        1256,
        32,
    )
    add_cards(
        detalhe,
        176,
        76,
        [
            ("fact_orders", "Valor contratado"),
            ("fact_orders", "OTIF %"),
            ("fact_orders", "Fill rate %"),
            ("fact_orders", "Lead time completo"),
            ("fact_orders", "Saldo vencido"),
        ],
    )
    detalhe.add(
        "linhas",
        table(
            "Linhas do fornecedor",
            [
                ("column", "fact_orders", "Pedido"),
                ("column", "fact_orders", "Linha"),
                ("column", "dim_product", "Produto"),
                ("column", "dim_product", "Categoria"),
                ("column", "dim_warehouse", "Almoxarifado"),
                ("column", "fact_orders", "Data do pedido"),
                ("column", "fact_orders", "Prazo"),
                ("column", "fact_orders", "Situação"),
                ("column", "fact_orders", "Qtd pedida"),
                ("column", "fact_orders", "Qtd recebida"),
                ("column", "fact_orders", "Lead time (dias)"),
                ("measure", "fact_orders", "Valor contratado"),
                ("measure", "fact_orders", "Saldo vencido"),
            ],
            "measure",
            "fact_orders",
            "Saldo vencido",
            "Descending",
        ),
        12,
        264,
        1256,
        444,
    )
    return [visao, fornecedores, estoque, detalhe]


def write_report():
    theme = {
        "name": "SupplyWatch",
        "dataColors": ["#00857C", "#274E73", "#F0A23B", "#92B8C5", "#B65555", "#5B8C5A"],
        "background": "#F7F9FC",
        "foreground": "#142D46",
        "tableAccent": "#00857C",
        "visualStyles": {
            "*": {
                "*": {
                    "background": [{"show": True, "color": {"solid": {"color": "#FFFFFF"}}}],
                    "border": [{"show": False}],
                }
            },
            "textbox": {"*": {"background": [{"show": False}], "border": [{"show": False}]}},
        },
    }
    write_json(REPORT / "StaticResources" / "RegisteredResources" / "SupplyWatch.json", theme)
    version = {
        "visual": "2.9.0",
        "report": "3.1.0",
        "page": "2.1.0",
    }
    write_json(
        REPORT / "definition.pbir",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {"byPath": {"path": "../SupplyWatch.SemanticModel"}},
        },
    )
    write_json(
        REPORT / "definition" / "version.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
            "version": "2.0.0",
        },
    )
    pages = build_pages()
    write_json(
        REPORT / "definition" / "pages" / "pages.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
            "pageOrder": [page.name for page in pages],
            "activePageName": pages[0].name,
        },
    )
    write_json(
        REPORT / "definition" / "report.json",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.1.0/schema.json",
            "themeCollection": {
                "baseTheme": {
                    "name": "CY24SU10",
                    "reportVersionAtImport": version,
                    "type": "SharedResources",
                },
                "customTheme": {
                    "name": "SupplyWatch",
                    "reportVersionAtImport": version,
                    "type": "RegisteredResources",
                },
            },
            "resourcePackages": [
                {
                    "name": "SharedResources",
                    "type": "SharedResources",
                    "items": [
                        {"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}
                    ],
                },
                {
                    "name": "RegisteredResources",
                    "type": "RegisteredResources",
                    "items": [
                        {"name": "SupplyWatch", "path": "SupplyWatch.json", "type": "CustomTheme"}
                    ],
                },
            ],
            "settings": {
                "useStylableVisualContainerHeader": True,
                "exportDataMode": "AllowSummarized",
                "defaultDrillFilterOtherVisuals": True,
                "allowChangeFilterTypes": True,
                "useEnhancedTooltips": True,
            },
        },
    )
    for page in pages:
        folder = REPORT / "definition" / "pages" / page.name
        payload = {
            "$schema": PAGE_SCHEMA,
            "name": page.name,
            "displayName": page.display,
            "displayOption": "FitToPage",
            "height": 720,
            "width": 1280,
        }
        payload.update(page.extra)
        write_json(folder / "page.json", payload)
        for index, (key, visual, x, y, w, h) in enumerate(page.visuals, start=1):
            name = visual_name(page.name, key)
            write_json(
                folder / "visuals" / name / "visual.json",
                {
                    "$schema": VISUAL_SCHEMA,
                    "name": name,
                    "position": {
                        "x": x,
                        "y": y,
                        "z": index * 1000,
                        "height": h,
                        "width": w,
                        "tabOrder": index * 1000,
                    },
                    "visual": visual,
                },
            )


def write_project_files():
    write_json(
        PBIP,
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [{"report": {"path": "SupplyWatch.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    write_json(
        MODEL / "definition.pbism",
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "4.2",
            "settings": {"qnaEnabled": False},
        },
    )
    platform = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"
    write_json(
        MODEL / ".platform",
        {
            "$schema": platform,
            "metadata": {"type": "SemanticModel", "displayName": "SupplyWatch"},
            "config": {"version": "2.0", "logicalId": logical_id("semantic-model")},
        },
    )
    write_json(
        REPORT / ".platform",
        {
            "$schema": platform,
            "metadata": {"type": "Report", "displayName": "SupplyWatch"},
            "config": {"version": "2.0", "logicalId": logical_id("report")},
        },
    )


def write_csvs(frames):
    DATA.mkdir(parents=True, exist_ok=True)
    for spec in tables():
        columns = [column["source"] for column in spec["columns"]]
        frame = frames[spec["name"]].loc[:, columns]
        frame.to_csv(DATA / spec["file"], index=False, encoding="utf-8", lineterminator="\n")


def file_sha256(path):
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def write_manifest(frames, orders, inventory):
    files = {}
    for spec in tables():
        path = DATA / spec["file"]
        files[spec["file"]] = {"rows": int(len(frames[spec["name"]])), "sha256": file_sha256(path)}
    payload = {
        "synthetic": True,
        "seed": SEED,
        "as_of": AS_OF,
        "label": "Dados sintéticos. Pedidos vêm do pipeline com semente 42. Almoxarifado do pedido e estoque foram gerados à parte, com a mesma semente.",
        "orders": orders,
        "inventory": inventory,
        "files": files,
    }
    write_json(DATA / "manifest.json", payload)
    return payload


def write_dictionary(orders, inventory):
    lines = [
        "# Dicionário de medidas",
        "",
        "Dados sintéticos, semente 42, posição "
        + as_of_label()
        + ". Os totais sem segmentador abaixo foram calculados em Python com a mesma regra das medidas DAX. O motor do Power BI Desktop não executou estas medidas.",
        "",
        "Não some percentuais nem médias entre linhas. `DIVIDE` devolve branco quando o denominador é zero.",
        "",
        "O segmentador de data filtra a data do pedido e a data da foto de estoque. Ele não recalcula `due_eligible`, `otif` nem `overdue_cents`, que já nascem com o corte "
        + as_of_label()
        + ".",
        "",
        "O segmentador de fornecedor filtra pedidos. Estoque é por produto e almoxarifado, sem fornecedor.",
        "",
        "## Totais sem segmentador",
        "",
        "| Medida | Valor |",
        "| --- | --- |",
        f"| Valor contratado | {format_brl(orders['valor_contratado'])} |",
        f"| Saldo em aberto | {format_brl(orders['saldo_aberto'])} |",
        f"| Saldo vencido | {format_brl(orders['saldo_vencido'])} |",
        f"| OTIF % | {format_pct(orders['otif'])} |",
        f"| Fill rate % | {format_pct(orders['fill_rate'])} |",
        f"| Lead time completo | {format_num(orders['lead_time'])} dias |",
        f"| Pedidos ativos | {orders['pedidos_ativos']} |",
        f"| Linhas elegíveis | {orders['linhas_elegiveis']} |",
        f"| Linhas OTIF | {orders['linhas_otif']} |",
        f"| Taxa de ruptura % | {format_pct(inventory['taxa_ruptura'])} |",
        f"| Dias em ruptura | {inventory['dias_em_ruptura']} |",
        f"| Dias observados | {inventory['dias_observados']} |",
        f"| Combinações em ruptura | {inventory['combinacoes_em_ruptura']} |",
        f"| Estoque na posição | {format_num(inventory['estoque_na_posicao'], 0)} |",
        f"| Cobertura em dias | {format_num(inventory['cobertura_dias'])} |",
        f"| Quantidade não atendida total | {format_num(inventory['quantidade_nao_atendida'], 0)} |",
        "",
        "Valor contratado, OTIF %, saldo vencido e pedidos ativos repetem `reports/sample/metrics.json`. Fill rate e ruptura não estão naquele arquivo: são medidas deste projeto.",
        "",
        "## Definições",
        "",
        "| Medida | Pasta | Fórmula DAX | O que responde |",
        "| --- | --- | --- | --- |",
    ]
    for item in MEASURES:
        dax = item["dax"].replace("|", "\\|")
        lines.append(
            f"| {item['name']} | {item['folder']} | `{dax}` | {item['description']} |"
        )
    lines.extend(
        [
            "",
            "## Grão e relacionamentos",
            "",
            "- `fact_orders`: uma linha por item de pedido. Chave `Linha`.",
            "- `fact_inventory`: uma linha por dia, produto e almoxarifado. Chave `snapshot_id`.",
            "- `dim_date` filtra `Data do pedido` e `Data do snapshot`. Direção única, da dimensão para a fato.",
            "- `dim_partner`, `dim_product` e `dim_warehouse` também filtram em direção única.",
            "- `dim_date` está marcada como tabela de datas (`dataCategory: Time`) na coluna `Data`.",
            "",
            "O almoxarifado do pedido não existe em `data/source/orders.csv`. A coluna `warehouse_id` é um rótulo estável por `order_id`, semente 42. Os dois itens do mesmo pedido ficam no mesmo almoxarifado.",
            "",
        ]
    )
    path = ROOT / "docs" / "dicionario_medidas.md"
    path.write_text("\n".join(lines), encoding="utf-8")


def write_data_readme():
    text = """# data/pbi

Dados sintéticos para o projeto Power BI `SupplyWatch.pbip`.

Não são extraídos de uma empresa. A semente é 42 e a posição é 31/12/2025.

- `dim_partner`, `dim_product` e `fact_orders` saem do pipeline de compras, com duas colunas a mais no fato: `warehouse_id` e `situacao`.
- `warehouse_id` não existe na fonte de pedidos. É atribuição determinística pela semente.
- `dim_warehouse`, `dim_date` e `fact_inventory` são gerados por `analytics/pbi_export.py`. A foto de estoque não passa pelo pipeline.
- `manifest.json` guarda contagens, hashes e os totais sem segmentador.

Para gerar de novo, na raiz do repositório:

```bash
python powerbi/build_pbip.py
```

O caminho no modelo é relativo à pasta do arquivo `.pbip`: `data/pbi`.
"""
    (DATA / "README.md").write_text(text, encoding="utf-8")


def write_dax_copy():
    lines = [
        "// Cópia de leitura das medidas do PBIP.",
        "// A definição que o Desktop abre está em SupplyWatch.SemanticModel/definition/tables.",
        "",
    ]
    for item in MEASURES:
        lines.append(f"// {item['table']} / {item['folder']}")
        lines.append(f"// {item['description']}")
        lines.append(f"{item['name']} = {item['dax']}")
        lines.append("")
    (ROOT / "powerbi" / "measures_pbip.dax").write_text("\n".join(lines), encoding="utf-8")


def main():
    frames = load_model_frames(ROOT)
    orders = order_kpis(frames["fact_orders"])
    inventory = inventory_kpis(frames["fact_inventory"])
    write_csvs(frames)
    write_manifest(frames, orders, inventory)
    write_data_readme()
    write_tmdl()
    write_project_files()
    write_report()
    write_dictionary(orders, inventory)
    write_dax_copy()
    from powerbi.preview_pages import render

    render(ROOT)
    print(json.dumps({"orders": orders, "inventory": inventory}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
