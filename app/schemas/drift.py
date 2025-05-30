from pydantic import BaseModel, Field
from typing import Optional, List, Annotated


MonthStr = Annotated[str, Field(pattern=r"^\d{4}-\d{2}$")]
PositiveFloat = Annotated[float, Field(ge=0.0)]


class DriftLogRequest(BaseModel):
    """
    Запрос на логирование дрейфа пользователя за указанный месяц.
    """
    user_id: str = Field(..., example="user_123")
    month: MonthStr = Field(..., example="2025-05")
    value: PositiveFloat = Field(..., example=0.153)


class DriftGetRequest(BaseModel):
    """
    Запрос на получение информации о дрейфе пользователя.
    """
    user_id: str = Field(..., example="user_123")
    month: MonthStr = Field(..., example="2025-05")


class DriftLogResponse(BaseModel):
    """
    Ответ после успешного логирования дрейфа.
    """
    status: str = Field(..., example="ok")
    message: Optional[str] = Field(None, example="Drift logged successfully")


class DriftEntry(BaseModel):
    """
    Один элемент истории дрейфа.
    """
    month: MonthStr = Field(..., example="2025-04")
    value: PositiveFloat = Field(..., example=0.12)


class DriftGetResponse(BaseModel):
    """
    Ответ с историей дрейфа и текущим значением.
    """
    user_id: str = Field(..., example="user_123")
    month: MonthStr = Field(..., example="2025-05")
    drift_value: PositiveFloat = Field(..., example=0.15)
    history: List[DriftEntry] = Field(default_factory=list)
