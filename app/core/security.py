import secrets

from fastapi import Depends, Header, WebSocket
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.errors import (
    AuthenticationRequired,
    AuthenticationServiceUnavailable,
    InvalidAuthenticationToken,
)
from app.infrastructure.auth import (
    AuthProviderError,
    ExpiredTokenError,
    InvalidTokenError,
    RevokedTokenError,
    verify_token,
)

_bearer_scheme = HTTPBearer(auto_error=False)


def _normalize_bearer_token(token: str) -> str:
    if token.lower().startswith("bearer "):
        return token[7:].strip()
    return token.strip()


async def _verify_token(token: str) -> dict:
    if not token:
        raise AuthenticationRequired()

    token = _normalize_bearer_token(token)
    if not token:
        raise AuthenticationRequired()

    try:
        return await verify_token(token)

    except InvalidTokenError:
        raise InvalidAuthenticationToken()

    except ExpiredTokenError:
        raise InvalidAuthenticationToken("Authentication token expired.")

    except RevokedTokenError:
        raise InvalidAuthenticationToken("Authentication token revoked.")

    except AuthProviderError:
        raise AuthenticationServiceUnavailable()


async def authenticate_websocket(websocket: WebSocket):

    token = websocket.headers.get("Authorization")
    return await _verify_token(token or "")


async def authenticate_rest(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
):
    token = credentials.credentials if credentials else ""
    return await _verify_token(token)


async def verify_cron_secret(
    x_cron_secret: str = Header(alias="X-Cron-Secret"),
) -> None:
    """
    Verifies that the request came from the cron service.
    """

    if not secrets.compare_digest(
        x_cron_secret,
        settings.CRON_SECRET,
    ):
        raise InvalidAuthenticationToken("Invalid cron secret.")
