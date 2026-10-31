# Dicionário de medidas

Dados sintéticos, semente 42, posição 31/12/2025. Os totais sem segmentador abaixo foram calculados em Python com a mesma regra das medidas DAX. O motor do Power BI Desktop não executou estas medidas.

Não some percentuais nem médias entre linhas. `DIVIDE` devolve branco quando o denominador é zero.

O segmentador de data filtra a data do pedido e a data da foto de estoque. Ele não recalcula `due_eligible`, `otif` nem `overdue_cents`, que já nascem com o corte 31/12/2025.

O segmentador de fornecedor filtra pedidos. Estoque é por produto e almoxarifado, sem fornecedor.

## Totais sem segmentador

| Medida | Valor |
| --- | --- |
| Valor contratado | R$ 39.510.615,23 |
| Saldo em aberto | R$ 3.424.817,55 |
| Saldo vencido | R$ 2.497.540,46 |
| OTIF % | 46,4% |
| Fill rate % | 89,7% |
| Lead time completo | 27,3 dias |
| Pedidos ativos | 873 |
| Linhas elegíveis | 1690 |
| Linhas OTIF | 784 |
| Taxa de ruptura % | 14,6% |
| Dias em ruptura | 3421 |
| Dias observados | 23392 |
| Combinações em ruptura | 4 |
| Estoque na posição | 1588 |
| Cobertura em dias | 12,8 |
| Quantidade não atendida total | 15550 |

Valor contratado, OTIF %, saldo vencido e pedidos ativos repetem `reports/sample/metrics.json`. Fill rate e ruptura não estão naquele arquivo: são medidas deste projeto.

## Definições

