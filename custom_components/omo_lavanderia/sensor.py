"""Sensor entities for Omo Lavanderia."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OmoLavanderiaCoordinator
from .entity import OmoLavanderiaEntity, OmoLavanderiaLaundryEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from config entry."""
    coordinator: OmoLavanderiaCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    if coordinator.data and coordinator.data.machines:
        for machine_id in coordinator.data.machines:
            entities.extend([
                OmoRemainingTimeSensor(coordinator, machine_id),
                OmoCycleTimeSensor(coordinator, machine_id),
                OmoPriceSensor(coordinator, machine_id),
                OmoMachineStatusSensor(coordinator, machine_id),
            ])

    # Add laundry-level sensor
    entities.append(OmoLaundryStatusSensor(coordinator))

    async_add_entities(entities)


class OmoRemainingTimeSensor(OmoLavanderiaEntity, SensorEntity):
    """Sensor for remaining cycle time."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer"
    _attr_translation_key = "remaining_time"

    def __init__(self, coordinator: OmoLavanderiaCoordinator, machine_id: str) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, machine_id)
        self._attr_unique_id = f"{machine_id}_remaining_time"

    @property
    def native_value(self) -> int | None:
        """Return remaining time in seconds."""
        state = self.machine_state
        if state and state.is_in_use_by_me:
            return state.remaining_time_seconds
        return None

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        state = self.machine_state
        return state is not None and state.is_in_use_by_me


class OmoCycleTimeSensor(OmoLavanderiaEntity, SensorEntity):
    """Sensor for machine cycle time."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:clock-outline"
    _attr_translation_key = "cycle_time"

    def __init__(self, coordinator: OmoLavanderiaCoordinator, machine_id: str) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, machine_id)
        self._attr_unique_id = f"{machine_id}_cycle_time"

    @property
    def native_value(self) -> int | None:
        """Return cycle time in minutes."""
        state = self.machine_state
        if state and state.machine:
            return state.machine.cycle_time
        return None


class OmoPriceSensor(OmoLavanderiaEntity, SensorEntity):
    """Sensor for machine price."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "BRL"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:currency-brl"
    _attr_translation_key = "price"

    def __init__(self, coordinator: OmoLavanderiaCoordinator, machine_id: str) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, machine_id)
        self._attr_unique_id = f"{machine_id}_price"

    @property
    def native_value(self) -> float | None:
        """Return machine price."""
        state = self.machine_state
        if state and state.machine and state.machine.price:
            return state.machine.price.price
        return None


class OmoMachineStatusSensor(OmoLavanderiaEntity, SensorEntity):
    """Sensor for machine status."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["available", "in_use", "in_use_by_me", "unavailable"]
    _attr_icon = "mdi:washing-machine"
    _attr_translation_key = "machine_status"

    def __init__(self, coordinator: OmoLavanderiaCoordinator, machine_id: str) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, machine_id)
        self._attr_unique_id = f"{machine_id}_status"

    @property
    def native_value(self) -> str | None:
        """Return machine status."""
        state = self.machine_state
        if state is None:
            return None

        if state.is_in_use_by_me:
            return "in_use_by_me"
        if state.is_available:
            return "available"
        if state.machine.status.value == "IN_USE":
            return "in_use"
        return "unavailable"


class OmoLaundryStatusSensor(OmoLavanderiaLaundryEntity, SensorEntity):
    """Sensor for laundry status."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["open", "closed", "blocked"]
    _attr_icon = "mdi:door"
    _attr_translation_key = "laundry_status"

    def __init__(self, coordinator: OmoLavanderiaCoordinator) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._laundry_id}_status"

    @property
    def native_value(self) -> str | None:
        """Return laundry status."""
        laundry = self.coordinator.data.laundry if self.coordinator.data else None
        if laundry is None:
            return None

        if laundry.is_blocked:
            return "blocked"
        if laundry.is_closed:
            return "closed"
        return "open"
