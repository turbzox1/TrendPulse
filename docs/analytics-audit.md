# Analytics-quality audit

## Corrections

- Report true percentage changes separately from stabilized ranking inputs. A
  positive-from-zero ratio is undefined, not a made-up percentage; zero-to-zero
  is explicitly treated as stable. Undefined source ratios are not silently dropped.
- Relative attention now divides by the actual positive past mean. An index of
  200 really means twice that mean, even for fractional Google interest values.
  Peak ratios, novelty and coefficient of variation likewise use actual denominators,
  with explicit zero cases; changing units no longer changes those relative features.
- Require exact UTC bin alignment and complete optional engagement coverage.
  Weight sentiment by attention, including its two-day aggregation; incomplete
  coverage stays unavailable. Importers must supply mention-weighted sentiment.
- Compare two-day mean attention with its own trailing maximum in lifecycle rules,
  rather than mixing a smoothed numerator with unsmoothed daily peaks.
- Give sustainability its own evidence coverage. Missing engagement quality or
  absence of two growing sources limits heuristic confidence to Low.
- Prevent related-topic correlations from treating multi-day gaps as one-day
  changes; do not recommend negatively correlated topics as similar patterns.
- Reject mixed-cadence propagation comparisons with an explanatory empty state.
  A supported zero lag means co-movement, not that one platform moved first.
- Align SQL growth with the dashboard's adjacent two-day mean comparison. Add
  dates to deterministic insights and flag older scores in the dashboard.
- Replace the synthetic sentiment generator's centered gradient (which used the
  next simulated observation) with a backward change. Analytics never consume
  generator archetype labels as targets or predictors.

## Metric definitions and interview decisions

| Metric | Meaning and decision use |
|---|---|
| Topics tracked / rising | Count of scored topics in the selected period / count classified Emerging or Accelerating, not all collected topics |
| Median momentum | Median over those topics; a prioritization index, not absolute audience demand |
| 48-hour change | Equal-weight mean of per-source relative changes between consecutive two-day means; not a change in summed cross-platform counts |
| Relative attention | Daily native attention divided by that source's expanding prior mean, after seven observed days, times 100 |
| Momentum / component points | Available weighted components normalized to 100; component points sum exactly to total |
| Growing sources / diversity | Sources exceeding 8% stabilized growth / fraction of the fixed two-source universe meeting that threshold |
| Sentiment | Attention-weighted supplied sentiment, -1 to +1; optional in imports and explicitly simulated in demo |
| Unusual changes | Number of flagged observations, not number of independent events or confirmed causes |
| Sustainability evidence | Weighted persistence, low volatility, engagement quality, breadth, repeated attention and acceleration; confidence is heuristic, not a probability |
| Pattern similarity | Positive Pearson correlation of consecutive-day relative-index changes with at least 21 overlapping changes |
| Best lag / correlation / null p | Exploratory maximum positive change correlation over tested shifts, with a shifted-series null; no causal attribution |
| Forecast / MAE / RMSE / coverage | Native-unit future estimate / average absolute error / root mean squared error / fraction of test outcomes inside the selected model's interval |
| Category momentum / complete days | Mean across selected scored topics / count of complete topic-source-days, not unique calendar days |

Momentum weights are **policy choices**, not coefficients learned from outcomes.
Growth (25%) and persistence (20%) emphasize discovery with staying power;
acceleration (15%) detects inflections; novelty (15%) measures renewed attention;
engagement growth and breadth (10% each) add corroboration; sentiment (5%) is a
small positivity preference, not proof of demand. Negative viral events can still
score highly. Correlated components deliberately overlap: the score is not seven
independent statistical tests. Saturation limits extreme tiny-base contributions;
the true percentage remains visible. Missing-factor renormalization changes the
effective weights, so compare coverage and source scope alongside rank.

Lifecycle thresholds are descriptive business rules, not validated universal
boundaries. Peak includes a plateau near a trailing maximum, not a claim that a
future decline is known. Zero activity is not an emerging trend. Sustainability
quality caps at two engagements per mention; this is a documented utility scale,
not an estimated natural threshold. Persistence and repetition overlap across
seven- and 21-day windows. These scores need external outcome validation before
being sold as predictive probabilities.

Anomalies use a preceding median/MAD and a conservative scale floor. This is a
robust screening rule, not a Gaussian p-value, Poisson model, or seasonal adjustment.
Repeated flags during a regime shift are expected. Lead/lag uses differenced log
attention, 40 aligned changes and a 49-draw lag-adjusted circular-shift null.
Autocorrelation, daily cycles, missingness and screening multiple topics limit
interpretation; a common event can move both sources. It cannot explain why a
real-world event occurred.

Forecast selection, interval calibration and final testing use separate chronological
14-day blocks. Each contains two weekly forecast origins; past realized test points
may train a later origin, but a forecast never sees its own targets. Last-value and
weekly seasonal baselines compete with fixed-feature ridge using validation MAE.
The scaler is fitted inside each origin's training data. Final-test errors never
choose the model. Intervals pool 14 calibration residuals across horizons; observed
coverage is reported, and 80% is nominal, not guaranteed under dependence or shocks.
Historical views hide forecasts fitted at the dataset end. Backtests use native
attention, never future-normalized relative indexes.

The synthetic data have stochastic counts, separate source noise, delayed search,
recurrence, nonlinear growth and decaying hype. They are curated demonstrations:
events cluster near the display end, search generally follows Reddit, and quality
is tied to archetypes. A shared latent curve makes propagation easier than in real
data. Changing requested duration changes event timing. This is not evidence of
real-world model accuracy or a sample for tuning the heuristic weights.

Charts answer prioritization (rank and category), timing (attention and lifecycle),
diagnosis (component contributions and anomalies), and planning (native-unit
forecasts with uncertainty) questions. Cross-platform lines show relative intensity,
not audience share. Leader selection is retrospective at the chosen as-of date;
those charts are not historical investment or campaign backtests.

SQL is substantive: normalized observations are joined with optional engagement
and sentiment; keyed tables enforce analytical grain; window functions select
latest metrics and compare baseline errors; date joins enforce calendar growth
windows; the Insights page aggregates the current filtered cohort in SQL.

## Verification

Regression tests cover baseline edge cases, aggregation, calendar gaps, smoothed
peaks, missing sustainability evidence, anomaly drops/zero baselines, mixed cadence,
forecast-origin isolation, SQL/Python parity and synthetic archetypes. Existing
tests cover as-of leakage, known lag recovery, baseline forecasting and all six pages.

Final verification: **60 tests passed**, compilation passed, and the HTTP health
and HTML smoke checks passed. The seed-42 demo database and exported synthetic
observations were rebuilt; README examples were checked against calculated output.
