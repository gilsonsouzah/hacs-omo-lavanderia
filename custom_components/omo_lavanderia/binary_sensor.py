"""Binary sensor entities for Omo Lavanderia."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.models import MachineType
from .const import DOMAIN
from .coordinator import OmoLavanderiaCoordinator
from .entity import OmoLavanderiaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from config entry."""
    coordinator: OmoLavanderiaCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BinarySensorEntity] = []

    if coordinator.data and coordinator.data.machines:
        for machine_id in coordinator.data.machines:
            entities.extend([
                OmoMachineAvailableBinarySensor(coordinator, machine_id),
                OmoMachineRunningBinarySensor(coordinator, machine_id),
            ])

    async_add_entities(entities)


class OmoMachineAvailableBinarySensor(OmoLavanderiaEntity, BinarySensorEntity):
    """Binary sensor indicating if machine is available."""

    _attr_translation_key = "available"

    def __init__(self, coordinator: OmoLavanderiaCoordinator, machine_id: str) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, machine_id)
        self._attr_unique_id = f"{machine_id}_available"

    @property
    def is_on(self) -> bool | None:
        """Return True if machine is available."""
        state = self.machine_state
        return state.is_available if state else None

    @property
    def icon(self) -> str:
        """Return icon based on machine type and state."""
        state = self.machine_state
        is_dryer = state and state.machine and state.machine.machine_type == MachineType.DRYER
        
        if self.is_on:
            return "mdi:tumble-dryer" if is_dryer else "mdi:washing-machine"
        return "mdi:tumble-dryer-off" if is_dryer else "mdi:washing-machine-off"


class OmoMachineRunningBinarySensor(OmoLavanderiaEntity, BinarySensorEntity):
    """Binary sensor indicating if machine is currently running (in use by me)."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "running"

    def __init__(self, coordinator: OmoLavanderiaCoordinator, machine_id: str) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, machine_id)
        self._attr_unique_id = f"{machine_id}_running"

    @property
    def is_on(self) -> bool | None:
        """Return True if machine is running (in use by current user)."""
        state = self.machine_state
        return state.is_in_use_by_me if state else None

    @property
    def icon(self) -> str:
        """Return icon based on machine type."""
        state = self.machine_state
        is_dryer = state and state.machine and state.machine.machine_type == MachineType.DRYER
        
        if self.is_on:
            return "mdi:tumble-dryer-alert" if is_dryer else "mdi:washing-machine-alert"
        return "mdi:tumble-dryer" if is_dryer else "mdi:washing-machine"
