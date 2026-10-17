# Manual do usuário e operação

## Roteiro de demonstração de três minutos

1. Abra Visão gerencial e explique o indicador principal e sua população.
2. Selecione UF RJ e uma categoria. Mostre que os valores mudam juntos.
3. Abra Explorar e exportar, agrupe por segmento e baixe os registros filtrados.
4. Abra Qualidade e uso: mostre os sete erros intencionais e a rastreabilidade.
5. Termine com a recomendação do parecer e a limitação mais importante do indicador.

## Uso diário

- Datas referem-se ao pedido. Seleção vazia de UF/categoria significa todas as opções.
- A aba de qualidade e o estudo estatístico, quando presente, abrangem toda a base.
- Totais monetários nos arquivos com sufixo `_cents` estão em centavos. No painel e medidas DAX, em reais.
- Sem registros, a interface exibe aviso. Não interprete ausência como faturamento zero.
- Use exportação para investigação; não some percentuais nem misture totais e linhas.
- A telemetria é desativada por padrão. Ao ativar, apenas sessão aleatória e tipo de ação ficam no banco local.

## Atualizar e investigar falhas

1. Preserve o contrato das fontes e execute `python -m analytics.pipeline` na raiz.
2. Confira o código de saída. Se falhar, leia a mensagem, `reports/runtime/quality.json` quando disponível e `data/quarantine`.
3. Corrija a origem e execute de novo. Não edite a fato para esconder o erro.
4. Após sucesso, recarregue o Streamlit e atualize os CSVs no Power BI.
5. Registre divergências e ações com o responsável pelo indicador.

Uma mudança de esquema pode falhar antes de gerar relatório de qualidade; nesse caso o erro da execução é a evidência.
O banco anterior permanece disponível. Não há scheduler ou alertas externos configurados.
Evite cargas simultâneas: o exemplo não implementa exclusão mútua de escritores.

## API

`python -m analytics.demo_api --port 8765` expõe `/events?page=1` em localhost.
Contrato: `{"items": [...], "next_page": 2}`; a última página usa `null`.
O cliente usa timeout de conexão/leitura, três tentativas para erros transitórios,
limite de 1.000 páginas e bloqueio de ciclos de paginação. Falhas não viram silenciosamente uma lista vazia.
Para um sistema real, implementar autenticação e segredo via ambiente/secret manager, sem versionar credenciais.

## Acompanhar efetividade

Revisão semanal proposta: sessões, exportações e perguntas recorrentes.
Revisão mensal proposta: entrevistar usuários, medir o tempo para responder uma pergunta e comparar retrabalho.
Eventos não comprovam impacto de negócio nem identificam usuários únicos entre dispositivos/sessões.
O botão registra o clique de exportação; não confirma que o usuário abriu o arquivo baixado.
Apague o banco local de uso apenas se quiser reiniciar essa medição; ele não é versionado.

## Validação e operação em produção

Os testes usam casos pequenos conhecidos, integração HTTP local, SQL, reprocessamento e AppTest.
A inspeção visual foi feita no Streamlit. O relatório Power BI exige importação, atualização e conferência no Desktop.
Docker é uma alternativa entregue, sem execução registrada neste ambiente.
Para produção: revisar autenticação, controle de acesso, backup, recuperação, logs centralizados,
alertas, frescor por fonte, volume, governança e implantação. Esses componentes não são simulados como se existissem.
