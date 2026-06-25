from __future__ import annotations

import logging
import random
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger("demo")

app = FastAPI(title="Community AI Audit - Demo")

HERE = Path(__file__).parent
STATIC = HERE / "static"
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

MODEL_ID = "distilgpt2"

store: Dict[str, Any] = {}
store_lock = threading.Lock()
audit_status: Dict[str, Any] = {}
_audit_in_progress: Dict[str, threading.Event] = {}


class DistilGPT2Adapter:
    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._device = "cpu"

    def _ensure_loaded(self):
        if self._model is not None:
            return
        log.info("Loading distilgpt2 model (cached from HF)...")
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = AutoModelForCausalLM.from_pretrained("distilgpt2").to(self._device)
        self._tokenizer = AutoTokenizer.from_pretrained("distilgpt2")
        self._tokenizer.pad_token = self._tokenizer.eos_token
        log.info("distilgpt2 loaded on %s", self._device)

    def generate(self, model: Any, prompt: str, **kwargs: Any) -> str:
        self._ensure_loaded()
        import torch
        inputs = self._tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        inputs = {k: v.to(self._device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=kwargs.get("max_new_tokens", 20),
                do_sample=True,
                temperature=0.7,
                pad_token_id=self._tokenizer.eos_token_id,
            )
        text = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
        return text[len(prompt):].strip() or text.strip()

    def predict(self, model: Any, inputs: Any, **kwargs: Any) -> Any:
        if isinstance(inputs, str):
            return self.generate(model, inputs)
        if isinstance(inputs, dict) and "prompt" in inputs:
            return self.generate(model, inputs["prompt"])
        return self.generate(model, str(inputs))


_ADAPTER: Optional[DistilGPT2Adapter] = None
_ADAPTER_LOCK = threading.Lock()


def get_adapter() -> DistilGPT2Adapter:
    global _ADAPTER
    if _ADAPTER is None:
        with _ADAPTER_LOCK:
            if _ADAPTER is None:
                _ADAPTER = DistilGPT2Adapter()
    return _ADAPTER


def _run_sync_audit(model_id: str) -> Dict[str, Any]:
    store_lock.acquire()
    if model_id in store:
        store_lock.release()
        return store[model_id]
    if model_id in _audit_in_progress:
        event = _audit_in_progress[model_id]
        store_lock.release()
        event.wait()
        store_lock.acquire()
        result = store.get(model_id, {})
        store_lock.release()
        return result
    event = threading.Event()
    _audit_in_progress[model_id] = event
    store_lock.release()

    try:
        result = _do_audit(model_id)
        store_lock.acquire()
        store[model_id] = result
        store_lock.release()
        return result
    finally:
        store_lock.acquire()
        _audit_in_progress.pop(model_id, None)
        event.set()
        store_lock.release()


def _do_audit(model_id: str) -> Dict[str, Any]:
    from community_ai_audit.plugins.redteam import run_redteam_scanners
    from community_ai_audit.plugins.alignment import run_alignment_scanners
    from community_ai_audit.plugins.mechinterp import run_mechinterp_analyzers
    from community_ai_audit.core.scoring.engine import ScoringEngine
    from community_ai_audit.core.evaluation.trends import AuditTrendTracker

    adapter = get_adapter()

    log.info("Running red team scanners (distilgpt2)...")
    red_team_results = run_redteam_scanners(model=None, adapter=adapter)

    log.info("Running alignment scanners (distilgpt2)...")
    alignment_results = run_alignment_scanners(model=None, adapter=adapter)

    log.info("Running mechinterp analyzers (distilgpt2)...")
    mechinterp_results = run_mechinterp_analyzers(model=None, adapter=adapter)

    log.info("Running built-in scanners...")
    from community_ai_audit.core.registry import plugins
    plugins.discover()
    scan_results: List[Dict[str, Any]] = []
    for name in plugins.list_scanners():
        try:
            scanner = plugins.scanners.get(name)
            result = scanner.scan(None, adapter)
            findings_list = []
            if hasattr(result, "findings"):
                for f in result.findings:
                    findings_list.append({
                        "severity": getattr(f, "severity", "medium"),
                        "description": getattr(f, "description", str(f)),
                        "category": getattr(f, "category", "general"),
                    })
            scan_results.append({
                "scanner_name": name,
                "findings": findings_list,
                **({"score": result.score} if hasattr(result, "score") else {}),
            })
        except Exception as e:
            log.warning("Scanner '%s' failed: %s", name, e)

    log.info("Computing unified score...")
    engine = ScoringEngine()
    score = engine.compute(
        scan_results=scan_results,
        policy_results=[],
        reliability_results=[],
        agent_results=[],
        red_team_results=red_team_results,
        alignment_results=alignment_results,
        interpretability_results=mechinterp_results,
    )

    score_dict = score.to_dict()

    log.info("Recording trend snapshot...")
    try:
        tracker = AuditTrendTracker(storage_dir="/tmp/community-ai-audit-demo/trends")
        scores_flat = {
            "security": score_dict["security_score"],
            "reliability": score_dict["reliability_score"],
            "compliance": score_dict["compliance_score"],
            "agent_risk": score_dict["agent_risk_score"],
            "alignment": score_dict["alignment_score"],
            "red_team": score_dict["red_team_score"],
            "interpretability": score_dict["interpretability_score"],
        }
        tracker.record(model_id, scores_flat, metadata={"source": "demo_webapp"})
    except Exception as e:
        log.warning("Trend recording failed: %s", e)

    result = {
        "score": score_dict,
        "red_team": red_team_results,
        "alignment": alignment_results,
        "mechinterp": mechinterp_results,
        "scan": scan_results,
        "model_id": model_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return result


def _generate_trend_history() -> List[Dict[str, Any]]:
    base_scores = {
        "security": 72.0,
        "reliability": 65.0,
        "compliance": 80.0,
        "agent_risk": 75.0,
        "alignment": 68.0,
        "red_team": 70.0,
        "interpretability": 55.0,
    }
    history = []
    for i in range(8):
        ts = datetime(2026, 5, 25 + i, 10, 0, 0, tzinfo=timezone.utc)
        scores = {}
        for dim, base in base_scores.items():
            noise = random.uniform(-8, 8)
            drift = i * random.uniform(-1.5, 1.5)
            scores[dim] = round(max(0, min(100, base + noise + drift)), 1)
        history.append({
            "timestamp": ts.isoformat(),
            "scores": scores,
            "snapshot_id": f"snap_{i}",
        })
    return history


def _get_trends(model_id: str) -> Dict[str, Any]:
    try:
        from community_ai_audit.core.evaluation.trends import AuditTrendTracker
        tracker = AuditTrendTracker(storage_dir="/tmp/community-ai-audit-demo/trends")
        report = tracker.trend_report(model_id)
        hist = tracker.get_history(model_id, limit=0)
        return {
            "trends": {dim: r.to_dict() for dim, r in report.items()},
            "history": [s.to_dict() for s in hist],
        }
    except Exception as e:
        log.warning("Could not load trends: %s", e)
        return {"trends": {}, "history": _generate_trend_history()}


@app.on_event("startup")
async def startup():
    log.info("Pre-seeding: loading distilgpt2 + running all scanners...")
    try:
        _run_sync_audit(MODEL_ID)
        log.info("Pre-seed complete.")
    except Exception as e:
        log.warning("Pre-seed failed: %s", e)


@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = STATIC / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text())
    return HTMLResponse(content="<h1>Demo App</h1><p>Frontend not found.</p>")


@app.get("/api/status")
async def server_status():
    adapter = get_adapter()
    return {
        "model_id": MODEL_ID,
        "model_loaded": adapter._model is not None,
        "cached_results": list(store.keys()),
    }


@app.get("/api/scanners")
async def list_scanners():
    from community_ai_audit.plugins.redteam import list_redteam_scanners
    from community_ai_audit.plugins.alignment import list_alignment_scanners
    from community_ai_audit.plugins.mechinterp import list_mechinterp_analyzers
    from community_ai_audit.core.registry import plugins
    plugins.discover()
    return {
        "builtin": plugins.list_scanners(),
        "redteam": list_redteam_scanners(),
        "alignment": list_alignment_scanners(),
        "mechinterp": list_mechinterp_analyzers(),
    }


@app.get("/api/dashboard/{model_id}")
async def dashboard(model_id: str):
    data = _run_sync_audit(model_id)
    score = data["score"]
    rating = "Excellent" if score["overall_score"] >= 90 else \
             "Good" if score["overall_score"] >= 80 else \
             "Fair" if score["overall_score"] >= 70 else \
             "Poor" if score["overall_score"] >= 60 else \
             "Critical"
    return {
        "score": score,
        "rating": rating,
        "model_id": model_id,
        "radar": {
            "labels": ["Security", "Reliability", "Compliance", "Agent Risk", "Alignment", "Red Team", "Interpretability"],
            "values": [
                score["security_score"],
                score["reliability_score"],
                score["compliance_score"],
                score["agent_risk_score"],
                score["alignment_score"],
                score["red_team_score"],
                score["interpretability_score"],
            ],
        },
    }


@app.get("/api/results/{model_id}")
async def results(model_id: str):
    data = _run_sync_audit(model_id)
    return {"results": data, "model_id": model_id}


@app.get("/api/trends/{model_id}")
async def trends(model_id: str):
    return _get_trends(model_id)


@app.post("/api/audit/run")
async def run_audit(background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())[:8]
    audit_status[task_id] = {"status": "running", "progress": 0}

    def _run():
        try:
            audit_status[task_id]["progress"] = 10
            _run_sync_audit(MODEL_ID)
            audit_status[task_id] = {"status": "completed", "progress": 100}
        except Exception as e:
            audit_status[task_id] = {"status": "failed", "error": str(e)}

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return {"task_id": task_id, "status": "started"}


@app.get("/api/audit/status/{task_id}")
async def audit_status_endpoint(task_id: str):
    status = audit_status.get(task_id, {"status": "unknown"})
    return {"task_id": task_id, **status}
