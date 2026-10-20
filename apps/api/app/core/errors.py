"""Standard API errors and exception handlers."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict | list | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)

    def as_dict(self) -> dict:
        body: dict = {"error": {"code": self.code, "message": self.message}}
        if self.details is not None:
            body["error"]["details"] = self.details
        return body


def unauthorized(message: str = "برای انجام این عملیات باید وارد شوید.") -> ApiError:
    return ApiError(status.HTTP_401_UNAUTHORIZED, "unauthorized", message)


def forbidden(message: str = "دسترسی به این بخش مجاز نیست.") -> ApiError:
    return ApiError(status.HTTP_403_FORBIDDEN, "forbidden", message)


def not_found(message: str = "مورد درخواستی یافت نشد.") -> ApiError:
    return ApiError(status.HTTP_404_NOT_FOUND, "not_found", message)


def conflict(message: str, code: str = "conflict") -> ApiError:
    return ApiError(status.HTTP_409_CONFLICT, code, message)


def bad_request(message: str, code: str = "bad_request") -> ApiError:
    return ApiError(status.HTTP_400_BAD_REQUEST, code, message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.as_dict())

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in err.get("loc", [])[1:]),
                "message": err.get("msg"),
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "داده های ارسالی معتبر نیستند.",
                    "details": details,
                }
            },
        )

    @app.exception_handler(IntegrityError)
    async def _integrity_handler(_: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("Database integrity error: %s", exc.orig)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": {
                    "code": "conflict",
                    "message": "این عملیات با داده های موجود در تعارض است.",
                }
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "خطای داخلی سرور رخ داد. لطفا دوباره تلاش کنید.",
                }
            },
        )
