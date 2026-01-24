"""Custom exceptions for Omo Lavanderia API."""


class OmoApiError(Exception):
    """Base exception for Omo Lavanderia API errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Initialize the exception.

        Args:
            message: Error message.
            status_code: HTTP status code if applicable.
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code

    def __str__(self) -> str:
        """Return string representation."""
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class OmoAuthError(OmoApiError):
    """Exception for authentication errors."""

    def __init__(self, message: str = "Authentication failed") -> None:
        """Initialize the authentication exception.

        Args:
            message: Error message.
        """
        super().__init__(message, status_code=401)
