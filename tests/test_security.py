"""Regression checks for actual import, export, storage and public UI boundaries."""
from io import StringIO
from pathlib import Path
import json
import logging
import shutil
import subprocess
import tomllib

import duckdb
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.ingestion.files import read_local_text, manifest_file
from src.ingestion import imports
from src.pipeline import load_manifest
from src.processing.exports import spreadsheet_csv
from src.database.store import read_database, write_database

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("path", ["https://example.invalid/input.csv", "file:///etc/passwd", "//server/share/input.csv", "\\\\server\\share\\input.csv"])
def test_import_never_delegates_urls_or_shares_to_pandas(path, monkeypatch):
    monkeypatch.setattr(pd, "read_csv", lambda *a, **k: pytest.fail("Network-capable CSV parser was reached"))
    with pytest.raises(ValueError, match="local files"):
        imports.reddit_csv(path, "example")


@pytest.mark.parametrize("value", ["../outside.csv", "nested/../../outside.csv", "..\\outside.csv", "/outside.csv", "C:\\outside.csv", "C:outside.csv", "\\\\server\\share\\x.csv", "https://example.invalid/x.csv"])
def test_manifest_cannot_escape_its_directory(tmp_path, value):
    with pytest.raises(ValueError, match="relative|escapes"):
        manifest_file(tmp_path, value)
    assert manifest_file(tmp_path, "nested/ok.csv") == tmp_path / "nested" / "ok.csv"


def test_local_file_size_type_and_content_limits(tmp_path):
    source = tmp_path / "input.csv"
    source.write_bytes(b"123456789")
    with pytest.raises(ValueError, match="size limit"):
        read_local_text(source, ".csv", 8)
    wrong_type = tmp_path / "input.pkl"
    wrong_type.write_bytes(b"plain text")
    with pytest.raises(ValueError, match="uncompressed .csv"):
        imports.reddit_csv(wrong_type, "example")
    source.write_bytes(b"x\x00y")
    with pytest.raises(ValueError, match="Binary"):
        read_local_text(source, ".csv", 10)
    source.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="UTF-8"):
        read_local_text(source, ".csv", 10)


def test_csv_row_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(imports, "MAX_ROWS", 1)
    source = tmp_path / "input.csv"
    source.write_text("timestamp,mentions\n2025-01-01,1\n2025-01-02,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="row limit"):
        imports.reddit_csv(source, "example")


@pytest.mark.parametrize("document", [[], {"topics":"bad"}, {"topics":[{}]}, {"topics":[{"topic_id":"x", "name":"X", "category":"Y", "google_column":[]}]}])
def test_manifest_schema_is_checked(tmp_path, document):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError):
        load_manifest(path)


def test_csv_formulas_are_literal_without_changing_numeric_values():
    payloads = ["=1+1", "+1+1", "-1+1", "@SUM(1)", " \t=1+1", "\r\n=1+1", "Normal topic"]
    frame = pd.DataFrame({"name":payloads, "growth":[-.25]*len(payloads)})
    exported = pd.read_csv(StringIO(spreadsheet_csv(frame)))
    assert exported.name.tolist() == ["'"+p for p in payloads[:-1]] + ["Normal topic"]
    assert exported.growth.tolist() == [-.25]*len(payloads)
    assert frame.name.tolist() == payloads


def test_database_views_cannot_read_external_files(tmp_path):
    external = tmp_path / "private.csv"
    external.write_text("value\nprivate-information\n", encoding="utf-8")
    db = tmp_path / "external.duckdb"
    with duckdb.connect(str(db)) as con:
        con.read_csv(str(external)).create_view("topics")
    with pytest.raises(duckdb.Error, match="disabled"):
        read_database(db)


def test_unique_staging_and_failed_transaction_preserve_existing_files(demo_db, tmp_path):
    data = read_database(demo_db)
    frames = {name:data[name] for name in ["daily_attention", "trend_metrics", "anomalies", "forecasts", "forecast_evaluation", "forecast_errors", "forecast_status"]}
    destination = tmp_path / "output.duckdb"
    other_staging = destination.with_suffix(".building.duckdb")
    other_staging.write_bytes(b"belongs-to-another-writer")
    write_database(destination, data["topics"], data["observation_detail"], frames, data["dataset_metadata"].iloc[0].to_dict())
    assert other_staging.read_bytes() == b"belongs-to-another-writer"
    before = destination.read_bytes()
    duplicate_topics = pd.concat([data["topics"], data["topics"].iloc[:1]])
    with pytest.raises(duckdb.ConstraintException):
        write_database(destination, duplicate_topics, data["observation_detail"], frames, {})
    assert destination.read_bytes() == before
    assert not list(tmp_path.glob(".trendpulse-*"))


def test_browser_errors_do_not_disclose_paths_or_data(tmp_path, monkeypatch, caplog):
    db = tmp_path / "private-client-name.duckdb"
    db.write_bytes(b"not a database")
    monkeypatch.setenv("TRENDPULSE_DB", str(db))
    with caplog.at_level(logging.ERROR):
        app = AppTest.from_file(str(ROOT / "app/dashboard.py"), default_timeout=30).run()
    assert not app.exception and len(app.error) == 1
    assert "Unable to load" in app.error[0].value
    assert "private-client-name" not in app.error[0].value + caplog.text
    assert str(tmp_path) not in app.error[0].value + caplog.text


def test_gitignore_protects_secrets_but_keeps_example_and_screenshots(tmp_path):
    git = shutil.which("git")
    if not git:
        pytest.skip("Git is needed to verify ignore semantics.")
    subprocess.run([git, "init", "-q", str(tmp_path)], check=True, capture_output=True)
    shutil.copyfile(ROOT / ".gitignore", tmp_path / ".gitignore")
    ignored = [".env", ".env.local", ".env.production", ".streamlit/secrets.toml", "private.pem", "data/trendpulse.duckdb", "data/raw/import.csv", ".browser-preview/Cookies", "dependency-audit.json"]
    kept = [".env.example", ".streamlit/config.toml", "docs/screenshots/overview.png", "README.md"]
    result = subprocess.run([git, "-C", str(tmp_path), "check-ignore", "--no-index", "-z", "--stdin"], input=("\0".join(ignored+kept)+"\0").encode("utf-8"), capture_output=True, check=True)
    assert set(result.stdout.decode("utf-8").rstrip("\0").split("\0")) == set(ignored)


def test_public_defaults_do_not_expose_files_or_tracebacks():
    config = tomllib.loads((ROOT / ".streamlit/config.toml").read_text(encoding="utf-8"))
    assert config["server"]["address"] == "127.0.0.1"
    assert config["server"]["enableCORS"] and config["server"]["enableXsrfProtection"]
    assert not config["server"]["enableStaticServing"]
    assert config["client"]["showErrorDetails"] == "none"
