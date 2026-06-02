import json
from functools import lru_cache
from typing import Optional

import firebase_admin
from firebase_admin import credentials

from app.core.config import settings


def _looks_like_private_key(value: str) -> bool:
    return "-----BEGIN PRIVATE KEY-----" in value


def _normalize_private_key(private_key: str) -> str:
    return private_key.replace("\\n", "\n").strip()


def _service_account_from_split_env(private_key: str) -> dict:
    client_email = settings.FIREBASE_CLIENT_EMAIL

    if not settings.FIREBASE_PROJECT_ID or not client_email:
        raise ValueError(
            "FIREBASE_SERVICE_ACCOUNT_JSON contains a private key, not JSON. "
            "Set FIREBASE_PROJECT_ID and FIREBASE_CLIENT_EMAIL, or replace "
            "FIREBASE_SERVICE_ACCOUNT_JSON with the full service account JSON."
        )

    return {
        "type": "service_account",
        "project_id": settings.FIREBASE_PROJECT_ID,
        "private_key": _normalize_private_key(private_key),
        "client_email": client_email,
        "token_uri": "https://oauth2.googleapis.com/token",
    }


def _certificate_from_payload(payload: dict):
    if isinstance(payload.get("private_key"), str):
        payload = {
            **payload,
            "private_key": _normalize_private_key(payload["private_key"]),
        }

    try:
        return credentials.Certificate(payload)
    except ValueError as exc:
        raise ValueError(
            "Firebase service account private key is not a valid PEM value. "
            "Check FIREBASE_SERVICE_ACCOUNT_JSON formatting."
        ) from exc


@lru_cache(maxsize=1)
def _get_credentials():
    """
    Resolve Firebase credentials from environment configuration.
    Supports:
        - JSON env var
        - private key plus FIREBASE_PROJECT_ID and FIREBASE_CLIENT_EMAIL
        - application default credentials
    """

    if settings.FIREBASE_SERVICE_ACCOUNT_JSON:
        raw_service_account = settings.FIREBASE_SERVICE_ACCOUNT_JSON.strip()

        if _looks_like_private_key(raw_service_account):
            payload = _service_account_from_split_env(raw_service_account)
            return _certificate_from_payload(payload)

        try:
            payload = json.loads(raw_service_account)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "FIREBASE_SERVICE_ACCOUNT_JSON must be a full service account "
                "JSON object, not a raw private key or another value."
            ) from exc

        return _certificate_from_payload(payload)

    return credentials.ApplicationDefault()


@lru_cache(maxsize=1)
def _get_options() -> Optional[dict]:
    """
    Optional Firebase initialization options.
    """

    options: dict[str, object] = {}

    if settings.FIREBASE_PROJECT_ID:
        options["projectId"] = settings.FIREBASE_PROJECT_ID

    return options or None


def initialize_firebase():
    """
    Initialize Firebase Admin SDK once.
    Safe for multi-import environments.
    """

    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            _get_credentials(),
            options=_get_options(),
        )

    return firebase_admin.get_app()
