
from datetime import datetime, timedelta
from jose import JWTError, jwt

from app.core.config import SECRET_KEY, ALGORITHM, settings

ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Could be replaced by Redis/DB storage
TOKEN_BLACKLIST = set()

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict):
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = data.copy()
    to_encode.update({"exp": expire, "scope": "refresh_token"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str, scope: str = "access_token"):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("scope") != scope:
            raise JWTError("Invalid token scope")
        if token in TOKEN_BLACKLIST:
            raise JWTError("Token is blacklisted")
        return payload
    except JWTError:
        return None

def blacklist_token(token: str):
    TOKEN_BLACKLIST.add(token)
