
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timedelta
from collections import defaultdict

# In-memory rate tracking
rate_limit_store = defaultdict(list)

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 5, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(p in path for p in ["/ocr", "/gpt", "/ai"]):
            client_ip = request.client.host
            now = datetime.utcnow()
            key = f"{client_ip}:{path}"
            rate_limit_store[key] = [t for t in rate_limit_store[key] if now - t < self.window]
            rate_limit_store[key].append(now)

            if len(rate_limit_store[key]) > self.max_requests:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")

        response = await call_next(request)
        return response
