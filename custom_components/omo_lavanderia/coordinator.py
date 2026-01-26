"""Data coordinator for Omo Lavanderia."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api.client import OmoLavanderiaApiClient
from .api.exceptions import OmoApiError, OmoAuthError
from .api.models import ActiveOrder, Laundry, LaundryMachine, MachineStatus
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN_EXPIRES_AT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class MachineState:
    """State of a single machine."""

    machine: LaundryMachine
    is_available: bool = False
    is_in_use_by_me: bool = False
    is_running: bool = False  # True only when actually running (IN_USE with remainingTime > 0)
    remaining_time_seconds: int | None = None
    order_id: str | None = None
    usage_status: str = "AVAILABLE"  # AVAILABLE, READY, IN_USE, COMPLETE, UNAVAILABLE, OFFLINE


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
        config_entry: ConfigEntry | None = None,
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
        self._config_entry = config_entry
        self._consecutive_errors: int = 0
        self._last_successful_update: float = 0

        # Set up token update callback to persist tokens
        client.set_token_update_callback(self._on_token_update)

    def _on_token_update(
        self, access_token: str, refresh_token: str, expires_at: int
    ) -> None:
        """Handle token updates by persisting to config entry."""
        if self._config_entry is None:
            return

        try:
            self.hass.config_entries.async_update_entry(
                self._config_entry,
                data={
                    **self._config_entry.data,
                    CONF_ACCESS_TOKEN: access_token,
                    CONF_REFRESH_TOKEN: refresh_token,
                    CONF_TOKEN_EXPIRES_AT: expires_at,
                },
            )
            _LOGGER.debug("Persisted updated tokens to config entry")
        except Exception as err:
            _LOGGER.warning("Failed to persist tokens: %s", err)

    async def _async_update_data(self) -> OmoLavanderiaData:
        """Fetch data from API with improved error handling."""
        import time
        
        try:
            # Ensure we have a valid token before making requests
            await self.client.async_ensure_valid_token()

            # Fetch laundry details and active orders
            _LOGGER.debug("Fetching laundry %s data", self.laundry_id)
            laundry = await self.client.async_get_laundry(self.laundry_id)
            
            _LOGGER.debug("Fetching active orders")
            active_orders = await self.client.async_get_active_orders()

            # Build machine states
            machines = self._build_machine_states(laundry, active_orders)
            
            # Success - reset error counter
            self._consecutive_errors = 0
            self._last_successful_update = time.time()
            
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
            self._consecutive_errors += 1
            _LOGGER.error(
                "Authentication error (attempt %d): %s",
                self._consecutive_errors,
                err,
            )
            # Keep existing data on transient auth errors
            if self.data and self._consecutive_errors < 3:
                _LOGGER.warning("Using cached data due to auth error")
                return self.data
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except OmoApiError as err:
            self._consecutive_errors += 1
            _LOGGER.error(
                "API error (attempt %d): %s",
                self._consecutive_errors,
                err,
            )
            # Keep existing data on transient errors
            if self.data and self._consecutive_errors < 5:
                _LOGGER.warning("Using cached data due to API error")
                return self.data
            raise UpdateFailed(f"API error: {err}") from err
        except Exception as err:
            self._consecutive_errors += 1
            _LOGGER.exception(
                "Unexpected error fetching data (attempt %d): %s",
                self._consecutive_errors,
                err,
            )
            # Keep existing data on transient errors
            if self.data and self._consecutive_errors < 5:
                _LOGGER.warning("Using cached data due to unexpected error")
                return self.data
            raise UpdateFailed(f"Unexpected error: {err}") from err

    def get_diagnostics(self) -> dict[str, Any]:
        """Get diagnostic information for troubleshooting."""
        import time
        
        token_status = self.client.get_token_status()
        
        return {
            "token": token_status,
            "coordinator": {
                "consecutive_errors": self._consecutive_errors,
                "last_successful_update": self._last_successful_update,
                "seconds_since_success": (
                    int(time.time() - self._last_successful_update)
                    if self._last_successful_update > 0
                    else None
                ),
                "has_data": self.data is not None,
                "machine_count": len(self.data.machines) if self.data else 0,
                "active_order_count": (
                    len(self.data.active_orders) if self.data else 0
                ),
            },
            "laundry_id": self.laundry_id,
            "username": self.client.username,
        }

    def _build_machine_states(
        self,
        laundry: Laundry,
        active_orders: list[ActiveOrder],
    ) -> dict[str, MachineState]:
        """Build machine states merging laundry data with active orders."""
        machines: dict[str, MachineState] = {}

        # Create lookup for active order machines
        # Stores: (remaining_time, order_id, usage_status)
        active_machine_map: dict[str, tuple[int, str, str]] = {}
        for order in active_orders:
            if order.laundry_id == self.laundry_id:
                for order_machine in order.machines:
                    # Map by display name since order machines have different IDs
                    active_machine_map[order_machine.display_name] = (
                        order_machine.remaining_time,
                        order.id,
                        order_machine.usage_status,
                    )

        # Process all machines
        all_machines = laundry.washers + laundry.dryers
        for machine in all_machines:
            is_available = machine.status == MachineStatus.AVAILABLE
            is_in_use_by_me = machine.display_name in active_machine_map
            remaining_time = None
            order_id = None
            usage_status: str = "AVAILABLE" if is_available else machine.status.value
            is_running = False

            if is_in_use_by_me:
                remaining_time, order_id, usage_status = active_machine_map[machine.display_name]
                # Machine is only "running" if usageStatus is IN_USE and has remaining time
                is_running = usage_status == "IN_USE" and remaining_time is not None and remaining_time > 0
                
                # Only set remaining_time if actually running, to prevent false triggers
                if not is_running:
                    remaining_time = None

            machines[machine.id] = MachineState(
                machine=machine,
                is_available=is_available,
                is_in_use_by_me=is_in_use_by_me,
                is_running=is_running,
                remaining_time_seconds=remaining_time,
                order_id=order_id,
                usage_status=usage_status,
            )

        return machines

    def get_machine_state(self, machine_id: str) -> MachineState | None:
        """Get state for a specific machine."""
        if self.data:
            return self.data.machines.get(machine_id)
        return None
