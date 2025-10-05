from common.utility.identifier import get_identifier
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import time


# Redis Fixed Window Rate Limiter Middleware

class RedisLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, limit: int = 10, window: int = 60):
        super().__init__(app)
        self.limit = limit
        self.window = window


    async def dispatch(self, request: Request, call_next):
        redis_client = request.app.state.redis
        identifier = get_identifier(request)

        key = f"r1:fixed:{identifier}:{request.url.path}"

        count = await redis_client.incr(key)
        # Initialize the window expiry on first request in the window
        if count == 1:
            await redis_client.expire(key, self.window)
        if count > self.limit:
            ttl = await redis_client.ttl(key)
            headers = {"Retry-After": str(ttl if ttl and ttl > 0 else self.window)}
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"}, headers=headers)
        
        response = await call_next(request)
        ttl = await redis_client.ttl(key)
        # Ensure sane defaults if Redis returns -2 (key does not exist) or -1 (no expiry)
        reset_seconds = ttl if ttl and ttl > 0 else self.window
        remaining = max(self.limit - count, 0)
        response.headers["X-RateLimit-Limit"] = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + int(reset_seconds))
        return response
