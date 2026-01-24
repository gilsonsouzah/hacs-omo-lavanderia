"""Base entity for Omo Lavanderia integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MachineState, OmoLavanderiaCoordinator


class OmoLavanderiaEntity(CoordinatorEntity[OmoLavanderiaCoordinator]):
    """Base entity for Omo Lavanderia."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OmoLavanderiaCoordinator, machine_id: str) -> None:
        """Initialize entity.

        Args:
            coordinator: The data update coordinator.
            machine_id: The ID of the machine this entity represents.
        """
        super().__init__(coordinator)
        self._machine_id = machine_id

    @property
    def machine_state(self) -> MachineState | None:
        """Get current machine state from coordinator."""
        return self.coordinator.get_machine_state(self._machine_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this machine."""
        machine = self.machine_state.machine if self.machine_state else None
        laundry = self.coordinator.data.laundry if self.coordinator.data else None

        return DeviceInfo(
            identifiers={(DOMAIN, self._machine_id)},
            name=f"{machine.display_name if machine else 'Machine'} - {machine.type.value if machine else ''}",
            manufacturer="Omo Lavanderia",
            model=machine.model if machine else None,
            serial_number=machine.serial if machine else None,
            via_device=(DOMAIN, laundry.id) if laundry else None,
        )
