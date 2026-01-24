"""Pytest configuration for Omo Lavanderia tests."""
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.config_entries.flow = MagicMock()
    hass.config_entries.flow.async_init = MagicMock()
    hass.config_entries.flow.async_configure = MagicMock()
    return hass


@pytest.fixture
def config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        "username": "test@email.com",
        "password": "password123",
        "laundry_id": "laundry-123",
        "laundry_name": "Test Laundry",
        "card_id": "card-123",
        "card_display": "Visa ****1234",
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "token_expires_at": 9999999999,
    }
    return entry
