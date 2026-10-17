"""Allowlisted dimensions and bound values for self-service exploration."""

from contextlib import closing
import sqlite3
import pandas as pd


def load(path, start="2024-01-01", end="2025-12-31", regions=(), categories=()):
    clauses, params = ["f.order_date BETWEEN ? AND ?"], [str(start), str(end)]
    for column, values in [("p.region", regions), ("d.category", categories)]:
        if values:
            clauses.append(column + " IN (" + ",".join("?" for _ in values) + ")")
            params.extend(values)
    sql = (
        "SELECT f.*, p.partner_name, p.region, p.segment, d.product_name, d.category "
        "FROM fact_orders f JOIN dim_partner p USING(partner_id) "
        "JOIN dim_product d USING(product_id) WHERE " + " AND ".join(clauses)
    )
    with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as db:
        return pd.read_sql_query(sql, db, params=params)


def csv_download(frame):
    # Spreadsheet formula injection protection for text exported by self-service users.
    safe = frame.copy()
    for col in safe.select_dtypes(include=["object", "string"]):
        safe[col] = safe[col].map(
            lambda x: "'" + x
            if isinstance(x, str) and x.lstrip().startswith(("=", "+", "-", "@"))
            else x
        )
    return safe.to_csv(index=False).encode("utf-8-sig")
