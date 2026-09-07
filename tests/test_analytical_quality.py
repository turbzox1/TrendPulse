import duckdb
import numpy as np
import pandas as pd
import pytest

from src.analytics.metrics import compute_metrics, percentage_growth, WEIGHTS
from src.analytics.insights import generate_insights, related_topics
from src.analytics.anomalies import detect_anomalies
from src.analytics.propagation import lag_analysis
from src.processing.prepare import daily_panel
from src.models.forecast import forecast_series, backtest
from src.ingestion.synthetic import generate


def daily(values, source="google_trends"):
    return pd.DataFrame({"topic_id": "t", "source_id": source,
        "timestamp": pd.date_range("2025-01-01", periods=len(values)),
        "attention": values, "engagements": np.nan, "sentiment": np.nan, "is_synthetic": True})


def test_true_growth_and_undefined_baselines():
    actual = percentage_growth(pd.Series([1., 5., 0., 0., 4.]), pd.Series([.5, 0., 0., 2., np.nan]))
    np.testing.assert_allclose(actual, [1., np.nan, 0., -1., np.nan], equal_nan=True)
    scores = compute_metrics(daily_panel(daily([0.] * 35 + [5., 5.])))
    row = scores.iloc[-1]
    assert np.isnan(row.growth_rate) and np.isfinite(row.momentum)
    assert row.lifecycle == "Accelerating"
    insight = generate_insights(scores.tail(1), pd.DataFrame({"topic_id": ["t"], "name": ["Example"]}))[0]
    assert "N/A" in insight and "nan" not in insight and "2025-02-06" in insight


def test_small_reference_has_literal_index_not_floored_ratio():
    panel = daily_panel(daily([.5] * 9 + [1.]))
    assert panel.attention_index.iloc[-1] == 200
    assert daily_panel(daily([0.] * 9 + [1.])).attention_index.isna().all()


def test_partial_engagement_and_volume_weighted_sentiment():
    obs = daily([1.] * 8, "reddit")
    obs["timestamp"] = pd.date_range("2025-01-01", periods=8, freq="6h")
    obs["attention"] = [1., 1., 1., 97.] * 2
    obs["engagements"] = [1., 1., np.nan, 97.] * 2
    obs["sentiment"] = [-1., -1., -1., 1.] * 2
    panel = daily_panel(obs)
    assert panel.engagements.isna().all()
    np.testing.assert_allclose(panel.sentiment, .94)
    obs.loc[0, "sentiment"] = np.nan
    assert np.isnan(daily_panel(obs).sentiment.iloc[0])


def test_off_grid_bins_not_counted_as_complete():
    obs = daily([1.] * 12)
    obs["timestamp"] = pd.date_range("2025-01-01 00:30", periods=12, freq="6h")
    with pytest.raises(ValueError, match="No complete"):
        daily_panel(obs)


def test_lifecycle_peak_uses_same_smoothed_units():
    scores = compute_metrics(daily_panel(daily([10., 90.] * 25)))
    assert scores.relative_peak.iloc[-1] == 1
    assert scores.lifecycle.iloc[-1] == "Peak"
    assert sum(WEIGHTS.values()) == pytest.approx(1)


def test_relative_features_are_scale_invariant_below_one():
    values = np.linspace(.05, .5, 60)
    small = compute_metrics(daily_panel(daily(values)))
    large = compute_metrics(daily_panel(daily(values * 100)))
    for col in ["relative_peak", "novelty", "volatility", "growth_rate"]:
        np.testing.assert_allclose(small[col], large[col], atol=1e-12)
    assert compute_metrics(daily_panel(daily([.1] * 40))).relative_peak.iloc[-1] == 1


def test_sustainability_missing_quality_never_has_medium_confidence():
    scores = compute_metrics(daily_panel(daily(np.linspace(1, 70, 70))))
    assert scores.confidence.eq("Low").all()
    assert scores.sustainability_coverage.iloc[-1] == pytest.approx(.85)


def test_related_topics_do_not_bridge_calendar_gaps_or_recommend_inverse_patterns():
    dates = pd.date_range("2025-01-01", periods=60, freq="2D")
    frames = [pd.DataFrame({"date": dates, "topic_id": t, "attention_index": v})
        for t, v in [("a", np.arange(60.)**2), ("b", np.arange(60.)**2)]]
    assert related_topics(pd.concat(frames), "a").empty
    for frame in frames:
        frame["date"] = pd.date_range("2025-01-01", periods=60)
    frames[1]["attention_index"] *= -1
    assert related_topics(pd.concat(frames), "a").empty


def test_anomaly_drop_zero_baseline_and_past_only():
    data = daily([100.] * 30 + [0.] + [100.] * 10, "reddit")
    flags = detect_anomalies(data)
    assert flags.iloc[0].direction == "Decrease" and flags.iloc[0]["pct_change"] == -100
    pd.testing.assert_frame_equal(flags, detect_anomalies(data.iloc[:32]))
    flags = detect_anomalies(daily([0.] * 30 + [10.]))
    assert len(flags) == 1 and np.isnan(flags.iloc[0]["pct_change"])


def test_mixed_cadence_lead_lag_not_inferred():
    reddit = daily(np.arange(100.), "reddit")
    reddit["timestamp"] = pd.date_range("2025-01-01", periods=100, freq="6h")
    _, summary = lag_analysis(pd.concat([reddit, daily(np.arange(70.))]))
    assert summary["lag_hours"] is None and "different cadences" in summary["status"]


def test_forecast_origin_predictions_cannot_see_its_targets():
    y = 30 + np.random.default_rng(2).normal(size=100)
    altered = y.copy()
    altered[70:] += 100
    for model in ["Last value", "Seasonal naive", "Ridge autoregression"]:
        a, b = backtest(y, 70, 77, model), backtest(altered, 70, 77, model)
        np.testing.assert_allclose(a.prediction, b.prediction)
    s = pd.Series(y, index=pd.date_range("2025-01-01", periods=100))
    _, metrics, _ = forecast_series(s)
    s.iloc[-14:] += 100
    _, changed, _ = forecast_series(s)
    np.testing.assert_allclose(metrics.validation_mae, changed.validation_mae)
    assert metrics.selected.tolist() == changed.selected.tolist()


def test_sql_and_python_growth_have_same_definition(demo_db):
    with duckdb.connect(str(demo_db), read_only=True) as con:
        panel = con.sql("SELECT * FROM daily_attention").df()
        sql = con.sql("SELECT topic_id, date, AVG(growth_two_days) growth_rate FROM source_daily_growth GROUP BY topic_id, date").df()
    calculated = compute_metrics(panel)[["topic_id", "date", "growth_rate"]]
    comparison = calculated.merge(sql, on=["topic_id", "date"], suffixes=("_python", "_sql"))
    np.testing.assert_allclose(comparison.growth_rate_python, comparison.growth_rate_sql, atol=1e-12)


def test_synthetic_archetypes_are_distinct_and_stochastic():
    topics, obs = generate()
    panel = daily_panel(obs)
    reddit = panel[panel.source_id.eq("reddit")].pivot(index="date", columns="topic_id", values="attention")
    assert reddit.t00.tail(7).mean() > 3 * reddit.t00.head(28).mean()  # organic
    assert reddit.t03.tail(2).mean() < .4 * reddit.t03.max()  # spent hype
    assert reddit.t08.autocorr(7) > .8  # recurrence
    assert reddit.t04.tail(2).mean() > 4 * reddit.t04.head(28).mean()  # emerging
    assert not obs.attention.equals(generate(seed=43)[1].attention)
    assert set(topics.provenance) == {"synthetic"}
