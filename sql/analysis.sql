-- Supplier concentration and overdue exposure. Read in sqlite3 or any SQLite client.
SELECT partner_name, ROUND(amount_cents/100.0,2) AS contracted_brl,
       ROUND(100*spend_share,2) AS spend_share_pct,
       ROUND(overdue_cents/100.0,2) AS overdue_brl,
       ROUND(100*otif_rate,1) AS otif_pct
FROM mart_partner ORDER BY overdue_cents DESC;

-- Prioritize open lines; preserve line IDs for action tracking.
SELECT * FROM mart_action_queue ORDER BY overdue_cents DESC LIMIT 20;

-- Compare cohorts. OTIF belongs to the order month at a fixed cutoff, not receipt month.
SELECT month, amount_cents/100.0 contracted_brl, otif_rate,
       LAG(otif_rate) OVER (ORDER BY month) previous_cohort_otif
FROM mart_monthly ORDER BY month;
