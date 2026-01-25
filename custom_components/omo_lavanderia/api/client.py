"""API client for Omo Lavanderia (Machine Guardian API)."""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

import aiohttp

from ..const import API_BASE_URL, APP_VERSION
from .exceptions import OmoApiError, OmoAuthError
from .models import ActiveOrder, Laundry, LaundryMachine, PaymentCard

_LOGGER = logging.getLogger(__name__)


class OmoLavanderiaApiClient:
    """Async API client for Omo Lavanderia service."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._username = username
        self._password = password
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expires_at: int = 0
        self._device_id = self._generate_device_id(username)

    @staticmethod
    def _generate_device_id(username: str) -> str:
        """Generate a consistent device ID based on username."""
        hash_input = f"omo_lavanderia_{username}".encode("utf-8")
        return hashlib.sha256(hash_input).hexdigest()

    def set_tokens(
        self,
        access_token: str,
        refresh_token: str,
        expires_at: int,
    ) -> None:
        """Set authentication tokens."""
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_expires_at = expires_at

    @property
    def access_token(self) -> str | None:
        """Get current access token."""
        return self._access_token

    @property
    def refresh_token(self) -> str | None:
        """Get current refresh token."""
        return self._refresh_token

    @property
    def token_expires_at(self) -> int:
        """Get token expiration timestamp."""
        return self._token_expires_at

    def is_token_expired(self) -> bool:
        """Check if token is expired or about to expire."""
        if self._token_expires_at == 0:
            return True
        
        # API returns timestamp in milliseconds, convert to seconds for comparison
        expires_at_seconds = self._token_expires_at
        if self._token_expires_at > 9999999999:  # If > year 2286, it's in milliseconds
            expires_at_seconds = self._token_expires_at / 1000
        
        # Token is expired if current time is within 5 minutes of expiration
        return time.time() >= (expires_at_seconds - 300)

    def _get_headers(self, include_auth: bool = True) -> dict[str, str]:
        """Get standard headers for API requests."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-app-version": APP_VERSION,
            "ngrok-skip-browser-warning": "69420",
        }
        if include_auth and self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        include_auth: bool = True,
        retry_on_401: bool = True,
    ) -> dict[str, Any]:
        """Make an HTTP request to the API."""
        url = f"{API_BASE_URL}{endpoint}"
        headers = self._get_headers(include_auth)

        _LOGGER.debug("Making %s request to %s", method, url)

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                json=data,
                params=params,
            ) as response:
                response_text = await response.text()

                _LOGGER.debug(
                    "Response status: %s, body: %s",
                    response.status,
                    response_text[:500] if response_text else "empty",
                )

                if response.status == 401:
                    if retry_on_401 and include_auth:
                        _LOGGER.debug("Token expired, attempting refresh/login")
                        await self.async_login()
                        return await self._request(
                            method, endpoint, data, params, include_auth, False
                        )
                    raise OmoAuthError("Authentication failed")

                if response.status >= 400:
                    raise OmoApiError(
                        f"API error: {response_text}", status_code=response.status
                    )

                if response_text:
                    result = await response.json()
                    # API wraps responses in "data" field
                    if isinstance(result, dict) and "data" in result:
                        return result["data"]
                    return result
                return {}

        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP request failed: %s", err)
            raise OmoApiError(f"Connection error: {err}") from err

    async def async_login(self) -> None:
        """Authenticate with the API."""
        login_data = {
            "username": self._username,
            "password": self._password,
            "isPassportLogin": False,
            "deviceId": self._device_id,
        }

        try:
            url = f"{API_BASE_URL}/auth/login"
            headers = self._get_headers(include_auth=False)

            async with self._session.post(
                url, headers=headers, json=login_data
            ) as response:
                if response.status >= 400:
                    raise OmoAuthError("Login failed")

                result = await response.json()
                data = result.get("data", result)

                self._access_token = data.get("accessToken", "")
                self._refresh_token = data.get("refreshToken", "")
                # API returns expiration as timestamp (sometimes in ms, sometimes in s)
                expires_in = data.get("accessTokenExpiresIn", 0)
                # Normalize to seconds
                if expires_in > 9999999999:  # If > year 2286, it's in milliseconds
                    expires_in = expires_in / 1000
                self._token_expires_at = int(expires_in)

                _LOGGER.info(
                    "Successfully logged in as %s, token expires at %s",
                    self._username,
                    self._token_expires_at,
                )

        except aiohttp.ClientError as err:
            raise OmoAuthError(f"Login failed: {err}") from err

    async def async_get_laundries(
        self,
        laundry_type: str = "OLC",
        page: int = 1,
    ) -> list[Laundry]:
        """Get list of laundries."""
        params = {
            "page": page,
            "type": laundry_type,
            "lat": 0,
            "lon": 0,
            "term": "",
        }

        data = await self._request("GET", "/laundry/paginated", params=params)
        items = data.get("items", []) if isinstance(data, dict) else []
        return [Laundry.from_list_item(item) for item in items]

    async def async_get_laundry(self, laundry_id: str) -> Laundry:
        """Get laundry details including machines."""
        data = await self._request("GET", f"/laundry/{laundry_id}")
        return Laundry.from_detail(data)

    async def async_get_active_orders(self) -> list[ActiveOrder]:
        """Get active orders for current user."""
        data = await self._request("GET", "/order/actives")
        if isinstance(data, list):
            return [ActiveOrder.from_dict(order) for order in data]
        return []

    async def async_get_payment_cards(self) -> list[PaymentCard]:
        """Get user's payment cards."""
        data = await self._request("GET", "/user/credit-card")
        if isinstance(data, list):
            return [PaymentCard.from_dict(card) for card in data]
        return []

    async def async_start_machine(
        self,
        machine_id: str,
        card_id: str,
        laundry_id: str,
    ) -> dict[str, Any]:
        """Start a machine cycle with payment."""
        payment_data = {
            "payment_method": "CREDIT_CARD",
            "machines_id": [machine_id],
            "card_id": card_id,
            "laundry_id": laundry_id,
        }

        data = await self._request("POST", "/order/payment-checkout", data=payment_data)
        return data

    def get_all_machines(self, laundry: Laundry) -> list[LaundryMachine]:
        """Get all machines from a laundry."""
        return laundry.washers + laundry.dryers
