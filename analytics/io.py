"""Source contracts, paginated HTTP ingestion and fail-closed dimension checks."""

import json
import time
from pathlib import Path
import pandas as pd
import requests


def require_columns(frame, columns, source):
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"{source}: missing columns {sorted(missing)}")


def read_partners(path):
    frame = pd.read_excel(path, sheet_name="Partners", skiprows=2, dtype=str)
    require_columns(frame, ["partner_id", "partner_name", "region", "segment"], "partners")
    for col in frame.columns:
        frame[col] = frame[col].str.strip()
    if frame.isna().any().any() or frame.eq("").any().any():
        raise ValueError("partners: null/blank attribute")
    if frame.partner_id.duplicated().any():
        raise ValueError("partners: duplicate primary key")
    return frame


def read_events(path, api_base_url=None, session=None):
    if not api_base_url:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("events: expected a JSON array")
        return (
            pd.DataFrame(payload)
            if payload
            else pd.DataFrame(columns=["event_id", "line_id", "event_date", "quantity"])
        )
    client = session or requests.Session()
    records, page, seen = [], 1, set()
    try:
        for _ in range(1000):
            if not isinstance(page, int) or isinstance(page, bool) or page < 1 or page in seen:
                raise ValueError("events: invalid or circular pagination")
            seen.add(page)
            for attempt in range(3):
                try:
                    response = client.get(
                        api_base_url.rstrip("/") + "/events", params={"page": page}, timeout=(3, 15)
                    )
                    response.raise_for_status()
                    break
                except requests.RequestException as exc:
                    # Retry only transient errors; contract and authentication failures are fatal.
                    status = exc.response.status_code if exc.response is not None else None
                    if attempt == 2 or (status is not None and status < 500 and status != 429):
                        raise
                    time.sleep(0.2 * (2**attempt))
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                raise ValueError("events: invalid API contract")
            if "next_page" not in payload:
                raise ValueError("events: missing next_page")
            records.extend(payload["items"])
            page = payload["next_page"]
            if page is None:
                return (
                    pd.DataFrame(records)
                    if records
                    else pd.DataFrame(columns=["event_id", "line_id", "event_date", "quantity"])
                )
        raise ValueError("events: maximum page count exceeded")
    finally:
        if session is None:
            client.close()
