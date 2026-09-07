"""Past-only, source-relative metrics. Weights are transparent policy choices."""
import numpy as np
import pandas as pd

WEIGHTS = {"growth": .25, "acceleration": .15, "engagement_growth": .10,
           "diversity": .10, "persistence": .20, "sentiment_movement": .05, "novelty": .15}


def bounded(x, scale=1):
    return 50 + 50 * np.tanh(x / scale)


def percentage_growth(recent, previous):
    """True relative change; zero-to-zero is stable, positive-from-zero undefined."""
    return ((recent-previous) / previous.where(previous > 0)).mask((recent == 0) & (previous == 0), 0)


def format_growth(value):
    return f"{value:+.0%}" if pd.notna(value) else "N/A (baseline unavailable)"


def lifecycle(growth: float, acceleration: float, relative_peak: float, prior_growth: float) -> str:
    if growth < -.25:
        return "Fading" if relative_peak < .55 else "Cooling"
    if growth < -.08:
        return "Cooling"
    if relative_peak >= .9 and prior_growth > .15 and growth < .15:
        return "Peak"
    if growth > .15 and acceleration > .03:
        return "Accelerating"
    if growth > .08:
        return "Emerging"
    return "Fading" if relative_peak < .45 else "Peak"


def compute_metrics(panel: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for (topic, source), original in panel.groupby(["topic_id", "source_id"]):
        g = original.set_index("date").reindex(pd.date_range(original.date.min(), original.date.max(), freq="D"))
        a = g.attention
        recent = a.rolling(2, min_periods=2).mean()
        previous = recent.shift(2)
        # Stabilize ranking features, but never present this as literal percentage growth.
        growth = (recent - previous) / previous.clip(lower=1)
        prior = growth.shift(2)
        engagement_rate = g.engagements / a.where(a > 0)
        engagement_recent = engagement_rate.rolling(2).mean()
        engagement_prior = engagement_recent.shift(2)
        sentiment = (g.sentiment * a).rolling(2, min_periods=2).sum() / a.rolling(2).sum().replace(0, np.nan)
        historical = a.shift(2).rolling(28, min_periods=14).mean()
        peak = recent.rolling(28, min_periods=14).max()
        weekly_mean = a.rolling(7).mean()
        # Missing evidence remains missing, so its weight is excluded explicitly.
        f = pd.DataFrame({"topic_id": topic, "source_id": source, "date": g.index,
            "attention_index": g.attention_index.values, "growth_rate": percentage_growth(recent, previous).values,
            "growth_signal": growth.values,
            "acceleration_raw": (growth-prior).values, "prior_growth": prior.values,
            "relative_peak": (recent / peak.where(peak > 0)).mask(peak.eq(0), 0).values,
            "growth": bounded(growth, .5).values,
            "acceleration": bounded(growth-prior, .3).values,
            "engagement_growth": bounded((engagement_recent-engagement_prior) / engagement_prior.clip(lower=.1), .4).values,
            "persistence": (100 * (a > historical).astype(float).where(a.notna() & historical.notna()).rolling(7, min_periods=7).mean()).values,
            "sentiment_movement": bounded(sentiment-sentiment.shift(2), .2).values,
            "novelty": (100 * ((recent-historical) / recent.where(recent > 0)).mask(recent.eq(0) & historical.notna(), 0).clip(0, 1)).values,
            "volatility": (a.rolling(7).std() / weekly_mean.where(weekly_mean > 0)).mask(weekly_mean.eq(0), 0).values,
            "quality": (engagement_rate.rolling(7).mean().clip(0, 2) / 2).values,
            "sentiment": sentiment.values,
            "repeated_attention": (a > historical).astype(float).where(a.notna() & historical.notna()).rolling(21, min_periods=14).mean().values})
        frames.append(f)
    joined = pd.concat(frames, ignore_index=True)
    nums = [c for c in joined if c not in ("topic_id", "source_id", "date")]
    result = joined.groupby(["topic_id", "date"])[nums].mean().reset_index()
    # Do not silently omit an undefined source ratio from the advertised combined growth.
    result["growth_rate"] = joined.groupby(["topic_id", "date"]).growth_rate.agg(lambda s: s.mean() if s.notna().all() else np.nan).to_numpy()
    active = joined.assign(active=joined.growth_signal.gt(.08) & joined.attention_index.notna()).groupby(["topic_id", "date"]).active.sum()
    result["active_sources"] = result.set_index(["topic_id", "date"]).index.map(active).to_numpy()
    result["diversity"] = 100 * result.active_sources / 2  # fixed supported-source universe
    weight = result[list(WEIGHTS)].notna().mul(pd.Series(WEIGHTS)).sum(axis=1)
    result["evidence_coverage"] = weight
    result["momentum"] = result[list(WEIGHTS)].mul(pd.Series(WEIGHTS)).sum(axis=1) / weight
    ready = result[["growth_signal", "acceleration_raw", "relative_peak", "persistence", "novelty"]].notna().all(axis=1)
    result = result.loc[ready].copy()
    result["lifecycle"] = [lifecycle(r.growth_signal, r.acceleration_raw, r.relative_peak, r.prior_growth) for r in result.itertuples()]
    # Evidence index, NOT a trained probability of future success.
    quality = result.quality.fillna(.5)
    result["sustainability_score"] = 100 * (
        .30 * result.persistence / 100 + .15 * (1-result.volatility.clip(0, 1)) +
        .15 * quality + .15 * result.diversity / 100 +
        .15 * result.repeated_attention.fillna(.5) + .10 * result.acceleration / 100)
    result["sustainability"] = np.select(
        [(result.sustainability_score >= 65) & (result.growth_signal > 0),
         (result.sustainability_score < 40) | (result.growth_signal < -.25)],
        ["Sustainable", "Short-lived"], default="Uncertain")
    result["sustainability_coverage"] = 1 - .15 * result.quality.isna() - .15 * result.repeated_attention.isna()
    result["confidence"] = np.where((result.sustainability_coverage >= .85) & result.quality.notna()
        & result.active_sources.eq(2) & (result.sustainability.ne("Uncertain")), "Medium", "Low")
    return result.reset_index(drop=True)


def contributions(row: pd.Series) -> pd.DataFrame:
    available = {k: w for k, w in WEIGHTS.items() if pd.notna(row[k])}
    total = sum(available.values())
    return pd.DataFrame([{"component": k.replace("_", " ").title(), "factor_score": row[k],
        "effective_weight": w / total, "points": row[k] * w / total} for k, w in available.items()])


def sustainability_explanation(row) -> str:
    quality_text = f"{row['quality']:.2f}" if pd.notna(row['quality']) else "unavailable"
    repeated_text = f"{row['repeated_attention']:.0%}" if pd.notna(row['repeated_attention']) else "unavailable (neutral 0.5 used)"
    return (f"Above-baseline persistence {row['persistence']:.0f}%; weekly coefficient of variation "
            f"{row['volatility']:.2f}; {int(row['active_sources'])} growing source(s); "
            f"engagement quality {quality_text} (missing uses neutral 0.5); "
            f"repeated above-baseline attention {repeated_text}; "
            f"acceleration factor {row['acceleration']:.0f}/100; "
            f"sustainability evidence coverage {row['sustainability_coverage']:.0%}. "
            f"48-hour growth {format_growth(row['growth_rate'])}. Confidence: {row['confidence'].lower()}. "
            "This is heuristic evidence, not a calibrated probability.")
