import os
import pytest

@pytest.fixture(autouse=True)
def _env_keys(monkeypatch):
    """
    Provide safe dummy keys in CI so settings can read them.
    """
    monkeypatch.setenv("GOOGLE_MAPS_BROWSER_KEY",  "test-browser-key")
    monkeypatch.setenv("GOOGLE_ROUTES_SERVER_KEY", "test-server-key")

@pytest.fixture(autouse=True)
def _settings_overrides(settings, tmp_path):
    """
    Keep tests hermetic: DEBUG on, sqlite memory DB if your settings switch DB
    based on env, and a small STATIC_ROOT so collectstatic (if any) won’t break.
    """
    settings.DEBUG = True
    settings.STATIC_ROOT = tmp_path / "staticfiles"
