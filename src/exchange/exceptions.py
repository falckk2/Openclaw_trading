"""Exchange-specific exceptions."""


class ExchangeError(Exception):
    """Base exception for exchange errors."""
    pass


class APIError(ExchangeError):
    """Raised when the exchange API returns an error."""
    def __init__(self, code: int, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


class NetworkError(ExchangeError):
    """Raised on network/connectivity errors."""
    pass


class OrderError(ExchangeError):
    """Raised when an order cannot be placed."""
    pass


class RateLimitError(ExchangeError):
    """Raised when rate limit is hit."""
    pass


class AuthenticationError(ExchangeError):
    """Raised on auth failures."""
    pass