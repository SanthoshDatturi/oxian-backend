from fastapi import Depends, HTTPException, WebSocket
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.integrations.auth.errors import (
    AuthProviderError,
    ExpiredTokenError,
    InvalidTokenError,
    RevokedTokenError,
)
from app.integrations.auth.provider import auth_provider

_bearer_scheme = HTTPBearer(auto_error=False)


def _normalize_bearer_token(token: str) -> str:
    if token.lower().startswith("bearer "):
        return token[7:].strip()
    return token.strip()


async def _verify_token(token: str) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    token = _normalize_bearer_token(token)
    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    try:
        return await auth_provider.verify_token(token)

    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    except ExpiredTokenError:
        raise HTTPException(status_code=401, detail="Token expired")

    except RevokedTokenError:
        raise HTTPException(status_code=401, detail="Token revoked")

    except AuthProviderError:
        raise HTTPException(
            status_code=503, detail="Authentication service unavailable"
        )


async def authenticate_websocket(websocket: WebSocket):

    token = websocket.headers.get("Authorization")
    return await _verify_token(token or "")


async def authenticate_rest(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
):
    token = credentials.credentials if credentials else ""
    return await _verify_token(token)
