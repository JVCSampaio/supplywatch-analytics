PRAGMA foreign_keys = ON;
CREATE TABLE dim_partner (
  partner_id TEXT PRIMARY KEY, partner_name TEXT NOT NULL,
  region TEXT NOT NULL, segment TEXT NOT NULL
);
CREATE TABLE dim_product (
  product_id TEXT PRIMARY KEY, product_name TEXT NOT NULL, category TEXT NOT NULL
);
CREATE TABLE dim_date (date TEXT PRIMARY KEY, year INTEGER NOT NULL, month TEXT NOT NULL);
CREATE TABLE fact_orders (
  line_id TEXT PRIMARY KEY, order_id TEXT NOT NULL,
  order_date TEXT NOT NULL REFERENCES dim_date(date), due_date TEXT NOT NULL,
  partner_id TEXT NOT NULL REFERENCES dim_partner(partner_id),
  product_id TEXT NOT NULL REFERENCES dim_product(product_id),
  quantity INTEGER NOT NULL CHECK(quantity > 0),
  unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents > 0),
  status TEXT NOT NULL CHECK(status IN ('ordered','cancelled')),
  received_quantity INTEGER NOT NULL CHECK(received_quantity BETWEEN 0 AND quantity),
  on_time_quantity INTEGER NOT NULL CHECK(on_time_quantity BETWEEN 0 AND received_quantity),
  last_received_date TEXT,
  amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0),
  open_quantity INTEGER NOT NULL CHECK(open_quantity >= 0),
  open_cents INTEGER NOT NULL CHECK(open_cents >= 0),
  due_eligible INTEGER NOT NULL CHECK(due_eligible IN (0,1)),
  otif INTEGER NOT NULL CHECK(otif BETWEEN 0 AND due_eligible),
  lead_days REAL CHECK(lead_days >= 0),
  overdue_cents INTEGER NOT NULL CHECK(overdue_cents >= 0)
);
CREATE INDEX ix_orders_date ON fact_orders(order_date);
CREATE INDEX ix_orders_partner ON fact_orders(partner_id);
