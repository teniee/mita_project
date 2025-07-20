from typing import Dict

from pydantic import BaseModel


class StyleRequest(BaseModel):
    profile: Dict


class StyleResponse(BaseModel):
    style: Dict
