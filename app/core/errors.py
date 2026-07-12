from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    AUTHENTICATION_REQUIRED = "authentication_required"
    INVALID_AUTHENTICATION_TOKEN = "invalid_authentication_token"
    AUTHENTICATION_SERVICE_UNAVAILABLE = "authentication_service_unavailable"
    FORBIDDEN = "forbidden"
    VALIDATION_FAILED = "validation_failed"
    INVALID_REQUEST = "invalid_request"
    INVALID_TIMESTAMP = "invalid_timestamp"
    CONFLICT = "conflict"
    NOT_FOUND = "not_found"
    FARM_PROFILE_NOT_FOUND = "farm_profile_not_found"
    CHAT_NOT_FOUND = "chat_not_found"
    FILE_NOT_FOUND = "file_not_found"
    MESSAGE_NOT_FOUND = "message_not_found"
    CROP_RECOMMENDATION_NOT_FOUND = "crop_recommendation_not_found"
    CULTIVATION_CROP_NOT_FOUND = "cultivation_crop_not_found"
    INTERCROPPING_CULTIVATION_NOT_FOUND = "intercropping_cultivation_not_found"
    DEVICE_REGISTRATION_NOT_FOUND = "device_registration_not_found"
    WEATHER_DATA_NOT_FOUND = "weather_data_not_found"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    EXTERNAL_SERVICE_FAILED = "external_service_failed"
    STORAGE_UNAVAILABLE = "storage_unavailable"
    STORAGE_OPERATION_FAILED = "storage_operation_failed"
    AI_PROVIDER_UNAVAILABLE = "ai_provider_unavailable"
    INTERNAL_OPERATION_FAILED = "internal_operation_failed"
    FILENAME_REQUIRED = "filename_required"
    IMAGE_FILE_REQUIRED = "image_file_required"
    CROP_NAME_REQUIRED = "crop_name_required"
    INVALID_FILE_STATE = "invalid_file_state"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    UNSUPPORTED_TTS_MODE = "unsupported_tts_mode"
    CROP_TTS_UNSUPPORTED = "crop_tts_unsupported"
    MESSAGE_TTS_UNAVAILABLE = "message_tts_unavailable"
    NOTIFICATION_CONTENT_REQUIRED = "notification_content_required"
    NOTIFICATION_TARGET_INVALID = "notification_target_invalid"
    CROP_SELECTION_INVALID = "crop_selection_invalid"
    SELECTED_AREA_REQUIRED = "selected_area_required"


class AppError(Exception):
    """Base application error with a safe public message and private context."""

    code: ErrorCode
    safe_message: str
    context: dict[str, Any]

    def __init__(
        self,
        safe_message: str,
        *,
        code: ErrorCode,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message
        self.code = code
        self.context = context or {}


class AuthenticationError(AppError):
    pass


class AuthenticationRequired(AuthenticationError):
    def __init__(self) -> None:
        super().__init__(
            "Authentication is required.",
            code=ErrorCode.AUTHENTICATION_REQUIRED,
        )


class InvalidAuthenticationToken(AuthenticationError):
    def __init__(self, message: str = "Invalid authentication token.") -> None:
        super().__init__(
            message,
            code=ErrorCode.INVALID_AUTHENTICATION_TOKEN,
        )


class AuthenticationServiceUnavailable(AppError):
    def __init__(self) -> None:
        super().__init__(
            "Authentication service unavailable.",
            code=ErrorCode.AUTHENTICATION_SERVICE_UNAVAILABLE,
        )


class Forbidden(AppError):
    def __init__(
        self,
        message: str = "You do not have permission to perform this action.",
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=ErrorCode.FORBIDDEN, context=context)


class ValidationFailed(AppError):
    def __init__(
        self,
        message: str = "Request validation failed.",
        *,
        code: ErrorCode = ErrorCode.VALIDATION_FAILED,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, context=context)


class ConflictError(AppError):
    def __init__(
        self,
        message: str = "Request conflicts with the current resource state.",
        *,
        code: ErrorCode = ErrorCode.CONFLICT,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, context=context)


class NotFoundError(AppError):
    def __init__(
        self,
        message: str = "Resource not found.",
        *,
        code: ErrorCode = ErrorCode.NOT_FOUND,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, context=context)


class DependencyUnavailable(AppError):
    def __init__(
        self,
        message: str = "A required dependency is unavailable.",
        *,
        code: ErrorCode = ErrorCode.DEPENDENCY_UNAVAILABLE,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, context=context)


class ExternalServiceFailed(AppError):
    def __init__(
        self,
        message: str = "External service request failed.",
        *,
        code: ErrorCode = ErrorCode.EXTERNAL_SERVICE_FAILED,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, context=context)


class InternalOperationFailed(AppError):
    def __init__(
        self,
        message: str = "Internal operation failed.",
        *,
        code: ErrorCode = ErrorCode.INTERNAL_OPERATION_FAILED,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, context=context)


class FarmProfileNotFound(NotFoundError):
    def __init__(self, farm_id: str) -> None:
        super().__init__(
            "Farm profile not found.",
            code=ErrorCode.FARM_PROFILE_NOT_FOUND,
            context={"farm_id": farm_id},
        )


class ChatNotFound(NotFoundError):
    def __init__(self, chat_id: str) -> None:
        super().__init__(
            "Chat not found.",
            code=ErrorCode.CHAT_NOT_FOUND,
            context={"chat_id": chat_id},
        )


class FileNotFound(NotFoundError):
    def __init__(self, file_id: str) -> None:
        super().__init__(
            "File not found.",
            code=ErrorCode.FILE_NOT_FOUND,
            context={"file_id": file_id},
        )


class MessageNotFound(NotFoundError):
    def __init__(self, message_id: str | None = None) -> None:
        context = {"message_id": message_id} if message_id else None
        super().__init__(
            "Message not found.",
            code=ErrorCode.MESSAGE_NOT_FOUND,
            context=context,
        )


class CropRecommendationNotFound(NotFoundError):
    def __init__(self, recommendation_id: str) -> None:
        super().__init__(
            "Recommendation not found.",
            code=ErrorCode.CROP_RECOMMENDATION_NOT_FOUND,
            context={"recommendation_id": recommendation_id},
        )


class CultivationCropNotFound(NotFoundError):
    def __init__(self, crop_id: str) -> None:
        super().__init__(
            "Cultivation crop not found.",
            code=ErrorCode.CULTIVATION_CROP_NOT_FOUND,
            context={"crop_id": crop_id},
        )


class IntercroppingCultivationNotFound(NotFoundError):
    def __init__(self, intercropping_id: str) -> None:
        super().__init__(
            "Intercropping cultivation not found.",
            code=ErrorCode.INTERCROPPING_CULTIVATION_NOT_FOUND,
            context={"intercropping_id": intercropping_id},
        )


class DeviceRegistrationNotFound(NotFoundError):
    def __init__(self, device_id: str) -> None:
        super().__init__(
            "Device registration not found.",
            code=ErrorCode.DEVICE_REGISTRATION_NOT_FOUND,
            context={"device_id": device_id},
        )


class WeatherDataNotFound(NotFoundError):
    def __init__(self) -> None:
        super().__init__(
            "Weather data not found.",
            code=ErrorCode.WEATHER_DATA_NOT_FOUND,
        )
