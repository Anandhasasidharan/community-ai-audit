"""FastAPI application — wraps AuditEngine behind an async HTTP API."""
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from community_ai_audit.api.routes import health, audit, scanners, auth, projects, schedules, webhooks
from community_ai_audit.api.database import init_db


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_reqs: int = 60, window: int = 60):
        super().__init__(app)
        self.max_reqs = max_reqs
        self.window = window
        self.requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client = request.client.host if request.client else "unknown"
        now = time.time()
        timestamps = self.requests[client]
        timestamps[:] = [t for t in timestamps if now - t < self.window]
        if len(timestamps) >= self.max_reqs:
            return JSONResponse({"error": "rate limit exceeded"}, status_code=429)
        timestamps.append(now)
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Community AI Audit API", version="0.6.1", lifespan=lifespan)
app.add_middleware(RateLimitMiddleware, max_reqs=60, window=60)
app.include_router(health.router)
app.include_router(audit.router, prefix="/audit")
app.include_router(scanners.router, prefix="/scanners")
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(schedules.router)
app.include_router(webhooks.router)
