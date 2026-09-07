"""Streamlit entrypoint: streamlit run app/dashboard.py."""
from pathlib import Path
import os
import sys
import logging
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.database.store import DEFAULT_DB, read_database
from src.pipeline import build
from src.processing.exports import spreadsheet_csv
from src.analytics.metrics import compute_metrics, contributions, sustainability_explanation, format_growth
from src.analytics.propagation import lag_analysis
from src.analytics.insights import generate_insights, related_topics
from app.ui import styles, brand, header, home_heading, section, topic_card, brief, COLORS, CATEGORY_COLORS, SOURCE_COLORS, STAGE_COLORS, SOURCE_NAMES, NAV

st.set_page_config(page_title="TrendPulse · Internet Trend Intelligence", page_icon="◉", layout="wide")
PALETTE = COLORS
px.defaults.color_discrete_sequence = PALETTE
styles()


@st.cache_data(show_spinner=False, max_entries=2, ttl=300)
def load(path, modified):
    return read_database(path)


@st.cache_data(show_spinner=False, max_entries=32, ttl=900)
def scoped_metrics(panel):
    return compute_metrics(panel)


@st.cache_data(show_spinner=False, max_entries=64, ttl=900)
def propagation(data):
    return lag_analysis(data)


def chart(fig, height=350):
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, Arial", color="#ADC0DA", size=12), height=height, margin=dict(l=8,r=12,t=12,b=65),
        legend=dict(orientation="h", y=-.22, x=0, title_text="", font=dict(size=11)), hovermode="x unified",
        hoverlabel=dict(bgcolor="#20314B", bordercolor="#6785AA", font_size=13), colorway=PALETTE)
    fig.update_xaxes(showgrid=False, tickfont_size=11, title_font_size=12)
    fig.update_yaxes(gridcolor="rgba(73,100,134,.22)", zeroline=False, tickfont_size=11, title_font_size=12)
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "displayModeBar": "hover", "scrollZoom": False})


def timeline(panel):
    view = panel.rename(columns={"source_id":"Source", "attention_index":"Attention index"})
    view = view.assign(Source=view.Source.map(SOURCE_NAMES))
    fig = px.line(view, x="date", y="Attention index", color="Source", color_discrete_map=SOURCE_COLORS, labels={"date":""})
    fig.update_traces(line_width=2.5)
    chart(fig)
    st.caption("100 means a source's prior average attention; 200 means twice that level. A zero reference is unavailable. These lines compare relative interest, not audience sizes.")
    with st.expander("How is this timeline calculated?"):
        st.write("Each source is compared with its prior expanding daily mean, after seven days of history. Sources receive equal weight. Reddit mentions and Google's 0–100 search index are never added together.")


