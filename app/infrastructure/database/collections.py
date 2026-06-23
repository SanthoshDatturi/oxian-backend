from motor.motor_asyncio import AsyncIOMotorCollection

from app.infrastructure.providers.mongodb import get_database


def _get_collection(collection_name: str) -> AsyncIOMotorCollection:
    return get_database()[collection_name]


def get_processes_collection() -> AsyncIOMotorCollection:
    return _get_collection("processes")


def get_chats_collection() -> AsyncIOMotorCollection:
    return _get_collection("chats")


def get_messages_collection() -> AsyncIOMotorCollection:
    return _get_collection("messages")


def get_files_collection() -> AsyncIOMotorCollection:
    return _get_collection("files")


def get_crop_images_collection() -> AsyncIOMotorCollection:
    return _get_collection("crop_images")


def get_farm_profiles_collection() -> AsyncIOMotorCollection:
    return _get_collection("farm_profiles")


def get_user_prefs_collection() -> AsyncIOMotorCollection:
    return _get_collection("user_prefs")


def get_device_registrations_collection() -> AsyncIOMotorCollection:
    return _get_collection("device_registrations")


def get_notification_records_collection() -> AsyncIOMotorCollection:
    return _get_collection("notification_records")


def get_crop_image_generate_requests_collection() -> AsyncIOMotorCollection:
    return _get_collection("crop_image_generate_requests")


def get_crop_recommendations_collection() -> AsyncIOMotorCollection:
    return _get_collection("crop_recommendations")


def get_cultivation_crops_collection() -> AsyncIOMotorCollection:
    return _get_collection("cultivation_crops")


def get_intercropping_details_collection() -> AsyncIOMotorCollection:
    return _get_collection("intercropping_details")


def get_cultivation_tasks_collection() -> AsyncIOMotorCollection:
    return _get_collection("cultivation_tasks")


def get_investment_breakdowns_collection() -> AsyncIOMotorCollection:
    return _get_collection("investment_breakdowns")


def get_agricultural_input_recommendations_collection() -> AsyncIOMotorCollection:
    return _get_collection("agricultural_input_recommendations")
