"""The Omo Lavanderia integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api.client import OmoLavanderiaApiClient
from .api.exceptions import OmoApiError, OmoAuthError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_LAUNDRY_ID,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN_EXPIRES_AT,
    DOMAIN,
)
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

    session = async_get_clientsession(hass)

    # Create API client
    client = OmoLavanderiaApiClient(
        session=session,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    # Set stored tokens if available
    if entry.data.get(CONF_ACCESS_TOKEN):
        client.set_tokens(
            access_token=entry.data[CONF_ACCESS_TOKEN],
            refresh_token=entry.data.get(CONF_REFRESH_TOKEN, ""),
            expires_at=entry.data.get(CONF_TOKEN_EXPIRES_AT, 0),
        )

    # Test connection and refresh tokens if needed
    try:
        if client.is_token_expired():
            _LOGGER.debug("Token expired, performing login")
            await client.async_login()

            # Update config entry with new tokens
            hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    CONF_ACCESS_TOKEN: client.access_token,
                    CONF_REFRESH_TOKEN: client.refresh_token,
                    CONF_TOKEN_EXPIRES_AT: client.token_expires_at,
                },
            )
    except OmoAuthError as err:
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
    except OmoApiError as err:
        raise ConfigEntryNotReady(f"API error: {err}") from err

    # Create coordinator
    coordinator = OmoLavanderiaCoordinator(
        hass=hass,
        client=client,
        laundry_id=entry.data[CONF_LAUNDRY_ID],
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
