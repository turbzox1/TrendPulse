import duckdb
import pytest
import json
import pandas as pd
from src.database.store import read_database
from src.pipeline import build


def test_database_schema_and_sql(demo_db):
    data = read_database(demo_db)
    assert len(data["observation_detail"]) == 16128
    assert len(data["forecasts"]) == 36*7
    assert len(data["forecast_evaluation"]) == 36*3
    with duckdb.connect(str(demo_db), read_only=True) as con:
        assert con.execute("SELECT COUNT(*) FROM latest_trends").fetchone()[0] == 18
        assert con.execute("SELECT SUM(topic_count) FROM category_summary").fetchone()[0] == 18
        assert con.execute("SELECT COUNT(*) FROM forecast_comparison WHERE selected").fetchone()[0] == 36
        assert con.execute("SELECT COUNT(*) FROM source_daily_growth WHERE growth_two_days IS NOT NULL").fetchone()[0] == 36*109
        assert con.execute("SELECT COUNT(*) FROM engagement e LEFT JOIN observations o USING(observation_id) WHERE o.observation_id IS NULL").fetchone()[0] == 0


def test_failed_import_preserves_database(demo_db, tmp_path):
    manifest = tmp_path / "invalid.json"
    manifest.write_text('{"topics": []}', encoding="utf-8")
    before = demo_db.read_bytes()
    with pytest.raises(ValueError, match="no source"):
        build(demo_db, manifest=manifest)
    assert demo_db.read_bytes() == before


@pytest.mark.parametrize("days", [2, 35])
def test_short_import_preserves_unavailable_forecast_state(tmp_path, days):
    export = tmp_path / "search.csv"
    pd.DataFrame({"Day": pd.date_range("2025-01-01", periods=days), "Example": range(days)}).to_csv(export, index=False)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"topics": [{"topic_id":"example", "name":"Example", "category":"Technology", "google_csv":"search.csv"}]}), encoding="utf-8")
    db = tmp_path / "import.duckdb"
    build(db, manifest=manifest)
    data = read_database(db)
    assert data["forecasts"].empty
    assert not data["observation_detail"].is_synthetic.any()
    assert "70 consecutive" in data["forecast_status"].status.iloc[0]
