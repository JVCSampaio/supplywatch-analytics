# Power BI: modelo semântico e roteiro do relatório

Este diretório contém um modelo TMDL completo, consultas Power Query M, medidas DAX e tema.
**Não inclui um .pbix nem um relatório visual validado no Power BI Desktop.**
O dashboard executável e revisado visualmente neste repositório é o Streamlit.

## Carregar o modelo

1. Execute `python -m analytics.pipeline` na raiz do repositório. Os CSVs tratados serão gerados em `data/exports`.
2. Abra um relatório vazio no Power BI Desktop com exibição TMDL disponível.
3. Copie `model.tmdl` para a exibição TMDL. Altere somente o valor de `DataFolder` para o caminho absoluto de `data/exports`, usando barras `/`.
4. Aplique o script e atualize os dados. O script usa `createOrReplace model`: utilize um relatório novo, pois ele substitui o modelo existente.
5. Confirme os três relacionamentos 1:N com filtro único das dimensões para a fato. Marque `dim_date` como tabela de datas usando `date`.
6. Importe `theme.json` em Exibir → Temas. Configure formatos de moeda e percentual conforme as medidas.
7. Salve como PBIX ou PBIP depois de conferir os totais com `reports/sample/metrics.json`.

Alternativa manual: crie um parâmetro de texto `DataFolder`, crie quatro consultas em branco
com os arquivos `.pq`, configure os relacionamentos abaixo e adicione as medidas de `measures.dax`, uma de cada vez.

| Muitos | Um | Direção |
| --- | --- | --- |
| fact_orders.partner_id | dim_partner.partner_id | Dimensão → fato |
| fact_orders.product_id | dim_product.product_id | Dimensão → fato |
| fact_orders.order_date | dim_date.date | Dimensão → fato |

## Página 1 — Visão gerencial

Tela 16:9, fundo `#F7F9FC`, margens de 24 px. Título e aviso “Dados simulados — posição 31/12/2025”.
Faixa superior: cartões de **Valor contratado, OTIF %, Saldo vencido, Pedidos ativos**.
Segmentadores: `dim_date.date`, `dim_partner.region` e `dim_product.category`.
Gráfico de linha: `dim_date.month` no eixo e `[Valor contratado]` no valor.
Gráfico de barras: `dim_product.category` e `[Valor contratado]`.
Tabela de ação: `dim_partner.partner_name` e Saldo vencido, OTIF %, Linhas elegíveis e Lead time completo.
Ordene por Saldo vencido decrescente.

## Página 2 — Exploração

Matriz: categoria → produto nas linhas; mês nas colunas; `[Valor contratado]` nos valores.
Adicione uma tabela de linhas de pedido e habilite drillthrough por `partner_name`.
Use os mesmos segmentadores, sincronizados entre as páginas.
Configure títulos e textos alternativos com o significado de cada indicador.

## Regras para homologação

- Sem filtros: comparar os quatro cartões com `reports/sample/metrics.json` (tolerância de R$ 0,01 e 0,000001 para proporções).
- UF RJ: comparar com `reports/sample/metrics_RJ.json`.
- Testar filtro vazio, cancelados, seleção de vários meses e exportação.
- Não somar percentuais ou médias. As medidas usam componentes aditivos e `DIVIDE` retorna BLANK se o denominador for zero.
- Centavos são convertidos para reais uma única vez nas medidas. IDs e valores técnicos ficam ocultos.
- A atualização importa a posição fixa de 31/12/2025; mudar o relógio do computador não altera o estudo.
- Este pacote não configura publicação no serviço, gateway, RLS ou agendamento.

## Referências técnicas

- [Exibição TMDL no Power BI Desktop](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-tmdl-view)
- [Linguagem TMDL e relacionamentos](https://learn.microsoft.com/en-us/analysis-services/tmdl/tmdl-overview)
- [Modelo estrela no Power BI](https://learn.microsoft.com/en-us/power-bi/guidance/star-schema)

## Validação estrutural realizada

O parser oficial `Microsoft.AnalysisServices 19.118.3` leu o modelo e resolveu quatro tabelas,
três relacionamentos e todas as medidas. Veja [evidência](../reports/sample/powerbi_validation.json).
Isso não executa DAX ou Power Query e não comprova funcionamento visual no Desktop.

Para repetir, instale .NET 8 SDK e, na raiz, rode:
`dotnet run --project tools/pbi-validator -- .`
Esse passo é opcional; a execução do pipeline e do dashboard exige somente Python.
