from datetime import datetime

from pydantic import BaseModel


class AdviceOut(BaseModel):
    id: str
    date: datetime
    type: str
    text: str

    class Config:
        orm_mode = True
