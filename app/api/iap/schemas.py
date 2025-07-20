from typing import Literal

from pydantic import BaseModel


class IAPReceipt(BaseModel):
    receipt: str
    platform: Literal["ios", "android"]
