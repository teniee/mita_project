from pydantic import BaseModel, EmailStr


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    country: str = "US"
    annual_income: float = 0.0
    timezone: str = "UTC"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthIn(BaseModel):
    id_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
