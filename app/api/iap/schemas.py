
from pydantic import BaseModel
from typing import Literal

class IAPReceipt(BaseModel):
    receipt: str
    platform: Literal["ios", "android"]
