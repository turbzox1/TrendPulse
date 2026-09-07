import numpy as np
import pandas as pd


def detect_anomalies(observations: pd.DataFrame, threshold=4.0) -> pd.DataFrame:
    columns = ["topic_id", "source_id", "timestamp", "magnitude", "baseline", "pct_change", "robust_z", "direction", "signals"]
    rows = []
    for (topic, source), g in observations.groupby(["topic_id", "source_id"]):
        g = g.sort_values("timestamp").set_index("timestamp")
        if len(g) < 16:
            continue
        cadence = g.index.to_series().diff().dropna().mode().iloc[0]
        g = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq=cadence))
        window = max(14, int(604800 / cadence.total_seconds()))
        history = g.attention.shift(1).rolling(window, min_periods=window)
        baseline = history.median()
        mad = history.apply(lambda x: np.median(np.abs(x - np.median(x))), raw=True)
        scale = pd.concat([1.4826 * mad, np.sqrt(baseline.clip(lower=1))], axis=1).max(axis=1)
        z = (g.attention - baseline) / scale
        for stamp in z.index[z.abs().ge(threshold)]:
            b, value = baseline.loc[stamp], g.loc[stamp, "attention"]
            signals = ["Attention diverged from the preceding rolling median"]
            if source == "reddit" and pd.notna(g.loc[stamp, "engagements"]):
                ebase = g.engagements.shift(1).rolling(window).median().loc[stamp]
                if g.loc[stamp, "engagements"] > 1.5 * max(1, ebase):
                    signals.append("engagement was also elevated")
            rows.append({"topic_id": topic, "source_id": source, "timestamp": stamp,
                "magnitude": value-b, "baseline": b, "pct_change": (value/b-1)*100 if b else np.nan,
                "robust_z": z.loc[stamp], "direction": "Increase" if value>b else "Decrease",
                "signals": "; ".join(signals) + ". Co-occurring signals do not establish a cause."})
    return pd.DataFrame(rows, columns=columns)
