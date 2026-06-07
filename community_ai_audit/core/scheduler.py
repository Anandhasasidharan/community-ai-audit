"""
Cron-based recurring audit scheduler.

Uses croniter to parse standard 5-field cron expressions and determines
which schedules are due based on the current time.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

def _get_croniter():
    """Lazy import of croniter to avoid breaking module imports."""
    try:
        from croniter import croniter as _ci
        return _ci
    except ImportError:
        raise ImportError(
            "The 'croniter' package is required for scheduling. "
            "Install it with: pip install croniter"
        )


DEFAULT_SCHEDULES_PATH = Path("~/.community-ai-audit/schedules.json").expanduser()


class AuditScheduler:
    """Manage recurring audit schedules persisted in a JSON file.

    Each schedule defines which model, scanners, interpreters, and
    connectors to run on a cron-based cadence.

    Attributes:
        schedules_path: Path to the JSON file storing schedule definitions.
    """

    def __init__(self, schedules_path: Optional[str] = None) -> None:
        """Load schedules from the JSON file.

        Args:
            schedules_path: Path to the schedules JSON file.
                Defaults to ``~/.community-ai-audit/schedules.json``.
        """
        self.schedules_path: Path = (
            Path(schedules_path).expanduser()
            if schedules_path
            else DEFAULT_SCHEDULES_PATH
        )
        self._schedules: Dict[str, Dict[str, Any]] = {}

        if self.schedules_path.exists():
            self._load()

    # ── Public API ───────────────────────────────────────────────

    def add_schedule(
        self,
        name: str,
        cron: str,
        model_id: str,
        provider: str,
        scanners: Optional[List[str]] = None,
        interpreters: Optional[List[str]] = None,
        connectors: Optional[List[str]] = None,
        profile: str = "standard",
        output_format: str = "markdown",
    ) -> Dict[str, Any]:
        """Add a new recurring audit schedule.

        Args:
            name: Unique name for this schedule.
            cron: Standard 5-field cron expression (e.g. ``"0 6 * * *"``).
            model_id: Model identifier to audit (e.g. ``"gpt-4o"``).
            provider: Model provider name (e.g. ``"openai"``).
            scanners: List of scanner plugin names to run.
            interpreters: List of interpreter plugin names to run.
            connectors: List of connector names to push results to.
            profile: Audit profile tag (default ``"standard"``).
            output_format: Report format (default ``"markdown"``).

        Returns:
            The newly created schedule dictionary.

        Raises:
            ValueError: If a schedule with the same name already exists
                or the cron expression is invalid.
        """
        if name in self._schedules:
            raise ValueError(f"Schedule '{name}' already exists.")

        # Validate cron expression by attempting to create a croniter instance
        try:
            _get_croniter()(cron, datetime.now(timezone.utc))
        except (ValueError, KeyError) as exc:
            raise ValueError(
                f"Invalid cron expression '{cron}': {exc}"
            ) from exc

        schedule: Dict[str, Any] = {
            "name": name,
            "cron": cron,
            "model_id": model_id,
            "provider": provider,
            "scanners": scanners or [],
            "interpreters": interpreters or [],
            "connectors": connectors or [],
            "profile": profile,
            "output_format": output_format,
            "last_run": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        self._schedules[name] = schedule
        self.save()
        log.info("Added schedule '%s': %s", name, cron)
        return schedule

    def remove_schedule(self, name: str) -> None:
        """Remove a schedule by name.

        Args:
            name: Name of the schedule to remove.

        Raises:
            KeyError: If no schedule with that name exists.
        """
        if name not in self._schedules:
            raise KeyError(f"Schedule '{name}' not found.")
        del self._schedules[name]
        self.save()
        log.info("Removed schedule '%s'", name)

    def list_schedules(self) -> List[Dict[str, Any]]:
        """Return all schedules as a list of dictionaries."""
        return list(self._schedules.values())

    def get_due_schedules(
        self,
        now: Optional[datetime] = None,
    ) -> List[Tuple[Dict[str, Any], datetime]]:
        """Check which schedules are due for execution.

        A schedule is due when the current time is at or past its next
        scheduled run time.

        Args:
            now: Current datetime (timezone-aware). Defaults to
                ``datetime.now(timezone.utc)``.

        Returns:
            List of ``(schedule_dict, next_run_time)`` tuples for every
            schedule whose next run is due.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        due: List[Tuple[Dict[str, Any], datetime]] = []

        for schedule in self._schedules.values():
            last_run = schedule.get("last_run")
            base_time: datetime

            if last_run:
                base_time = datetime.fromisoformat(last_run)
                if base_time.tzinfo is None:
                    base_time = base_time.replace(tzinfo=timezone.utc)
            else:
                # Never run before — use schedule creation time as base
                created = schedule.get("created_at")
                if created:
                    base_time = datetime.fromisoformat(created)
                else:
                    base_time = now
                if base_time.tzinfo is None:
                    base_time = base_time.replace(tzinfo=timezone.utc)

            try:
                cron_iter = _get_croniter()(schedule["cron"], base_time)
                next_run = cron_iter.get_next(datetime)
            except (ValueError, KeyError) as exc:
                log.warning(
                    "Skipping schedule '%s': invalid cron '%s' — %s",
                    schedule["name"],
                    schedule["cron"],
                    exc,
                )
                continue

            if next_run <= now:
                due.append((schedule, next_run))

        return due

    def mark_run(self, name: str) -> None:
        """Update the ``last_run`` timestamp for a schedule.

        Call this after a schedule has been executed to advance its
        cron reference point.

        Args:
            name: Name of the schedule to update.

        Raises:
            KeyError: If no schedule with that name exists.
        """
        if name not in self._schedules:
            raise KeyError(f"Schedule '{name}' not found.")
        self._schedules[name]["last_run"] = datetime.now(timezone.utc).isoformat()
        self.save()
        log.debug("Marked run for schedule '%s'", name)

    def save(self) -> None:
        """Persist all schedules to the JSON file."""
        self.schedules_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.schedules_path, "w") as f:
            json.dump(self._schedules, f, indent=2)
        log.debug("Schedules saved to %s", self.schedules_path)

    def run_due(
        self,
        engine: Any,
        now: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Run all due schedules using an AuditEngine instance.

        For each due schedule the engine is configured with the
        schedule's model, scanners, interpreters, and connectors.
        After the audit completes, ``mark_run`` is called so the
        schedule advances to its next interval.

        Args:
            engine: An ``AuditEngine`` instance ready for ``load_model``
                and ``audit`` calls.
            now: Current datetime. Defaults to UTC now.

        Returns:
            List of result dicts — one per executed schedule — each
            containing ``schedule`` and ``session`` keys.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        results: List[Dict[str, Any]] = []
        due = self.get_due_schedules(now)

        if not due:
            log.info("No schedules due.")
            return results

        for schedule, next_run in due:
            log.info(
                "Running schedule '%s' (next run was due at %s)",
                schedule["name"],
                next_run.isoformat(),
            )

            try:
                engine.load_model(
                    model_id=schedule["model_id"],
                    provider=schedule["provider"],
                )

                session = engine.audit(
                    scanners=schedule.get("scanners") or None,
                    interpreters=schedule.get("interpreters") or None,
                    connectors=schedule.get("connectors") or None,
                )

                report = engine.generate_report(
                    session,
                    format=schedule.get("output_format", "markdown"),
                )

                self.mark_run(schedule["name"])

                results.append({
                    "schedule": schedule["name"],
                    "session": session.to_dict(),
                    "report": report,
                })

                log.info(
                    "Schedule '%s' completed: %d findings",
                    schedule["name"],
                    session.total_findings,
                )

            except Exception as exc:
                log.error(
                    "Schedule '%s' failed: %s",
                    schedule["name"],
                    exc,
                )
                results.append({
                    "schedule": schedule["name"],
                    "error": str(exc),
                })

        return results

    def _get_next_run(self, cron_expr: str) -> Optional[datetime]:
        """Compute the next run time for a cron expression from now."""
        try:
            cron_iter = _get_croniter()(cron_expr, datetime.now(timezone.utc))
            return cron_iter.get_next(datetime)
        except Exception:
            return None

    # ── Internal Helpers ─────────────────────────────────────────

    def _load(self) -> None:
        """Load schedules from the JSON file into memory."""
        try:
            with open(self.schedules_path) as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._schedules = data
            else:
                log.warning(
                    "Expected dict in schedules file, got %s. Resetting.",
                    type(data).__name__,
                )
                self._schedules = {}
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Failed to load schedules from %s: %s", self.schedules_path, exc)
            self._schedules = {}
