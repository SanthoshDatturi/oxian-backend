import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import (
    AppError,
    AuthenticationError,
    AuthenticationServiceUnavailable,
    ConflictError,
    DependencyUnavailable,
    ErrorCode,
    ExternalServiceFailed,
    Forbidden,
    InternalOperationFailed,
    NotFoundError,
    ValidationFailed,
)

logger = logging.getLogger(__name__)


def _status_code_for_error(error: AppError) -> int:
    if isinstance(error, AuthenticationError):
        return 401
    if isinstance(error, Forbidden):
        return 403
    if isinstance(error, NotFoundError):
        return 404
    if isinstance(error, ConflictError):
        return 409
    if isinstance(error, ValidationFailed):
        return 400
    if isinstance(
        error,
        (AuthenticationServiceUnavailable, DependencyUnavailable),
    ):
        return 503
    if isinstance(error, ExternalServiceFailed):
        return 502
    if isinstance(error, InternalOperationFailed):
        return 500
    return 500


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        logger.info("Request validation failed errors=%s", exc.errors())
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": str(ErrorCode.VALIDATION_FAILED),
                    "message": "Request validation failed.",
                },
            },
        )

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        status_code = _status_code_for_error(exc)
        if status_code >= 500:
            logger.error(
                "Application error code=%s context=%s",
                exc.code,
                exc.context,
                exc_info=(type(exc), exc, exc.__traceback__),
            )

        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": str(exc.code),
                    "message": exc.safe_message,
                },
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unexpected application error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": str(ErrorCode.INTERNAL_OPERATION_FAILED),
                    "message": "Unexpected server error.",
                },
            },
        )
