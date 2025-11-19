"""
Schemas package.

Base schemas for reducing code duplication.
"""

from app.schemas.base import (
    BaseSchema,
    BaseResponseSchema,
    UserOwnedResponseSchema,
    DecimalResponseSchema,
    UserOwnedDecimalResponseSchema,
    PaginatedResponseSchema,
    SuccessResponseSchema,
    ErrorResponseSchema,
    TimestampMixin,
)

__all__ = [
    "BaseSchema",
    "BaseResponseSchema",
    "UserOwnedResponseSchema",
    "DecimalResponseSchema",
    "UserOwnedDecimalResponseSchema",
    "PaginatedResponseSchema",
    "SuccessResponseSchema",
    "ErrorResponseSchema",
    "TimestampMixin",
]
