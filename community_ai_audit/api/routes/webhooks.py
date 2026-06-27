"""Webhook CRUD."""

import json
from urllib.request import Request, urlopen
from urllib.error import URLError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from community_ai_audit.api.deps import require_user
from community_ai_audit.api.database import get_session, Webhook, Project

router = APIRouter(prefix="/webhooks", dependencies=[Depends(require_user)])


class CreateWebhook(BaseModel):
    project_id: str
    url: str
    events: list[str] = ["audit.completed"]


@router.post("")
def create_webhook(body: CreateWebhook):
    db = get_session()
    p = db.query(Project).filter(Project.id == body.project_id).first()
    if not p:
        db.close()
        raise HTTPException(404, "Project not found")
    w = Webhook(project_id=body.project_id, url=body.url, events=json.dumps(body.events))
    db.add(w)
    db.commit()
    db.close()
    return {"webhook_id": w.id}


@router.get("")
def list_webhooks():
    db = get_session()
    webhooks = db.query(Webhook).all()
    db.close()
    return [
        {"id": w.id, "project_id": w.project_id, "url": w.url, "events": json.loads(w.events)}
        for w in webhooks
    ]


@router.delete("/{webhook_id}")
def delete_webhook(webhook_id: str):
    db = get_session()
    w = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    if not w:
        db.close()
        raise HTTPException(404, "Webhook not found")
    db.delete(w)
    db.commit()
    db.close()
    return {"ok": True}


def deliver_webhook(url: str, event: str, payload: dict) -> str:
    data = json.dumps({"event": event, "payload": payload}).encode()
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = urlopen(req, timeout=10)
        return f"delivered ({resp.status})"
    except URLError as e:
        return f"failed ({e.reason})"
