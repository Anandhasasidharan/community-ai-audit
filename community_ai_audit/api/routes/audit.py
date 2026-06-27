"""Audit job submission and status endpoints."""
import json
from fastapi import APIRouter, Depends
from community_ai_audit.api.models import AuditRequest, AuditResponse, JobStatus
from community_ai_audit.api.deps import current_user
from community_ai_audit.api.database import get_session, AuditJob

router = APIRouter()


@router.post("", response_model=AuditResponse)
async def create_audit(req: AuditRequest, user: dict = Depends(current_user)):
    db = get_session()
    job = AuditJob(
        status="pending",
        model_id=req.model,
        provider=req.provider,
        scanners=json.dumps(req.scanners or []),
    )
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()
    return AuditResponse(job_id=job_id, status="pending", status_url=f"/audit/{job_id}")


@router.get("/{job_id}", response_model=JobStatus)
async def get_audit(job_id: str, user: dict = Depends(current_user)):
    db = get_session()
    job = db.query(AuditJob).filter(AuditJob.id == job_id).first()
    db.close()
    if not job:
        from fastapi import HTTPException
        raise HTTPException(404, "Job not found")
    return JobStatus(
        job_id=job.id,
        status=job.status,
        result=json.loads(job.results) if job.results else None,
        error=job.error,
    )
