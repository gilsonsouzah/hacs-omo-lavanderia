"""Authentication handler for Omo Lavanderia API."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass
class OmoAuth:
    """Manages authentication state for Omo Lavanderia API."""

    access_token: str
    refresh_token: str
    expires_at: datetime
    device_id: str

    @classmethod
    def from_login_response(
        cls, data: dict[str, Any], username: str
    ) -> OmoAuth:
        """Create OmoAuth from login API response.

        Args:
            data: Dictionary containing login response data.
            username: Username used for login (to generate device_id).

        Returns:
            OmoAuth instance.
        """
        # Calculate expiration time
        expires_in = data.get("expiresIn", data.get("expires_in", 3600))
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        return cls(
            access_token=data.get("accessToken", data.get("access_token", "")),
            refresh_token=data.get("refreshToken", data.get("refresh_token", "")),
            expires_at=expires_at,
            device_id=cls.generate_device_id(username),
        )

    @staticmethod
    def generate_device_id(username: str) -> str:
        """Generate a consistent device ID based on username.

        Creates a SHA-256 hash of the username to generate a unique
        but consistent device identifier for API requests.

        Args:
            username: The username to hash.

        Returns:
            A hexadecimal string representing the device ID.
        """
        hash_input = f"omo_lavanderia_{username}".encode("utf-8")
        return hashlib.sha256(hash_input).hexdigest()[:32]

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """Check if the access token is expired or about to expire.

        Args:
            buffer_seconds: Number of seconds before actual expiration
                          to consider the token expired. Defaults to 60.

        Returns:
            True if token is expired or will expire within buffer time.
        """
        expiration_threshold = datetime.now(timezone.utc) + timedelta(
            seconds=buffer_seconds
        )
        return self.expires_at <= expiration_threshold

    def update_tokens(
        self,
        access_token: str,
        refresh_token: str | None = None,
        expires_in: int = 3600,
    ) -> None:
        """Update the authentication tokens.

        Args:
            access_token: New access token.
            refresh_token: New refresh token (optional, keeps current if None).
            expires_in: Token validity duration in seconds.
        """
        self.access_token = access_token
        if refresh_token:
            self.refresh_token = refresh_token
        self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    def to_dict(self) -> dict[str, Any]:
        """Serialize authentication data to dictionary.

        Useful for storing auth state in Home Assistant storage.

        Returns:
            Dictionary containing serializable auth data.
        """
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at.isoformat(),
            "device_id": self.device_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OmoAuth:
        """Deserialize authentication data from dictionary.

        Args:
            data: Dictionary containing auth data.

        Returns:
            OmoAuth instance.
        """
        expires_at_str = data.get("expires_at", "")
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str)
        else:
            # Default to expired if no expiration time
            expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        return cls(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token", ""),
            expires_at=expires_at,
            device_id=data.get("device_id", ""),
        )
