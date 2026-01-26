"""Button entities for Omo Lavanderia."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.exceptions import OmoApiError
from .api.models import MachineType
from .const import CONF_CARD_ID, CONF_LAUNDRY_ID, DOMAIN
from .coordinator import OmoLavanderiaCoordinator
from .entity import OmoLavanderiaEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities from config entry."""
    coordinator: OmoLavanderiaCoordinator = hass.data[DOMAIN][entry.entry_id]
    card_id = entry.data.get(CONF_CARD_ID)
    laundry_id = entry.data.get(CONF_LAUNDRY_ID)

    entities: list[ButtonEntity] = []

    if coordinator.data and coordinator.data.machines and card_id and laundry_id:
        for machine_id in coordinator.data.machines:
            entities.append(
                OmoStartCycleButton(coordinator, machine_id, card_id, laundry_id)
            )

    async_add_entities(entities)


class OmoStartCycleButton(OmoLavanderiaEntity, ButtonEntity):
    """Button to start a machine cycle."""

    _attr_translation_key = "start_cycle"

    def __init__(
        self,
        coordinator: OmoLavanderiaCoordinator,
        machine_id: str,
        card_id: str,
        laundry_id: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, machine_id)
        self._card_id = card_id
        self._laundry_id = laundry_id
        self._attr_unique_id = f"{machine_id}_start_cycle"

    @property
    def icon(self) -> str:
        """Return icon based on machine type."""
        state = self.machine_state
        is_dryer = state and state.machine and state.machine.machine_type == MachineType.DRYER
        return "mdi:tumble-dryer" if is_dryer else "mdi:washing-machine"

    @property
    def available(self) -> bool:
        """Return True if button is available (machine is available)."""
        state = self.machine_state
        if state is None:
            return False
        return state.is_available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes including price."""
        state = self.machine_state
        attrs = {}
        if state and state.machine:
            if state.machine.price:
                attrs["price"] = state.machine.price.price
                attrs["price_formatted"] = f"R$ {state.machine.price.price:.2f}"
            if state.machine.cycle_time:
                attrs["cycle_time_minutes"] = state.machine.cycle_time
        return attrs

    async def async_press(self) -> None:
        """Handle button press - start machine cycle."""
        state = self.machine_state
        if state is None or not state.is_available:
            raise HomeAssistantError("Machine is not available")

        machine_name = state.machine.display_name if state.machine else self._machine_id
        price = state.machine.price.price if state.machine and state.machine.price else 0
        
        try:
            _LOGGER.info(
                "Starting cycle on machine %s (R$ %.2f)",
                machine_name,
                price,
            )
            
            result = await self.coordinator.client.async_start_machine(
                machine_id=self._machine_id,
                card_id=self._card_id,
                laundry_id=self._laundry_id,
            )

            if not result.get("success"):
                error_msg = result.get("error", "Unknown error")
                raise HomeAssistantError(f"Failed to start machine: {error_msg}")

            usage_status = result.get("usageStatus", "UNKNOWN")
            order_id = result.get("orderId", "")
            
            _LOGGER.info(
                "Cycle initiated on machine %s, status: %s, order: %s",
                machine_name,
                usage_status,
                order_id[:8] if order_id else "N/A",
            )
            
            if result.get("warning"):
                _LOGGER.warning("Warning: %s", result["warning"])

            # Wait a moment for the machine to update its status
            await asyncio.sleep(2)
            
            # Refresh coordinator to update states
            await self.coordinator.async_request_refresh()

        except OmoApiError as err:
            _LOGGER.error("API error starting machine: %s", err)
            raise HomeAssistantError(f"Failed to start machine: {err}") from err
