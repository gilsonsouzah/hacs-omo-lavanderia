"""API exceptions for Omo Lavanderia."""


class OmoApiError(Exception):
    """Exception for API errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Initialize the exception."""
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class OmoAuthError(OmoApiError):
    """Exception for authentication errors."""

    def __init__(self, message: str = "Authentication failed") -> None:
        """Initialize the exception."""
        super().__init__(message, status_code=401)
