"""Usage metering — query usage records for the current user."""

from fastapi import APIRouter, Depends, Query
from community_ai_audit.api.deps import current_user
from community_ai_audit.api.database import get_session, UseageRecord

router = APIRouter(prefix="/usage")


@router.get("")
async def get_usage(
    user: dict = Depends(current_user),
    limit: int = Query(100, le=1000),
):
    db = get_session()
    q = db.query(UseageRecord)
    if user.get("role") == "admin":
        pass
    elif "org_id" in user:
        q = q.filter((UseageRecord.org_id == user["org_id"]) | UseageRecord.org_id.is_(None))
    elif "user_id" in user:
        q = q.filter((UseageRecord.user_id == user["user_id"]) | UseageRecord.user_id.is_(None))
    else:
        q = q.filter(UseageRecord.user_id.is_(None))
    records = q.order_by(UseageRecord.timestamp.desc()).limit(limit).all()
    db.close()
    return [
        {
            "id": r.id,
            "endpoint": r.endpoint,
            "method": r.method,
            "status_code": r.status_code,
            "timestamp": r.timestamp.isoformat(),
        }
        for r in records
    ]
