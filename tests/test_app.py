from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app" / "dashboard.py"


def test_all_six_pages_and_filters(demo_db, monkeypatch):
    monkeypatch.setenv("TRENDPULSE_DB", str(demo_db))
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not app.exception and not app.error
    assert len(app.metric) == 4
    app.button(key="open_t09").click().run()
    assert app.sidebar.radio[0].value == "Trend Explorer"
    assert app.selectbox(key="topic_picker").value == "t09"
    assert not app.exception and not app.error
    assert [t.label for t in app.tabs] == ["Summary", "Why it's moving", "Sources & spikes", "Forecast", "Related topics"]
    for page in ["Emerging Trends", "Trend Explorer", "Cross-Platform Analysis", "Forecasting", "Analytics / Insights"]:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, (page, [e.message for e in app.exception])
        assert not app.error, (page, [e.value for e in app.error])
    app.sidebar.multiselect[1].set_value([]).run()
    assert not app.exception and any("at least one" in i.value for i in app.info)
    app.sidebar.multiselect[1].set_value(["reddit"]).run()
    assert not app.exception and not app.error
    app.sidebar.radio[0].set_value("Cross-Platform Analysis").run()
    assert any("both sources" in i.value for i in app.info)
    app.button(key="both_sources").click().run()
    assert app.multiselect(key="filter_sources").value == ["reddit", "google_trends"]
    assert not app.exception and not app.error


def test_historical_forecast_is_hidden(demo_db, monkeypatch):
    monkeypatch.setenv("TRENDPULSE_DB", str(demo_db))
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    app.sidebar.radio[0].set_value("Forecasting").run()
    from datetime import date
    app.sidebar.date_input[0].set_value(date(2025,3,15)).run()
    assert not app.exception
    assert any("hidden" in i.value for i in app.info)
    app.button(key="latest_forecast").click().run()
    assert app.date_input(key="filter_date").value == date(2025,4,22)
    assert not app.exception and not app.error


def test_missing_database_message(tmp_path, monkeypatch):
    monkeypatch.setenv("TRENDPULSE_DB", str(tmp_path / "absent.duckdb"))
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception
    assert any("does not exist" in e.value for e in app.error)


def test_search_navigation_and_reset(demo_db, monkeypatch):
    monkeypatch.setenv("TRENDPULSE_DB", str(demo_db))
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    app.selectbox(key="home_topic").set_value("t01").run()
    app.button(key="home_topic_open").click().run()
    assert app.selectbox(key="topic_picker").value == "t01"
    app.sidebar.radio[0].set_value("Emerging Trends").run()
    app.text_input(key="trend_search").set_value("Walking").run()
    assert app.selectbox(key="result_topic").options == ["Walking clubs"]
    app.button(key="result_topic_open").click().run()
    assert app.selectbox(key="topic_picker").value == "t09"
    app.multiselect(key="filter_categories").set_value([]).run()
    assert any("at least one" in i.value for i in app.info)
    app.button(key="reset_filters").click().run()
    assert len(app.multiselect(key="filter_categories").value) == 4
    assert not app.exception and not app.error
    app.sidebar.radio[0].set_value("Emerging Trends").run()
    app.text_input(key="trend_search").set_value("no-such-topic-123").run()
    assert any("No matching topics" in i.value for i in app.info)
    assert not app.exception and not app.error
