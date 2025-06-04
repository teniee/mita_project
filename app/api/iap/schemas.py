
from pydantic import BaseModel
from typing import Literal

class IAPReceipt(BaseModel):
    user_id: str
    receipt: str
    platform: Literal["ios", "android"]
