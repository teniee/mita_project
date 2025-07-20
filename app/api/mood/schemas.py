from datetime import date

from pydantic import BaseModel


class MoodIn(BaseModel):
    date: date
    mood: str


class MoodOut(BaseModel):
    id: str
    date: date
    mood: str
