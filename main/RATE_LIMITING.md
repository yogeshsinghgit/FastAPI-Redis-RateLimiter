## Rate Limiting Architecture and Flow

### Overview
This project implements a fixed-window rate limiter for FastAPI using a custom middleware backed by Redis. Every incoming request is identified (via a client identifier) and counted within a discrete time window. If the number of requests exceeds the configured limit, the request is rejected with HTTP 429 Too Many Requests and appropriate headers instructing the client when to retry.

### Components
- **FastAPI application**: Hosts the API endpoints and installs the rate-limiting middleware.
- **Redis**: Acts as a fast, atomic counter and TTL store for request counts per identifier and route.
- **Middleware (`RedisLimitMiddleware`)**: Intercepts requests, increments counters in Redis, enforces limits, and sets response headers.
- **Identifier utility**: Extracts a stable identifier for the requester (e.g., IP address, API key, or a header), used to scope limits per client.

### Request Flow
1. **Request enters FastAPI** and is intercepted by `RedisLimitMiddleware`.
2. The middleware **derives a unique key** combining the identifier and path, e.g., `r1:fixed:{identifier}:{path}`.
3. The middleware **atomically increments** the Redis counter for that key using `INCR`.
4. On the **first increment in a window** (`count == 1`), the middleware **sets a TTL** on the key to the window size (seconds). This creates the fixed time window.
5. If the **count exceeds the limit**, the middleware reads the **remaining TTL** and returns `429 Too Many Requests` with `Retry-After`.
6. If under the limit, the middleware calls the route handler and then **annotates the response** with rate-limit headers.

### Fixed-Window Algorithm Details
- **Key format**: `r1:fixed:{identifier}:{route_path}`.
- **Atomic counter**: `INCR key` returns the current count for the window.
- **TTL management**:
  - When `count == 1`, set `EXPIRE key window_seconds`.
  - On subsequent increments within the same window, TTL remains unchanged; the window will expire naturally.
- **Limit enforcement**: If `count > limit`, reject with `429` and include `Retry-After` equal to the key TTL (fallback to window if TTL is missing).

### Why set TTL when `count == 1`?
Setting `TTL` on the first increment ensures that each unique key represents a fixed-length window that begins at the time of the first request in that window. Without setting the TTL at `count == 1`, the counter could persist indefinitely, and the concept of a window would be lost. Using `EXPIRE` only on the first hit avoids unnecessarily resetting the window and preserves the semantics of a fixed window.

### Response and Error Headers
- `X-RateLimit-Limit`: The maximum number of requests allowed in the window.
- `X-RateLimit-Remaining`: Remaining requests in the current window (never negative).
- `X-RateLimit-Reset`: Unix timestamp (seconds) when the current window resets.
- On `429 Too Many Requests`, the middleware sets `Retry-After` to the remaining TTL (seconds) for the current window.

### Middleware Responsibilities
- Resolve client identifier via `get_identifier(request)`.
- Build Redis key for the identifier and request path.
- Atomically increment request count and manage TTL on first request.
- Enforce limits and return `429` with `Retry-After` when exceeded.
- On success, propagate the request and set informative rate-limit headers on the response.

### Code Reference: Key Steps
Increment, TTL on first hit, and headers are handled in `main/middleware/redis_limit_middleware.py`:

```16:33:main/middleware/redis_limit_middleware.py
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
```

### Identifier Strategy
The identifier can be derived from client IP, an API key, a JWT subject, or a custom header. It should be stable across requests for the same client and difficult to spoof. Adjust `get_identifier` to fit your trust model (e.g., respect `X-Forwarded-For` only when behind a trusted proxy).

### Configuration
- **limit**: Maximum allowed requests per window (default: 10).
- **window**: Window size in seconds (default: 60).
- Tune these when instantiating the middleware (e.g., per-route or globally) based on endpoint sensitivity.

### Edge Cases and Safeguards
- **Redis TTL values**:
  - `-2`: key does not exist → fallback to window.
  - `-1`: key has no expiry → fallback to window.
- **Clock and header values**: `X-RateLimit-Reset` uses server time; clients should treat it as advisory.
- **Burstiness**: Fixed windows can be bursty at boundaries. If this is problematic, consider a sliding window or token-bucket algorithm as a future enhancement.

### Local Development and Running
- Ensure Redis is running (e.g., via Docker Compose).
- The FastAPI app attaches the middleware and provides a Redis client in `app.state.redis` during startup.

### Summary
The middleware implements a simple, robust fixed-window rate limiter using Redis atomic counters and key expirations. By setting the expiry only on the first increment, it establishes predictable windows, enforces limits consistently, and communicates rate-limit status to clients through standard headers.


