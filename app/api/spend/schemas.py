from pydantic import BaseModel
from typing import List, Dict, Any

class SpendCheckRequest(BaseModel):
    calendar: List[Dict[str, Any]]
    day: int
    category: str

class LimitCheckRequest(BaseModel):
    calendar: List[Dict[str, Any]]
    day: int
    category: str
