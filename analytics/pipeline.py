"""Build a validated SQLite star schema; publish only after all checks succeed."""

from contextlib import closing
import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from analytics.io import read_events, read_partners, require_columns
from analytics.domain import transform, describe, AS_OF

ROOT = Path(__file__).resolve().parents[1]


def run(root=ROOT, api_base_url=None, max_reject_rate=0.03):
    root = Path(root)
    if not 0 <= max_reject_rate <= 1:
        raise ValueError("max_reject_rate must be between 0 and 1")
    source = root / "data/source"
    partners = read_partners(source / "partners.xlsx")
    products = pd.read_csv(source / "products.csv")
    require_columns(products, ["product_id", "product_name", "category"], "products")
    if products.isna().any().any() or products.product_id.duplicated().any():
        raise ValueError("products: null attribute or duplicate key")
    if products.astype(str).apply(lambda col: col.str.strip().eq("")).any().any():
        raise ValueError("products: blank attribute")
    orders = pd.read_csv(source / "orders.csv", keep_default_na=False)
    events = read_events(source / "events.json", api_base_url)
    fact, rejects = transform(orders, events, partners, products)
    total = len(orders) + len(events)
    rejected = sum(len(frame) for frame in rejects)
    rate = rejected / total if total else 1.0
    report_dir = root / "reports/runtime"
    report_dir.mkdir(parents=True, exist_ok=True)
    hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(source.iterdir())
        if p.suffix in {".csv", ".json", ".xlsx"}
    }
    # Capture the actual API payload hash as well as bundled source hashes.
    event_hash = hashlib.sha256(events.to_json(orient="records").encode()).hexdigest()
    quality = dict(
        as_of=AS_OF,
        source_rows=total,
        rejected_rows=rejected,
        rejected_rate=rate,
        published_rows=len(fact),
        status="failed" if rate > max_reject_rate or fact.empty else "passed",
        threshold=max_reject_rate,
        source_sha256=hashes,
        events_mode="http" if api_base_url else "file",
        events_sha256=event_hash,
    )
    (report_dir / "quality.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")
    quarantine = root / "data/quarantine"
    quarantine.mkdir(parents=True, exist_ok=True)
    for i, frame in enumerate(rejects):
        frame.to_csv(quarantine / f"rejected_{i}.csv", index=False)
    if quality["status"] != "passed":
        raise ValueError(f"Quality gate failed: {rejected}/{total} rows rejected")
    dates = pd.date_range("2024-01-01", AS_OF)
    calendar = pd.DataFrame(
        {"date": dates.strftime("%Y-%m-%d"), "year": dates.year, "month": dates.strftime("%Y-%m")}
    )
    tables = {
        "dim_partner": partners,
        "dim_product": products,
        "dim_date": calendar,
        "fact_orders": fact,
    }
    target = root / "data/warehouse/analytics.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(suffix=".db", dir=target.parent)
    os.close(fd)
    try:
        with closing(sqlite3.connect(temp_name)) as db:
            # SQL declares PKs, FKs and CHECK constraints; pandas never creates the schema.
            db.executescript((root / "sql/schema.sql").read_text(encoding="utf-8"))
            for name, frame in tables.items():
                frame.to_sql(name, db, if_exists="append", index=False)
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Relational integrity check failed")
            db.executescript((root / "sql/marts.sql").read_text(encoding="utf-8"))
            monthly = pd.read_sql_query("SELECT * FROM mart_monthly ORDER BY month", db)
            partner_mart = pd.read_sql_query("SELECT * FROM mart_partner", db)
            manifest = {
                "built_at_utc": datetime.now(timezone.utc).isoformat(),
                "as_of": AS_OF,
                "quality": quality,
            }
            db.execute("CREATE TABLE build_manifest (payload TEXT NOT NULL)")
            db.execute("INSERT INTO build_manifest VALUES (?)", (json.dumps(manifest),))
            db.commit()
        os.replace(temp_name, target)
    finally:
        Path(temp_name).unlink(missing_ok=True)
    exports = root / "data/exports"
    exports.mkdir(parents=True, exist_ok=True)
    for name, frame in {**tables, "mart_monthly": monthly, "mart_partner": partner_mart}.items():
        frame.to_csv(exports / (name + ".csv"), index=False, encoding="utf-8")
    summary = describe(fact, partner_mart, monthly, report_dir)
    (report_dir / "executive_summary.md").write_text(summary, encoding="utf-8")
    print(json.dumps(quality, indent=2))
    return quality


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-base-url", help="Optional local source API; defaults to JSON fixture"
    )
    parser.add_argument("--max-reject-rate", type=float, default=0.03)
    args = parser.parse_args()
    run(api_base_url=args.api_base_url, max_reject_rate=args.max_reject_rate)
