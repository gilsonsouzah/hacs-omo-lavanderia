"""Base entity for Omo Lavanderia."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.models import MachineType
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
        is_dryer = machine and machine.machine_type == MachineType.DRYER
        
        # Use friendly names for device type
        type_name = "Secadora" if is_dryer else "Lavadora"
        laundry_short = laundry.name.split(" - ")[-1][:20] if laundry else "Omo"

        return DeviceInfo(
            identifiers={(DOMAIN, self._machine_id)},
            name=f"{type_name} {machine_name}",
            manufacturer="Omo Lavanderia",
            model=machine.model if machine else None,
            suggested_area=laundry_short,
        )
