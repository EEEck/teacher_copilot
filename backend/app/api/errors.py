"""Typed error envelope + global exception handlers.

Centralizes error responses so every failure returns a consistent shape and
unexpected errors are logged with a full traceback (instead of being flattened
to a bare string like ``'title'``).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("klassenpilot")


class ErrorBody(BaseModel):
    type: str
    message: str
    detail: str | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody


def _envelope(
    type_: str, message: str, status: int, detail: str | None = None
) -> JSONResponse:
    body = ErrorEnvelope(error=ErrorBody(type=type_, message=message, detail=detail))
    return JSONResponse(status_code=status, content=body.model_dump())


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _envelope("http_error", str(exc.detail), status=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _envelope(
            "validation_error",
            "Request validation failed",
            status=422,
            detail=str(exc.errors()),
        )

    @app.exception_handler(Exception)
    async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _envelope(
            type(exc).__name__,
            str(exc) or "Internal server error",
            status=500,
        )
