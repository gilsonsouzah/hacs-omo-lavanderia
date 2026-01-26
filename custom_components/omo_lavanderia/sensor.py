"""Sensor entities for Omo Lavanderia."""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
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
                OmoDiagnosticSensor(coordinator, machine_id),
            ])

    async_add_entities(entities)


class OmoRemainingTimeSensor(OmoLavanderiaEntity, SensorEntity):
    """Sensor for remaining cycle time."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "remaining_time"

    @property
    def icon(self) -> str:
        """Return icon based on machine type."""
        state = self.machine_state
        if state and state.machine:
            if state.machine.machine_type == MachineType.DRYER:
                return "mdi:tumble-dryer"
        return "mdi:washing-machine"

    def __init__(self, coordinator: OmoLavanderiaCoordinator, machine_id: str) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, machine_id)
        self._attr_unique_id = f"{machine_id}_remaining_time"

    @property
    def native_value(self) -> int | None:
        """Return remaining time in seconds.
        
        Only returns a value when the machine is actually running (IN_USE with time remaining).
        This prevents false triggers on automations when machine is just reserved.
        """
        state = self.machine_state
        if state and state.is_running and state.remaining_time_seconds is not None:
            return state.remaining_time_seconds
        return None

    @property
    def available(self) -> bool:
        """Return if sensor is available.
        
        Only available when machine is actually running.
        """
        state = self.machine_state
        return state is not None and state.is_running


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
    _attr_translation_key = "machine_status"

    @property
    def icon(self) -> str:
        """Return icon based on machine type and state."""
        state = self.machine_state
        is_dryer = state and state.machine and state.machine.machine_type == MachineType.DRYER
        
        if state and (state.is_in_use_by_me or not state.is_available):
            return "mdi:tumble-dryer-alert" if is_dryer else "mdi:washing-machine-alert"
        return "mdi:tumble-dryer" if is_dryer else "mdi:washing-machine"

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


class OmoDiagnosticSensor(OmoLavanderiaEntity, SensorEntity):
    """Diagnostic sensor for connectivity and session debugging.
    
    This sensor provides:
    - Token status and expiration info
    - Connection health metrics
    - Active order/session details when machine is in use
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:bug"
    _attr_translation_key = "diagnostic"

    def __init__(self, coordinator: OmoLavanderiaCoordinator, machine_id: str) -> None:
        """Initialize diagnostic sensor."""
        super().__init__(coordinator, machine_id)
        self._attr_unique_id = f"{machine_id}_diagnostic"

    @property
    def native_value(self) -> str:
        """Return connection status as main value."""
        token_status = self.coordinator.client.get_token_status()
        
        if not token_status["has_token"]:
            return "no_token"
        if token_status["is_expired"]:
            return "token_expired"
        if token_status["is_expiring_soon"]:
            return "token_expiring"
        if token_status["login_failures"] > 0:
            return "auth_issues"
        return "connected"

    @property
    def icon(self) -> str:
        """Return icon based on connection status."""
        status = self.native_value
        icons = {
            "connected": "mdi:check-network",
            "no_token": "mdi:network-off",
            "token_expired": "mdi:alert-circle",
            "token_expiring": "mdi:clock-alert",
            "auth_issues": "mdi:alert",
        }
        return icons.get(status, "mdi:bug")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed diagnostic attributes."""
        diagnostics = self.coordinator.get_diagnostics()
        state = self.machine_state
        
        # Base attributes from coordinator diagnostics
        attrs: dict[str, Any] = {
            # Token info
            "token_valid": not diagnostics["token"]["is_expired"],
            "token_expiring_soon": diagnostics["token"]["is_expiring_soon"],
            "token_expires_in_seconds": diagnostics["token"]["time_until_expiry_seconds"],
            "token_expires_at": (
                datetime.fromtimestamp(diagnostics["token"]["expires_at"]).isoformat()
                if diagnostics["token"]["expires_at"] > 0
                else None
            ),
            "login_failures": diagnostics["token"]["login_failures"],
            
            # Coordinator health
            "consecutive_errors": diagnostics["coordinator"]["consecutive_errors"],
            "last_successful_update": (
                datetime.fromtimestamp(
                    diagnostics["coordinator"]["last_successful_update"]
                ).isoformat()
                if diagnostics["coordinator"]["last_successful_update"] > 0
                else None
            ),
            "seconds_since_success": diagnostics["coordinator"]["seconds_since_success"],
            
            # Connection info
            "laundry_id": diagnostics["laundry_id"],
            "username": diagnostics["username"],
        }

        # Machine-specific info
        if state:
            attrs.update({
                "machine_id": state.machine.id if state.machine else None,
                "machine_code": state.machine.code if state.machine else None,
                "machine_status": state.machine.status.value if state.machine else None,
                "is_available": state.is_available,
                "is_in_use_by_me": state.is_in_use_by_me,
                "is_running": state.is_running,
                "usage_status": state.usage_status,
            })

            # Active order/session details when in use
            if state.is_in_use_by_me and state.order_id:
                attrs["order_id"] = state.order_id
                attrs["remaining_time_seconds"] = state.remaining_time_seconds
                
                # Find the full order details
                if self.coordinator.data and self.coordinator.data.active_orders:
                    for order in self.coordinator.data.active_orders:
                        if order.id == state.order_id:
                            attrs.update({
                                "order_laundry_name": order.laundry_name,
                                "order_total_price": order.total_price,
                                "order_status": order.status,
                            })
                            # Find this machine in the order
                            for order_machine in order.machines:
                                if order_machine.display_name == state.machine.display_name:
                                    attrs.update({
                                        "order_machine_status": order_machine.status,
                                        "order_machine_usage_status": order_machine.usage_status,
                                        "order_machine_remaining_time": order_machine.remaining_time,
                                    })
                                    break
                            break

        return attrs

    async def async_update(self) -> None:
        """Force token refresh if expired during update."""
        # Check and refresh token proactively
        if self.coordinator.client.is_token_expired():
            try:
                await self.coordinator.client.async_ensure_valid_token()
            except Exception as err:
                # Log but don't fail - the status will show the error
                logging.getLogger(__name__).debug("Token refresh failed: %s", err)
