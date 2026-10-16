import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def no_refine_by_default(monkeypatch):
    """The refine loop calls the model and Chromium. Tests for other modules must
    not trigger it, so it is off unless a test turns it on explicitly."""
    monkeypatch.setattr(settings, "REFINE_ROUNDS", 0)