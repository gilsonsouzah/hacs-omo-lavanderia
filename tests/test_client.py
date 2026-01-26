"""Tests for Omo Lavanderia API client."""
import pytest
import time

from custom_components.omo_lavanderia.api.client import OmoLavanderiaApiClient
from custom_components.omo_lavanderia.api.exceptions import (
    OmoAuthError,
    OmoApiError,
)


class MockResponse:
    """Mock aiohttp response."""
    
    def __init__(self, status: int, json_data: dict = None, text_data: str = None):
        self.status = status
        self._json_data = json_data or {}
        self._text_data = text_data or ""
    
    async def json(self):
        return self._json_data
    
    async def text(self):
        return self._text_data


class MockContextManager:
    """Mock async context manager for aiohttp."""
    
    def __init__(self, response: MockResponse):
        self.response = response
    
    async def __aenter__(self):
        return self.response
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class MockSession:
    """Mock aiohttp ClientSession."""
    
    def __init__(self):
        self.post_response = None
        self.request_response = None
        self.post_calls = []
        self.request_calls = []
    
    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return MockContextManager(self.post_response)
    
    def request(self, method, url, **kwargs):
        self.request_calls.append((method, url, kwargs))
        return MockContextManager(self.request_response)


@pytest.fixture
def mock_session():
    """Create a mock aiohttp session."""
    return MockSession()


@pytest.fixture
def client(mock_session):
    """Create a client instance."""
    return OmoLavanderiaApiClient(mock_session, "test@email.com", "password123")


class TestOmoLavanderiaApiClient:
    """Tests for OmoLavanderiaApiClient."""

    @pytest.mark.asyncio
    async def test_login_success(self, client, mock_session):
        """Test successful login."""
        mock_session.post_response = MockResponse(
            status=200,
            json_data={
                "data": {
                    "accessToken": "access_token_123",
                    "refreshToken": "refresh_token_456",
                    "accessTokenExpiresIn": int(time.time()) + 3600,
                },
                "success": True,
            }
        )

        await client.async_login()

        assert client._access_token == "access_token_123"
        assert client._refresh_token == "refresh_token_456"
        assert len(mock_session.post_calls) == 1

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client, mock_session):
        """Test login with invalid credentials."""
        mock_session.post_response = MockResponse(
            status=400,
            text_data="Invalid credentials"
        )

        with pytest.raises(OmoAuthError):
            await client.async_login()

    @pytest.mark.asyncio
    async def test_get_laundries(self, client, mock_session):
        """Test getting laundries."""
        client.set_tokens("access", "refresh", int(time.time()) + 3600)

        mock_session.request_response = MockResponse(
            status=200,
            text_data='{"data": {"items": []}}',
            json_data={
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
                },
            }
        )

        laundries = await client.async_get_laundries()

        assert len(laundries) == 1
        assert laundries[0].id == "laundry-123"
        assert laundries[0].name == "Test Laundry"

    @pytest.mark.asyncio
    async def test_get_laundry_details(self, client, mock_session):
        """Test getting laundry details."""
        client.set_tokens("access", "refresh", int(time.time()) + 3600)

        mock_session.request_response = MockResponse(
            status=200,
            text_data='{"data": {}}',
            json_data={
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
                                "code": "W1",
                                "laundryId": "laundry-123",
                                "serial": "123",
                                "model": "Model1",
                            }
                        ],
                        "dryers": [],
                    },
                },
            }
        )

        laundry = await client.async_get_laundry("laundry-123")

        assert laundry.id == "laundry-123"
        assert len(laundry.washers) == 1
        assert laundry.washers[0].display_name == "L1"

    @pytest.mark.asyncio
    async def test_get_active_orders(self, client, mock_session):
        """Test getting active orders."""
        client.set_tokens("access", "refresh", int(time.time()) + 3600)

        mock_session.request_response = MockResponse(
            status=200,
            text_data='{"data": []}',
            json_data={
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
            }
        )

        orders = await client.async_get_active_orders()

        assert len(orders) == 1
        assert orders[0].id == "order-123"
        assert orders[0].machines[0].remaining_time == 600

    @pytest.mark.asyncio
    async def test_get_payment_cards(self, client, mock_session):
        """Test getting payment cards."""
        client.set_tokens("access", "refresh", int(time.time()) + 3600)

        mock_session.request_response = MockResponse(
            status=200,
            text_data='{"data": []}',
            json_data={
                "data": [
                    {
                        "id": "card-123",
                        "nickname": "My Card",
                        "holderName": "Test User",
                        "lastFour": "4242",
                        "brand": "visa",
                    }
                ],
            }
        )

        cards = await client.async_get_payment_cards()

        assert len(cards) == 1
        assert cards[0].id == "card-123"
        assert cards[0].nickname == "My Card"
        assert cards[0].brand == "visa"

    def test_is_token_expired_no_token(self, client):
        """Test token expiration check when no token is set."""
        assert client.is_token_expired() is True

    def test_is_token_expired_with_valid_token(self, client):
        """Test token expiration check with valid token."""
        client.set_tokens("access", "refresh", int(time.time()) + 3600)
        assert client.is_token_expired() is False

    def test_is_token_expired_with_expired_token(self, client):
        """Test token expiration check with expired token."""
        client.set_tokens("access", "refresh", 1000000000)
        assert client.is_token_expired() is True

    def test_set_tokens(self, client):
        """Test setting tokens."""
        client.set_tokens("access_abc", "refresh_xyz", 1749692400)

        assert client._access_token == "access_abc"
        assert client._refresh_token == "refresh_xyz"
        assert client._token_expires_at == 1749692400

    def test_get_token_status(self, client):
        """Test getting token status."""
        status = client.get_token_status()
        assert status["has_token"] is False
        assert status["is_expired"] is True

        client.set_tokens("access", "refresh", int(time.time()) + 3600)
        status = client.get_token_status()
        assert status["has_token"] is True
        assert status["is_expired"] is False

    def test_token_update_callback(self, client):
        """Test token update callback can be set."""
        def callback(access, refresh, expires):
            pass
        
        client.set_token_update_callback(callback)
        assert client._token_update_callback is not None

    def test_rate_limiting(self, client):
        """Test rate limiting for login attempts."""
        client._login_failures = 3
        client._last_login_attempt = time.time()
        
        assert client._should_rate_limit_login() is True
        
        client._login_failures = 0
        assert client._should_rate_limit_login() is False

    def test_username_property(self, client):
        """Test username property."""
        assert client.username == "test@email.com"
