class IBKRError(Exception):
    """Base exception for Interactive Brokers integrations."""


class IBKRConfigurationError(IBKRError):
    """Raised when IBKR configuration is incomplete or invalid."""


class IBKRConnectionError(IBKRError):
    """Raised when the adapter cannot establish a transport connection."""


class IBKRAuthError(IBKRError):
    """Raised when authentication or brokerage-session setup fails."""


class IBKRSessionError(IBKRError):
    """Raised when an authenticated session has expired or is unusable."""


class IBKRApiError(IBKRError):
    """Raised when the remote IBKR API returns a non-success response."""


class IBKRRateLimitError(IBKRApiError):
    """Raised when an IBKR endpoint returns a pacing or rate-limit error."""


class IBKROrderRejectedError(IBKRApiError):
    """Raised when IBKR rejects an order request."""
