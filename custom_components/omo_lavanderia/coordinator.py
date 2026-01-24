"""DataUpdateCoordinator for Omo Lavanderia integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api.client import OmoLavanderiaApiClient
from .api.exceptions import OmoApiError, OmoAuthError
from .api.models import (
    ActiveOrder,
    Laundry,
    LaundryMachine,
    MachineStatus,
    OrderMachine,
    UsageStatus,
)
from .const import CONF_LAUNDRY_ID, DEFAULT_SCAN_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from .api.models import MachineType

_LOGGER = logging.getLogger(__name__)


@dataclass
class MachineState:
    """Merged state of a machine."""

    machine: LaundryMachine
    is_available: bool
    is_in_use_by_me: bool
    remaining_time_seconds: int | None
    order_id: str | None
    start_usage_at: datetime | None
    order_machine: OrderMachine | None = None

    @property
    def machine_id(self) -> str:
        """Return the machine ID."""
        return self.machine.id

    @property
    def machine_code(self) -> str:
        """Return the machine code."""
        return self.machine.code

    @property
    def display_name(self) -> str:
        """Return the display name."""
        return self.machine.display_name

    @property
    def machine_type(self) -> MachineType:
        """Return the machine type."""
        return self.machine.type

    @property
    def status(self) -> MachineStatus:
        """Return the machine status."""
        return self.machine.status


@dataclass
class OmoLavanderiaData:
    """Data returned by coordinator."""

    laundry: Laundry
    active_orders: list[ActiveOrder]
    machines: dict[str, MachineState]


class OmoLavanderiaCoordinator(DataUpdateCoordinator[OmoLavanderiaData]):
    """Coordinator for Omo Lavanderia data.

    This coordinator handles centralized polling of the Omo Lavanderia API,
    fetching laundry details and active orders, then merging the data
    to provide a complete view of machine states.
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: OmoLavanderiaApiClient,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance.
            entry: Config entry for this integration.
            client: API client for making requests.
        """
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )
        self.client = client
        self.laundry_id: str = entry.data[CONF_LAUNDRY_ID]

    async def _async_update_data(self) -> OmoLavanderiaData:
        """Fetch data from API.

        This method fetches laundry details (including machines) and active orders,
        then merges the data to create a complete picture of machine states.

        Returns:
            OmoLavanderiaData with laundry, active orders, and merged machine states.

        Raises:
            ConfigEntryAuthFailed: If authentication fails.
            UpdateFailed: If there's an error communicating with the API.
        """
        try:
            # 1. Fetch laundry details (includes machines)
            laundry = await self.client.async_get_laundry(self.laundry_id)

            # 2. Fetch active orders
            active_orders = await self.client.async_get_active_orders()

            # 3. Merge machine states
            machines = self._merge_machine_states(laundry, active_orders)

            _LOGGER.debug(
                "Updated data: %d machines, %d active orders",
                len(machines),
                len(active_orders),
            )

            return OmoLavanderiaData(
                laundry=laundry,
                active_orders=active_orders,
                machines=machines,
            )

        except OmoAuthError as err:
            _LOGGER.error("Authentication failed: %s", err)
            raise ConfigEntryAuthFailed(err) from err
        except OmoApiError as err:
            _LOGGER.error("Error communicating with API: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def _merge_machine_states(
        self,
        laundry: Laundry,
        active_orders: list[ActiveOrder],
    ) -> dict[str, MachineState]:
        """Merge laundry machines with active order status.

        For each machine in the laundry, check if it's being used by the current user
        by looking for matching machines in active orders.

        Args:
            laundry: Laundry data containing machines.
            active_orders: List of active orders for the current user.

        Returns:
            Dictionary mapping machine ID to MachineState.
        """
        # Build a lookup of active order machines by machine_id
        order_machines_by_id: dict[str, tuple[OrderMachine, str]] = {}
        for order in active_orders:
            for order_machine in order.machines:
                # Only consider machines that are in progress or pending
                if order_machine.usage_status in (
                    UsageStatus.PENDING,
                    UsageStatus.IN_PROGRESS,
                ):
                    order_machines_by_id[order_machine.machine_id] = (
                        order_machine,
                        order.id,
                    )

        machines: dict[str, MachineState] = {}

        for machine in laundry.machines:
            # Check if this machine is in an active order (used by me)
            order_info = order_machines_by_id.get(machine.id)

            if order_info:
                order_machine, order_id = order_info
                machines[machine.id] = MachineState(
                    machine=machine,
                    is_available=False,
                    is_in_use_by_me=True,
                    remaining_time_seconds=order_machine.remaining_time,
                    order_id=order_id,
                    start_usage_at=order_machine.start_usage_at,
                    order_machine=order_machine,
                )
            else:
                # Machine is not in any of my active orders
                is_available = machine.status == MachineStatus.AVAILABLE
                is_in_use = machine.status == MachineStatus.IN_USE

                machines[machine.id] = MachineState(
                    machine=machine,
                    is_available=is_available,
                    is_in_use_by_me=False,
                    remaining_time_seconds=None,
                    order_id=None,
                    start_usage_at=None,
                    order_machine=None,
                )

                if is_in_use:
                    _LOGGER.debug(
                        "Machine %s (%s) is in use by another user",
                        machine.code,
                        machine.display_name,
                    )

        return machines

    def get_machine_state(self, machine_id: str) -> MachineState | None:
        """Get the state of a specific machine.

        Args:
            machine_id: The ID of the machine.

        Returns:
            MachineState if found, None otherwise.
        """
        if self.data is None:
            return None
        return self.data.machines.get(machine_id)

    def get_machines_by_type(self, machine_type: MachineType) -> list[MachineState]:
        """Get all machines of a specific type.

        Args:
            machine_type: The type of machine to filter by.

        Returns:
            List of MachineState for machines of the specified type.
        """
        if self.data is None:
            return []
        return [
            state
            for state in self.data.machines.values()
            if state.machine.type == machine_type
        ]

    @property
    def available_machines(self) -> list[MachineState]:
        """Get all available machines."""
        if self.data is None:
            return []
        return [
            state for state in self.data.machines.values() if state.is_available
        ]

    @property
    def machines_in_use_by_me(self) -> list[MachineState]:
        """Get all machines currently in use by the current user."""
        if self.data is None:
            return []
        return [
            state for state in self.data.machines.values() if state.is_in_use_by_me
        ]
