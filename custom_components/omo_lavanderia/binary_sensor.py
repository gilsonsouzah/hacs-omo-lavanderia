"""Binary sensor entities for Omo Lavanderia."""
from __future__ import annotations

from typing import Any

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
                OmoMachineEndingSoonBinarySensor(coordinator, machine_id),
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
    """Binary sensor indicating if machine is currently running (actually IN_USE with time remaining).
    
    This is different from is_in_use_by_me which is True even when the machine is just reserved.
    is_running is only True when the machine is physically running (usageStatus = IN_USE and remainingTime > 0).
    """

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "running"

    def __init__(self, coordinator: OmoLavanderiaCoordinator, machine_id: str) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, machine_id)
        self._attr_unique_id = f"{machine_id}_running"

    @property
    def is_on(self) -> bool | None:
        """Return True if machine is actually running (physically in use, not just reserved)."""
        state = self.machine_state
        return state.is_running if state else None

    @property
    def icon(self) -> str:
        """Return icon based on machine type."""
        state = self.machine_state
        is_dryer = state and state.machine and state.machine.machine_type == MachineType.DRYER
        
        if self.is_on:
            return "mdi:tumble-dryer-alert" if is_dryer else "mdi:washing-machine-alert"
        return "mdi:tumble-dryer" if is_dryer else "mdi:washing-machine"


class OmoMachineEndingSoonBinarySensor(OmoLavanderiaEntity, BinarySensorEntity):
    """Binary sensor indicating if machine cycle is ending soon (< 4 minutes remaining).
    
    This sensor turns ON when:
    - Machine is running (is_running = True)
    - Remaining time is less than 240 seconds (4 minutes)
    
    Use this for automations like "notify me when laundry is almost done".
    """

    _attr_translation_key = "ending_soon"
    
    # Threshold in seconds (4 minutes)
    ENDING_SOON_THRESHOLD = 240

    def __init__(self, coordinator: OmoLavanderiaCoordinator, machine_id: str) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, machine_id)
        self._attr_unique_id = f"{machine_id}_ending_soon"

    @property
    def is_on(self) -> bool | None:
        """Return True if machine is running and ending soon (< 4 min remaining)."""
        state = self.machine_state
        if not state or not state.is_running:
            return False
        
        remaining = state.remaining_time_seconds
        if remaining is None:
            return False
        
        return 0 < remaining < self.ENDING_SOON_THRESHOLD

    @property
    def available(self) -> bool:
        """Return if sensor is available (only when machine is running)."""
        state = self.machine_state
        return state is not None and state.is_running

    @property
    def icon(self) -> str:
        """Return icon based on state."""
        if self.is_on:
            return "mdi:timer-alert"
        return "mdi:timer-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        state = self.machine_state
        attrs = {
            "threshold_seconds": self.ENDING_SOON_THRESHOLD,
            "threshold_minutes": self.ENDING_SOON_THRESHOLD // 60,
        }
        
        if state and state.is_running and state.remaining_time_seconds is not None:
            attrs["remaining_seconds"] = state.remaining_time_seconds
            attrs["remaining_minutes"] = round(state.remaining_time_seconds / 60, 1)
        
        return attrs
