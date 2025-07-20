
from pydantic import BaseModel
from typing import Dict

class StyleRequest(BaseModel):
    profile: Dict

class StyleResponse(BaseModel):
    style: Dict
