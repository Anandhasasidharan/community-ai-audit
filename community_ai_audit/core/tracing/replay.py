from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .models import ExecutionTrace, TraceStep


class Replayer:
    """Replays an execution trace step by step."""

    def __init__(self, trace: ExecutionTrace):
        self.trace = trace
        self._current_step: int = 0

    @property
    def total_steps(self) -> int:
        return len(self.trace.steps)

    @property
    def progress(self) -> float:
        if self.total_steps == 0:
            return 1.0
        return self._current_step / self.total_steps

    def reset(self) -> None:
        self._current_step = 0

    def next(self) -> Optional[TraceStep]:
        if self._current_step >= len(self.trace.steps):
            return None
        step = self.trace.steps[self._current_step]
        self._current_step += 1
        return step

    def previous(self) -> Optional[TraceStep]:
        if self._current_step <= 0:
            return None
        self._current_step -= 1
        return self.trace.steps[self._current_step]

    @property
    def current_step(self) -> Optional[TraceStep]:
        if self._current_step >= len(self.trace.steps):
            return None
        return self.trace.steps[self._current_step]

    def seek(self, step_number: int) -> Optional[TraceStep]:
        for i, s in enumerate(self.trace.steps):
            if s.step == step_number:
                self._current_step = i
                return s
        return None

    def replay_all(
        self,
        step_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        step_filter: Optional[Callable[[TraceStep], bool]] = None,
    ) -> None:
        for step in self.trace.steps:
            if step_filter and not step_filter(step):
                continue
            if step_callback:
                step_callback(step.to_dict())

    def summary(self) -> Dict[str, Any]:
        return {
            "agent_id": self.trace.agent_id,
            "session_id": self.trace.session_id,
            "total_steps": self.total_steps,
            "tool_calls": len(self.trace.tool_calls),
            "decisions": len(self.trace.decisions),
            "actions": len(self.trace.actions),
            "total_duration": round(self.trace.total_duration, 4),
            "wall_clock": round(self.trace.duration, 2),
        }

    def stats(self) -> Dict[str, Any]:
        durations = [s.duration for s in self.trace.steps]
        return {
            "min_step_duration": round(min(durations), 4) if durations else 0.0,
            "max_step_duration": round(max(durations), 4) if durations else 0.0,
            "avg_step_duration": round(sum(durations) / len(durations), 4) if durations else 0.0,
            "total_duration": round(sum(durations), 4),
            "step_count": len(durations),
            "tool_call_count": len(self.trace.tool_calls),
            "decision_count": len(self.trace.decisions),
            "action_count": len(self.trace.actions),
        }
