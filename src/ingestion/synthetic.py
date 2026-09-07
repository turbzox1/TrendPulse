"""Fictional topic trajectories with known shapes and delayed search responses."""
import numpy as np
import pandas as pd

TOPICS = [
    ("Local AI assistants", "Technology", "organic"),
    ("Sodium-ion batteries", "Technology", "gradual"),
    ("Pocket projectors", "Technology", "viral"),
    ("Spatial workspaces", "Technology", "hype"),
    ("Repairable phones", "Technology", "emerging"),
    ("Micro workouts", "Wellness", "organic"),
    ("Sleep tourism", "Wellness", "gradual"),
    ("Protein soda", "Wellness", "hype"),
    ("Sunday meal prep", "Wellness", "recurring"),
    ("Walking clubs", "Wellness", "emerging"),
    ("Balcony solar", "Climate", "organic"),
    ("Refill stores", "Climate", "gradual"),
    ("Algae packaging", "Climate", "viral"),
    ("Night trains", "Culture", "organic"),
    ("Analog photography", "Culture", "recurring"),
    ("Tiny desk setups", "Culture", "hype"),
    ("Cozy strategy games", "Culture", "viral"),
    ("Community kitchens", "Culture", "emerging"),
]


def generate(seed: int = 42, days: int = 112) -> tuple[pd.DataFrame, pd.DataFrame]:
    if days < 35:
        raise ValueError("Generate at least 35 days for meaningful history.")
    rng = np.random.default_rng(seed)
    stamps = pd.date_range("2025-01-01", periods=days * 4, freq="6h")
    x = np.arange(len(stamps)) / 4
    topics, frames = [], []
    for i, (name, category, kind) in enumerate(TOPICS):
        topic = f"t{i:02d}"
        topics.append((topic, name, category, "synthetic"))
        shift = (i % 3) * 0.8
        def curve(t):
            base = 7 + i % 5
            if kind == "organic":
                return base + 95 / (1 + np.exp(-(t - days + 8 + shift) / 3.5))
            if kind == "gradual":
                return base + 0.002 * t ** 2 + 1.2 * np.maximum(t - days + 16, 0)
            if kind == "viral":
                return base + 165 * np.exp(-0.5 * ((t - days + 2 + shift) / 1.3) ** 2)
            if kind == "hype":
                return base + 150 * np.exp(-0.5 * ((t - days + 9 + shift) / 1.7) ** 2)
            if kind == "emerging":
                return base + 9 * np.maximum(t - days + 3 + shift, 0) ** 1.7
            return base + 32 * (1 + np.cos(2 * np.pi * (t + shift) / 7)) ** 3 / 8
        for source, lag in [("reddit", 0), ("google_trends", 1 + i % 4)]:
            t = x - lag / 4
            signal = curve(t) * (1 + 0.12 * np.sin(2 * np.pi * t))
            if source == "reddit":
                attention = rng.poisson(np.maximum(signal * 2, 0.1)).astype(float)
                quality = 1.5 if kind in ("organic", "gradual", "emerging") else 0.65
                engagements = rng.poisson(attention * quality)
                sentiment = np.clip(0.15 + 0.2 * np.tanh(np.diff(signal, prepend=signal[0])) + rng.normal(0, .12, len(x)), -1, 1)
            else:
                # Fixed scale for this simulated export; never a global search count.
                attention = np.clip(signal * 0.42 + rng.normal(0, 1.3, len(x)), 0, 100).round(1)
                engagements = np.full(len(x), np.nan)
                sentiment = np.full(len(x), np.nan)
            frames.append(pd.DataFrame({"topic_id": topic, "source_id": source,
                "timestamp": stamps, "attention": attention, "engagements": engagements,
                "sentiment": sentiment, "is_synthetic": True}))
    return pd.DataFrame(topics, columns=["topic_id", "name", "category", "provenance"]), pd.concat(frames, ignore_index=True)
