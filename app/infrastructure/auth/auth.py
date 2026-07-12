from fastapi.concurrency import run_in_threadpool
from firebase_admin import auth
from firebase_admin import exceptions as firebase_exceptions

from app.infrastructure.providers.firebase import initialize_firebase

# ── Errors ──────────────────────────────────────────────────────────


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


# ── Token Verification ──────────────────────────────────────────────


async def verify_token(token: str) -> dict:
    """
    Verify an authentication token and return the decoded payload.
    """
    try:
        app = initialize_firebase()
        decoded = await run_in_threadpool(auth.verify_id_token, token, app, True)
        return decoded

    except ValueError as exc:
        raise AuthProviderError("Firebase authentication is not configured") from exc

    except auth.InvalidIdTokenError as exc:
        raise InvalidTokenError("Invalid authentication token") from exc

    except auth.ExpiredIdTokenError as exc:
        raise ExpiredTokenError("Authentication token expired") from exc

    except auth.RevokedIdTokenError as exc:
        raise RevokedTokenError("Authentication token revoked") from exc

    except firebase_exceptions.FirebaseError as exc:
        raise AuthProviderError("Firebase authentication failure") from exc

    except Exception as exc:
        raise AuthProviderError("Unexpected authentication failure") from exc
