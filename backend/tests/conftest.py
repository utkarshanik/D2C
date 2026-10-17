"""Keep every test off the real SQLite file and screenshot folder."""
import pytest

from app.config import settings
from app.db.session import reset_engine


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    db_path = tmp_path / "d2c.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path / "data"))
    reset_engine()
    yield
    reset_engine()
