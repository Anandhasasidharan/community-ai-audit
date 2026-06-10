from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class TraceStep:
    step: int
    step_type: str
    input: Any
    output: Any
    duration: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "step_type": self.step_type,
            "input": self.input,
            "output": self.output,
            "duration": round(self.duration, 4),
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TraceStep:
        return cls(
            step=data["step"],
            step_type=data["step_type"],
            input=data["input"],
            output=data["output"],
            duration=data["duration"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ExecutionTrace:
    agent_id: str
    session_id: str
    steps: List[TraceStep] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        end = self.end_time or datetime.now(timezone.utc)
        return (end - self.start_time).total_seconds()

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def tool_calls(self) -> List[TraceStep]:
        return [s for s in self.steps if s.step_type == "tool_call"]

    @property
    def decisions(self) -> List[TraceStep]:
        return [s for s in self.steps if s.step_type == "decision"]

    @property
    def actions(self) -> List[TraceStep]:
        return [s for s in self.steps if s.step_type == "action"]

    @property
    def total_duration(self) -> float:
        return sum(s.duration for s in self.steps)

    def add_step(self, step: TraceStep) -> None:
        self.steps.append(step)

    def finish(self) -> None:
        self.end_time = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "steps": [s.to_dict() for s in self.steps],
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": round(self.duration, 2),
            "step_count": self.step_count,
            "total_duration": round(self.total_duration, 4),
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionTrace:
        trace = cls(
            agent_id=data["agent_id"],
            session_id=data["session_id"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
            metadata=data.get("metadata", {}),
        )
        for step_data in data.get("steps", []):
            trace.steps.append(TraceStep.from_dict(step_data))
        return trace

    @classmethod
    def from_json(cls, json_str: str) -> ExecutionTrace:
        return cls.from_dict(json.loads(json_str))
