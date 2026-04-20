from __future__ import annotations


class SchwabError(Exception):
    """Base exception for Schwab broker integration failures."""


class SchwabConfigurationError(SchwabError):
    """Raised when Schwab broker configuration is invalid."""


class SchwabAuthError(SchwabError):
    """Raised when OAuth authentication fails."""


class SchwabTokenExpiredError(SchwabAuthError):
    """Raised when stored tokens are unavailable or no longer usable."""


class SchwabApiError(SchwabError):
    """Raised when a Schwab API request fails."""


class SchwabRateLimitError(SchwabApiError):
    """Raised when Schwab returns a rate-limit response."""


class SchwabOrderRejectedError(SchwabApiError):
    """Raised when Schwab rejects an order submission."""


class SchwabConnectionError(SchwabApiError):
    """Raised for transport or connectivity issues."""
