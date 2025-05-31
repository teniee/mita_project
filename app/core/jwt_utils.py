import os, datetime, uuid
import jwt
from passlib.context import CryptContext

SECRET_KEY=os.getenv("JWT_SECRET","change_me")
ALGORITHM="HS256"
ACCESS_EXPIRES_MIN=30
REFRESH_EXPIRES_DAYS=7

pwd_context=CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_token(data:dict, expires_delta:datetime.timedelta):
    to_encode=data.copy()
    to_encode.update({"exp": datetime.datetime.utcnow()+expires_delta,
                      "jti": str(uuid.uuid4())})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_access_token(user_id:str):
    return create_token({"sub": str(user_id), "type":"access"},
        datetime.timedelta(minutes=ACCESS_EXPIRES_MIN))

def create_refresh_token(user_id:str):
    return create_token({"sub": str(user_id), "type":"refresh"},
        datetime.timedelta(days=REFRESH_EXPIRES_DAYS))

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def hash_password(plain):
    return pwd_context.hash(plain)

def decode_token(token:str):
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])