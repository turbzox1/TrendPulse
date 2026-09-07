from pathlib import Path
from tempfile import TemporaryDirectory
import duckdb
import numpy as np
import pandas as pd

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "trendpulse.duckdb"


def write_database(path, topics, observations, frames, metadata):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # A private sibling directory avoids clobbering another writer's staging file.
    with TemporaryDirectory(prefix=".trendpulse-", dir=path.parent) as directory:
        staging = Path(directory) / "building.duckdb"
        _write_staging(staging, topics, observations, frames, metadata)
        staging.replace(path)


def _write_staging(staging, topics, observations, frames, metadata):
    con = duckdb.connect(str(staging))
    try:
        con.execute("BEGIN TRANSACTION")
        con.execute(Path(__file__).with_name("schema.sql").read_text())
        con.register("input_topics", topics)
        con.execute("INSERT INTO topics SELECT topic_id, name, category, provenance FROM input_topics")
        con.execute("INSERT INTO sources VALUES ('reddit', 'Reddit', 'mentions'), ('google_trends', 'Google Trends', 'relative search interest (0-100)')")
        obs = observations.copy()
        obs["observation_id"] = np.arange(len(obs))
        con.register("input_observations", obs)
        con.execute("INSERT INTO observations SELECT observation_id, topic_id, source_id, timestamp, attention, is_synthetic FROM input_observations")
        con.execute("INSERT INTO engagement SELECT observation_id, engagements FROM input_observations WHERE engagements IS NOT NULL")
        con.execute("INSERT INTO sentiment SELECT observation_id, sentiment FROM input_observations WHERE sentiment IS NOT NULL")
        for name, frame in frames.items():
            if name not in {"daily_attention", "trend_metrics", "anomalies", "forecasts", "forecast_evaluation", "forecast_errors", "forecast_status"}:
                raise ValueError(f"Unsupported analytical table: {name}")
            con.register("frame", frame)
            con.execute(f'CREATE TABLE "{name}" AS SELECT * FROM frame')
        con.execute("ALTER TABLE trend_metrics ADD PRIMARY KEY (topic_id, date)")
        con.execute("ALTER TABLE forecasts ADD PRIMARY KEY (topic_id, source_id, date)")
        con.register("meta", pd.DataFrame([metadata]))
        con.execute("CREATE TABLE dataset_metadata AS SELECT * FROM meta")
        con.execute(Path(__file__).with_name("views.sql").read_text())
        con.execute("COMMIT")
    except Exception:
        con.close()
        raise
    else:
        con.close()


def read_database(path=DEFAULT_DB):
    with duckdb.connect(str(path), read_only=True, config={"enable_external_access":False}) as con:
        return {name: con.execute(f'SELECT * FROM "{name}"').df() for name in (
            "topics", "sources", "observation_detail", "daily_attention", "trend_metrics",
            "anomalies", "forecasts", "forecast_evaluation", "forecast_errors", "forecast_status", "dataset_metadata")}
