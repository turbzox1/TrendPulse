"""Presentation components; values always come from the analytical pipeline."""
from html import escape
import base64
from pathlib import Path
import numpy as np
import streamlit as st
from src.analytics.metrics import format_growth

COLORS = ["#71EBCA", "#83B7FF", "#C2A2FF", "#FFD091", "#FFA3B6", "#8ADBEF"]
CATEGORY_COLORS = {"Wellness":"#71EBCA", "Technology":"#83B7FF", "Culture":"#C2A2FF", "Climate":"#FFD091"}
SOURCE_COLORS = {"Reddit":"#FFD091", "Google Trends":"#83B7FF"}
STAGE_COLORS = {"Emerging":"#83B7FF", "Accelerating":"#71EBCA", "Peak":"#FFD091", "Cooling":"#C2A2FF", "Fading":"#FFA3B6"}
SOURCE_NAMES = {"reddit": "Reddit", "google_trends": "Google Trends"}
NAV = {"Overview": "Home", "Emerging Trends": "Find trends",
       "Trend Explorer": "Topic details", "Cross-Platform Analysis": "Compare sources",
       "Forecasting": "Forecast", "Analytics / Insights": "Insights"}


def styles():
    st.html(f"<style>{Path(__file__).with_name('styles.css').read_text(encoding='utf-8')}</style>")


def brand():
    st.html('<div class="brand"><span class="brand-icon">⌁</span><span>trendpulse<span class="brand-dot">.</span></span></div><div class="brand-sub">Discover. Understand. Anticipate.</div>')


def home_heading():
    st.html('<div class="home-heading"><div class="eyebrow"><span class="heading-mark"></span> YOUR TREND WORKSPACE</div><h1>What’s gaining <em>attention?</em></h1><p>Explore a topic. Understand its growth. See what could come next.</p></div>')


def section(label, description="", tag=""):
    st.html(f'<div class="section-head"><div><h3>{escape(label)}</h3><p>{escape(description)}</p></div><span class="section-tag">{escape(tag)}</span></div>')


def spark(values, color=COLORS[0], height=56):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)][-30:]
    if len(values) < 2:
        return '<div class="spark-empty">Building signal history</div>'
    ys = 5 + (height-10) * (1-(values-values.min()) / max(float(np.ptp(values)), 1))
    xs = np.linspace(0, 260, len(values))
    points = " ".join(f"{x:.1f},{y:.1f}" for x,y in zip(xs,ys))
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-3 0 266 {height}"><polygon points="0,{height} {points} 260,{height}" fill="{color}" opacity=".07"/><polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/><circle cx="260" cy="{ys[-1]:.1f}" r="3" fill="{color}"/></svg>'
    encoded = base64.b64encode(svg.encode()).decode()
    return f'<img class="spark" src="data:image/svg+xml;base64,{encoded}" alt="Recent relative attention history" />'


def header(page, meta, end, window):
    mode = "SYNTHETIC DEMO" if meta["mode"] == "Synthetic demo" else "IMPORTED DATA"
    st.html(f'<div class="topbar"><span>TrendPulse <span class="slash">/</span> <b>{escape(NAV[page])}</b></span><span class="data-pill"><i></i>{mode}</span></div>')
    if page != "Overview":
        descriptions = {"Emerging Trends":"Search and compare topics that are gaining attention.", "Trend Explorer":"Choose a topic, then use the tabs to explore it.",
            "Cross-Platform Analysis":"See whether Reddit or Google search moves first.", "Forecasting":"See the next 1–7 days, including a range of possible outcomes.",
            "Analytics / Insights":"Read the main takeaways and compare categories."}
        st.html(f'<div class="page-heading"><h1>{escape(NAV[page])}</h1><p>{descriptions[page]}</p></div>')
    st.html(f'<div class="context-strip"><span>◷ &nbsp; {end:%d %b %Y}</span><span>Last {window} days</span><span>{"Simulated observations · not live market data" if mode == "SYNTHETIC DEMO" else "User-supplied source exports"}</span></div>')


def topic_card(row, values, rank):
    color = CATEGORY_COLORS.get(row.category, COLORS[0])
    stage_color = STAGE_COLORS.get(row.lifecycle, COLORS[0])
    direction = "positive" if row.growth_rate >= 0 else "negative"
    st.html(f'''<div class="topic-card" style="--accent:{color};--wash:{color}16;--stage:{stage_color};--delay:{(rank-1)*45}ms"><div class="topic-top"><span class="chip"><span class="chip-dot"></span>{escape(row.category)}</span><span class="rank">#{rank:02d}</span></div>
      <h3>{escape(row['name'])}</h3><div class="topic-numbers"><strong>{row.momentum:.0f}<small>/ 100 momentum</small></strong><span class="{direction}">{format_growth(row.growth_rate)}<small> / 48h</small></span></div>
      {spark(values, color)}<div class="topic-bottom"><span class="stage-badge"><i></i>{escape(row.lifecycle)}</span><span>{int(row.active_sources)} growing sources</span></div></div>''')


def brief(text, number):
    st.html(f'<div class="brief"><span class="brief-number">0{number}</span><div><span class="eyebrow">SIGNAL BRIEF</span><p>{escape(text)}</p></div><span class="brief-arrow">↗</span></div>')
