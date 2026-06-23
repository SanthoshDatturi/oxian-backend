from abc import ABC, abstractmethod
from typing import Dict


class AuthProvider(ABC):
    """
    Base authentication provider interface.
    """

    @abstractmethod
    async def verify_token(self, token: str) -> Dict:
        """
        Verify authentication token and return decoded payload.
        """
        raise NotImplementedError
