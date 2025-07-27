import os

import httpx

UPSTASH_URL = os.getenv("UPSTASH_URL", "https://global.api.upstash.com")
UPSTASH_AUTH_TOKEN = os.getenv("UPSTASH_AUTH_TOKEN")


def _auth_header() -> dict:
    if not UPSTASH_AUTH_TOKEN:
        raise RuntimeError("UPSTASH_AUTH_TOKEN not configured")
    return {"Authorization": f"Bearer {UPSTASH_AUTH_TOKEN}"}


def blacklist_token(jti: str, ttl: int):
    if not UPSTASH_AUTH_TOKEN:
        # If upstash is not configured, skip blacklisting
        print("Warning: UPSTASH_AUTH_TOKEN not configured, skipping token blacklisting")
        return
    
    url = f"{UPSTASH_URL}/set/revoked:jwt:{jti}?EX={ttl}"
    response = httpx.post(url, headers=_auth_header())
    response.raise_for_status()


def is_token_blacklisted(jti: str) -> bool:
    if not UPSTASH_AUTH_TOKEN:
        # If upstash is not configured, assume token is not blacklisted
        print("Warning: UPSTASH_AUTH_TOKEN not configured, assuming token is not blacklisted")
        return False
    
    url = f"{UPSTASH_URL}/get/revoked:jwt:{jti}"
    response = httpx.get(url, headers=_auth_header())
    return response.json().get("result") is not None
