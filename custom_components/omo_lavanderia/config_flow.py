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
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CARD_DISPLAY,
    CONF_CARD_ID,
    CONF_LAUNDRY_ID,
    CONF_LAUNDRY_NAME,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN_EXPIRES_AT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

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
        self._client: OmoLavanderiaApiClient | None = None
        self._username: str = ""
        self._password: str = ""
        self._laundries: dict[str, str] = {}
        self._cards: dict[str, str] = {}
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

            await self.async_set_unique_id(self._username.lower())
            self._abort_if_unique_id_configured()

            try:
                session = async_get_clientsession(self.hass)
                self._client = OmoLavanderiaApiClient(
                    session=session,
                    username=self._username,
                    password=self._password,
                )
                await self._client.async_login()
                return await self.async_step_select_laundry()

            except OmoAuthError:
                errors["base"] = "invalid_auth"
            except (OmoApiError, aiohttp.ClientError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during login")
                errors["base"] = "unknown"

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
            self._selected_laundry_id = user_input[CONF_LAUNDRY_ID]
            self._selected_laundry_name = self._laundries.get(
                self._selected_laundry_id, ""
            )
            return await self.async_step_select_card()

        if not self._laundries and self._client:
            try:
                laundries = await self._client.async_get_laundries(laundry_type="OLC")
                self._laundries = {l.id: l.name for l in laundries}

                if not self._laundries:
                    errors["base"] = "no_laundries"

            except (OmoApiError, OmoAuthError, aiohttp.ClientError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception fetching laundries")
                errors["base"] = "unknown"

        if errors or not self._laundries:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors or {"base": "no_laundries"},
            )

        return self.async_show_form(
            step_id="select_laundry",
            data_schema=vol.Schema(
                {vol.Required(CONF_LAUNDRY_ID): vol.In(self._laundries)}
            ),
            errors=errors,
        )

    async def async_step_select_card(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle step 3: select payment card."""
        errors: dict[str, str] = {}

        if user_input is not None:
            card_id = user_input[CONF_CARD_ID]
            card_display = self._cards.get(card_id, "")

            return self.async_create_entry(
                title=self._selected_laundry_name or "Omo Lavanderia",
                data={
                    CONF_USERNAME: self._username,
                    CONF_PASSWORD: self._password,
                    CONF_ACCESS_TOKEN: self._client.access_token if self._client else "",
                    CONF_REFRESH_TOKEN: self._client.refresh_token if self._client else "",
                    CONF_TOKEN_EXPIRES_AT: self._client.token_expires_at if self._client else 0,
                    CONF_LAUNDRY_ID: self._selected_laundry_id,
                    CONF_LAUNDRY_NAME: self._selected_laundry_name,
                    CONF_CARD_ID: card_id,
                    CONF_CARD_DISPLAY: card_display,
                },
            )

        if not self._cards and self._client:
            try:
                cards = await self._client.async_get_payment_cards()
                self._cards = {c.id: c.display_name for c in cards}

                if not self._cards:
                    errors["base"] = "no_cards"

            except (OmoApiError, OmoAuthError, aiohttp.ClientError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception fetching cards")
                errors["base"] = "unknown"

        if errors or not self._cards:
            return self.async_show_form(
                step_id="select_laundry",
                data_schema=vol.Schema(
                    {vol.Required(CONF_LAUNDRY_ID): vol.In(self._laundries)}
                ),
                errors=errors or {"base": "no_cards"},
            )

        return self.async_show_form(
            step_id="select_card",
            data_schema=vol.Schema(
                {vol.Required(CONF_CARD_ID): vol.In(self._cards)}
            ),
            errors=errors,
        )
