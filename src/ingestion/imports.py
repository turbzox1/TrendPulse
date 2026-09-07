"""Offline import adapters: no scraping, unofficial endpoints, or hidden network IO."""
from pathlib import Path
from io import StringIO
import pandas as pd
from src.processing.prepare import validate
from src.ingestion.files import read_local_text, MAX_CSV_BYTES, MAX_ROWS


def parse_csv(text):
    try:
        result = pd.read_csv(StringIO(text), nrows=MAX_ROWS+1)
    except (pd.errors.ParserError, pd.errors.EmptyDataError):
        raise ValueError("CSV is empty or malformed.") from None
    if len(result) > MAX_ROWS:
        raise ValueError("CSV exceeds the row limit.")
    return result


def google_csv(path: str | Path, topic_id: str, column: str | None = None) -> pd.DataFrame:
    lines = read_local_text(path, ".csv", MAX_CSV_BYTES).splitlines()
    start = next((i for i, line in enumerate(lines) if line.split(",")[0] in ("Day", "Date", "Time")), None)
    if start is None:
        raise ValueError("Export a daily Interest over time CSV with a Day/Date/Time header (English locale).")
    raw = parse_csv("\n".join(lines[start:]))
    if column is None and len(raw.columns) != 2:
        raise ValueError("Multiple series: specify --column exactly as named in the export.")
    column = column or raw.columns[1]
    if column not in raw.columns:
        raise ValueError("The selected Google Trends column is absent from the export.")
    values = raw[column].replace("<1", "0.5")
    return validate(pd.DataFrame({"topic_id": topic_id, "source_id": "google_trends",
        "timestamp": raw.iloc[:, 0], "attention": values, "engagements": float("nan"),
        "sentiment": float("nan"), "is_synthetic": False}))


def reddit_csv(path: str | Path, topic_id: str) -> pd.DataFrame:
    """Import authorized aggregates, with explicit complete daily/6h observation windows."""
    raw = parse_csv(read_local_text(path, ".csv", MAX_CSV_BYTES))
    if not {"timestamp", "mentions"}.issubset(raw):
        raise ValueError("Reddit CSV needs timestamp and mentions columns.")
    result = pd.DataFrame({"timestamp": raw.timestamp, "attention": raw.mentions})
    result["topic_id"], result["source_id"] = topic_id, "reddit"
    for col in ["engagements", "sentiment"]:
        result[col] = raw[col] if col in raw else float("nan")
    result["is_synthetic"] = False
    return validate(result)
