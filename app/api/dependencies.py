from fastapi import Depends

from app.core.errors import InvalidAuthenticationToken
from app.core.security import authenticate_rest


def user_id_from_payload(user_payload: dict) -> str:
    user_id = user_payload.get("uid") or user_payload.get("sub")
    if not user_id:
        raise InvalidAuthenticationToken()
    return user_id


async def get_current_user_id(
    user_payload: dict = Depends(authenticate_rest),
) -> str:
    return user_id_from_payload(user_payload)
