"""Opt-in local usage events. No names, IP addresses, or external telemetry."""

from contextlib import closing
import sqlite3
from datetime import datetime, timezone


def record(path, session_id, event):
    if event not in {"view", "filter", "export"}:
        raise ValueError("unsupported usage event")
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=10)) as db:
        db.execute("CREATE TABLE IF NOT EXISTS usage (time TEXT, session TEXT, event TEXT)")
        db.execute(
            "INSERT INTO usage VALUES (?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), session_id, event),
        )
        db.commit()


def summary(path):
    if not path.exists():
        return {"sessions": 0, "views": 0, "exports": 0}
    with closing(sqlite3.connect(path)) as db:
        sessions, views, exports = db.execute(
            "SELECT COUNT(DISTINCT session), COALESCE(SUM(event='view'),0), "
            "COALESCE(SUM(event='export'),0) FROM usage"
        ).fetchone()
    return dict(sessions=sessions, views=views, exports=exports)
