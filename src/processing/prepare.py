import numpy as np
import pandas as pd

REQUIRED = {"topic_id", "source_id", "timestamp", "attention", "engagements", "sentiment", "is_synthetic"}


def validate(observations: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED - set(observations.columns)
    if missing:
        raise ValueError(f"Missing observation columns: {sorted(missing)}")
    df = observations.copy()
    if df.empty:
        raise ValueError("No observations supplied.")
    if df[["topic_id", "source_id", "timestamp"]].isna().any().any():
        raise ValueError("Observation keys cannot be missing.")
    if not set(df.source_id).issubset({"reddit", "google_trends"}):
        raise ValueError("Supported sources: reddit, google_trends.")
    df["timestamp"] = pd.to_datetime(df.timestamp, utc=True, errors="raise").dt.tz_localize(None)
    if df.duplicated(["topic_id", "source_id", "timestamp"]).any():
        raise ValueError("Duplicate topic/source/timestamp observations.")
    for column in ["attention", "engagements", "sentiment"]:
        df[column] = pd.to_numeric(df[column], errors="raise")
        if np.isinf(df[column]).any():
            raise ValueError(f"Nonfinite {column}.")
    if df.attention.isna().any() or (df.attention < 0).any():
        raise ValueError("Attention must be finite and nonnegative; missing bins are not zeros.")
    if (df.engagements.dropna() < 0).any() or (df.sentiment.dropna().abs() > 1).any():
        raise ValueError("Invalid engagement or sentiment range.")
    if (df.loc[df.source_id.eq("google_trends"), "attention"] > 100).any():
        raise ValueError("Google Trends interest must be between 0 and 100.")
    if not df.is_synthetic.isin([True, False]).all():
        raise ValueError("is_synthetic must be boolean.")
    return df.sort_values(["topic_id", "source_id", "timestamp"]).reset_index(drop=True)


def daily_panel(observations: pd.DataFrame) -> pd.DataFrame:
    """Use complete regular bins only; no interpolation or zero-filling gaps."""
    df = validate(observations)
    pieces = []
    for (topic, source), g in df.groupby(["topic_id", "source_id"]):
        deltas = g.timestamp.diff().dropna()
        if deltas.empty:
            continue
        cadence = deltas.mode().iloc[0]
        seconds = cadence.total_seconds()
        if seconds not in (21600, 86400):
            raise ValueError("Supply regular daily or 6-hour observations; weekly exports are unsupported.")
        expected = int(86400 / seconds)
        g = g.assign(date=g.timestamp.dt.floor("D"))
        for date, day in g.groupby("date"):
            if len(day) != expected or set(day.timestamp) != set(pd.date_range(date, periods=expected, freq=cadence)):
                continue
            # Optional aggregate fields need complete coverage, not partial sums.
            sentiment = np.nan
            if day.sentiment.notna().all() and day.attention.sum() > 0:
                sentiment = np.average(day.sentiment, weights=day.attention)
            pieces.append({"topic_id": topic, "source_id": source, "date": date,
                "attention": day.attention.sum() if source == "reddit" else day.attention.mean(),
                "engagements": day.engagements.sum(min_count=expected), "sentiment": sentiment})
    if not pieces:
        raise ValueError("No complete daily bins found.")
    panel = pd.DataFrame(pieces).sort_values(["topic_id", "source_id", "date"])
    # Expanding reference uses prior days only. Index = 100 at prior historical mean.
    panel["reference"] = panel.groupby(["topic_id", "source_id"]).attention.transform(
        lambda s: s.expanding(min_periods=7).mean().shift(1))
    panel["attention_index"] = 100 * panel.attention / panel.reference.where(panel.reference > 0)
    return panel
