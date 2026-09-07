import numpy as np
import pandas as pd
import pytest
from src.analytics.metrics import compute_metrics, contributions, lifecycle
from src.analytics.anomalies import detect_anomalies
from src.analytics.propagation import lag_analysis
from src.ingestion.synthetic import generate
from src.processing.prepare import daily_panel
from src.models.forecast import forecast_series, predict


def test_scores_bounds_explanation_and_no_future_leakage():
    _, obs = generate(days=70)
    panel = daily_panel(obs)
    scores = compute_metrics(panel)
    assert scores.momentum.between(0, 100).all()
    assert scores.sustainability_score.between(0, 100).all()
    assert contributions(scores.iloc[-1]).points.sum() == pytest.approx(scores.iloc[-1].momentum)
    cutoff = pd.Timestamp("2025-02-20")
    truncated = compute_metrics(panel[panel.date <= cutoff])
    pd.testing.assert_frame_equal(scores[scores.date <= cutoff].reset_index(drop=True), truncated)


@pytest.mark.parametrize("args,stage", [((.4,.2,.8,.1),"Accelerating"), ((.12,0,.8,.12),"Emerging"),
    ((.02,-.2,.95,.4),"Peak"), ((-.2,-.2,.7,.1),"Cooling"), ((-.5,-.2,.3,0),"Fading")])
def test_lifecycle(args, stage):
    assert lifecycle(*args) == stage


def observations(values, source="reddit"):
    return pd.DataFrame({"topic_id":"t", "source_id":source, "timestamp":pd.date_range("2025-01-01", periods=len(values), freq="6h"),
        "attention":values, "engagements":np.nan, "sentiment":np.nan, "is_synthetic":True})


def test_anomaly_spike_baseline_and_causality():
    vals = np.full(80, 10.)
    vals[50] = 100
    data = observations(vals)
    anomalies = detect_anomalies(data)
    row = anomalies.iloc[0]
    assert row.baseline == 10 and row.magnitude == 90 and row["pct_change"] == 900
    pd.testing.assert_frame_equal(anomalies, detect_anomalies(data.iloc[:60]))
    assert detect_anomalies(observations(np.ones(80))).empty


def test_known_lag_and_constant_signal():
    rng = np.random.default_rng(4)
    a = np.exp(rng.normal(2, .3, 150))
    b = np.r_[np.full(3, a[0]), a[:-3]]
    _, summary = lag_analysis(pd.concat([observations(a), observations(b, "google_trends")]))
    assert summary["lag_hours"] == 18 and summary["supported"]
    _, summary = lag_analysis(pd.concat([observations(np.ones(100)), observations(np.ones(100), "google_trends")]))
    assert summary["lag_hours"] is None


def test_forecast_baselines_intervals_and_chronological_boundaries():
    s = pd.Series(np.tile([10,20,30,40,50,60,70], 16), index=pd.date_range("2025-01-01", periods=112))
    future, metrics, errors = forecast_series(s)
    assert metrics.loc[metrics.model.eq("Seasonal naive"), "mae"].iloc[0] == 0
    assert future.date.min() > s.index.max()
    assert (future.lower <= future.prediction).all() and (future.upper >= future.prediction).all()
    assert (metrics.validation_end < metrics.calibration_end).all()
    assert (metrics.calibration_end < metrics.test_end).all()
    changed = s.copy()
    changed.iloc[-14:] *= 100
    _, changed_metrics, _ = forecast_series(changed)
    assert metrics.loc[metrics.selected, "model"].iloc[0] == changed_metrics.loc[changed_metrics.selected, "model"].iloc[0]
    np.testing.assert_allclose(metrics.validation_mae, changed_metrics.validation_mae)
    assert np.isfinite(errors.prediction).all()
    with pytest.raises(ValueError, match="70 consecutive"):
        forecast_series(s.drop(s.index[20]))
    np.testing.assert_allclose(predict(np.ones(30), model="Ridge autoregression"), 1)


def test_zero_attention_has_zero_growth_and_novelty():
    data = observations(np.zeros(160))
    scores = compute_metrics(daily_panel(data))
    assert not scores.empty
    assert (scores.growth_rate == 0).all() and (scores.novelty == 0).all()
    assert np.isfinite(scores.momentum).all()
