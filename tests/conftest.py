"""Real Home Assistant fixtures with synthetic accounts only."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

import custom_components.ouderapp  # noqa: F401
from custom_components.ouderapp.api import Session, account_key

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Enable this test repository's custom integration."""


@pytest.fixture
def session():
    return Session(
        "example",
        "synthetic@example.invalid",
        account_key("example", "synthetic@example.invalid"),
        "access-test",
        "refresh-test",
        {"uuid": "test"},
    )


@pytest.fixture
def config_entry(session):
    return MockConfigEntry(
        domain="ouderapp",
        title="OuderApp test",
        unique_id=session.account_id,
        data={"session": session.storage()},
    )


@pytest.fixture
def mock_api(session):
    api = AsyncMock()
    api.session = session
    api.async_fetch_summary.return_value = {
        "children_count": 2,
        "unread_messages": 3,
        "unread_news": None,
    }
    return api
