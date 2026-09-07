"""Run with python -m src.pipeline. The default path performs no network calls."""
import argparse
import json
import logging
import re
from pathlib import Path
import pandas as pd
from src.ingestion.synthetic import generate
from src.ingestion.imports import reddit_csv, google_csv
from src.ingestion.files import read_local_text, manifest_file, MAX_MANIFEST_BYTES, MAX_TOPICS, MAX_TOTAL_BYTES, MAX_ROWS
from src.processing.prepare import validate, daily_panel
from src.analytics.metrics import compute_metrics
from src.analytics.anomalies import detect_anomalies
from src.models.forecast import forecast_series
from src.database.store import DEFAULT_DB, write_database

log = logging.getLogger("trendpulse")


def load_manifest(path):
    path = Path(path)
    try:
        manifest = json.loads(read_local_text(path, ".json", MAX_MANIFEST_BYTES))
    except json.JSONDecodeError:
        raise ValueError("Manifest must contain valid JSON.") from None
    if not isinstance(manifest, dict) or not isinstance(manifest.get("topics"), list):
        raise ValueError("Manifest must contain a topics list.")
    if len(manifest["topics"]) > MAX_TOPICS:
        raise ValueError("Manifest exceeds the topic limit.")
    topics, frames = [], []
    total_bytes, total_rows = 0, 0
    for topic in manifest["topics"]:
        if not isinstance(topic, dict):
            raise ValueError("Each manifest topic must be an object.")
        for key, limit in [("topic_id",64), ("name",200), ("category",80)]:
            value = topic.get(key)
            if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
                raise ValueError(f"Invalid topic {key}.")
        tid = topic["topic_id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", tid):
            raise ValueError("Topic IDs may contain only letters, digits, underscores and hyphens.")
        google_column = topic.get("google_column")
        if google_column is not None and (not isinstance(google_column, str) or not google_column or len(google_column) > 512):
            raise ValueError("Google column must be a nonempty column name.")
        topics.append({k: topic[k] for k in ("topic_id", "name", "category")})
        for key, adapter in [("reddit_csv", reddit_csv), ("google_csv", google_csv)]:
            if topic.get(key):
                kwargs = {"column": topic.get("google_column")} if key == "google_csv" else {}
                source_path = manifest_file(path.parent, topic[key])
                total_bytes += source_path.stat().st_size
                if total_bytes > MAX_TOTAL_BYTES:
                    raise ValueError("Manifest exports exceed the combined size limit.")
                frame = adapter(source_path, tid, **kwargs)
                total_rows += len(frame)
                if total_rows > MAX_ROWS:
                    raise ValueError("Manifest exports exceed the combined row limit.")
                frames.append(frame)
    if not frames:
        raise ValueError("Manifest has no source exports.")
    topics = pd.DataFrame(topics).assign(provenance="user-supplied export")
    if topics.topic_id.duplicated().any():
        raise ValueError("Topic IDs in manifest must be unique.")
    return topics, validate(pd.concat(frames, ignore_index=True))


def build(db=DEFAULT_DB, seed=42, days=112, manifest=None, export_demo=False):
    topics, observations = load_manifest(manifest) if manifest else generate(seed, days)
    observations = validate(observations)
    panel = daily_panel(observations)
    metrics = compute_metrics(panel)
    anomalies = detect_anomalies(observations)
    future_frames, eval_frames, error_frames, statuses = [], [], [], []
    for (topic, source), g in panel.groupby(["topic_id", "source_id"]):
        try:
            future, evaluation, errors = forecast_series(g.set_index("date").attention,
                upper_bound=100 if source == "google_trends" else None)
            for frame, destination in [(future, future_frames), (evaluation, eval_frames), (errors, error_frames)]:
                destination.append(frame.assign(topic_id=topic, source_id=source))
            statuses.append({"topic_id": topic, "source_id": source, "status": "Ready"})
        except ValueError as exc:
            log.info("Forecast unavailable for %s/%s: %s", topic, source, exc)
            statuses.append({"topic_id": topic, "source_id": source, "status": str(exc)})
    def combine(frames, columns):
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)
    frames = {"daily_attention": panel, "trend_metrics": metrics, "anomalies": anomalies,
        "forecasts": combine(future_frames, ["date", "prediction", "lower", "upper", "model", "nominal_coverage", "as_of", "topic_id", "source_id"]),
        "forecast_evaluation": combine(eval_frames, ["model", "selected", "validation_mae", "mae", "rmse", "interval_coverage", "train_end", "validation_end", "calibration_end", "test_end", "test_points", "topic_id", "source_id"]),
        "forecast_errors": combine(error_frames, ["origin", "horizon", "actual", "prediction", "model", "date", "topic_id", "source_id"]),
        "forecast_status": pd.DataFrame(statuses)}
    write_database(db, topics, observations, frames, {"mode": "Imported exports" if manifest else "Synthetic demo",
        "seed": seed if not manifest else -1, "observation_count": len(observations),
        "start": observations.timestamp.min(), "end": observations.timestamp.max(), "version": "1.0.0"})
    if export_demo and not manifest:
        destination = Path(db).parent / "processed"
        destination.mkdir(exist_ok=True)
        observations.to_csv(destination / "demo_observations.csv", index=False)
        topics.to_csv(destination / "demo_topics.csv", index=False)
    log.info("Built %s: %s observations, %s metrics, %s forecast series", db, len(observations), len(metrics), len(future_frames))
    return frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--days", type=int, default=112)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--export-demo", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    build(**vars(args))


if __name__ == "__main__":
    main()
