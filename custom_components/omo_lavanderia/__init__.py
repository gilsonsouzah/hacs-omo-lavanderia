"""The Omo Lavanderia integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_LAUNDRY_ID,
    CONF_CARD_ID,
    SERVICE_START_CYCLE,
)
from .api.client import OmoLavanderiaApiClient
from .api.auth import OmoAuth
from .api.exceptions import OmoAuthError, OmoApiError
from .coordinator import OmoLavanderiaCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Omo Lavanderia from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create auth with tokens from config
    auth = OmoAuth(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )
    auth.access_token = entry.data.get(CONF_ACCESS_TOKEN)
    auth.refresh_token = entry.data.get(CONF_REFRESH_TOKEN)

    # Create API client
    api = OmoLavanderiaApiClient(auth)

    # Test connection and refresh tokens if needed
    try:
        if not auth.is_valid:
            _LOGGER.debug("Token expired, attempting login")
            await api.async_login()
            # Update config entry with new tokens
            hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    CONF_ACCESS_TOKEN: auth.access_token,
                    CONF_REFRESH_TOKEN: auth.refresh_token,
                },
            )
    except OmoAuthError as err:
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
    except OmoApiError as err:
        raise ConfigEntryNotReady(f"API error: {err}") from err

    # Create coordinator
    coordinator = OmoLavanderiaCoordinator(
        hass=hass,
        api=api,
        laundry_id=entry.data[CONF_LAUNDRY_ID],
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

        # Remove services if no more entries
        if not hass.data[DOMAIN]:
            await async_unload_services(hass)

    return unload_ok


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the integration."""
    # Check if services are already registered
    if hass.services.has_service(DOMAIN, SERVICE_START_CYCLE):
        return

    async def handle_start_cycle(call):
        """Handle start_cycle service call."""
        machine_id = call.data.get("machine_id")
        card_id = call.data.get("card_id")

        # Find the coordinator that has this machine
        for entry_id, coordinator in hass.data[DOMAIN].items():
            if coordinator.data and machine_id in coordinator.data.machines:
                # Use provided card_id or get from config
                if not card_id:
                    entry = hass.config_entries.async_get_entry(entry_id)
                    card_id = entry.data.get(CONF_CARD_ID) if entry else None

                if not card_id:
                    raise ValueError("No card_id provided and none configured")

                try:
                    await coordinator.api.async_start_machine(machine_id, card_id)
                    await coordinator.async_request_refresh()
                    return
                except OmoApiError as err:
                    raise ValueError(f"Failed to start machine: {err}") from err

        raise ValueError(f"Machine {machine_id} not found")

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_CYCLE,
        handle_start_cycle,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services."""
    hass.services.async_remove(DOMAIN, SERVICE_START_CYCLE)
