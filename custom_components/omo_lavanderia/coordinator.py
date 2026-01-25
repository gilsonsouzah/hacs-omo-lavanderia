"""Data coordinator for Omo Lavanderia."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api.client import OmoLavanderiaApiClient
from .api.exceptions import OmoApiError, OmoAuthError
from .api.models import ActiveOrder, Laundry, LaundryMachine, MachineStatus
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class MachineState:
    """State of a single machine."""

    machine: LaundryMachine
    is_available: bool = False
    is_in_use_by_me: bool = False
    remaining_time_seconds: int | None = None
    order_id: str | None = None


@dataclass
class OmoLavanderiaData:
    """Data from the coordinator."""

    laundry: Laundry | None = None
    active_orders: list[ActiveOrder] = field(default_factory=list)
    machines: dict[str, MachineState] = field(default_factory=dict)


class OmoLavanderiaCoordinator(DataUpdateCoordinator[OmoLavanderiaData]):
    """Coordinator to fetch data from Omo Lavanderia API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: OmoLavanderiaApiClient,
        laundry_id: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.laundry_id = laundry_id

    async def _async_update_data(self) -> OmoLavanderiaData:
        """Fetch data from API."""
        try:
            # Check if token needs refresh
            if self.client.is_token_expired():
                _LOGGER.debug("Token expired, performing login")
                await self.client.async_login()

            # Fetch laundry details and active orders
            _LOGGER.debug("Fetching laundry %s data", self.laundry_id)
            laundry = await self.client.async_get_laundry(self.laundry_id)
            
            _LOGGER.debug("Fetching active orders")
            active_orders = await self.client.async_get_active_orders()

            # Build machine states
            machines = self._build_machine_states(laundry, active_orders)
            
            _LOGGER.debug(
                "Update complete: %d machines, %d active orders",
                len(machines),
                len(active_orders),
            )

            return OmoLavanderiaData(
                laundry=laundry,
                active_orders=active_orders,
                machines=machines,
            )

        except OmoAuthError as err:
            _LOGGER.error("Authentication error: %s", err)
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except OmoApiError as err:
            _LOGGER.error("API error: %s", err)
            raise UpdateFailed(f"API error: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching data: %s", err)
            raise UpdateFailed(f"Unexpected error: {err}") from err

    def _build_machine_states(
        self,
        laundry: Laundry,
        active_orders: list[ActiveOrder],
    ) -> dict[str, MachineState]:
        """Build machine states merging laundry data with active orders."""
        machines: dict[str, MachineState] = {}

        # Create lookup for active order machines
        active_machine_map: dict[str, tuple[int, str]] = {}
        for order in active_orders:
            if order.laundry_id == self.laundry_id:
                for order_machine in order.machines:
                    # Map by display name since order machines have different IDs
                    active_machine_map[order_machine.display_name] = (
                        order_machine.remaining_time,
                        order.id,
                    )

        # Process all machines
        all_machines = laundry.washers + laundry.dryers
        for machine in all_machines:
            is_available = machine.status == MachineStatus.AVAILABLE
            is_in_use_by_me = machine.display_name in active_machine_map
            remaining_time = None
            order_id = None

            if is_in_use_by_me:
                remaining_time, order_id = active_machine_map[machine.display_name]

            machines[machine.id] = MachineState(
                machine=machine,
                is_available=is_available,
                is_in_use_by_me=is_in_use_by_me,
                remaining_time_seconds=remaining_time,
                order_id=order_id,
            )

        return machines

    def get_machine_state(self, machine_id: str) -> MachineState | None:
        """Get state for a specific machine."""
        if self.data:
            return self.data.machines.get(machine_id)
        return None
