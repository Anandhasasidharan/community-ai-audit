"""ARQ background tasks — audit, webhook delivery, schedule check."""

import json
import logging
from datetime import datetime, timezone
from croniter import croniter
from community_ai_audit.core.audit import AuditEngine
from community_ai_audit.api.database import get_session, AuditJob, Webhook, Schedule
from community_ai_audit.api.routes.webhooks import deliver_webhook

log = logging.getLogger(__name__)


async def run_audit_task(
    ctx: dict, job_id: str, model: str, provider: str, scanners: list[str] | None = None
) -> dict:
    db = get_session()
    job = db.query(AuditJob).filter(AuditJob.id == job_id).first()
    if not job:
        return {"error": "job not found"}
    job.status = "running"
    db.commit()
    try:
        engine = AuditEngine()
        engine.load_model(model, provider=provider)
        session = engine.audit(scanners=scanners)
        result = session.to_dict()
        job.status = "done"
        job.results = json.dumps(result)
        job.risk_score = result.get("risk_score")
        job.severity = result.get("severity")
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        # fire webhooks
        if job.project_id:
            _fire_webhooks(
                db,
                job.project_id,
                "audit.completed",
                {"job_id": job_id, "status": "done", "model": model},
            )
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        log.exception("audit job %s failed", job_id)
    finally:
        db.close()
    return {"job_id": job_id, "status": job.status}


async def check_schedules(ctx: dict) -> None:
    db = get_session()
    now = datetime.now(timezone.utc)
    schedules = db.query(Schedule).filter(Schedule.next_run <= now).all()
    for s in schedules:
        job = AuditJob(
            project_id=s.project_id,
            status="pending",
            model_id=s.model_id,
            scanners="[]",
        )
        db.add(job)
        db.flush()
        s.next_run = croniter(s.cron_expr, now).get_next(datetime)
        db.commit()
        await ctx["redis"].enqueue_job("run_audit_task", job.id, s.model_id, "huggingface")
        log.info("scheduled audit %s from schedule %s", job.id, s.id)
    db.close()


def _fire_webhooks(db, project_id: str, event: str, payload: dict) -> None:
    webhooks = (
        db.query(Webhook)
        .filter(
            Webhook.project_id == project_id,
        )
        .all()
    )
    for w in webhooks:
        events = json.loads(w.events)
        if event in events:
            result = deliver_webhook(w.url, event, payload)
            log.info("webhook %s -> %s: %s", w.id, w.url, result)
