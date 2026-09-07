CREATE VIEW observation_detail AS
SELECT o.*, e.engagements, s.sentiment
FROM observations o
LEFT JOIN engagement e USING (observation_id)
LEFT JOIN sentiment s USING (observation_id);

CREATE VIEW latest_trends AS
SELECT m.*, t.name, t.category
FROM trend_metrics m JOIN topics t USING (topic_id)
QUALIFY ROW_NUMBER() OVER (PARTITION BY topic_id ORDER BY date DESC) = 1;

CREATE VIEW category_summary AS
SELECT category, COUNT(*) AS topic_count, ROUND(AVG(momentum), 1) AS mean_momentum,
       COUNT(*) FILTER (WHERE lifecycle IN ('Emerging', 'Accelerating')) AS rising_topics
FROM latest_trends GROUP BY category;

CREATE VIEW source_daily_growth AS
WITH windows AS (
    SELECT c.topic_id, c.source_id, c.date, c.attention,
           (c.attention + d1.attention) / 2 AS recent_mean,
           (d2.attention + d3.attention) / 2 AS previous_mean
    FROM daily_attention c
    LEFT JOIN daily_attention d1 ON c.topic_id = d1.topic_id AND c.source_id = d1.source_id
        AND d1.date = c.date - INTERVAL '1 day'
    LEFT JOIN daily_attention d2 ON c.topic_id = d2.topic_id AND c.source_id = d2.source_id
        AND d2.date = c.date - INTERVAL '2 days'
    LEFT JOIN daily_attention d3 ON c.topic_id = d3.topic_id AND c.source_id = d3.source_id
        AND d3.date = c.date - INTERVAL '3 days'
)
SELECT topic_id, source_id, date, attention,
       CASE WHEN recent_mean = 0 AND previous_mean = 0 THEN 0
            ELSE recent_mean / NULLIF(previous_mean, 0) - 1 END AS growth_two_days
FROM windows;

CREATE VIEW forecast_comparison AS
SELECT topic_id, source_id, model, selected, mae, rmse, interval_coverage,
       1 - mae / NULLIF(MAX(CASE WHEN model = 'Last value' THEN mae END)
           OVER (PARTITION BY topic_id, source_id), 0) AS improvement_over_last_value
FROM forecast_evaluation;
