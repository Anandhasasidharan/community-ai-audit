"""Dependencies — JWT + API key auth."""
import os
from fastapi import Header, HTTPException
from community_ai_audit.api.auth import decode_jwt
from community_ai_audit.api.database import get_session, ApiKey

MASTER_KEY = os.environ.get("COMMUNITY_AI_AUDIT_API_KEY")


async def current_user(
    authorization: str = Header(None),
    x_api_key: str = Header(None),
) -> dict:
    if authorization and authorization.startswith("Bearer "):
        payload = decode_jwt(authorization[7:])
        if payload:
            return payload
    if x_api_key:
        if MASTER_KEY and x_api_key == MASTER_KEY:
            return {"role": "admin"}
        db = get_session()
        row = db.query(ApiKey).filter(ApiKey.key == x_api_key).first()
        db.close()
        if row:
            return {"user_id": row.user_id, "role": "user"}
    raise HTTPException(401, "Authentication required")


require_user = current_user
