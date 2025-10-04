from main.common.utility.identifier import get_identifier
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi import FastAPI, Request, Callable
from fastapi.responses import JSONResponse


# Redis Fixed Window Rate Limiter Middleware

class RedisLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, limit: int = 10, window: int = 60):
        super().__init__(app)
        self.limit = limit
        self.window = window


    async def dispatch(self, request: Request, call_next: Callable):
        redis_client = request.app.state.redis
        identifier = get_identifier(request)

        key = f"r1:fixed:{identifier}:{request.url.path}"

        count = await redis_client.incr(key)
        if count > self.limit:
            ttl = await redis_client.ttl(key)
            headers = {"Retry-After": str(ttl if ttl and ttl > 0 else self.window)}
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"}, headers=headers)
        
        response = await call_next(request)
        response.headers.update(f"X-RateLimit-Limit:{self.limit}")
        response.headers.update(f"X-RateLimit-Remaining:{self.limit - count}")
        response.headers.update(f"X-RateLimit-Reset:{time.time() + self.window}")
        return response
