import numpy as np
import pandas as pd
import pytest
from src.ingestion.synthetic import generate
from src.ingestion.imports import google_csv, reddit_csv
from src.processing.prepare import validate, daily_panel


def test_demo_reproducible_and_valid():
    topics, obs = generate()
    pd.testing.assert_frame_equal(obs, generate()[1])
    assert len(topics) == 18 and len(obs) == 18*2*112*4
    assert len(validate(obs)) == len(obs)
    panel = daily_panel(obs)
    assert len(panel) == 18*2*112
    first = panel[(panel.topic_id == "t00") & (panel.source_id == "reddit")].iloc[0]
    assert first.attention == obs.iloc[:4].attention.sum()
    assert np.isnan(first.attention_index)


def test_duplicate_negative_and_missing_rejected():
    _, obs = generate(days=35)
    with pytest.raises(ValueError, match="Duplicate"):
        validate(pd.concat([obs, obs.iloc[:1]]))
    obs.loc[0, "attention"] = -1
    with pytest.raises(ValueError, match="nonnegative"):
        validate(obs)


def test_partial_days_are_not_zero_filled():
    _, obs = generate(days=35)
    panel = daily_panel(obs.iloc[1:])
    assert len(panel) == 18*2*35-1


def test_reference_is_past_only():
    _, obs = generate(days=35)
    before = daily_panel(obs)
    obs.loc[obs.timestamp >= "2025-02-01", "attention"] = 0
    after = daily_panel(obs)
    pd.testing.assert_frame_equal(before[before.date < "2025-02-01"], after[after.date < "2025-02-01"])


def test_export_adapters(tmp_path):
    google = tmp_path / "google.csv"
    google.write_text("Category: All categories\n\nDay,Example: (Worldwide)\n2025-01-01,<1\n2025-01-02,50\n", encoding="utf-8")
    result = google_csv(google, "example")
    assert result.attention.tolist() == [.5, 50]
    assert not result.is_synthetic.any()
    reddit = tmp_path / "reddit.csv"
    reddit.write_text("timestamp,mentions\n2025-01-01,20\n2025-01-02,40\n", encoding="utf-8")
    assert reddit_csv(reddit, "example").engagements.isna().all()
