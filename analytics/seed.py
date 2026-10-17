"""Generate synthetic source transactions. Never overwrites Excel dimensions."""

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPLY = True


def seed(root=ROOT, seed_value=42):
    rng = random.Random(seed_value)
    out = root / "data/source"
    out.mkdir(parents=True, exist_ok=True)
    products = [
        {"product_id": f"P{i:03}", "product_name": name, "category": category}
        for i, (name, category) in enumerate(
            [
                ("Válvula industrial", "Equipamentos"),
                ("Bomba centrífuga", "Equipamentos"),
                ("Sensor de pressão", "Instrumentação"),
                ("Transmissor de nível", "Instrumentação"),
                ("Kit de vedação", "Manutenção"),
                ("Filtro industrial", "Manutenção"),
                ("Capacete de proteção", "Segurança"),
                ("Detector de gás", "Segurança"),
            ],
            1,
        )
    ]
    prices = [85000, 245000, 45000, 68000, 12000, 18500, 9500, 130000]
    orders, events = [], []
    n = 1800 if SUPPLY else 3600
    for i in range(n):
        # Two lines per order share customer/supplier and order date.
        if i % 2 == 0:
            ordered = date(2024, 1, 1) + timedelta(days=rng.randrange(731))
            partner = rng.randrange(1, 13 if SUPPLY else 49)
            cancelled = rng.random() < 0.035
        p = rng.randrange(8)
        quantity = rng.randint(2, 60)
        price = int(prices[p] * rng.uniform(0.92, 1.12))
        line = f"L{i + 1:05}"
        row = dict(
            line_id=line,
            order_id=f"O{i // 2 + 1:05}",
            order_date=ordered.isoformat(),
            partner_id=f"{'SUP' if SUPPLY else 'CUS'}{partner:03}",
            product_id=f"P{p + 1:03}",
            quantity=quantity,
            unit_price_cents=price,
            status="cancelled" if cancelled else ("ordered" if SUPPLY else "invoiced"),
        )
        if SUPPLY:
            due = ordered + timedelta(days=rng.randint(10, 40))
            row["due_date"] = due.isoformat()
            lag = rng.randint(-5, 3) if partner % 4 else rng.randint(5, 22)
            if not cancelled and rng.random() > 0.07:
                first = quantity // 2
                for amount, offset in [(first, lag - 2), (quantity - first, lag)]:
                    arrival = due + timedelta(days=offset)
                    if arrival <= date(2025, 12, 31):
                        events.append(
                            dict(
                                event_id=f"E{len(events) + 1:05}",
                                line_id=line,
                                event_date=arrival.isoformat(),
                                quantity=amount,
                            )
                        )
        else:
            row["unit_cost_cents"] = int(prices[p] * rng.uniform(0.55, 0.78))
            row["discount_bps"] = rng.choice([0, 300, 500, 1000, 1800, 2500])
            if partner % 7 == 0:
                row["discount_bps"] = 3500
            if not cancelled and rng.random() < 0.16:
                returned_on = ordered + timedelta(days=rng.randint(1, 35))
                if returned_on <= date(2025, 12, 31):
                    events.append(
                        dict(
                            event_id=f"E{len(events) + 1:05}",
                            line_id=line,
                            event_date=returned_on.isoformat(),
                            quantity=rng.randint(1, quantity),
                        )
                    )
        orders.append(row)
    # Deliberate, documented defects with fresh keys; do not distort valid source transactions.
    for i, (key, value) in enumerate(
        [
            ("quantity", -5),
            ("partner_id", "UNKNOWN"),
            ("order_date", "2025-02-30"),
            ("product_id", "MISSING"),
        ]
    ):
        bad = dict(orders[0], line_id=f"BAD{i}", order_id=f"BADORDER{i}")
        bad[key] = value
        orders.append(bad)
    duplicate = dict(orders[0], line_id="DUPLICATE", order_id="DUPORDER")
    orders += [duplicate, dict(duplicate, quantity=99)]
    events.append(dict(event_id="ORPHAN", line_id="UNKNOWN", event_date="2025-05-01", quantity=1))
    for name, rows in [("orders", orders), ("products", products)]:
        with (out / f"{name}.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    (out / "events.json").write_text(
        json.dumps(events, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    seed()
