"""Tests for Omo Lavanderia config flow."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType

from custom_components.omo_lavanderia.const import (
    CONF_CARD_DISPLAY,
    CONF_CARD_ID,
    CONF_LAUNDRY_ID,
    CONF_LAUNDRY_NAME,
    DOMAIN,
)


@pytest.fixture
def mock_client():
    """Create a mock client."""
    client = MagicMock()
    client.async_login = AsyncMock(return_value=True)
    client.async_get_laundries = AsyncMock(
        return_value=[
            MagicMock(id="laundry-1", name="Laundry 1"),
            MagicMock(id="laundry-2", name="Laundry 2"),
        ]
    )
    client.async_get_payment_cards = AsyncMock(
        return_value=[
            MagicMock(id="card-1", display_name="Visa ****1234"),
            MagicMock(id="card-2", display_name="Master ****5678"),
        ]
    )
    client.get_tokens = MagicMock(
        return_value={
            "access_token": "test_access",
            "refresh_token": "test_refresh",
            "expires_at": 9999999999,
        }
    )
    return client


class TestConfigFlow:
    """Tests for config flow."""

    @pytest.mark.asyncio
    async def test_form_shows_user_step(self, hass):
        """Test that user step shows form."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

    @pytest.mark.asyncio
    async def test_user_step_invalid_credentials(self, hass, mock_client):
        """Test user step with invalid credentials."""
        mock_client.async_login = AsyncMock(side_effect=Exception("Invalid credentials"))

        with patch(
            "custom_components.omo_lavanderia.config_flow.OmoLavanderiaClient",
            return_value=mock_client,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_USERNAME: "test@email.com",
                    CONF_PASSWORD: "wrongpassword",
                },
            )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert "base" in result["errors"]

    @pytest.mark.asyncio
    async def test_user_step_success_goes_to_laundry_selection(self, hass, mock_client):
        """Test user step success proceeds to laundry selection."""
        with patch(
            "custom_components.omo_lavanderia.config_flow.OmoLavanderiaClient",
            return_value=mock_client,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_USERNAME: "test@email.com",
                    CONF_PASSWORD: "password123",
                },
            )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "select_laundry"

    @pytest.mark.asyncio
    async def test_laundry_selection_goes_to_card_selection(self, hass, mock_client):
        """Test laundry selection proceeds to card selection."""
        with patch(
            "custom_components.omo_lavanderia.config_flow.OmoLavanderiaClient",
            return_value=mock_client,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_USERNAME: "test@email.com",
                    CONF_PASSWORD: "password123",
                },
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_LAUNDRY_ID: "laundry-1"},
            )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "select_card"

    @pytest.mark.asyncio
    async def test_full_flow_creates_entry(self, hass, mock_client):
        """Test complete flow creates config entry."""
        with patch(
            "custom_components.omo_lavanderia.config_flow.OmoLavanderiaClient",
            return_value=mock_client,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_USERNAME: "test@email.com",
                    CONF_PASSWORD: "password123",
                },
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_LAUNDRY_ID: "laundry-1"},
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_CARD_ID: "card-1"},
            )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Laundry 1"
        assert result["data"][CONF_USERNAME] == "test@email.com"
        assert result["data"][CONF_LAUNDRY_ID] == "laundry-1"
        assert result["data"][CONF_CARD_ID] == "card-1"
