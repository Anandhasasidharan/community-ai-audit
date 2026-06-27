"""Audit schedule CRUD."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from croniter import croniter
from community_ai_audit.api.deps import require_user
from community_ai_audit.api.database import get_session, Schedule, Project

router = APIRouter(prefix="/schedules", dependencies=[Depends(require_user)])


class CreateSchedule(BaseModel):
    project_id: str
    cron_expr: str
    model_id: str


@router.post("")
def create_schedule(body: CreateSchedule):
    if not croniter.is_valid(body.cron_expr):
        raise HTTPException(400, "Invalid cron expression")
    db = get_session()
    p = db.query(Project).filter(Project.id == body.project_id).first()
    if not p:
        db.close()
        raise HTTPException(404, "Project not found")
    now = datetime.now(timezone.utc)
    next_run = croniter(body.cron_expr, now).get_next(datetime)
    s = Schedule(
        project_id=body.project_id,
        cron_expr=body.cron_expr,
        model_id=body.model_id,
        next_run=next_run,
    )
    db.add(s)
    db.commit()
    db.close()
    return {"schedule_id": s.id, "next_run": str(next_run)}


@router.get("")
def list_schedules():
    db = get_session()
    schedules = db.query(Schedule).all()
    db.close()
    return [
        {
            "id": s.id,
            "project_id": s.project_id,
            "cron_expr": s.cron_expr,
            "model_id": s.model_id,
            "next_run": str(s.next_run),
        }
        for s in schedules
    ]


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: str):
    db = get_session()
    s = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not s:
        db.close()
        raise HTTPException(404, "Schedule not found")
    db.delete(s)
    db.commit()
    db.close()
    return {"ok": True}
