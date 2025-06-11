import datetime
import uuid
import jwt
from passlib.context import CryptContext

from app.core.config import SECRET_KEY, ALGORITHM, settings


ACCESS_EXPIRES_MIN = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_EXPIRES_DAYS = 7


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_token(data: dict, expires_delta: datetime.timedelta) -> str:
    to_encode = data.copy()
    to_encode.update({
        "exp": datetime.datetime.utcnow() + expires_delta,
        "jti": str(uuid.uuid4()),
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: str) -> str:
    return create_token(
        {"sub": str(user_id), "type": "access"},
        datetime.timedelta(minutes=ACCESS_EXPIRES_MIN),
    )


def create_refresh_token(user_id: str) -> str:
    return create_token(
        {"sub": str(user_id), "type": "refresh"},
        datetime.timedelta(days=REFRESH_EXPIRES_DAYS),
    )


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
