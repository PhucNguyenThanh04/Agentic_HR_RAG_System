"""Backward-compatible imports for the historical misspelled module name.

New code should import from src.core.exceptions and src.core.exception_handlers.
"""

from src.core.exception_handlers import app_exception_handler
from src.core.exceptions import (
    AppException,
    BadRequestException,
    ConflictException,
    DatabaseException,
    ForbiddenException,
    InternalServerException,
    MLProcessingException,
    NotFoundException,
    UnauthorizedException,
    UnprocessableEntityException,
    ValidationException,
)

__all__ = [
    "AppException",
    "BadRequestException",
    "ConflictException",
    "DatabaseException",
    "ForbiddenException",
    "InternalServerException",
    "MLProcessingException",
    "NotFoundException",
    "UnauthorizedException",
    "UnprocessableEntityException",
    "ValidationException",
    "app_exception_handler",
]
