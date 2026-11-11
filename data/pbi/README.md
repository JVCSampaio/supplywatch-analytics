# data/pbi

Dados sintéticos para o projeto Power BI `SupplyWatch.pbip`.

Não são extraídos de uma empresa. A semente é 42 e a posição é 31/12/2025.

- `dim_partner`, `dim_product` e `fact_orders` saem do pipeline de compras, com duas colunas a mais no fato: `warehouse_id` e `situacao`.
- `warehouse_id` não existe na fonte de pedidos. É atribuição determinística pela semente.
- `dim_warehouse`, `dim_date` e `fact_inventory` são gerados por `analytics/pbi_export.py`. A foto de estoque não passa pelo pipeline.
- `supplier_risk.csv` é o índice de risco por fornecedor, calculado no pipeline. Não é tabela do modelo: a medida DAX recalcula o mesmo índice dentro dos segmentadores.
- `manifest.json` guarda contagens, hashes, os totais sem segmentador e o maior risco da amostra.

Para gerar de novo, na raiz do repositório:

```bash
python powerbi/build_pbip.py
```

O caminho no modelo é relativo à pasta do arquivo `.pbip`: `data/pbi`.
