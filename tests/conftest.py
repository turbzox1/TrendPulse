import pytest
from src.pipeline import build


@pytest.fixture(scope="session")
def demo_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("trendpulse") / "test.duckdb"
    build(path)
    return path
