from typing import Annotated, List, Optional

from pydantic import BaseModel, Field

MonthStr = Annotated[str, Field(pattern=r"^\d{4}-\d{2}$")]
PositiveFloat = Annotated[float, Field(ge=0.0)]


class DriftLogRequest(BaseModel):
    """Request to log user drift for a given month."""

    user_id: str = Field(..., example="user_123")
    month: MonthStr = Field(..., example="2025-05")
    value: PositiveFloat = Field(..., example=0.153)


class DriftGetRequest(BaseModel):
    """Request to fetch drift information for a user."""

    user_id: str = Field(..., example="user_123")
    month: MonthStr = Field(..., example="2025-05")


class DriftLogResponse(BaseModel):
    """Response after logging drift successfully."""

    status: str = Field(..., example="ok")
    message: Optional[str] = Field(None, example="Drift logged successfully")


class DriftEntry(BaseModel):
    """Single item of user drift history."""

    month: MonthStr = Field(..., example="2025-04")
    value: PositiveFloat = Field(..., example=0.12)


class DriftGetResponse(BaseModel):
    """Response containing drift history and current value."""

    user_id: str = Field(..., example="user_123")
    month: MonthStr = Field(..., example="2025-05")
    drift_value: PositiveFloat = Field(..., example=0.15)
    history: List[DriftEntry] = Field(default_factory=list)
