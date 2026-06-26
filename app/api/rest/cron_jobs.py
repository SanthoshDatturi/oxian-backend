from fastapi import APIRouter, Depends

from app.core.security import verify_cron_secret
from app.services.storage_service import cleanup_expired_temporary_files

router = APIRouter(prefix="/cron")


@router.post("/cleanup", dependencies=[Depends(verify_cron_secret)], status_code=200)
async def cleanup():

    await cleanup_expired_temporary_files()

    return {"success": True}
