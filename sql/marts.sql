-- Ratios are calculated from their components, never averaged across groups.
CREATE VIEW mart_monthly AS
SELECT d.month, SUM(f.amount_cents) AS amount_cents,
       SUM(f.overdue_cents) AS overdue_cents,
       SUM(f.otif) AS otif_lines, SUM(f.due_eligible) AS eligible_lines,
       1.0 * SUM(f.otif) / NULLIF(SUM(f.due_eligible), 0) AS otif_rate
FROM fact_orders f JOIN dim_date d ON f.order_date=d.date GROUP BY d.month;

CREATE VIEW mart_partner AS
WITH totals AS (
  SELECT partner_id, SUM(amount_cents) amount_cents, SUM(overdue_cents) overdue_cents,
         SUM(otif) otif_lines, SUM(due_eligible) eligible_lines,
         AVG(lead_days) lead_days
  FROM fact_orders GROUP BY partner_id
)
SELECT p.*, t.amount_cents, t.overdue_cents, t.otif_lines, t.eligible_lines, t.lead_days,
       1.0*t.otif_lines/NULLIF(t.eligible_lines,0) AS otif_rate,
       1.0*t.amount_cents/NULLIF(SUM(t.amount_cents) OVER (),0) AS spend_share
FROM totals t JOIN dim_partner p USING(partner_id);

-- Same weights as analytics/risk.py: 0.5 OTIF miss, 0.5 overdue exposure.
-- Blank when there is no eligible line or no contracted value.
CREATE VIEW mart_supplier_risk AS
WITH totals AS (
  SELECT partner_id, SUM(amount_cents) AS amount_cents, SUM(overdue_cents) AS overdue_cents,
         SUM(otif) AS otif_lines, SUM(due_eligible) AS eligible_lines
  FROM fact_orders GROUP BY partner_id
)
SELECT p.partner_id, p.partner_name, p.region, p.segment,
       t.amount_cents, t.overdue_cents, t.otif_lines, t.eligible_lines,
       CASE WHEN t.eligible_lines = 0 THEN NULL
            ELSE 1.0 - (1.0 * t.otif_lines / t.eligible_lines) END AS falha_otif,
       CASE WHEN t.amount_cents = 0 THEN NULL
            ELSE 1.0 * t.overdue_cents / t.amount_cents END AS exposicao_vencida,
       CASE WHEN t.eligible_lines = 0 OR t.amount_cents = 0 THEN NULL
            ELSE 100.0 * (
              0.5 * (1.0 - (1.0 * t.otif_lines / t.eligible_lines))
              + 0.5 * (1.0 * t.overdue_cents / t.amount_cents)
            ) END AS risk_score
FROM totals t JOIN dim_partner p USING(partner_id);

CREATE VIEW mart_action_queue AS
SELECT f.line_id, f.order_id, p.partner_name, d.product_name,
       f.due_date, f.open_quantity, f.overdue_cents
FROM fact_orders f JOIN dim_partner p USING(partner_id)
JOIN dim_product d USING(product_id)
WHERE f.overdue_cents > 0;
