"""Base entity for Omo Lavanderia."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MachineState, OmoLavanderiaCoordinator


class OmoLavanderiaEntity(CoordinatorEntity[OmoLavanderiaCoordinator]):
    """Base entity for Omo Lavanderia."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OmoLavanderiaCoordinator,
        machine_id: str,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self._machine_id = machine_id

    @property
    def machine_state(self) -> MachineState | None:
        """Get current machine state from coordinator."""
        return self.coordinator.get_machine_state(self._machine_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this machine."""
        state = self.machine_state
        machine = state.machine if state else None
        laundry = self.coordinator.data.laundry if self.coordinator.data else None

        machine_name = machine.display_name if machine else "Machine"
        machine_type = machine.machine_type.value if machine else "UNKNOWN"

        return DeviceInfo(
            identifiers={(DOMAIN, self._machine_id)},
            name=f"{machine_name} ({machine_type})",
            manufacturer="Omo Lavanderia",
            model=machine.model if machine else None,
            via_device=(DOMAIN, laundry.id) if laundry else None,
        )


class OmoLavanderiaLaundryEntity(CoordinatorEntity[OmoLavanderiaCoordinator]):
    """Base entity for laundry-level entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OmoLavanderiaCoordinator) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        laundry = coordinator.data.laundry if coordinator.data else None
        self._laundry_id = laundry.id if laundry else "unknown"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the laundry."""
        laundry = self.coordinator.data.laundry if self.coordinator.data else None

        return DeviceInfo(
            identifiers={(DOMAIN, self._laundry_id)},
            name=laundry.name if laundry else "Lavanderia",
            manufacturer="Omo Lavanderia",
        )