| Medida | Pasta | Fórmula DAX | O que responde |
| --- | --- | --- | --- |
| Valor contratado | Pedidos | `DIVIDE(SUM(fact_orders[amount_cents]), 100)` | Soma de quantidade vezes preço unitário, em reais. Cancelados entram como zero. É valor contratado, não valor pago. |
| Saldo em aberto | Pedidos | `DIVIDE(SUM(fact_orders[open_cents]), 100)` | Quantidade ainda não recebida vezes preço, em reais. Cancelados entram como zero. É exposição contratual, não perda realizada. |
| Saldo vencido | Pedidos | `DIVIDE(SUM(fact_orders[overdue_cents]), 100)` | Saldo em aberto das linhas com prazo até 31/12/2025. O corte está gravado na coluna e não acompanha o relógio do computador. |
| Linhas elegíveis | Pedidos | `SUM(fact_orders[due_eligible])` | Linhas ativas cujo prazo é menor ou igual à posição 31/12/2025. Cancelados ficam de fora. |
| Linhas OTIF | Pedidos | `SUM(fact_orders[otif])` | Linhas elegíveis recebidas por completo até o prazo. |
| OTIF % | Pedidos | `DIVIDE([Linhas OTIF], [Linhas elegíveis])` | Linhas OTIF divididas pelas linhas elegíveis. Linha vencida e ainda não entregue entra no denominador. Denominador zero retorna branco. |
| Lead time completo | Pedidos | `AVERAGE(fact_orders[Lead time (dias)])` | Média de dias entre o pedido e o último recebimento. Só entra linha recebida por completo. Há viés de sobrevivência. |
| Pedidos ativos | Pedidos | `CALCULATE(DISTINCTCOUNT(fact_orders[Pedido]), KEEPFILTERS(fact_orders[Status] = "ordered"))` | Pedidos distintos com status ordered. Cancelados não entram. |
| Participação fornecedor % | Pedidos | `DIVIDE([Valor contratado], CALCULATE([Valor contratado], ALLSELECTED(dim_partner)))` | Valor do fornecedor dividido pelo valor contratado no universo selecionado de fornecedores. |
| Quantidade pedida | Pedidos | `CALCULATE(SUM(fact_orders[Qtd pedida]), KEEPFILTERS(fact_orders[Status] = "ordered"))` | Soma da quantidade pedida nas linhas ativas. É o denominador do fill rate. |
| Quantidade recebida | Pedidos | `CALCULATE(SUM(fact_orders[Qtd recebida]), KEEPFILTERS(fact_orders[Status] = "ordered"))` | Soma da quantidade recebida nas linhas ativas, com ou sem atraso. É o numerador do fill rate. |
| Fill rate % | Pedidos | `DIVIDE([Quantidade recebida], [Quantidade pedida])` | Quantidade recebida dividida pela quantidade pedida, só em linhas ativas. Não exige pontualidade. É diferente do OTIF, que é por linha e exige o prazo. |
| Dias observados | Estoque | `COUNTROWS(fact_inventory)` | Linhas da foto diária no filtro. Cada linha é um dia de um produto em um almoxarifado. |
| Dias em ruptura | Estoque | `SUM(fact_inventory[Ruptura])` | Dias em que a demanda do produto no almoxarifado não foi toda atendida. |
| Taxa de ruptura % | Estoque | `DIVIDE([Dias em ruptura], [Dias observados])` | Dias em ruptura divididos pelos dias observados. Dia sem demanda não conta como ruptura, mesmo com estoque zerado. |
| Quantidade não atendida total | Estoque | `SUM(fact_inventory[Quantidade não atendida])` | Soma das unidades pedidas pelo consumo do dia e não atendidas pelo estoque. |
| Estoque na posição | Estoque | `VAR UltimaData = MAX(dim_date[Data]) RETURN CALCULATE(SUM(fact_inventory[Estoque]), dim_date[Data] = UltimaData)` | Soma do estoque no último dia visível do calendário. Sem filtro, a posição é 31/12/2025. |
| Demanda na posição | Estoque | `VAR UltimaData = MAX(dim_date[Data]) RETURN CALCULATE(SUM(fact_inventory[Demanda do dia]), dim_date[Data] = UltimaData)` | Demanda do último dia visível do calendário. Serve de contexto da posição, não de média. |
| Combinações em ruptura | Estoque | `VAR UltimaData = MAX(dim_date[Data]) RETURN CALCULATE(COUNTROWS(fact_inventory), dim_date[Data] = UltimaData, fact_inventory[Ruptura] = 1)` | Pares produto-almoxarifado em ruptura no último dia visível. |
| Cobertura em dias | Estoque | `VAR UltimaData = MAX(dim_date[Data]) VAR Estoque = CALCULATE(SUM(fact_inventory[Estoque]), dim_date[Data] = UltimaData) VAR Media = AVERAGEX(VALUES(dim_date[Data]), CALCULATE(SUM(fact_inventory[Demanda do dia]))) RETURN DIVIDE(Estoque, Media)` | Estoque no último dia do filtro dividido pela demanda média diária do período filtrado. Não é meta de cobertura. |
| Estoque de segurança na posição | Estoque | `VAR UltimaData = MAX(dim_date[Data]) RETURN CALCULATE(SUM(fact_inventory[Estoque de segurança]), dim_date[Data] = UltimaData)` | Soma do parâmetro de estoque de segurança no último dia do filtro. O parâmetro é constante por produto e almoxarifado. |
| Posição | Calendário | `MAX(dim_date[Data])` | Última data visível no calendário filtrado. Sem filtro, é 31/12/2025. |

## Grão e relacionamentos

- `fact_orders`: uma linha por item de pedido. Chave `Linha`.
- `fact_inventory`: uma linha por dia, produto e almoxarifado. Chave `snapshot_id`.
- `dim_date` filtra `Data do pedido` e `Data do snapshot`. Direção única, da dimensão para a fato.
- `dim_partner`, `dim_product` e `dim_warehouse` também filtram em direção única.
- `dim_date` está marcada como tabela de datas (`dataCategory: Time`) na coluna `Data`.

O almoxarifado do pedido não existe em `data/source/orders.csv`. A coluna `warehouse_id` é um rótulo estável por `order_id`, semente 42. Os dois itens do mesmo pedido ficam no mesmo almoxarifado.
