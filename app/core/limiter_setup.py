from fastapi import FastAPI
from fastapi_limiter import FastAPILimiter
import redis.asyncio as redis
import os


async def init_rate_limiter(app: FastAPI):
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = redis.Redis.from_url(redis_url, encoding="utf-8", decode_responses=True)

    await FastAPILimiter.init(redis_client)

    @app.on_event("shutdown")
    async def shutdown():
        await redis_client.aclose()
