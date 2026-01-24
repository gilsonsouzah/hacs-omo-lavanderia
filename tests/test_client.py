"""Tests for Omo Lavanderia API client."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from aiohttp import ClientResponseError

from custom_components.omo_lavanderia.api.client import OmoLavanderiaClient
from custom_components.omo_lavanderia.api.exceptions import (
    AuthenticationError,
    ApiError,
)


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    session = MagicMock()
    session.request = AsyncMock()
    return session


@pytest.fixture
def client(mock_session):
    """Create a client instance."""
    return OmoLavanderiaClient(mock_session, "test@email.com", "password123")


class TestOmoLavanderiaClient:
    """Tests for OmoLavanderiaClient."""

    @pytest.mark.asyncio
    async def test_login_success(self, client, mock_session):
        """Test successful login."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": {
                    "accessToken": "access_token_123",
                    "refreshToken": "refresh_token_456",
                    "accessTokenExpiresIn": 1749692400000,
                },
                "message": "Success!",
                "success": True,
            }
        )
        mock_session.request.return_value.__aenter__.return_value = mock_response

        result = await client.async_login()

        assert result is True
        assert client._access_token == "access_token_123"
        assert client._refresh_token == "refresh_token_456"
        mock_session.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client, mock_session):
        """Test login with invalid credentials."""
        mock_response = MagicMock()
        mock_response.status = 400
        mock_response.json = AsyncMock(
            return_value={
                "data": None,
                "message": "Invalid credentials",
                "success": False,
            }
        )
        mock_session.request.return_value.__aenter__.return_value = mock_response

        with pytest.raises(AuthenticationError):
            await client.async_login()

    @pytest.mark.asyncio
    async def test_get_laundries(self, client, mock_session):
        """Test getting laundries."""
        # Set tokens first
        client.set_tokens("access", "refresh", 9999999999)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": {
                    "items": [
                        {
                            "id": "laundry-123",
                            "name": "Test Laundry",
                            "code": "abc123",
                            "type": "OLC",
                            "isClosed": False,
                            "isBlocked": False,
                        }
                    ],
                    "totalPages": 1,
                    "currentPage": 1,
                },
                "message": "Success!",
                "success": True,
            }
        )
        mock_session.request.return_value.__aenter__.return_value = mock_response

        laundries = await client.async_get_laundries()

        assert len(laundries) == 1
        assert laundries[0].id == "laundry-123"
        assert laundries[0].name == "Test Laundry"

    @pytest.mark.asyncio
    async def test_get_laundry_details(self, client, mock_session):
        """Test getting laundry details."""
        client.set_tokens("access", "refresh", 9999999999)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": {
                    "id": "laundry-123",
                    "name": "Test Laundry",
                    "code": "abc123",
                    "type": "OLC",
                    "paymentMode": "PREPAID",
                    "isClosed": False,
                    "isBlocked": False,
                    "machines": {
                        "washers": [
                            {
                                "id": "washer-1",
                                "displayName": "L1",
                                "type": "WASHER",
                                "status": "AVAILABLE",
                                "cycleTime": 30,
                            }
                        ],
                        "dryers": [
                            {
                                "id": "dryer-1",
                                "displayName": "S1",
                                "type": "DRYER",
                                "status": "IN_USE",
                                "cycleTime": 45,
                            }
                        ],
                    },
                },
                "message": "Success!",
                "success": True,
            }
        )
        mock_session.request.return_value.__aenter__.return_value = mock_response

        laundry = await client.async_get_laundry("laundry-123")

        assert laundry.id == "laundry-123"
        assert len(laundry.washers) == 1
        assert len(laundry.dryers) == 1
        assert laundry.washers[0].display_name == "L1"

    @pytest.mark.asyncio
    async def test_get_active_orders(self, client, mock_session):
        """Test getting active orders."""
        client.set_tokens("access", "refresh", 9999999999)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": "order-123",
                        "laundryId": "laundry-123",
                        "laundryName": "Test Laundry",
                        "totalPrice": 10.28,
                        "status": "IN_PROGRESS",
                        "machines": [
                            {
                                "id": "machine-1",
                                "type": "WASHER",
                                "status": "IN_PROGRESS",
                                "remainingTime": 600,
                                "usageStatus": "IN_USE",
                                "displayName": "L1",
                            }
                        ],
                    }
                ],
                "message": "Success!",
                "success": True,
            }
        )
        mock_session.request.return_value.__aenter__.return_value = mock_response

        orders = await client.async_get_active_orders()

        assert len(orders) == 1
        assert orders[0].id == "order-123"
        assert orders[0].machines[0].remaining_time == 600

    @pytest.mark.asyncio
    async def test_get_payment_cards(self, client, mock_session):
        """Test getting payment cards."""
        client.set_tokens("access", "refresh", 9999999999)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": "card-123",
                        "nickname": "My Card",
                        "holderName": "Test User",
                        "lastFour": "4242",
                        "brand": "visa",
                    }
                ],
                "message": "Success!",
                "success": True,
            }
        )
        mock_session.request.return_value.__aenter__.return_value = mock_response

        cards = await client.async_get_payment_cards()

        assert len(cards) == 1
        assert cards[0].id == "card-123"
        assert cards[0].nickname == "My Card"
        assert cards[0].brand == "visa"

    @pytest.mark.asyncio
    async def test_start_machine(self, client, mock_session):
        """Test starting a machine."""
        client.set_tokens("access", "refresh", 9999999999)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "data": {"orderId": "new-order-123"},
                "message": "Success!",
                "success": True,
            }
        )
        mock_session.request.return_value.__aenter__.return_value = mock_response

        result = await client.async_start_machine("laundry-123", "machine-123", "card-123")

        assert result == {"orderId": "new-order-123"}

    def test_is_token_expired_no_token(self, client):
        """Test token expiration check when no token is set."""
        assert client.is_token_expired() is True

    def test_is_token_expired_with_valid_token(self, client):
        """Test token expiration check with valid token."""
        client.set_tokens("access", "refresh", 9999999999)
        assert client.is_token_expired() is False

    def test_is_token_expired_with_expired_token(self, client):
        """Test token expiration check with expired token."""
        client.set_tokens("access", "refresh", 1000000000)  # Very old timestamp
        assert client.is_token_expired() is True

    def test_set_tokens(self, client):
        """Test setting tokens."""
        client.set_tokens("access_abc", "refresh_xyz", 1749692400)

        assert client._access_token == "access_abc"
        assert client._refresh_token == "refresh_xyz"
        assert client._token_expires_at == 1749692400

    def test_get_tokens(self, client):
        """Test getting tokens."""
        client.set_tokens("access_abc", "refresh_xyz", 1749692400)

        tokens = client.get_tokens()

        assert tokens["access_token"] == "access_abc"
        assert tokens["refresh_token"] == "refresh_xyz"
        assert tokens["expires_at"] == 1749692400
