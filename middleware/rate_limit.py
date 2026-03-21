"""Redis-backed rate limiting middleware."""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from services.redis import get_redis
from services.logging import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window rate limiter using Redis."""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.rpm = requests_per_minute

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and WebSocket
        if request.url.path in ("/health",) or request.url.path.startswith("/ws"):
            return await call_next(request)

        # Use IP as the rate limit key (swap for user_id in production)
        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{client_ip}"

        try:
            redis = await get_redis()
            now = time.time()
            window_start = now - 60

            pipe = redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, 70)
            results = await pipe.execute()

            request_count = results[2]
            if request_count > self.rpm:
                logger.warning("rate_limit.exceeded", ip=client_ip, count=request_count)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                    headers={"Retry-After": "60"},
                )
        except Exception:
            # If Redis is down, allow the request
            pass

        return await call_next(request)
