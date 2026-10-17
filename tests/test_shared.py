from contextlib import closing
import json
import shutil
import sqlite3
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
import pandas as pd
import pytest
import requests
from analytics.pipeline import run
from analytics.io import read_events, read_partners
from analytics.demo_api import make_handler
from analytics.query import load, csv_download
from analytics.quality import Gate
from analytics.telemetry import record, summary

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project(tmp_path):
    shutil.copytree(ROOT / "data/source", tmp_path / "data/source")
    shutil.copytree(ROOT / "sql", tmp_path / "sql")
    run(tmp_path)
    return tmp_path


def test_rebuild_is_idempotent(project):
    db = project / "data/warehouse/analytics.db"
    before = load(db)
    run(project)
    pd.testing.assert_frame_equal(before, load(db))
    with closing(sqlite3.connect(db)) as conn:
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def test_failed_quality_does_not_replace_warehouse(project):
    db = project / "data/warehouse/analytics.db"
    before = db.read_bytes()
    with pytest.raises(ValueError, match="Quality gate"):
        run(project, max_reject_rate=0)
    assert before == db.read_bytes()


def test_schema_drift_stops_pipeline(project):
    source = project / "data/source/orders.csv"
    frame = pd.read_csv(source).drop(columns=["quantity"])
    frame.to_csv(source, index=False)
    with pytest.raises(ValueError, match="missing columns"):
        run(project)


def test_http_pagination_matches_fixture():
    path = ROOT / "data/source/events.json"
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(path, page_size=23))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        actual = read_events(path, f"http://127.0.0.1:{server.server_port}")
        pd.testing.assert_frame_equal(read_events(path), actual)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_api_cycle_is_rejected():
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"items": [], "next_page": 1}

    class Session:
        def get(self, *a, **kw):
            return Response()

    with pytest.raises(ValueError, match="circular"):
        read_events("unused", "http://example.test", Session())


def test_api_retries_transient_failure(monkeypatch):
    monkeypatch.setattr("analytics.io.time.sleep", lambda _: None)

    class Session:
        calls = 0

        def get(self, *a, **kw):
            self.calls += 1
            if self.calls < 3:
                raise requests.ConnectionError("temporary failure")
            response = requests.Response()
            response.status_code = 200
            response._content = b'{"items": [], "next_page": null}'
            return response

    session = Session()
    assert read_events("unused", "http://example.test", session).empty
    assert session.calls == 3


def test_api_error_is_not_silent_empty_data(monkeypatch):
    monkeypatch.setattr("analytics.io.time.sleep", lambda _: None)

    class Session:
        def get(self, *a, **kw):
            raise requests.Timeout("offline")

    with pytest.raises(requests.Timeout):
        read_events("unused", "http://example.test", Session())


def test_dates_filters_and_injection(project):
    db = project / "data/warehouse/analytics.db"
    frame = load(db, "2025-01-01", "2025-12-31", ["RJ"])
    assert not frame.empty and set(frame.region) == {"RJ"}
    assert frame.order_date.min() >= "2025-01-01"
    assert load(db, regions=["RJ'); DROP TABLE fact_orders;--"]).empty
    assert not load(db).empty


def test_numeric_validation_rejects_infinity_and_fractional_units():
    gate = Gate(pd.DataFrame({"n": [0, 1, float("inf"), "bad", 1.5]}), "test")
    values = gate.number("n", integer=True)
    valid, rejected = gate.finish(pd.DataFrame({"n": values}))
    assert list(valid.n) == [0, 1]
    assert len(rejected) == 3


def test_no_arbitrary_duplicate_winner():
    frame = pd.DataFrame({"id": ["A", "A", "B"], "value": [10, 20, 30]})
    gate = Gate(frame, "test")
    gate.key("id")
    valid, rejected = gate.finish(frame)
    assert list(valid.id) == ["B"] and len(rejected) == 2


def test_excel_source_is_real_and_unique():
    frame = read_partners(ROOT / "data/source/partners.xlsx")
    assert frame.partner_id.is_unique and not frame.empty


def test_export_protects_formula_text():
    output = csv_download(pd.DataFrame({"name": ["=SUM(1,1)", "ok"], "n": [-1, 2]}))
    assert b"'=SUM" in output and b"-1" in output


def test_usage_is_local_and_counts_distinct_sessions(tmp_path):
    path = tmp_path / "usage.db"
    assert summary(path)["sessions"] == 0
    record(path, "random-session", "view")
    record(path, "random-session", "export")
    assert summary(path) == {"sessions": 1, "views": 1, "exports": 1}


def test_quality_report_has_lineage(project):
    report = json.loads((project / "reports/runtime/quality.json").read_text())
    assert report["status"] == "passed"
    assert report["rejected_rows"] > 0
    assert len(report["source_sha256"]["orders.csv"]) == 64


def test_reference_metrics_match_sql_and_dataframe(project):
    from analytics.domain import kpis

    for suffix, regions in [("", ()), ("_RJ", ("RJ",))]:
        expected = json.loads((ROOT / f"reports/sample/metrics{suffix}.json").read_text())
        actual = kpis(load(project / "data/warehouse/analytics.db", regions=regions))
        assert list(actual.values()) == pytest.approx(list(expected.values()))


def test_seed_reproduces_committed_sources(tmp_path):
    from analytics.seed import seed

    seed(tmp_path)
    for name in ["orders.csv", "products.csv", "events.json"]:
        assert (tmp_path / "data/source" / name).read_text(encoding="utf-8") == (
            ROOT / "data/source" / name
        ).read_text(encoding="utf-8")


def test_empty_events_is_a_valid_input(tmp_path):
    source = tmp_path / "empty.json"
    source.write_text("[]")
    result = read_events(source)
    assert result.empty and "event_id" in result.columns


def test_powerbi_schema_matches_published_tables(project):
    schema = json.loads((ROOT / "powerbi/schema.json").read_text())
    with closing(sqlite3.connect(project / "data/warehouse/analytics.db")) as db:
        for table, expected in schema.items():
            columns = [row[1] for row in db.execute(f"PRAGMA table_info({table})")]
            assert set(columns) == set(expected)
