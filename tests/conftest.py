"""Pytest bootstrap: expose the src/app layer packages and provide a Django client."""

import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
APP_PATH = SRC_PATH / "app"
UI_ARTIFACTS = Path(__file__).parent / "_ui_artifacts"

for path in (str(SRC_PATH), str(APP_PATH)):
    if path not in sys.path:
        sys.path.insert(0, path)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "agent_dashboard.settings")
os.environ.setdefault("AGENT_CONFIG_DIR", str(UI_ARTIFACTS))


def pytest_sessionstart(session):
    """Start from a clean slate for UI test artifacts."""
    shutil.rmtree(UI_ARTIFACTS, ignore_errors=True)
    UI_ARTIFACTS.mkdir(parents=True, exist_ok=True)


def pytest_sessionfinish(session, exitstatus):
    """Remove UI test artifacts after the run."""
    shutil.rmtree(UI_ARTIFACTS, ignore_errors=True)


@pytest.fixture(autouse=True)
def _isolated_container():
    """Give each UI test a fresh container, database, and storage folder."""
    yield

    from django.apps import apps
    from agent_dashboard.container import container

    if apps.ready:
        container.reset()
    shutil.rmtree(UI_ARTIFACTS, ignore_errors=True)


@pytest.fixture()
def client():
    """Provide a Django test client with the app configured, per test."""
    import django
    from django.test import Client

    if not django.apps.apps.ready:
        django.setup()

    return Client()
