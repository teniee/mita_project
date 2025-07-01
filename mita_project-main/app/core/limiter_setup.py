from fastapi import FastAPI
from fastapi_limiter import FastAPILimiter
import redis.asyncio as redis


async def init_rate_limiter(app: FastAPI):
    # Your Upstash Redis URL with TLS
    redis_url = "rediss://default:AV-OAAIjcDE4YzViNmZmNzY5ZTc0NWM4ODI3MzU0M2VlODgzYTQwNnAxMA@boss-koi-24462.upstash.io:6379"

    # Create the Redis client connection
    redis_client = await redis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True
    )

    # Initialize FastAPI Limiter with this Redis connection
    await FastAPILimiter.init(redis_client)

    @app.on_event("shutdown")
    async def shutdown():
        await redis_client.aclose()
