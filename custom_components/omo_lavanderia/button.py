"""Button entities for Omo Lavanderia integration."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, CONF_CARD_ID
from .coordinator import OmoLavanderiaCoordinator
from .entity import OmoLavanderiaEntity
from .api.exceptions import OmoApiError

_LOGGER = logging.getLogger(__name__)


class OmoStartCycleButton(OmoLavanderiaEntity, ButtonEntity):
    """Button to start a machine cycle."""

    _attr_translation_key = "start_cycle"
    _attr_icon = "mdi:play-circle"

    def __init__(
        self,
        coordinator: OmoLavanderiaCoordinator,
        machine_id: str,
        card_id: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, machine_id)
        self._card_id = card_id
        self._attr_unique_id = f"{machine_id}_start_cycle"

    @property
    def available(self) -> bool:
        """Return True if button is available (machine is available)."""
        state = self.machine_state
        if state is None:
            return False
        return state.is_available

    async def async_press(self) -> None:
        """Handle button press - start machine cycle."""
        state = self.machine_state
        if state is None or not state.is_available:
            raise HomeAssistantError("Machine is not available")

        try:
            success = await self.coordinator.api.async_start_machine(
                machine_id=self._machine_id,
                card_id=self._card_id,
            )

            if not success:
                raise HomeAssistantError("Failed to start machine cycle")

            _LOGGER.info(
                "Started cycle on machine %s",
                state.machine.displayName if state.machine else self._machine_id,
            )

            # Refresh coordinator to update states
            await self.coordinator.async_request_refresh()

        except OmoApiError as err:
            _LOGGER.error("API error starting machine: %s", err)
            raise HomeAssistantError(f"Failed to start machine: {err}") from err


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities from config entry."""
    coordinator: OmoLavanderiaCoordinator = hass.data[DOMAIN][entry.entry_id]
    card_id = entry.data.get(CONF_CARD_ID)

    entities: list[ButtonEntity] = []

    if coordinator.data and coordinator.data.machines and card_id:
        for machine_id in coordinator.data.machines:
            entities.append(
                OmoStartCycleButton(coordinator, machine_id, card_id)
            )

    async_add_entities(entities)
