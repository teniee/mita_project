from __future__ import annotations

from datetime import datetime, timedelta
import time
import uuid

from jose import JWTError, jwt

from app.core.config import ALGORITHM, settings
from app.core.upstash import (
    blacklist_token as upstash_blacklist_token,
    is_token_blacklisted,
)

ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = 7


def _current_secret() -> str:
    return settings.SECRET_KEY


def _previous_secret() -> str | None:
    return settings.JWT_PREVIOUS_SECRET


def _create_token(data: dict, expires_delta: timedelta, scope: str) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({
        "exp": expire,
        "scope": scope,
        "jti": str(uuid.uuid4()),
    })
    return jwt.encode(to_encode, _current_secret(), algorithm=ALGORITHM)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    return _create_token(
        data,
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "access_token",
    )


def create_refresh_token(data: dict) -> str:
    return _create_token(
        data,
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "refresh_token",
    )


def verify_token(token: str, scope: str = "access_token") -> dict | None:
    secrets = [_current_secret()]
    prev = _previous_secret()
    if prev:
        secrets.append(prev)

    for secret in secrets:
        try:
            payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
            if payload.get("scope") != scope:
                raise JWTError("Invalid token scope")
            jti = payload.get("jti")
            if jti and is_token_blacklisted(jti):
                raise JWTError("Token is blacklisted")
            return payload
        except JWTError:
            continue
    return None


def blacklist_token(token: str) -> None:
    secrets = [_current_secret()]
    prev = _previous_secret()
    if prev:
        secrets.append(prev)

    for secret in secrets:
        try:
            payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                ttl = max(0, int(exp - time.time()))
                upstash_blacklist_token(jti, ttl)
            break
        except JWTError:
            continue

