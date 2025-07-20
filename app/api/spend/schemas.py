from typing import Any, Dict, List

from pydantic import BaseModel


class SpendCheckRequest(BaseModel):
    calendar: List[Dict[str, Any]]
    day: int
    category: str


class LimitCheckRequest(BaseModel):
    calendar: List[Dict[str, Any]]
    day: int
    category: str
