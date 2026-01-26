"""Tests for Omo Lavanderia __init__.py."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from custom_components.omo_lavanderia.const import (
    CONF_ACCESS_TOKEN,
    CONF_CARD_ID,
    CONF_LAUNDRY_ID,
    CONF_LAUNDRY_NAME,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN_EXPIRES_AT,
    DOMAIN,
)


class TestAsyncSetupEntry:
    """Tests for async_setup_entry."""

    @pytest.mark.asyncio
    async def test_setup_entry_success(self, hass, config_entry):
        """Test successful setup of entry."""
        with patch(
            "custom_components.omo_lavanderia.async_get_clientsession"
        ) as mock_session, patch(
            "custom_components.omo_lavanderia.OmoLavanderiaApiClient"
        ) as mock_client_class, patch(
            "custom_components.omo_lavanderia.OmoLavanderiaCoordinator"
        ) as mock_coordinator_class:
            mock_client = MagicMock()
            mock_client.set_tokens = MagicMock()
            mock_client.is_token_expired = MagicMock(return_value=False)
            mock_client_class.return_value = mock_client

            mock_coordinator = MagicMock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            hass.config_entries.async_forward_entry_setups = AsyncMock()

            # Import and call the function
            from custom_components.omo_lavanderia import async_setup_entry

            result = await async_setup_entry(hass, config_entry)

            assert result is True
            assert DOMAIN in hass.data
            mock_client.set_tokens.assert_called_once()
            mock_coordinator.async_config_entry_first_refresh.assert_called_once()


class TestAsyncUnloadEntry:
    """Tests for async_unload_entry."""

    @pytest.mark.asyncio
    async def test_unload_entry_success(self, hass, config_entry):
        """Test successful unload of entry."""
        # Setup mock data
        hass.data[DOMAIN] = {
            config_entry.entry_id: MagicMock()
        }
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        from custom_components.omo_lavanderia import async_unload_entry

        result = await async_unload_entry(hass, config_entry)

        assert result is True
        assert config_entry.entry_id not in hass.data[DOMAIN]
