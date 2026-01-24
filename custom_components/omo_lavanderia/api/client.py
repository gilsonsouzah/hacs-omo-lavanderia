"""API client for Omo Lavanderia (Machine Guardian API)."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from ..const import API_BASE_URL, APP_VERSION
from .auth import OmoAuth
from .exceptions import OmoApiError, OmoAuthError
from .models import (
    ActiveOrder,
    Laundry,
    PaymentCard,
    UserInfo,
)

_LOGGER = logging.getLogger(__name__)


class OmoLavanderiaApiClient:
    """Async API client for Omo Lavanderia service.

    This client handles all communication with the Machine Guardian API,
    including authentication, token refresh, and all laundry-related operations.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
    ) -> None:
        """Initialize the API client.

        Args:
            session: aiohttp ClientSession for making HTTP requests.
            username: User's email/username for authentication.
            password: User's password for authentication.
        """
        self._session = session
        self._username = username
        self._password = password
        self._auth: OmoAuth | None = None
        self._base_url = API_BASE_URL

    @property
    def is_authenticated(self) -> bool:
        """Check if client has valid authentication."""
        return self._auth is not None and not self._auth.is_expired()

    @property
    def auth(self) -> OmoAuth | None:
        """Get current authentication state."""
        return self._auth

    def _get_headers(self, include_auth: bool = True) -> dict[str, str]:
        """Get standard headers for API requests.

        Args:
            include_auth: Whether to include Authorization header.

        Returns:
            Dictionary of headers.
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-app-version": APP_VERSION,
            "ngrok-skip-browser-warning": "69420",
        }

        if include_auth and self._auth:
            headers["Authorization"] = f"Bearer {self._auth.access_token}"

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
        """Make an HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            endpoint: API endpoint path (without base URL).
            data: JSON body data for POST/PUT requests.
            params: Query parameters for the request.
            include_auth: Whether to include auth header.
            retry_on_401: Whether to retry with fresh token on 401.

        Returns:
            Parsed JSON response.

        Raises:
            OmoAuthError: If authentication fails.
            OmoApiError: If API request fails.
        """
        url = f"{self._base_url}{endpoint}"
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

                # Handle 401 Unauthorized
                if response.status == 401:
                    if retry_on_401 and include_auth:
                        _LOGGER.debug("Token expired, attempting refresh")
                        await self._refresh_token()
                        return await self._request(
                            method,
                            endpoint,
                            data,
                            params,
                            include_auth,
                            retry_on_401=False,
                        )
                    raise OmoAuthError("Authentication failed")

                # Handle other error responses
                if response.status >= 400:
                    raise OmoApiError(
                        f"API error: {response_text}",
                        status_code=response.status,
                    )

                # Parse JSON response
                if response_text:
                    try:
                        return await response.json()
                    except aiohttp.ContentTypeError:
                        return {"raw": response_text}
                return {}

        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP request failed: %s", err)
            raise OmoApiError(f"Connection error: {err}") from err

    async def _refresh_token(self) -> None:
        """Refresh the access token using the refresh token.

        Raises:
            OmoAuthError: If token refresh fails.
        """
        if not self._auth or not self._auth.refresh_token:
            _LOGGER.debug("No refresh token available, performing full login")
            await self.async_login()
            return

        try:
            response = await self._request(
                "POST",
                "/auth/refresh",
                data={"refreshToken": self._auth.refresh_token},
                include_auth=False,
                retry_on_401=False,
            )

            self._auth.update_tokens(
                access_token=response.get("accessToken", response.get("access_token", "")),
                refresh_token=response.get("refreshToken", response.get("refresh_token")),
                expires_in=response.get("expiresIn", response.get("expires_in", 3600)),
            )
            _LOGGER.debug("Token refreshed successfully")

        except OmoApiError:
            _LOGGER.debug("Token refresh failed, performing full login")
            await self.async_login()

    async def async_login(self) -> OmoAuth:
        """Authenticate with the API.

        Performs login with username and password to obtain
        access and refresh tokens.

        Returns:
            OmoAuth instance with authentication tokens.

        Raises:
            OmoAuthError: If login fails.
        """
        device_id = OmoAuth.generate_device_id(self._username)

        login_data = {
            "username": self._username,
            "password": self._password,
            "isPassportLogin": False,
            "deviceId": device_id,
        }

        try:
            response = await self._request(
                "POST",
                "/auth/login",
                data=login_data,
                include_auth=False,
                retry_on_401=False,
            )

            self._auth = OmoAuth.from_login_response(response, self._username)
            _LOGGER.info("Successfully logged in as %s", self._username)
            return self._auth

        except OmoApiError as err:
            _LOGGER.error("Login failed: %s", err)
            raise OmoAuthError(f"Login failed: {err.message}") from err

    async def async_get_user(self) -> UserInfo:
        """Get current user information.

        Returns:
            UserInfo instance with user details.

        Raises:
            OmoApiError: If request fails.
        """
        await self._ensure_authenticated()

        response = await self._request("GET", "/user")
        return UserInfo.from_dict(response)

    async def async_get_laundries(
        self,
        lat: float,
        lon: float,
        laundry_type: str = "OLC",
        page: int = 1,
    ) -> list[Laundry]:
        """Get list of laundries near a location.

        Args:
            lat: Latitude coordinate.
            lon: Longitude coordinate.
            laundry_type: Type of laundry (default: "OLC").
            page: Page number for pagination.

        Returns:
            List of Laundry instances.

        Raises:
            OmoApiError: If request fails.
        """
        await self._ensure_authenticated()

        params = {
            "page": page,
            "type": laundry_type,
            "lat": lat,
            "lon": lon,
        }

        response = await self._request(
            "GET",
            "/laundry/paginated",
            params=params,
        )

        # Handle paginated response
        laundries_data = response.get("data", response.get("laundries", []))
        if isinstance(response, list):
            laundries_data = response

        return [Laundry.from_dict(l) for l in laundries_data]

    async def async_get_laundry(self, laundry_id: str) -> Laundry:
        """Get detailed information about a specific laundry.

        Args:
            laundry_id: Unique identifier of the laundry.

        Returns:
            Laundry instance with machine details.

        Raises:
            OmoApiError: If request fails.
        """
        await self._ensure_authenticated()

        response = await self._request("GET", f"/laundry/{laundry_id}")
        return Laundry.from_dict(response)

    async def async_get_active_orders(self) -> list[ActiveOrder]:
        """Get list of user's active orders.

        Returns:
            List of ActiveOrder instances.

        Raises:
            OmoApiError: If request fails.
        """
        await self._ensure_authenticated()

        response = await self._request("GET", "/order/actives")

        # Handle response format
        orders_data = response.get("data", response.get("orders", []))
        if isinstance(response, list):
            orders_data = response

        return [ActiveOrder.from_dict(o) for o in orders_data]

    async def async_get_payment_cards(self) -> list[PaymentCard]:
        """Get list of user's payment cards.

        Returns:
            List of PaymentCard instances.

        Raises:
            OmoApiError: If request fails.
        """
        await self._ensure_authenticated()

        response = await self._request("GET", "/payment/card")

        # Handle response format
        cards_data = response.get("data", response.get("cards", []))
        if isinstance(response, list):
            cards_data = response

        return [PaymentCard.from_dict(c) for c in cards_data]

    async def async_start_machine(
        self,
        machine_id: str,
        service_id: str,
        card_id: str,
    ) -> ActiveOrder:
        """Start a machine by creating an order and completing checkout.

        This method handles the full checkout flow:
        1. Create order with machine and service
        2. Process payment with selected card
        3. Start the machine

        Args:
            machine_id: ID of the machine to start.
            service_id: ID of the service/cycle to use.
            card_id: ID of the payment card to charge.

        Returns:
            ActiveOrder instance representing the started order.

        Raises:
            OmoApiError: If any step of the checkout fails.
        """
        await self._ensure_authenticated()

        # Step 1: Create order
        order_data = {
            "machineId": machine_id,
            "serviceId": service_id,
        }

        order_response = await self._request(
            "POST",
            "/order",
            data=order_data,
        )

        order_id = order_response.get("id", order_response.get("orderId"))
        if not order_id:
            raise OmoApiError("Failed to create order: no order ID returned")

        _LOGGER.debug("Created order %s", order_id)

        # Step 2: Process payment and start machine
        checkout_data = {
            "orderId": order_id,
            "cardId": card_id,
        }

        checkout_response = await self._request(
            "POST",
            "/order/checkout",
            data=checkout_data,
        )

        _LOGGER.info("Successfully started machine %s with order %s", machine_id, order_id)

        return ActiveOrder.from_dict(checkout_response)

    async def _ensure_authenticated(self) -> None:
        """Ensure the client is authenticated.

        Automatically logs in if not authenticated or token is expired.

        Raises:
            OmoAuthError: If authentication fails.
        """
        if not self._auth:
            await self.async_login()
        elif self._auth.is_expired():
            await self._refresh_token()

    def set_auth(self, auth: OmoAuth) -> None:
        """Set authentication state from external source.

        Useful for restoring auth state from Home Assistant storage.

        Args:
            auth: OmoAuth instance to use.
        """
        self._auth = auth

    async def async_close(self) -> None:
        """Close the API client.

        Note: Does not close the aiohttp session as it's managed externally.
        """
        self._auth = None
        _LOGGER.debug("API client closed")
