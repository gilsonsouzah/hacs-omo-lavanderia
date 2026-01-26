"""API client for Omo Lavanderia (Machine Guardian API)."""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Callable

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
        self._last_login_attempt: float = 0
        self._login_failures: int = 0
        self._device_id = self._generate_device_id(username)
        self._token_update_callback: Callable[[str, str, int], None] | None = None

    @staticmethod
    def _generate_device_id(username: str) -> str:
        """Generate a consistent device ID based on username."""
        hash_input = f"omo_lavanderia_{username}".encode("utf-8")
        return hashlib.sha256(hash_input).hexdigest()

    def set_token_update_callback(
        self, callback: Callable[[str, str, int], None]
    ) -> None:
        """Set callback to be called when tokens are updated."""
        self._token_update_callback = callback

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
        # Reset failure count when tokens are set successfully
        self._login_failures = 0

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

    @property
    def username(self) -> str:
        """Get username."""
        return self._username

    @property
    def login_failures(self) -> int:
        """Get number of consecutive login failures."""
        return self._login_failures

    @property
    def last_login_attempt(self) -> float:
        """Get timestamp of last login attempt."""
        return self._last_login_attempt

    def get_token_status(self) -> dict[str, Any]:
        """Get detailed token status for diagnostics."""
        now = time.time()
        expires_at_seconds = self._normalize_timestamp(self._token_expires_at)
        
        if expires_at_seconds > 0:
            time_until_expiry = expires_at_seconds - now
            is_expired = time_until_expiry <= 0
            is_expiring_soon = time_until_expiry <= 300  # 5 minutes
        else:
            time_until_expiry = 0
            is_expired = True
            is_expiring_soon = True

        return {
            "has_token": bool(self._access_token),
            "is_expired": is_expired,
            "is_expiring_soon": is_expiring_soon,
            "expires_at": expires_at_seconds,
            "time_until_expiry_seconds": max(0, int(time_until_expiry)),
            "login_failures": self._login_failures,
            "last_login_attempt": self._last_login_attempt,
        }

    def _normalize_timestamp(self, timestamp: int) -> float:
        """Normalize timestamp from ms to seconds if needed."""
        if timestamp == 0:
            return 0
        # If > year 2286, it's in milliseconds
        if timestamp > 9999999999:
            return timestamp / 1000
        return float(timestamp)

    def is_token_expired(self) -> bool:
        """Check if token is expired or about to expire."""
        if not self._access_token or self._token_expires_at == 0:
            return True
        
        expires_at_seconds = self._normalize_timestamp(self._token_expires_at)
        
        # Token is expired if current time is within 5 minutes of expiration
        return time.time() >= (expires_at_seconds - 300)

    def _should_rate_limit_login(self) -> bool:
        """Check if we should wait before attempting login again."""
        if self._login_failures == 0:
            return False
        
        # Exponential backoff: wait 2^failures seconds, max 5 minutes
        wait_time = min(2 ** self._login_failures, 300)
        time_since_last = time.time() - self._last_login_attempt
        
        return time_since_last < wait_time

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
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                response_text = await response.text()

                _LOGGER.debug(
                    "Response status: %s, body: %s",
                    response.status,
                    response_text[:500] if response_text else "empty",
                )

                if response.status == 401:
                    if retry_on_401 and include_auth:
                        _LOGGER.debug("Token expired (401), attempting refresh/login")
                        await self.async_ensure_valid_token()
                        return await self._request(
                            method, endpoint, data, params, include_auth, False
                        )
                    raise OmoAuthError("Authentication failed - token invalid")

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
        except TimeoutError as err:
            _LOGGER.error("Request timeout: %s", err)
            raise OmoApiError(f"Request timeout: {err}") from err

    async def async_ensure_valid_token(self) -> bool:
        """Ensure we have a valid token, refreshing if needed.
        
        Returns True if token is valid, raises exception otherwise.
        """
        if not self.is_token_expired():
            return True
        
        _LOGGER.info("Token expired or missing, performing login")
        await self.async_login()
        return True

    async def async_login(self) -> None:
        """Authenticate with the API."""
        # Rate limit login attempts
        if self._should_rate_limit_login():
            wait_time = min(2 ** self._login_failures, 300)
            raise OmoAuthError(
                f"Too many login failures ({self._login_failures}), "
                f"waiting {wait_time}s before retry"
            )

        self._last_login_attempt = time.time()

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
                url,
                headers=headers,
                json=login_data,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status >= 400:
                    self._login_failures += 1
                    response_text = await response.text()
                    _LOGGER.error(
                        "Login failed with status %s: %s",
                        response.status,
                        response_text[:200],
                    )
                    raise OmoAuthError(f"Login failed: HTTP {response.status}")

                result = await response.json()
                data = result.get("data", result)

                new_access_token = data.get("accessToken", "")
                new_refresh_token = data.get("refreshToken", "")
                expires_in = data.get("accessTokenExpiresIn", 0)
                
                if not new_access_token:
                    self._login_failures += 1
                    raise OmoAuthError("Login response missing access token")

                # Normalize expiration timestamp
                expires_at = int(self._normalize_timestamp(expires_in))

                # Update tokens
                self._access_token = new_access_token
                self._refresh_token = new_refresh_token
                self._token_expires_at = expires_at
                self._login_failures = 0  # Reset on success

                _LOGGER.info(
                    "Successfully logged in as %s, token expires at %s (in %d seconds)",
                    self._username,
                    self._token_expires_at,
                    max(0, expires_at - int(time.time())),
                )

                # Notify callback about token update
                if self._token_update_callback:
                    try:
                        self._token_update_callback(
                            new_access_token, new_refresh_token, expires_at
                        )
                    except Exception as err:
                        _LOGGER.warning("Token update callback failed: %s", err)

        except aiohttp.ClientError as err:
            self._login_failures += 1
            raise OmoAuthError(f"Login failed: {err}") from err
        except TimeoutError as err:
            self._login_failures += 1
            raise OmoAuthError(f"Login timeout: {err}") from err

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
        """Start a machine cycle with payment and unlock.
        
        This performs the full flow:
        1. POST /order/payment-checkout - Create order and process payment
        2. POST /machine/start-machine - Unlock the machine (if canUnlock=true)
        
        After unlock (usageStatus=READY), user must press physical button on machine.
        Then machine goes to IN_USE with remainingTime counting down.
        """
        # Step 1: Payment checkout
        payment_data = {
            "payment_method": "CREDIT_CARD",
            "machines_id": [machine_id],
            "card_id": card_id,
            "laundry_id": laundry_id,
        }

        _LOGGER.debug("Starting checkout for machine %s", machine_id)
        checkout_result = await self._request("POST", "/order/payment-checkout", data=payment_data)
        
        # Extract order_id from checkout response
        # API returns order_id in different places: order.id, orderId, or id
        order_id = None
        if isinstance(checkout_result, dict):
            # Try order.id first (most common based on Washer Machine.js)
            order_obj = checkout_result.get("order")
            if isinstance(order_obj, dict):
                order_id = order_obj.get("id")
            # Fallback to direct fields
            if not order_id:
                order_id = checkout_result.get("orderId") or checkout_result.get("id")
        
        if not order_id:
            _LOGGER.error("Checkout succeeded but no order_id returned: %s", checkout_result)
            return {"success": False, "error": "No order_id in checkout response"}
        
        _LOGGER.info("Checkout complete, order_id: %s, payment confirmed", order_id)
        
        # Step 2: Unlock/Start the machine
        # According to API flow, after payment the machine has canUnlock=true
        unlock_data = {
            "laundryId": laundry_id,
            "machineId": machine_id,
            "orderId": order_id,
        }
        
        _LOGGER.debug("Unlocking machine %s with order %s", machine_id, order_id)
        try:
            unlock_result = await self._request("POST", "/machine/start-machine", data=unlock_data)
            usage_status = unlock_result.get("usageStatus") if isinstance(unlock_result, dict) else None
            machine_name = unlock_result.get("machineName") if isinstance(unlock_result, dict) else machine_id
            
            _LOGGER.info(
                "Machine %s unlocked successfully, usageStatus: %s (press button to start)",
                machine_name,
                usage_status,
            )
            
            return {
                "success": True,
                "orderId": order_id,
                "machineId": machine_id,
                "usageStatus": usage_status,
                "message": "Machine unlocked - press button on machine to start cycle",
            }
            
        except OmoApiError as err:
            _LOGGER.warning(
                "Unlock request failed (machine may need manual unlock): %s. "
                "Payment was successful, order_id: %s",
                err,
                order_id,
            )
            # Return success with warning - payment was processed, user can unlock via app
            return {
                "success": True,
                "orderId": order_id,
                "machineId": machine_id,
                "usageStatus": "AWAITING_UNLOCK",
                "warning": f"Unlock failed, but payment succeeded: {err}",
            }

    async def async_unlock_machine(
        self,
        machine_id: str,
        laundry_id: str,
        order_id: str,
    ) -> dict[str, Any]:
        """Unlock a machine that was already paid for."""
        unlock_data = {
            "laundryId": laundry_id,
            "machineId": machine_id,
            "orderId": order_id,
        }
        
        data = await self._request("POST", "/machine/start-machine", data=unlock_data)
        return data

    def get_all_machines(self, laundry: Laundry) -> list[LaundryMachine]:
        """Get all machines from a laundry."""
        return laundry.washers + laundry.dryers
