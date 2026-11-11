# SupplyWatch: technical overview

This portfolio case study answers a business question using Python, relational SQL and self-service analytics.
All companies and transactions are synthetic. It does not claim real operational savings or employment experience.

The pipeline reads purchase-order lines from CSV, receipts from JSON or a paginated HTTP API,
and partner master data from an Excel workbook. Invalid records are quarantined with source positions and reasons.
Invalid child events also quarantine their parent order line, preventing understated or misleading metrics.

A SQLite star schema enforces primary keys, foreign keys and value constraints. Events are aggregated before joining
to order lines. Financial values use integer cents. Ratios are computed from aggregated numerators and denominators.
Validated data is published by replacing a temporary database. Rebuilding the same sources is idempotent.

The Streamlit app provides filters, governed exploration, CSV exports, data-quality evidence and optional local usage events.
Power BI assets include a PBIP project (`SupplyWatch.pbip`) with a star schema, DAX measures and a four-page PBIR report.
There is no PBIX in this repository. The pictures under `docs/powerbi/` are script-generated previews, not Desktop screenshots.
The TMDL parser loaded the model. Power BI Desktop was not run here.

OTIF measures fully received quantities by their due date over all due order lines, including undelivered overdue lines. Open commitments are exposure, not realized losses.

## Reproduce

Use Python 3.12. Install `requirements.txt`, run `python -m analytics.pipeline`, then `python -m streamlit run app.py`.
Run `python -m pytest -q` for tests and `python -m ruff check .` for linting.
The demo API is started with `python -m analytics.demo_api`; pass `--api-base-url http://127.0.0.1:8765` to the pipeline.

## Technical vocabulary

| English | Português | Meaning here |
| --- | --- | --- |
| Grain | Granularidade | One record per order line |
| Data quality gate | Controle de qualidade | Prevents publication above an agreed rejection threshold |
| Lineage | Rastreabilidade | Source hashes and row rejection reasons |
| OTIF | OTIF | Due lines received in full by the due date, divided by due lines |
| Supplier risk index | Risco do fornecedor | Equal weights on the OTIF miss and the overdue share of contracted value. Blank if either denominator is zero |
| Self-service | Autosserviço | Governed filtering and exploration without changing business definitions |

This written technical overview is a portfolio artifact; it does not certify the author's spoken English proficiency.
