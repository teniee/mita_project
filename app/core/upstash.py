
import httpx

UPSTASH_URL = "https://global.api.upstash.com"
UPSTASH_AUTH_HEADER = {
    "Authorization": "Bearer AUgCAAIjcDFmNDAzNWFlMGM0NWU0NDQxYjU4OWNhZjg0OTNhYWEzNnAxMA"
}

def blacklist_token(jti: str, ttl: int):
    url = f"{UPSTASH_URL}/set/revoked:jwt:{jti}?EX={ttl}"
    response = httpx.post(url, headers=UPSTASH_AUTH_HEADER)
    response.raise_for_status()

def is_token_blacklisted(jti: str) -> bool:
    url = f"{UPSTASH_URL}/get/revoked:jwt:{jti}"
    response = httpx.get(url, headers=UPSTASH_AUTH_HEADER)
    return response.json().get("result") is not None
