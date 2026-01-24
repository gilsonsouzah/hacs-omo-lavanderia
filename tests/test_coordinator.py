"""Tests for Omo Lavanderia coordinator."""
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.omo_lavanderia.api.models import (
    ActiveOrder,
    ActiveOrderMachine,
    Laundry,
    LaundryMachine,
    MachineStatus,
    MachineType,
)
from custom_components.omo_lavanderia.coordinator import (
    MachineState,
    OmoLavanderiaCoordinator,
)


@pytest.fixture
def mock_client():
    """Create a mock client."""
    client = MagicMock()
    client.async_get_laundry = AsyncMock()
    client.async_get_active_orders = AsyncMock(return_value=[])
    return client


@pytest.fixture
def coordinator(hass, mock_client):
    """Create a coordinator instance."""
    return OmoLavanderiaCoordinator(
        hass=hass,
        client=mock_client,
        laundry_id="laundry-123",
        laundry_name="Test Laundry",
        card_id="card-123",
    )


class TestMachineState:
    """Tests for MachineState dataclass."""

    def test_machine_state_available(self):
        """Test available machine state."""
        state = MachineState(
            is_available=True,
            is_in_use_by_me=False,
            remaining_time_seconds=None,
        )

        assert state.is_available is True
        assert state.is_in_use_by_me is False
        assert state.remaining_time_seconds is None

    def test_machine_state_in_use_by_me(self):
        """Test machine in use by current user."""
        state = MachineState(
            is_available=False,
            is_in_use_by_me=True,
            remaining_time_seconds=600,
        )

        assert state.is_available is False
        assert state.is_in_use_by_me is True
        assert state.remaining_time_seconds == 600


class TestOmoLavanderiaCoordinator:
    """Tests for OmoLavanderiaCoordinator."""

    @pytest.mark.asyncio
    async def test_update_fetches_laundry_data(self, coordinator, mock_client):
        """Test update fetches laundry data."""
        mock_laundry = MagicMock(spec=Laundry)
        mock_laundry.washers = [
            MagicMock(
                spec=LaundryMachine,
                id="washer-1",
                display_name="L1",
                machine_type=MachineType.WASHER,
                status=MachineStatus.AVAILABLE,
            )
        ]
        mock_laundry.dryers = [
            MagicMock(
                spec=LaundryMachine,
                id="dryer-1",
                display_name="S1",
                machine_type=MachineType.DRYER,
                status=MachineStatus.IN_USE,
            )
        ]
        mock_client.async_get_laundry.return_value = mock_laundry

        await coordinator._async_update_data()

        assert coordinator.laundry == mock_laundry
        mock_client.async_get_laundry.assert_called_once_with("laundry-123")
        mock_client.async_get_active_orders.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_handles_api_error(self, coordinator, mock_client):
        """Test update handles API errors."""
        mock_client.async_get_laundry.side_effect = Exception("API Error")

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_update_matches_active_orders(self, coordinator, mock_client):
        """Test update correctly matches active orders to machines."""
        mock_laundry = MagicMock(spec=Laundry)
        mock_washer = MagicMock(
            spec=LaundryMachine,
            id="washer-1",
            display_name="L1",
            machine_type=MachineType.WASHER,
            status=MachineStatus.IN_USE,
        )
        mock_laundry.washers = [mock_washer]
        mock_laundry.dryers = []
        mock_client.async_get_laundry.return_value = mock_laundry

        mock_order = MagicMock(spec=ActiveOrder)
        mock_order.laundry_id = "laundry-123"
        mock_order.machines = [
            MagicMock(
                spec=ActiveOrderMachine,
                display_name="L1",
                remaining_time=300,
                machine_type=MachineType.WASHER,
            )
        ]
        mock_client.async_get_active_orders.return_value = [mock_order]

        await coordinator._async_update_data()

        assert "washer-1" in coordinator.machine_states
        state = coordinator.machine_states["washer-1"]
        assert state.is_in_use_by_me is True
        assert state.remaining_time_seconds == 300

    def test_coordinator_properties(self, coordinator):
        """Test coordinator properties."""
        assert coordinator.laundry_id == "laundry-123"
        assert coordinator.laundry_name == "Test Laundry"
        assert coordinator.card_id == "card-123"
