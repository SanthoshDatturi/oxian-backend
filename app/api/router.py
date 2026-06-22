from fastapi import APIRouter

from .rest.admin import router as admin_router
from .rest.chat import router as chat_router
from .rest.crop_recommendation import router as crop_recommendation_router
from .rest.cultivation_crop import router as cultivation_crop_router
from .rest.farm_profile import router as farm_profile_router
from .rest.files import router as files_router
from .rest.notification import router as notification_router
from .rest.user_pref import router as user_pref_router
from .rest.weather import router as weather_router

api_router = APIRouter()


api_router.include_router(files_router)
api_router.include_router(chat_router)
api_router.include_router(farm_profile_router)
api_router.include_router(user_pref_router)
api_router.include_router(weather_router)
api_router.include_router(admin_router)
api_router.include_router(crop_recommendation_router)
api_router.include_router(cultivation_crop_router)
api_router.include_router(notification_router)
