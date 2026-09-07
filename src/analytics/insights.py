import pandas as pd
from src.analytics.metrics import format_growth


def generate_insights(latest: pd.DataFrame, topics: pd.DataFrame) -> list[str]:
    names = topics.set_index("topic_id").name.to_dict()
    result = []
    for row in latest.sort_values("momentum", ascending=False).head(4).itertuples():
        result.append(f"{names.get(row.topic_id, row.topic_id)}: 48-hour change {format_growth(row.growth_rate)} "
            f"(two-day mean versus preceding two days), with momentum {row.momentum:.0f}/100. "
            f"{int(row.active_sources)} source(s) exceed 8% stabilized growth; lifecycle: {row.lifecycle.lower()}. "
            f"Scored as of {row.date:%Y-%m-%d}.")
    return result


def related_topics(panel: pd.DataFrame, topic_id: str) -> pd.DataFrame:
    wide = panel.groupby(["date", "topic_id"]).attention_index.mean().unstack()
    if topic_id not in wide:
        return pd.DataFrame(columns=["topic_id", "correlation"])
    wide = wide.reindex(pd.date_range(wide.index.min(), wide.index.max(), freq="D"))
    changes = wide.diff()
    corr = changes.corr(min_periods=21)[topic_id].drop(topic_id).dropna()
    corr = corr[corr > 0].sort_values(ascending=False).head(5)
    return corr.rename("correlation").rename_axis("topic_id").reset_index()
