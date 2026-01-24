"""Config flow for Omo Lavanderia integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api.client import OmoLavanderiaApiClient
from .api.exceptions import OmoApiError, OmoAuthError
from .const import CONF_CARD_ID, CONF_LAUNDRY_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Schema for step 1: User login
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class OmoLavanderiaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Omo Lavanderia."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._username: str = ""
        self._password: str = ""
        self._access_token: str = ""
        self._refresh_token: str = ""
        self._token_expires_at: int = 0
        self._laundries: dict[str, str] = {}  # id -> name mapping
        self._cards: dict[str, str] = {}  # id -> display mapping
        self._selected_laundry_id: str = ""
        self._selected_laundry_name: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: user login."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]

            # Set unique ID and abort if already configured
            await self.async_set_unique_id(self._username.lower())
            self._abort_if_unique_id_configured()

            try:
                # Validate credentials by logging in
                session = async_get_clientsession(self.hass)
                client = OmoLavanderiaApiClient(
                    session=session,
                    username=self._username,
                    password=self._password,
                )

                auth = await client.async_login()

                # Store tokens for later
                self._access_token = auth.access_token
                self._refresh_token = auth.refresh_token
                self._token_expires_at = int(auth.expires_at.timestamp())

                # Proceed to laundry selection
                return await self.async_step_select_laundry()

            except OmoAuthError:
                errors["base"] = "invalid_auth"
            except (OmoApiError, aiohttp.ClientError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during login")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_select_laundry(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle step 2: select laundry location."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # User selected a laundry
            self._selected_laundry_id = user_input[CONF_LAUNDRY_ID]
            self._selected_laundry_name = self._laundries.get(
                self._selected_laundry_id, ""
            )

            # Proceed to card selection
            return await self.async_step_select_card()

        # Fetch laundries if not already cached
        if not self._laundries:
            try:
                session = async_get_clientsession(self.hass)
                client = OmoLavanderiaApiClient(
                    session=session,
                    username=self._username,
                    password=self._password,
                )

                # Restore auth state
                from .api.auth import OmoAuth
                from datetime import datetime, timezone

                auth = OmoAuth(
                    access_token=self._access_token,
                    refresh_token=self._refresh_token,
                    expires_at=datetime.fromtimestamp(
                        self._token_expires_at, tz=timezone.utc
                    ),
                    device_id=OmoAuth.generate_device_id(self._username),
                )
                client.set_auth(auth)

                # Fetch OLC type laundries (using 0,0 as coords for user's laundries)
                laundries = await client.async_get_laundries(
                    lat=0.0,
                    lon=0.0,
                    laundry_type="OLC",
                )

                # Filter for OLC type and build mapping
                self._laundries = {
                    laundry.id: laundry.name
                    for laundry in laundries
                    if laundry.type == "OLC"
                }

                if not self._laundries:
                    # Include all returned laundries if OLC filter returns empty
                    self._laundries = {
                        laundry.id: laundry.name for laundry in laundries
                    }

                if not self._laundries:
                    errors["base"] = "no_laundries"

            except (OmoApiError, OmoAuthError, aiohttp.ClientError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception fetching laundries")
                errors["base"] = "cannot_connect"

        if errors:
            # Go back to user step if we can't fetch laundries
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
            )

        # Build schema with laundry options
        laundry_schema = vol.Schema(
            {
                vol.Required(CONF_LAUNDRY_ID): vol.In(self._laundries),
            }
        )

        return self.async_show_form(
            step_id="select_laundry",
            data_schema=laundry_schema,
            errors=errors,
        )

    async def async_step_select_card(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle step 3: select payment card."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # User selected a card - create the config entry
            card_id = user_input[CONF_CARD_ID]
            card_display = self._cards.get(card_id, "")

            return self.async_create_entry(
                title=self._selected_laundry_name or "Omo Lavanderia",
                data={
                    CONF_USERNAME: self._username,
                    CONF_PASSWORD: self._password,
                    "access_token": self._access_token,
                    "refresh_token": self._refresh_token,
                    "token_expires_at": self._token_expires_at,
                    CONF_LAUNDRY_ID: self._selected_laundry_id,
                    "laundry_name": self._selected_laundry_name,
                    CONF_CARD_ID: card_id,
                    "card_display": card_display,
                },
            )

        # Fetch payment cards if not already cached
        if not self._cards:
            try:
                session = async_get_clientsession(self.hass)
                client = OmoLavanderiaApiClient(
                    session=session,
                    username=self._username,
                    password=self._password,
                )

                # Restore auth state
                from .api.auth import OmoAuth
                from datetime import datetime, timezone

                auth = OmoAuth(
                    access_token=self._access_token,
                    refresh_token=self._refresh_token,
                    expires_at=datetime.fromtimestamp(
                        self._token_expires_at, tz=timezone.utc
                    ),
                    device_id=OmoAuth.generate_device_id(self._username),
                )
                client.set_auth(auth)

                cards = await client.async_get_payment_cards()

                # Build card display mapping (brand + last 4 digits)
                self._cards = {
                    card.id: f"{card.brand.lower()} **** {card.last_digits}"
                    for card in cards
                    if card.is_active
                }

                if not self._cards:
                    errors["base"] = "no_cards"

            except (OmoApiError, OmoAuthError, aiohttp.ClientError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception fetching cards")
                errors["base"] = "cannot_connect"

        if errors:
            # Show error on laundry step
            laundry_schema = vol.Schema(
                {
                    vol.Required(CONF_LAUNDRY_ID): vol.In(self._laundries),
                }
            )
            return self.async_show_form(
                step_id="select_laundry",
                data_schema=laundry_schema,
                errors=errors,
            )

        # Build schema with card options
        card_schema = vol.Schema(
            {
                vol.Required(CONF_CARD_ID): vol.In(self._cards),
            }
        )

        return self.async_show_form(
            step_id="select_card",
            data_schema=card_schema,
            errors=errors,
        )
