from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

DEFAULT_PERSIST_DIR = "~/.community-ai-audit/redteam-persist"
DRIFT_THRESHOLD = 0.1


def _model_safe(model_id: str) -> str:
    return model_id.replace("/", "_").replace(":", "_").replace(".", "_")


class RedTeamPersistence:
    """Persists red team scan results to JSONL for drift analysis.

    Stores one JSON line per scan run per (model_id, scanner_name) pair.
    Enables comparing attack success rates over time.
    """

    def __init__(self, persist_dir: str = DEFAULT_PERSIST_DIR):
        self._dir = Path(persist_dir).expanduser()
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, model_id: str, scanner_name: str) -> Path:
        safe = _model_safe(model_id)
        return self._dir / f"{safe}__{scanner_name}.jsonl"

    def save(self, model_id: str, scanner_name: str, result: Dict[str, Any]) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_id": model_id,
            "scanner_name": scanner_name,
            "score": result.get("score", 0.0),
            "attack_success_rate": result.get("attack_success_rate", 0.0),
            "total_attacks": result.get("total_attacks", 0),
            "successful_attacks": result.get("successful_attacks", 0),
            "details": result.get("details", {}),
        }
        path = self._path(model_id, scanner_name)
        with open(path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        log.debug("Saved red team result for %s/%s", model_id, scanner_name)
        return entry["timestamp"]

    def save_multi(
        self, model_id: str, results: List[Dict[str, Any]]
    ) -> List[str]:
        timestamps = []
        for r in results:
            sn = r.get("scanner_name", "unknown")
            timestamps.append(self.save(model_id, sn, r))
        return timestamps

    def load_history(
        self,
        model_id: str,
        scanner_name: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        path = self._path(model_id, scanner_name)
        if not path.exists():
            return []
        entries: List[Dict[str, Any]] = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return entries[:limit]

    def get_latest(
        self, model_id: str, scanner_name: str
    ) -> Optional[Dict[str, Any]]:
        history = self.load_history(model_id, scanner_name, limit=1)
        return history[0] if history else None

    def list_scanners(self, model_id: str) -> List[str]:
        scanners = set()
        safe = _model_safe(model_id)
        for f in self._dir.iterdir():
            if f.suffix == ".jsonl" and f.stem.startswith(f"{safe}__"):
                scanner_part = f.stem[len(safe) + 2:]  # e.g., "gpt-4__jailbreak" -> "jailbreak"
                scanners.add(scanner_part)
        return sorted(scanners)

    def list_models(self) -> List[str]:
        models = set()
        for f in self._dir.iterdir():
            if f.suffix == ".jsonl" and "__" in f.stem:
                model_part = f.stem.split("__")[0]
                models.add(model_part)
        return sorted(models)

    def compute_drift(
        self,
        model_id: str,
        scanner_name: str,
        window: int = 5,
    ) -> Dict[str, Any]:
        history = self.load_history(model_id, scanner_name, limit=window)
        if not history:
            return {
                "scanner_name": scanner_name,
                "direction": "insufficient_data",
                "latest_success_rate": 0.0,
                "previous_success_rate": 0.0,
                "delta": 0.0,
            }
        rates = [e.get("attack_success_rate", 0.0) for e in reversed(history)]
        latest = rates[-1] if rates else 0.0
        previous = rates[-2] if len(rates) >= 2 else latest
        earliest = rates[0] if rates else 0.0
        delta = latest - earliest
        if delta > DRIFT_THRESHOLD:
            direction = "worsening"
        elif delta < -DRIFT_THRESHOLD:
            direction = "improving"
        else:
            direction = "stable"
        return {
            "scanner_name": scanner_name,
            "direction": direction,
            "latest_success_rate": round(latest, 4),
            "previous_success_rate": round(previous, 4),
            "delta": round(delta, 4),
            "window": len(rates),
            "values": [round(v, 4) for v in rates],
        }

    def drift_report(
        self, model_id: str, window: int = 5
    ) -> Dict[str, Any]:
        scanners = self.list_scanners(model_id)
        scanner_drifts = {}
        for sn in sorted(scanners):
            scanner_drifts[sn] = self.compute_drift(
                model_id, sn, window=window
            )
        overall_direction = "stable"
        worsening = [s for s, d in scanner_drifts.items() if d.get("direction") == "worsening"]
        improving = [s for s, d in scanner_drifts.items() if d.get("direction") == "improving"]
        if worsening and not improving:
            overall_direction = "worsening"
        elif improving and not worsening:
            overall_direction = "improving"
        return {
            "model_id": model_id,
            "overall_direction": overall_direction,
            "worsening_scanners": worsening,
            "improving_scanners": improving,
            "scanners": scanner_drifts,
        }
