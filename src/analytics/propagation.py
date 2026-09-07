import numpy as np
import pandas as pd


def lag_analysis(observations: pd.DataFrame, max_lag: int = 8) -> tuple[pd.DataFrame, dict]:
    """Positive lag means Reddit changes precede search changes. No interpolation."""
    wide = observations.pivot(index="timestamp", columns="source_id", values="attention").sort_index()
    empty = {"status": "Need both sources and at least 40 aligned changes.", "lag_hours": None, "correlation": None, "p_value": None}
    if not {"reddit", "google_trends"}.issubset(wide.columns) or len(wide) < 42:
        return pd.DataFrame(), empty
    cadences = observations.groupby("source_id").timestamp.apply(lambda s: s.sort_values().diff().dropna().mode().iloc[0])
    if cadences.nunique() != 1:
        return pd.DataFrame(), {**empty, "status": "Sources have different cadences. Supply aligned daily or aligned 6-hour aggregates; no sub-daily lead is inferred from daily exports."}
    cadence = wide.index.to_series().diff().dropna().mode().iloc[0]
    wide = wide.reindex(pd.date_range(wide.index.min(), wide.index.max(), freq=cadence))
    changes = np.log1p(wide).diff()
    def correlations(y):
        values = []
        for lag in range(-max_lag, max_lag+1):
            pair = pd.concat([changes.reddit, y.shift(-lag)], axis=1).dropna()
            corr = pair.iloc[:, 0].corr(pair.iloc[:, 1]) if len(pair) >= 40 and pair.std().min() > 1e-8 else np.nan
            values.append((lag, corr, len(pair)))
        return values
    result = pd.DataFrame(correlations(changes.google_trends), columns=["lag", "correlation", "pairs"])
    result["lag_hours"] = result.lag * cadence.total_seconds() / 3600
    valid = result.dropna()
    if valid.empty:
        return result, {**empty, "status": "Insufficient variation or overlapping observations."}
    best = valid.loc[valid.correlation.idxmax()]
    # Circular-shift null preserves serial structure; maximum across searched lags
    # reduces lag-selection optimism. This is exploratory, not a causal test.
    rng = np.random.default_rng(42)
    null = []
    y = changes.google_trends
    if len(y) <= 4*max_lag + 2:
        return result, empty
    for offset in rng.integers(2*max_lag+1, len(y)-2*max_lag, size=49):
        shuffled = pd.Series(np.roll(y.to_numpy(), offset), index=y.index)
        vals = [c for _, c, _ in correlations(shuffled) if np.isfinite(c)]
        if vals:
            null.append(max(vals))
    p = (1 + sum(v >= best.correlation for v in null)) / (len(null)+1)
    supported = best.correlation >= .25 and p <= .1
    return result, {"status": "Exploratory lead/lag association" if supported else "No clear propagation signal",
        "lag_hours": float(best.lag_hours), "correlation": float(best.correlation), "p_value": p,
        "supported": supported, "pairs": int(best.pairs)}
