"""Health check endpoints."""

from fastapi import APIRouter
from community_ai_audit.api.database import engine

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "version": "0.6.1"}


@router.get("/health/ready")
async def ready():
    try:
        with engine.connect() as conn:
            conn.execute(conn.default_schema_name or "SELECT 1")
        return {"status": "ready"}
    except Exception as e:
        return {"status": "unavailable", "detail": str(e)}
