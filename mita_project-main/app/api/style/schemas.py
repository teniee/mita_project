
from pydantic import BaseModel
from typing import Dict

class StyleRequest(BaseModel):
    user_id: str
    profile: Dict

class StyleResponse(BaseModel):
    style: Dict
