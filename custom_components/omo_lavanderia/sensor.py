"""Sensor entities for Omo Lavanderia integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.models import MachineStatus
from .const import DOMAIN
from .coordinator import OmoLavanderiaCoordinator
from .entity import OmoLavanderiaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from config entry.

    Args:
        hass: Home Assistant instance.
        entry: Config entry.
        async_add_entities: Callback to add entities.
    """
    coordinator: OmoLavanderiaCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    if coordinator.data:
        # Add per-machine sensors
        for machine_id in coordinator.data.machines:
            entities.extend(
                [
                    OmoRemainingTimeSensor(coordinator, machine_id),
                    OmoCycleTimeSensor(coordinator, machine_id),
                    OmoPriceSensor(coordinator, machine_id),
                    OmoMachineStatusSensor(coordinator, machine_id),
                ]
            )

        # Add laundry-level sensors
        entities.append(OmoLaundryStatusSensor(coordinator))

    async_add_entities(entities)


class OmoRemainingTimeSensor(OmoLavanderiaEntity, SensorEntity):
    """Sensor for remaining cycle time."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "s"
    _attr_icon = "mdi:timer"

    def __init__(
        self, coordinator: OmoLavanderiaCoordinator, machine_id: str
    ) -> None:
        """Initialize remaining time sensor.

        Args:
            coordinator: The data update coordinator.
            machine_id: The ID of the machine.
        """
        super().__init__(coordinator, machine_id)
        self._attr_unique_id = f"{machine_id}_remaining_time"
        self._attr_translation_key = "remaining_time"

    @property
    def native_value(self) -> int | None:
        """Return the remaining time in seconds."""
        state = self.machine_state
        if state and state.is_in_use_by_me:
            return state.remaining_time_seconds
        return None


class OmoCycleTimeSensor(OmoLavanderiaEntity, SensorEntity):
    """Sensor for machine cycle time."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "min"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: OmoLavanderiaCoordinator, machine_id: str
    ) -> None:
        """Initialize cycle time sensor.

        Args:
            coordinator: The data update coordinator.
            machine_id: The ID of the machine.
        """
        super().__init__(coordinator, machine_id)
        self._attr_unique_id = f"{machine_id}_cycle_time"
        self._attr_translation_key = "cycle_time"

    @property
    def native_value(self) -> int | None:
        """Return the cycle time in minutes."""
        state = self.machine_state
        if state and state.machine:
            return state.machine.cycle_time
        return None


class OmoPriceSensor(OmoLavanderiaEntity, SensorEntity):
    """Sensor for machine price."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "BRL"
    _attr_icon = "mdi:currency-brl"

    def __init__(
        self, coordinator: OmoLavanderiaCoordinator, machine_id: str
    ) -> None:
        """Initialize price sensor.

        Args:
            coordinator: The data update coordinator.
            machine_id: The ID of the machine.
        """
        super().__init__(coordinator, machine_id)
        self._attr_unique_id = f"{machine_id}_price"
        self._attr_translation_key = "price"

    @property
    def native_value(self) -> float | None:
        """Return the machine price."""
        state = self.machine_state
        if state and state.machine:
            return state.machine.price
        return None


class OmoMachineStatusSensor(OmoLavanderiaEntity, SensorEntity):
    """Sensor for machine status."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["available", "in_use", "in_use_by_me", "unavailable"]

    def __init__(
        self, coordinator: OmoLavanderiaCoordinator, machine_id: str
    ) -> None:
        """Initialize status sensor.

        Args:
            coordinator: The data update coordinator.
            machine_id: The ID of the machine.
        """
        super().__init__(coordinator, machine_id)
        self._attr_unique_id = f"{machine_id}_status"
        self._attr_translation_key = "machine_status"

    @property
    def native_value(self) -> str | None:
        """Return the machine status."""
        state = self.machine_state
        if state is None:
            return None

        if state.is_in_use_by_me:
            return "in_use_by_me"

        if state.is_available:
            return "available"

        if state.machine.status == MachineStatus.IN_USE:
            return "in_use"

        # Covers OUT_OF_ORDER, RESERVED, OFFLINE
        return "unavailable"


class OmoLaundryStatusSensor(SensorEntity):
    """Sensor for laundry status."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["open", "closed", "blocked"]

    def __init__(self, coordinator: OmoLavanderiaCoordinator) -> None:
        """Initialize laundry status sensor.

        Args:
            coordinator: The data update coordinator.
        """
        self.coordinator = coordinator
        laundry = coordinator.data.laundry if coordinator.data else None
        laundry_id = laundry.id if laundry else "unknown"

        self._attr_unique_id = f"{laundry_id}_laundry_status"
        self._attr_translation_key = "laundry_status"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the laundry."""
        laundry = self.coordinator.data.laundry if self.coordinator.data else None

        return DeviceInfo(
            identifiers={(DOMAIN, laundry.id if laundry else "unknown")},
            name=laundry.name if laundry else "Laundry",
            manufacturer="Omo Lavanderia",
            model="Laundry Location",
        )

    @property
    def native_value(self) -> str | None:
        """Return the laundry status."""
        if self.coordinator.data is None:
            return None

        laundry = self.coordinator.data.laundry

        if laundry.is_blocked:
            return "blocked"

        if laundry.is_closed:
            return "closed"

        return "open"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
