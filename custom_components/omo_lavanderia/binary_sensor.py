"""Binary sensor platform for Omo Lavanderia integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OmoLavanderiaCoordinator
from .entity import OmoLavanderiaEntity


class OmoMachineAvailableBinarySensor(OmoLavanderiaEntity, BinarySensorEntity):
    """Binary sensor indicating if machine is available."""

    _attr_translation_key = "available"

    def __init__(self, coordinator: OmoLavanderiaCoordinator, machine_id: str) -> None:
        """Initialize the available binary sensor.

        Args:
            coordinator: The data update coordinator.
            machine_id: The ID of the machine this entity represents.
        """
        super().__init__(coordinator, machine_id)
        self._attr_unique_id = f"{machine_id}_available"

    @property
    def is_on(self) -> bool | None:
        """Return True if machine is available."""
        state = self.machine_state
        if state is None:
            return None
        return state.is_available

    @property
    def icon(self) -> str:
        """Return icon based on availability."""
        return "mdi:washing-machine" if self.is_on else "mdi:washing-machine-off"


class OmoMachineInUseByMeBinarySensor(OmoLavanderiaEntity, BinarySensorEntity):
    """Binary sensor indicating if machine is being used by current user."""

    _attr_translation_key = "in_use_by_me"

    def __init__(self, coordinator: OmoLavanderiaCoordinator, machine_id: str) -> None:
        """Initialize the in-use-by-me binary sensor.

        Args:
            coordinator: The data update coordinator.
            machine_id: The ID of the machine this entity represents.
        """
        super().__init__(coordinator, machine_id)
        self._attr_unique_id = f"{machine_id}_in_use_by_me"

    @property
    def is_on(self) -> bool | None:
        """Return True if machine is being used by current user."""
        state = self.machine_state
        if state is None:
            return None
        return state.is_in_use_by_me

    @property
    def icon(self) -> str:
        """Return icon based on usage state."""
        return "mdi:account-check" if self.is_on else "mdi:account"


class OmoLaundryOpenBinarySensor(
    CoordinatorEntity[OmoLavanderiaCoordinator], BinarySensorEntity
):
    """Binary sensor indicating if laundry is open."""

    _attr_has_entity_name = True
    _attr_translation_key = "laundry_open"
    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(self, coordinator: OmoLavanderiaCoordinator) -> None:
        """Initialize the laundry open binary sensor.

        Args:
            coordinator: The data update coordinator.
        """
        super().__init__(coordinator)
        laundry = coordinator.data.laundry if coordinator.data else None
        self._laundry_id = laundry.id if laundry else "unknown"
        self._attr_unique_id = f"{self._laundry_id}_is_open"

    @property
    def is_on(self) -> bool | None:
        """Return True if laundry is open (not closed and not blocked)."""
        if self.coordinator.data is None:
            return None
        laundry = self.coordinator.data.laundry
        if laundry is None:
            return None
        return not laundry.isClosed and not laundry.isBlocked

    @property
    def icon(self) -> str:
        """Return icon based on open state."""
        return "mdi:door-open" if self.is_on else "mdi:door-closed"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the laundry."""
        laundry = self.coordinator.data.laundry if self.coordinator.data else None
        return DeviceInfo(
            identifiers={(DOMAIN, self._laundry_id)},
            name=laundry.name if laundry else "Laundry",
            manufacturer="Omo Lavanderia",
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from config entry.

    Args:
        hass: Home Assistant instance.
        entry: Config entry for this integration.
        async_add_entities: Callback to add entities.
    """
    coordinator: OmoLavanderiaCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BinarySensorEntity] = []

    # Add per-machine binary sensors
    if coordinator.data and coordinator.data.machines:
        for machine_id in coordinator.data.machines:
            entities.extend([
                OmoMachineAvailableBinarySensor(coordinator, machine_id),
                OmoMachineInUseByMeBinarySensor(coordinator, machine_id),
            ])

    # Add laundry-level binary sensor
    entities.append(OmoLaundryOpenBinarySensor(coordinator))

    async_add_entities(entities)