def show_forecast(topic, sources, data, end, horizon=7):
    available = data["forecasts"]
    available = available[(available.topic_id == topic) & available.source_id.isin(sources)]
    if available.empty:
        st.info("Forecast unavailable. At least 70 consecutive complete days are required.")
        status = data["forecast_status"]
        st.dataframe(status[(status.topic_id == topic) & status.source_id.isin(sources)], hide_index=True)
        return
    if end != pd.Timestamp(data["daily_attention"].date.max()):
        st.info("Forecasts are fitted at the dataset's latest date. Set As of to the latest date to view them; future-fitted forecasts are hidden in historical views.")
        st.button("Use the latest data", key="latest_forecast", on_click=lambda: st.session_state.update(filter_date=data["daily_attention"].date.max().date()))
        return
    available = available[pd.to_datetime(available.as_of) == end]
    if available.empty:
        st.info("This topic's forecast is stale relative to the selected date. Import current complete observations and rebuild to refresh it.")
        return
    source = st.selectbox("Forecast source", sorted(available.source_id.unique()), key="forecast_source", format_func=SOURCE_NAMES.get)
    f = available[available.source_id == source].head(horizon)
    history = data["daily_attention"]
    history = history[(history.topic_id == topic) & (history.source_id == source)].tail(35)
    unit = "Daily mentions" if source == "reddit" else "Search interest (0–100)"
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=history.date, y=history.attention, name="Observed", line=dict(color=PALETTE[0])))
    fig.add_trace(go.Scatter(x=f.date, y=f.upper, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=f.date, y=f.lower, fill="tonexty", fillcolor="rgba(141,158,255,.18)", mode="lines", line=dict(width=0), name="Nominal 80% interval"))
    fig.add_trace(go.Scatter(x=f.date, y=f.prediction, name=f.model.iloc[0], line=dict(color=PALETTE[1], dash="dash")))
    fig.update_yaxes(title=unit)
    chart(fig)
    evaluation = data["forecast_evaluation"]
    evaluation = evaluation[(evaluation.topic_id == topic) & (evaluation.source_id == source)]
    selected = evaluation[evaluation.selected].iloc[0]
    st.write(f"The dashed line is the forecast. The shaded band shows an approximate 80% range; sharp spikes may fall outside it.")
    st.caption(f"Model: {selected.model} · Average test error: {selected.mae:.1f} {unit.lower()} · Lower errors are better.")
    with st.expander("Model comparison, accuracy and assumptions"):
        st.write("MAE is the average size of the prediction error. RMSE gives more weight to large errors. Coverage is the fraction of test observations inside the forecast range. The selected model was chosen before the final test.")
        st.dataframe(evaluation[["model","selected","validation_mae","mae","rmse","interval_coverage"]], hide_index=True,
            column_config={"mae":st.column_config.NumberColumn("Test MAE", format="%.2f"),
                "rmse":st.column_config.NumberColumn("Test RMSE", format="%.2f"),
                "validation_mae":st.column_config.NumberColumn("Validation MAE", format="%.2f"),
                "interval_coverage":st.column_config.NumberColumn("Test interval coverage", format="%.2f")})
        st.caption(f"Selected on validation MAE; final test: 14 daily predictions in two rolling 7-day blocks. Units: {unit.lower()}. Train through {selected.train_end:%d %b}; validation through {selected.validation_end:%d %b}; calibration through {selected.calibration_end:%d %b}; test through {selected.test_end:%d %b %Y}.")
        st.caption("Intervals use 14 held-out calibration residuals pooled across horizons. Coverage can deteriorate during spikes; these are approximate empirical intervals, not guaranteed bounds. Final forecasts refit on all available history.")


def open_topic(topic):
    st.session_state.workspace = "Trend Explorer"
    st.session_state.topic_picker = topic


def go_to(page):
    st.session_state.workspace = page


def reset_filters(categories, latest_date):
    st.session_state.filter_categories = list(categories)
    st.session_state.filter_sources = list(SOURCE_NAMES)
    st.session_state.filter_date = latest_date
    st.session_state.filter_window = 30


def topic_link(rows, key):
    """Searchable topic selector and a clearly labeled action."""
    names = rows.set_index("topic_id").name.to_dict()
    search, action = st.columns([4,1.3], vertical_alignment="bottom")
    with search:
        selected = st.selectbox("Search or choose a topic", rows.topic_id.tolist(), format_func=names.get,
            key=key, help="Click this field and type a topic name to find it.")
    with action:
        st.button("View topic details", key=f"{key}_open", type="primary", width="stretch", on_click=open_topic, args=(selected,))


