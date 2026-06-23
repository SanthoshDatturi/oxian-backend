class AuthError(Exception):
    """Base authentication error."""


class InvalidTokenError(AuthError):
    """Token is malformed or invalid."""


class ExpiredTokenError(AuthError):
    """Token has expired."""


class RevokedTokenError(AuthError):
    """Token has been revoked."""


class AuthProviderError(AuthError):
    """Authentication provider failed internally."""
