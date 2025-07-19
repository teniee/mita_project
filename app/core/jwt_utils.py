import jwt
from passlib.context import CryptContext

from app.core.config import SECRET_KEY, ALGORITHM
from app.services import auth_jwt_service


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(user_id: str) -> str:
    return auth_jwt_service.create_access_token({"sub": str(user_id)})


def create_refresh_token(user_id: str) -> str:
    return auth_jwt_service.create_refresh_token({"sub": str(user_id)})


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
