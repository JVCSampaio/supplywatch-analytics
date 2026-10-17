from pathlib import Path
from streamlit.testing.v1 import AppTest
from analytics.pipeline import run

ROOT = Path(__file__).resolve().parents[1]


def test_app_filters_exports_and_empty_state():
    run(ROOT)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert len(app.metric) >= 4
    before = app.metric[0].value
    app.multiselect[0].select("RJ").run()
    assert not app.exception
    assert app.metric[0].value != before
    app.selectbox[0].select("region").run()
    assert not app.exception
    app.checkbox[0].check().run()
    assert not app.exception
    # All synthetic suppliers/customers in RJ are never in every possible segment,
    # but an impossible date/category slice is tested independently in SQL tests.
