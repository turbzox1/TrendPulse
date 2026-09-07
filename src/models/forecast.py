"""Fixed-feature ridge model, honest validation/calibration/test blocks, naive controls."""
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error

MODELS = ("Last value", "Seasonal naive", "Ridge autoregression")


def features(history):
    h = np.asarray(history, dtype=float)
    return [h[-1], h[-2], h[-7], np.mean(h[-7:]), (h[-1]-h[-7])/6]


def predict(history, horizon=7, model="Last value", upper_bound=None):
    h = list(np.asarray(history, dtype=float))
    if len(h) < 14 or not np.isfinite(h).all():
        raise ValueError("Forecast needs at least 14 finite consecutive daily values.")
    if model not in MODELS:
        raise ValueError(f"Unknown model: {model}")
    fitted = None
    if model == "Ridge autoregression":
        X = np.array([features(h[:i]) for i in range(7, len(h))])
        fitted = make_pipeline(StandardScaler(), Ridge(alpha=10)).fit(X, h[7:])
    values = []
    for _ in range(horizon):
        value = h[-1] if model == "Last value" else h[-7]
        if fitted is not None:
            value = float(fitted.predict([features(h)])[0])
        value = max(0, value)
        if upper_bound is not None:
            value = min(upper_bound, value)
        values.append(value)
        h.append(value)
    return np.asarray(values)


def backtest(y, start, end, model, upper_bound=None):
    rows = []
    for origin in range(start, end, 7):
        horizon = min(7, end-origin)
        pred = predict(y[:origin], horizon, model, upper_bound)
        for h, value in enumerate(pred):
            rows.append({"origin": origin, "horizon": h+1, "actual": y[origin+h], "prediction": value})
    return pd.DataFrame(rows)


def forecast_series(series: pd.Series, upper_bound=None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    series = series.sort_index().asfreq("D")
    if len(series) < 70 or series.isna().any() or not np.isfinite(series).all():
        raise ValueError("Evaluation needs at least 70 consecutive complete days; gaps are not filled.")
    y = series.to_numpy(float)
    n = len(y)
    val_start, cal_start, test_start = n-42, n-28, n-14
    validation = {m: backtest(y, val_start, cal_start, m, upper_bound) for m in MODELS}
    selected = min(MODELS, key=lambda m: mean_absolute_error(validation[m].actual, validation[m].prediction))
    calibration = backtest(y, cal_start, test_start, selected, upper_bound)
    residuals = np.abs(calibration.actual-calibration.prediction)
    radius = float(np.quantile(residuals, .8, method="higher"))
    metrics, errors = [], []
    for model in MODELS:
        test = backtest(y, test_start, n, model, upper_bound)
        test["model"] = model
        test["date"] = [series.index[int(r.origin+r.horizon-1)] for r in test.itertuples()]
        errors.append(test)
        metrics.append({"model": model, "selected": model == selected,
            "validation_mae": mean_absolute_error(validation[model].actual, validation[model].prediction),
            "mae": mean_absolute_error(test.actual, test.prediction),
            "rmse": np.sqrt(mean_squared_error(test.actual, test.prediction)),
            "interval_coverage": float((np.abs(test.actual-test.prediction) <= radius).mean()) if model==selected else np.nan,
            "train_end": series.index[val_start-1], "validation_end": series.index[cal_start-1],
            "calibration_end": series.index[test_start-1], "test_end": series.index[-1], "test_points": len(test)})
    prediction = predict(y, 7, selected, upper_bound)
    future = pd.DataFrame({"date": pd.date_range(series.index[-1]+pd.Timedelta(days=1), periods=7),
        "prediction": prediction, "lower": np.maximum(0, prediction-radius), "upper": prediction+radius,
        "model": selected, "nominal_coverage": .8, "as_of": series.index[-1]})
    if upper_bound is not None:
        future["upper"] = future.upper.clip(upper=upper_bound)
    return future, pd.DataFrame(metrics), pd.concat(errors, ignore_index=True)
