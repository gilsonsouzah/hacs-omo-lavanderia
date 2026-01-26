"""Tests for Omo Lavanderia coordinator."""
from unittest.mock import AsyncMock, MagicMock

import pytest

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
    OmoLavanderiaData,
)


@pytest.fixture
def mock_client():
    """Create a mock client."""
    client = MagicMock()
    client.async_get_laundry = AsyncMock()
    client.async_get_active_orders = AsyncMock(return_value=[])
    client.is_token_expired = MagicMock(return_value=False)
    client.async_ensure_valid_token = AsyncMock(return_value=True)
    client.get_token_status = MagicMock(return_value={
        "has_token": True,
        "is_expired": False,
        "is_expiring_soon": False,
        "expires_at": 9999999999,
        "time_until_expiry_seconds": 3600,
        "login_failures": 0,
        "last_login_attempt": 0,
    })
    client.username = "test@example.com"
    client.set_token_update_callback = MagicMock()
    return client


@pytest.fixture
def coordinator(hass, mock_client):
    """Create a coordinator instance."""
    return OmoLavanderiaCoordinator(
        hass=hass,
        client=mock_client,
        laundry_id="laundry-123",
    )


class TestMachineState:
    """Tests for MachineState dataclass."""

    def test_machine_state_available(self):
        """Test available machine state."""
        mock_machine = MagicMock(spec=LaundryMachine)
        state = MachineState(
            machine=mock_machine,
            is_available=True,
            is_in_use_by_me=False,
            is_running=False,
            remaining_time_seconds=None,
        )

        assert state.is_available is True
        assert state.is_in_use_by_me is False
        assert state.is_running is False
        assert state.remaining_time_seconds is None

    def test_machine_state_in_use_by_me(self):
        """Test machine in use by current user."""
        mock_machine = MagicMock(spec=LaundryMachine)
        state = MachineState(
            machine=mock_machine,
            is_available=False,
            is_in_use_by_me=True,
            is_running=True,
            remaining_time_seconds=600,
            order_id="order-123",
            usage_status="IN_USE",
        )

        assert state.is_available is False
        assert state.is_in_use_by_me is True
        assert state.is_running is True
        assert state.remaining_time_seconds == 600
        assert state.order_id == "order-123"
        assert state.usage_status == "IN_USE"


class TestOmoLavanderiaCoordinator:
    """Tests for OmoLavanderiaCoordinator.
    
    Note: Full coordinator tests require Home Assistant frame helper setup.
    These tests are skipped in unit tests and run in integration tests.
    """
    pass


class TestOmoLavanderiaData:
    """Tests for OmoLavanderiaData dataclass."""

    def test_data_defaults(self):
        """Test OmoLavanderiaData default values."""
        data = OmoLavanderiaData()
        
        assert data.laundry is None
        assert data.active_orders == []
        assert data.machines == {}

    def test_data_with_values(self):
        """Test OmoLavanderiaData with values."""
        mock_laundry = MagicMock(spec=Laundry)
        mock_order = MagicMock(spec=ActiveOrder)
        mock_machine = MagicMock(spec=LaundryMachine)
        mock_state = MachineState(
            machine=mock_machine,
            is_available=True,
        )
        
        data = OmoLavanderiaData(
            laundry=mock_laundry,
            active_orders=[mock_order],
            machines={"machine-1": mock_state},
        )
        
        assert data.laundry == mock_laundry
        assert len(data.active_orders) == 1
        assert "machine-1" in data.machines
