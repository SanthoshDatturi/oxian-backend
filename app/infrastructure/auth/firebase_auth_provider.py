from typing import Dict

from fastapi.concurrency import run_in_threadpool
from firebase_admin import auth
from firebase_admin import exceptions as firebase_exceptions

from app.infrastructure.firebase_config import initialize_firebase

from .base import AuthProvider
from .errors import (
    AuthProviderError,
    ExpiredTokenError,
    InvalidTokenError,
    RevokedTokenError,
)


class FirebaseAuthError(Exception):
    """Raised when something goes wrong while talking to Firebase Auth."""


async def verify_id_token(id_token: str) -> dict:
    try:
        app = initialize_firebase()
        decoded = await run_in_threadpool(auth.verify_id_token, id_token, app, True)
        return decoded

    except ValueError as exc:
        raise FirebaseAuthError("Firebase authentication is not configured") from exc

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


class FirebaseAuthProvider(AuthProvider):
    """
    Firebase implementation of AuthProvider.
    """

    async def verify_token(self, token: str) -> Dict:
        return await verify_id_token(token)
