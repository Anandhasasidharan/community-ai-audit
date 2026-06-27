"""List available scanners."""

from fastapi import APIRouter, Depends
from community_ai_audit.api.deps import current_user

router = APIRouter()


@router.get("")
async def list_scanners(user: dict = Depends(current_user)):
    from community_ai_audit.core.registry import plugins

    plugins.discover()
    return {"scanners": plugins.list_scanners()}