def main():
    path = Path(os.environ.get("TRENDPULSE_DB", str(DEFAULT_DB)))
    if not path.exists():
        if "TRENDPULSE_DB" in os.environ:
            st.error("The database selected by TRENDPULSE_DB does not exist. Build it with python -m src.pipeline --db <path>.")
            return
        with st.spinner("Building the reproducible demo dataset and benchmarking forecasts…"):
            build(path)
    data = load(str(path), path.stat().st_mtime_ns)
    topics, all_panel = data["topics"], data["daily_attention"]
    meta = data["dataset_metadata"].iloc[0]
    with st.sidebar:
        brand()
        st.markdown('<div class="eyebrow">WORKSPACE</div>', unsafe_allow_html=True)
        page = st.radio("Workspace", list(NAV), label_visibility="collapsed", key="workspace", format_func=NAV.get)
        st.divider()
        window = st.selectbox("Time period", [14, 30, 60, 112], index=1, format_func=lambda d:f"Last {d} days", key="filter_window")
        with st.expander("Filter by category, source or date"):
            st.caption("These filters apply to every page. Forecasts use the most recent complete data.")
            asof = st.date_input("As of", value=all_panel.date.max().date(), min_value=all_panel.date.min().date(), max_value=all_panel.date.max().date(), key="filter_date")
            categories = st.multiselect("Category", sorted(topics.category.unique()), default=sorted(topics.category.unique()), key="filter_categories")
            sources = st.multiselect("Source", list(SOURCE_NAMES), default=list(SOURCE_NAMES), format_func=SOURCE_NAMES.get, key="filter_sources")
        st.button("Reset filters", key="reset_filters", on_click=reset_filters, args=(sorted(topics.category.unique()), all_panel.date.max().date()), width="stretch")
        with st.expander("What do the numbers mean?"):
            st.markdown("**Momentum:** strength of recent attention growth, scored 0–100. It is not a probability.\n\n**48-hour change:** the latest two-day average compared with the previous two days.\n\n**Stage:** Emerging → Accelerating → Peak → Cooling → Fading. A topic can revisit stages.\n\n**Unusual changes:** observations far from the recent baseline.\n\n**Sustainability:** evidence that attention may last, with a Low or Medium confidence label.\n\n**Sentiment:** −1 is negative, 0 neutral, +1 positive.\n\n**Forecast range:** an approximate uncertainty interval, not a guarantee.")
        st.divider()
        st.caption(f"{meta['mode']} · {int(meta.observation_count):,} observations")
        st.caption(f"Coverage: {meta['start']:%d %b} – {meta['end']:%d %b %Y} · UTC")
    header(page, meta, pd.Timestamp(asof), window)
    if len(categories) != topics.category.nunique() or len(sources) != 2 or pd.Timestamp(asof) != all_panel.date.max():
        st.caption(f"Filters active: {', '.join(categories) or 'no categories'} · {', '.join(SOURCE_NAMES[s] for s in sources) or 'no sources'} · through {asof:%d %b %Y}. Use Reset filters in the sidebar to start over.")
    if not categories or not sources:
        st.info("Choose at least one category and source to explore trends.")
        return
    end = pd.Timestamp(asof)
    start = end-pd.Timedelta(days=window-1)
    ids = topics[topics.category.isin(categories)].topic_id
    history = all_panel[all_panel.topic_id.isin(ids) & all_panel.source_id.isin(sources) & (all_panel.date <= end)]
    if history.empty:
        st.info("No observations match these filters.")
        return
    panel = history[history.date >= start]
    metrics = scoped_metrics(history)
    if metrics.empty:
        st.info("Not enough history for trend scoring. Move As of later; scoring needs approximately 23 complete days.")
        return
    latest = metrics.sort_values("date").groupby("topic_id").tail(1).merge(topics, on="topic_id")
    latest = latest[latest.date >= start].sort_values("momentum", ascending=False)
    if latest.empty:
        st.info("No scored trends in the selected period.")
        return
    if (latest.date < end).any():
        st.caption("Some topics have older scores because recent observations are incomplete. Check each topic's scored-as-of date before comparing.")
    observations = data["observation_detail"]
    observations = observations[observations.topic_id.isin(ids) & observations.source_id.isin(sources) & (observations.timestamp < end+pd.Timedelta(days=1)) & (observations.timestamp >= start)]
    anomalies = data["anomalies"]
    anomalies = anomalies[anomalies.topic_id.isin(ids) & anomalies.source_id.isin(sources) & (anomalies.timestamp >= start) & (anomalies.timestamp < end+pd.Timedelta(days=1))]

    if page == "Overview":
        home_heading()
        with st.container(border=True, key="home_search"):
            topic_link(latest, "home_topic")
        section("Or start with one of these topics", "Highest momentum in your selected sources and time period.")
        for rank, (col, (_, row)) in enumerate(zip(st.columns(3), latest.head(3).iterrows()), 1):
            with col:
                values = panel[panel.topic_id.eq(row.topic_id)].groupby("date").attention_index.mean()
                topic_card(row, values, rank)
                st.button(f"View {row['name']}", key=f"open_{row.topic_id}", width="stretch", on_click=open_topic, args=(row.topic_id,))
        with st.expander("How to read these cards"):
            st.write("Momentum is a 0–100 score of recent growth, not total popularity. The percentage compares two-day averages. The small line shows recent attention, and the stage describes whether the topic is growing, peaking or fading.")
        section("At a glance")
        cols = st.columns(4)
        cols[0].metric("Topics tracked", len(latest))
        cols[1].metric("Rising topics", int(latest.lifecycle.isin(["Emerging","Accelerating"]).sum()))
        cols[2].metric("Median momentum", f"{latest.momentum.median():.0f}/100")
        cols[3].metric("Unusual changes", len(anomalies), help="Observations that differ sharply from their recent baseline. Open a topic's Sources & spikes tab to investigate.")
        comparison = st.expander("Compare attention and momentum across topics")
        left, right = comparison.columns([1.7,1], gap="medium")
        with left:
            with st.container(border=True):
                section("Attention in motion", "Relative attention across your leading topics", f"{window} DAYS")
                leaders = latest.head(4).topic_id
                v = panel[panel.topic_id.isin(leaders)].groupby(["date","topic_id"]).attention_index.mean().reset_index().merge(topics, on="topic_id")
                topic_colors = {r['name']:CATEGORY_COLORS.get(r['category'], COLORS[0]) for _, r in topics.iterrows()}
                fig = px.line(v, x="date", y="attention_index", color="name", color_discrete_map=topic_colors, labels={"date":"", "attention_index":"Attention index"})
                fig.update_traces(line_width=2.6)
                chart(fig, 310)
                st.caption("100 = prior source mean · equal source weights · not audience share")
        with right:
            with st.container(border=True):
                section("The momentum list", "Ranked by change, not just popularity", "TOP 5")
                v = latest.head(5).sort_values("momentum")
                fig = px.bar(v, x="momentum", y="name", orientation="h", text="momentum", color="momentum", color_continuous_scale=["#3A6483", "#71EBCA"], range_x=[0,103], labels={"name":"","momentum":"Momentum / 100"})
                fig.update_traces(texttemplate="%{text:.0f}", textposition="outside", width=.38, marker_cornerradius=4)
                fig.update_layout(coloraxis_showscale=False)
                chart(fig,310)
                st.caption("Explainable score · 7 contributing factors · 0–100")
        with st.expander("Read the main takeaways"):
            for i, insight in enumerate(generate_insights(latest, topics)[:3], 1):
                brief(insight, i)

    elif page == "Emerging Trends":
        query = st.text_input("Search topics", placeholder="For example, batteries or walking", key="trend_search")
        with st.expander("Choose trend stages", expanded=False):
            stage = st.multiselect("Lifecycle stage", ["Emerging","Accelerating","Peak","Cooling","Fading"], default=["Emerging","Accelerating"])
            st.caption("Emerging and Accelerating show growing topics. Add other stages to include peaks and declines.")
        ranking = latest[latest.lifecycle.isin(stage) & latest.name.str.contains(query, case=False, regex=False)].copy()
        st.caption(f"{len(ranking)} results · stages: {', '.join(stage) or 'none'} · sorted by momentum")
        if ranking.empty:
            st.info("No matching topics. Try a shorter search, choose more stages, or reset the sidebar filters.")
        else:
            ranking["growth_pct"] = ranking.growth_rate * 100
            st.dataframe(ranking[["name","category","momentum","growth_pct","lifecycle","sustainability","confidence","date"]], hide_index=True,
                column_config={"momentum":st.column_config.ProgressColumn("Momentum", min_value=0, max_value=100, format="%.0f"),
                    "growth_pct":st.column_config.NumberColumn("48-hour change",format="%+.0f%%"), "name":"Topic", "lifecycle":"Stage", "date":"Scored as of"}, width="stretch")
            topic_link(ranking, "result_topic")
            st.download_button("Download ranked signals", spreadsheet_csv(ranking), "trendpulse_ranking.csv", "text/csv")
            with st.expander("Compare growth and momentum on a chart"):
                chart(px.scatter(ranking, x="growth_pct", y="momentum", color="category", color_discrete_map=CATEGORY_COLORS, hover_name="name", size="sustainability_score", size_max=35,
                    labels={"growth_pct":"48-hour change (%)","momentum":"Momentum / 100"}))
        st.caption("Percentages use true source ratios; positive growth from zero is N/A. Small baselines can produce large percentages. Ranking and lifecycle stabilize denominators at one native unit; peak position compares two-day means.")

    elif page in ["Trend Explorer", "Cross-Platform Analysis", "Forecasting"]:
        names = topics.set_index("topic_id").name.to_dict()
        if st.session_state.get("topic_picker") not in latest.topic_id.tolist():
            st.session_state.topic_picker = latest.topic_id.iloc[0]
        topic = st.selectbox("Select a topic", latest.topic_id.tolist(), format_func=lambda t:names[t], key="topic_picker")
        row = latest[latest.topic_id == topic].iloc[0]
        selected_panel = panel[panel.topic_id == topic]
        if page == "Trend Explorer":
            cols = st.columns(4)
            cols[0].metric("Momentum", f"{row.momentum:.0f}/100", help="How strongly attention is growing. The Why it's moving tab shows every component. This is not a probability.")
            cols[1].metric("48-hour change", format_growth(row.growth_rate), help="Mean source percentage change between two-day windows. Positive growth from a zero baseline is undefined; zero-to-zero is treated as no change.")
            cols[2].metric("Stage", row.lifecycle, help="The topic's current position in its growth and decline cycle.")
            cols[3].metric("Sentiment", f"{row.sentiment:+.2f}" if pd.notna(row.sentiment) else "Unavailable", help="−1 is negative; 0 neutral; +1 positive. No score is inferred when sentiment is missing.")
            st.caption(f"Metrics as of {row.date:%d %b %Y}. Sentiment is on −1 to +1; simulated in demo and optional in imports.")
            summary, reasons, evidence, future, related_tab = st.tabs(["Summary", "Why it's moving", "Sources & spikes", "Forecast", "Related topics"])
            with summary:
                st.subheader("How attention is changing")
                timeline(selected_panel)
                st.subheader("Is this likely to last?")
                st.write(f"**{row.sustainability}** · {row.confidence.lower()} confidence")
                st.caption("An assessment from the available signals, not a guaranteed outcome.")
                with st.expander("See sustainability score and evidence"):
                    st.metric("Sustainability evidence", f"{row.sustainability_score:.0f}/100")
                    st.write(sustainability_explanation(row))
                    st.caption("Evidence combines persistence, volatility, engagement per mention, source breadth, repeated attention and acceleration. It is not trained on future outcomes.")
                with st.expander("See how the trend stage has changed"):
                    st.caption("Stages can repeat or be skipped. Emerging → Accelerating → Peak → Cooling → Fading.")
                    trail = metrics[(metrics.topic_id == topic) & (metrics.date >= start)]
                    chart(px.scatter(trail, x="date", y="lifecycle", color="lifecycle", color_discrete_map=STAGE_COLORS, hover_data=["momentum","growth_rate"], category_orders={"lifecycle":["Emerging","Accelerating","Peak","Cooling","Fading"]}),260)
            with reasons:
                st.subheader("Inside the momentum score")
                st.write("Longer bars contribute more points. Together, these add up to the momentum score above.")
                c = contributions(row)
                chart(px.bar(c, y="component", x="points", orientation="h", color="factor_score", color_continuous_scale=["#3A6483", "#71EBCA"], labels={"component":"","points":"Points contributed"}),350)
                st.caption(f"Available evidence weight: {row.evidence_coverage:.0%}. Missing factors are excluded and remaining weights renormalized.")
                with st.expander("What each component measures"):
                    st.write("Growth: how fast attention is rising. Acceleration: whether growth is speeding up. Engagement growth: change in engagement per mention. Diversity: how many sources are growing. Persistence: how often attention stays above its baseline. Sentiment movement: change in sentiment. Novelty: renewed attention compared with recent history.")
                    st.dataframe(c, hide_index=True)
            with evidence:
                st.subheader("Where attention is coming from")
                source_view = selected_panel.sort_values("date").groupby("source_id").tail(1).copy()
                source_view["source_id"] = source_view.source_id.map(SOURCE_NAMES)
                st.dataframe(source_view[["source_id","date","attention","attention_index","engagements"]], hide_index=True,
                    column_config={"source_id":"Source", "attention":"Daily attention", "attention_index":"Relative attention", "engagements":"Engagements", "date":"Date"})
                st.caption("Reddit: daily mentions. Google: daily mean search interest (0–100). These are different units and cannot be added together.")
                st.button("See which source moved first", key="compare_topic", on_click=go_to, args=("Cross-Platform Analysis",))
                st.subheader("Unusual attention changes")
                st.caption("Spikes and drops compared with the recent baseline. Contributing signals are associations, not proven causes.")
                a = anomalies[anomalies.topic_id == topic].sort_values("timestamp", ascending=False)
                if a.empty:
                    st.info("No unusual deviations exceeded the anomaly threshold in this window.")
                else:
                    st.dataframe(a.drop(columns="topic_id"), hide_index=True,
                        column_config={"timestamp":"When", "source_id":"Source", "magnitude":st.column_config.NumberColumn("Change in native units", format="%.1f"),
                            "baseline":st.column_config.NumberColumn("Usual level", format="%.1f"), "pct_change":st.column_config.NumberColumn("Change (%)", format="%.0f"),
                            "robust_z":st.column_config.NumberColumn("Anomaly score", format="%.1f"), "signals":"Contributing signals"})
            with future:
                horizon = st.slider("Forecast horizon (days)", 1, 7, 7, key="detail_horizon")
                show_forecast(topic, sources, data, end, horizon)
            with related_tab:
                st.subheader("Topics with similar attention patterns")
                related = related_topics(panel, topic).merge(topics, on="topic_id")
                if related.empty:
                    st.info("Not enough shared history to find related patterns. Try a longer time period.")
                else:
                    st.dataframe(related[["name","category","correlation"]], hide_index=True,
                        column_config={"name":"Topic", "category":"Category", "correlation":st.column_config.NumberColumn("Pattern similarity", format="%.2f")})
                    topic_link(related, "related_topic")
                st.caption("Similarity compares changes in attention across at least 21 overlapping days. It does not mean the topics share a cause or meaning.")
        elif page == "Cross-Platform Analysis":
            if len(sources) < 2:
                st.info("Select both sources to examine propagation.")
                st.button("Use both sources", on_click=lambda: st.session_state.update(filter_sources=list(SOURCE_NAMES)), key="both_sources")
                return
            timeline(selected_panel)
            with st.spinner("Comparing time-shifted attention changes…"):
                lags, summary = propagation(observations[observations.topic_id == topic])
            st.subheader(("Sources appear to move together" if summary.get("lag_hours") == 0 else "One source appears to move first") if summary.get("supported") else "No clear evidence of a leading source")
            if summary["lag_hours"] is None:
                st.info(summary["status"])
            if summary["lag_hours"] is not None:
                with st.expander("See comparison statistics"):
                    cols = st.columns(3)
                    cols[0].metric("Best lag", f"{summary['lag_hours']:+.0f} hours", help="Positive means Reddit leads; negative means Google search leads. A best match alone does not establish a reliable relationship.")
                    cols[1].metric("Change correlation", f"{summary['correlation']:.2f}", help="Similarity of attention changes, from −1 to +1.")
                    cols[2].metric("Exploratory null p", f"{summary['p_value']:.2f}", help="How often randomly shifted data produced an equally strong match. This is exploratory, not causal proof.")
                if summary.get("supported"):
                    lag = summary["lag_hours"]
                    direction = "Reddit preceded search" if lag>0 else "Search preceded Reddit" if lag<0 else "Both sources moved together"
                    st.info(f"{direction}{f' by approximately {abs(lag):.0f} hours' if lag else ''} within this window. This is an association, not evidence of influence.")
                chart(px.bar(lags, x="lag_hours", y="correlation", labels={"lag_hours":"Lag in hours · positive = Reddit leads","correlation":"Correlation of log attention changes"}))
            with st.expander("How to interpret the comparison"):
                st.write("A positive lag means Reddit changed first; a negative lag means Google search changed first. Correlation measures how similarly changes move. A low p-value provides exploratory evidence against a chance alignment, not proof that one source caused the other.")
                st.caption("Searches ±8 observation bins using differenced log attention; at least 40 aligned changes per lag. Circular-shift null (49 draws) compares the maximum across lags. Signals require r ≥ 0.25 and exploratory p ≤ 0.10. This exploratory screen is not corrected across topics. Shared events, sampling and daily cycles can create spurious lead/lag relationships.")
        else:
            horizon = st.slider("Forecast horizon (days)", 1, 7, 7)
            show_forecast(topic, sources, data, end, horizon)

    else:
        st.subheader("Calculated insights")
        for i, insight in enumerate(generate_insights(latest, topics), 1):
            brief(insight, i)
        st.subheader("Where momentum is concentrated")
        with duckdb.connect() as con:
            con.register("selected_trends", latest)
            categories_sql = con.execute("""SELECT category, COUNT(*) AS topics,
                ROUND(AVG(momentum), 1) AS mean_momentum,
                COUNT(*) FILTER (WHERE lifecycle IN ('Emerging', 'Accelerating')) AS rising
                FROM selected_trends GROUP BY category ORDER BY mean_momentum DESC""").df()
        chart(px.bar(categories_sql, x="category", y="mean_momentum", color="category", color_discrete_map=CATEGORY_COLORS, range_y=[0,100], labels={"category":"","mean_momentum":"Mean momentum"}))
        st.dataframe(categories_sql, hide_index=True)
        with st.expander("Methodology & decision guidance"):
            st.write("Use rising, persistent, multi-source topics to prioritize research or content experiments. Cooling spikes can flag campaign timing risk. Verify the underlying context before acting; the app has no event/news corpus with which to establish why a spike happened.")
            st.write("48-hour growth compares two complete daily averages with the preceding two days within each source, then averages source ratios. Historical data before the display window are retained for warm-up. Source filters recompute momentum and lifecycle. Forecasts always use a single source in native units.")
            st.code((ROOT / "src/database/views.sql").read_text(), language="sql")
        st.subheader("Data quality & coverage")
        st.dataframe(history.groupby("source_id").agg(complete_days=("date","size"), topics=("topic_id","nunique"), first_day=("date","min"), last_day=("date","max")), width="stretch")
        st.caption("Complete days counts topic-source-days. Missing observations are never silently replaced by zeros. Imports with gaps remain visible but cannot produce a forecast until there are 70 consecutive complete days.")
    st.markdown('<div class="footer"><strong>trendpulse. / Evidence over noise</strong><span>Built for the curious. Grounded in data.</span></div>', unsafe_allow_html=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, duckdb.Error) as exc:
        logging.error("Dashboard data error (%s); verify the dataset locally.", type(exc).__name__)
        st.error("Unable to load this dataset. Ask the operator to check or rebuild the data.")
        st.caption("Check the data format and database path, or rebuild the demo with python -m src.pipeline.")
