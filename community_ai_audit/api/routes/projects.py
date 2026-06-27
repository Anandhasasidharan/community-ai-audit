"""Project CRUD and project-scoped audit submission."""
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from community_ai_audit.api.deps import require_user
from community_ai_audit.api.database import get_session, Project, AuditJob

router = APIRouter(prefix="/projects", dependencies=[Depends(require_user)])


class CreateProject(BaseModel):
    name: str


class AuditRequest(BaseModel):
    model: str
    provider: str
    scanners: list[str] | None = None


@router.post("")
def create_project(body: CreateProject):
    db = get_session()
    p = Project(name=body.name)
    db.add(p)
    db.commit()
    db.close()
    return {"project_id": p.id}


@router.get("")
def list_projects():
    db = get_session()
    projects = db.query(Project).all()
    db.close()
    return [{"id": p.id, "name": p.name} for p in projects]


@router.post("/{project_id}/audits")
def create_project_audit(project_id: str, body: AuditRequest):
    db = get_session()
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        db.close()
        raise HTTPException(404, "Project not found")
    job = AuditJob(
        project_id=project_id,
        status="pending",
        model_id=body.model,
        provider=body.provider,
        scanners=json.dumps(body.scanners or []),
    )
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()
    return {"job_id": job_id, "status": "pending"}


@router.get("/{project_id}/audits")
def list_project_audits(project_id: str):
    db = get_session()
    jobs = db.query(AuditJob).filter(AuditJob.project_id == project_id).all()
    db.close()
    return [
        {"id": j.id, "status": j.status, "created_at": str(j.created_at)} for j in jobs
    ]
