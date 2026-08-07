"""Structured connector errors (B3).

Every adapter failure is a typed error. Errors never leak authentication
material; messages contain safe summaries only.
"""


class ConnectorError(Exception):
    """Base class for all connector errors."""

    safe_code = "connector_error"


class ConnectorRateLimited(ConnectorError):
    safe_code = "rate_limited"

    def __init__(self, retry_after, message="rate limit reached"):
        super().__init__(message)
        self.retry_after = retry_after


class ConnectorRevoked(ConnectorError):
    safe_code = "revoked"


class ConnectorAuthenticationError(ConnectorError):
    safe_code = "authentication_failed"


class ConnectorTimeout(ConnectorError):
    safe_code = "provider_timeout"


class ConnectorMalformedResponse(ConnectorError):
    safe_code = "malformed_response"


class ConnectorPermissionDenied(ConnectorError):
    safe_code = "permission_denied"


class ConnectorUnavailable(ConnectorError):
    safe_code = "provider_unavailable"
