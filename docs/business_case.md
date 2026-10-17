# Caso de negócio e levantamento de requisitos

Cenário fictício elaborado para demonstrar o trabalho de análise. As entrevistas abaixo são perguntas
propostas; não foram realizadas com uma empresa nem com a contratante da vaga.

## Problema

Quanto está contratado, quais fornecedores atrasam e qual saldo vencido merece ação primeiro? A organização fictícia recebe pedidos em CSV, eventos operacionais por API/JSON e um cadastro Excel de fornecedores.
As áreas precisam consultar uma definição comum de indicador e rastrear divergências até a origem.

## Perguntas para descoberta

1. Qual decisão será tomada com o painel e com que frequência?
2. O que identifica unicamente um pedido e uma linha? Há alterações e cancelamentos retroativos?
3. Qual data define o período: pedido, recebimento, faturamento ou devolução?
4. Quem aprova as regras e trata as exceções? Quanto atraso da fonte é aceitável?
5. Quais filtros, níveis de acesso e formatos de exportação são necessários?
6. O que caracteriza sucesso: menor retrabalho, decisões mais rápidas ou maior cobertura de informação?

## Requisitos e aceite

| ID | Necessidade | Critério verificável | Evidência |
| --- | --- | --- | --- |
| R01 | Uma única definição financeira | Total do SQL igual à soma da fato, centavos preservados | Testes de domínio e métricas de referência |
| R02 | Integrar formatos distintos | CSV + JSON/HTTP + Excel realmente lidos pelo pipeline | Teste HTTP paginado e leitura Excel |
| R03 | Confiança na carga | Duplicidades, nulos, datas e referências inválidas em quarentena | `test_shared.py` e relatório de qualidade |
| R04 | Continuidade | Carga recusada não substitui banco aprovado | Teste com limiar zero |
| R05 | Autonomia | Filtrar UF/período/categoria e exportar o mesmo recorte | AppTest + revisão visual |
| R06 | Compartilhar modelo BI | Dimensões com chaves únicas, medidas documentadas e pacote Power BI | SQL e `powerbi/` |
| R07 | Transformar análise em ação | Parecer identifica problema, responsável proposto, prazo e revisão | `executive_summary.md` |
| R08 | Monitorar utilidade | Sessões, aberturas e exportações opt-in, sem identificação pessoal | Testes de telemetria e aba Qualidade |
| R09 | Evitar viés de entrega | Linhas vencidas não entregues entram no denominador OTIF | Testes de entregas parciais e ausência de recebimentos |

## Responsabilidades propostas

Negócio valida o significado e as metas. Dados implementa contratos, métricas e monitoramento.
Tecnologia cuida de acesso, disponibilidade e recuperação. Produto acompanha adoção e prioriza melhorias.
O analista facilita a homologação com exemplos pequenos, totais conhecidos e critérios de aceite.

## Backlog de evolução

1. Revisão das métricas e do relatório com usuários reais; registrar divergências e aprovação.
2. Conexão com ERP autorizado e controle de versões de pedidos, preservando histórico.
3. Agendamento e alerta de falha; migração de armazenamento somente quando volume/concor­rência justificar.
4. Controle de acesso por área, testes de atualização Power BI e monitoramento de freshness por fonte.
5. Acompanhamento de efetividade com entrevistas e tempo para completar tarefas, além de cliques.
