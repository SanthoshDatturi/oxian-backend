from typing import Dict

from .base import AuthProvider
from .firebase_config import verify_id_token


class FirebaseAuthProvider(AuthProvider):
    """
    Firebase implementation of AuthProvider.
    """

    async def verify_token(self, token: str) -> Dict:
        return await verify_id_token(token)
