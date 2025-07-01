from datetime import datetime, timedelta

from jose import JWTError, jwt

from app.core.config import ALGORITHM, settings

ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Could be replaced by Redis/DB storage
TOKEN_BLACKLIST = set()


def _current_secret():
    return settings.SECRET_KEY


def _previous_secret():
    return settings.JWT_PREVIOUS_SECRET


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, _current_secret(), algorithm=ALGORITHM)


def create_refresh_token(data: dict):
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = data.copy()
    to_encode.update({"exp": expire, "scope": "refresh_token"})
    return jwt.encode(to_encode, _current_secret(), algorithm=ALGORITHM)


def verify_token(token: str, scope: str = "access_token"):
    secrets = [_current_secret()]
    prev = _previous_secret()
    if prev:
        secrets.append(prev)

    for secret in secrets:
        try:
            payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
            if payload.get("scope") != scope:
                raise JWTError("Invalid token scope")
            if token in TOKEN_BLACKLIST:
                raise JWTError("Token is blacklisted")
            return payload
        except JWTError:
            continue
    return None


def blacklist_token(token: str):
    TOKEN_BLACKLIST.add(token)
