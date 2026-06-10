from __future__ import annotations

import copy
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class StepType(str, Enum):
    TOOL_CALL = "tool_call"
    MEMORY_ACCESS = "memory_access"
    DECISION = "decision"
    ACTION = "action"
    PROMPT = "prompt"
    RESPONSE = "response"


@dataclass
class TraceStep:
    step: int
    step_type: StepType
    input: Any
    output: Any
    duration: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryAccess:
    operation: str  # "read", "write", "delete"
    key: str
    value: Optional[Any] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Decision:
    description: str
    reasoning: str
    alternatives: List[str] = field(default_factory=list)
    chosen_action: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Action:
    action_type: str
    input_data: Any
    output: Any
    success: bool = True
    duration: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentAuditSession:
    """Tracks a complete agent interaction for auditing and tracing.

    Records tool calls, memory accesses, decisions, and actions
    to enable replay, analysis, and continuous monitoring.
    """

    def __init__(
        self,
        agent_id: str,
        session_id: Optional[str] = None,
        goal: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.agent_id = agent_id
        self.session_id = session_id or str(uuid.uuid4())
        self.goal = goal or ""
        self.metadata = metadata or {}
        self.steps: List[TraceStep] = []
        self.memory_accesses: List[MemoryAccess] = []
        self.decisions: List[Decision] = []
        self.actions: List[Action] = []
        self.start_time: datetime = datetime.now(timezone.utc)
        self.end_time: Optional[datetime] = None
        self._step_counter: int = 0
        self._session_data: Dict[str, Any] = {}

    def record_tool_call(
        self,
        tool: str,
        input_data: Any,
        output: Any,
        duration: float,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceStep:
        self._step_counter += 1
        step = TraceStep(
            step=self._step_counter,
            step_type=StepType.TOOL_CALL,
            input={"tool": tool, "input": input_data},
            output=output,
            duration=duration,
            metadata={"success": success, **(metadata or {})},
        )
        self.steps.append(step)
        return step

    def record_memory_access(
        self,
        operation: str,
        key: str,
        value: Optional[Any] = None,
    ) -> MemoryAccess:
        access = MemoryAccess(operation=operation, key=key, value=value)
        self.memory_accesses.append(access)
        self._step_counter += 1
        self.steps.append(
            TraceStep(
                step=self._step_counter,
                step_type=StepType.MEMORY_ACCESS,
                input={"operation": operation, "key": key},
                output=value,
                duration=0.0,
            )
        )
        return access

    def record_decision(
        self,
        description: str,
        reasoning: str,
        alternatives: Optional[List[str]] = None,
        chosen_action: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Decision:
        decision = Decision(
            description=description,
            reasoning=reasoning,
            alternatives=alternatives or [],
            chosen_action=chosen_action,
            metadata=metadata or {},
        )
        self.decisions.append(decision)
        self._step_counter += 1
        self.steps.append(
            TraceStep(
                step=self._step_counter,
                step_type=StepType.DECISION,
                input={"description": description, "alternatives": alternatives or []},
                output=chosen_action,
                duration=0.0,
                metadata=metadata or {},
            )
        )
        return decision

    def record_action(
        self,
        action_type: str,
        input_data: Any,
        output: Any,
        success: bool = True,
        duration: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Action:
        action = Action(
            action_type=action_type,
            input_data=input_data,
            output=output,
            success=success,
            duration=duration,
            metadata=metadata or {},
        )
        self.actions.append(action)
        self._step_counter += 1
        self.steps.append(
            TraceStep(
                step=self._step_counter,
                step_type=StepType.ACTION,
                input=input_data,
                output=output,
                duration=duration,
                metadata={"action_type": action_type, "success": success, **(metadata or {})},
            )
        )
        return action

    def record_prompt(self, prompt: str, response: str, duration: float = 0.0) -> TraceStep:
        self._step_counter += 1
        step = TraceStep(
            step=self._step_counter,
            step_type=StepType.PROMPT,
            input=prompt,
            output=response,
            duration=duration,
        )
        self.steps.append(step)
        return step

    def set_session_data(self, key: str, value: Any) -> None:
        self._session_data[key] = value

    def get_session_data(self, key: str, default: Any = None) -> Any:
        return self._session_data.get(key, default)

    def get_session_data_all(self) -> Dict[str, Any]:
        return dict(self._session_data)

    def finish(self) -> None:
        self.end_time = datetime.now(timezone.utc)

    @property
    def duration(self) -> float:
        end = self.end_time or datetime.now(timezone.utc)
        return (end - self.start_time).total_seconds()

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def tool_call_count(self) -> int:
        return sum(1 for s in self.steps if s.step_type == StepType.TOOL_CALL)

    @property
    def action_count(self) -> int:
        return sum(1 for s in self.steps if s.step_type == StepType.ACTION)

    @property
    def decision_count(self) -> int:
        return sum(1 for s in self.steps if s.step_type == StepType.DECISION)

    @property
    def memory_access_count(self) -> int:
        return sum(1 for s in self.steps if s.step_type == StepType.MEMORY_ACCESS)

    @property
    def failed_action_count(self) -> int:
        return sum(1 for a in self.actions if not a.success)

    def get_trace(self) -> List[Dict[str, Any]]:
        return [self._step_to_dict(s) for s in self.steps]

    def _step_to_dict(self, step: TraceStep) -> Dict[str, Any]:
        return {
            "step": step.step,
            "step_type": step.step_type.value,
            "input": step.input,
            "output": step.output,
            "duration": round(step.duration, 4),
            "timestamp": step.timestamp.isoformat(),
            "metadata": step.metadata,
        }

    def get_timeline(self) -> List[Dict[str, Any]]:
        timeline = []
        for step in self.steps:
            timeline.append(
                {
                    "step": step.step,
                    "type": step.step_type.value,
                    "timestamp": step.timestamp.isoformat(),
                    "duration": round(step.duration, 4),
                    "summary": self._summarize_step(step),
                }
            )
        return timeline

    def _summarize_step(self, step: TraceStep) -> str:
        if step.step_type == StepType.TOOL_CALL:
            tool = step.input.get("tool", "?") if isinstance(step.input, dict) else "?"
            return f"Tool call: {tool}"
        if step.step_type == StepType.MEMORY_ACCESS:
            op = step.input.get("operation", "?") if isinstance(step.input, dict) else "?"
            key = step.input.get("key", "?") if isinstance(step.input, dict) else "?"
            return f"Memory {op}: {key}"
        if step.step_type == StepType.DECISION:
            desc = step.input.get("description", "?") if isinstance(step.input, dict) else "?"
            return f"Decision: {desc}"
        if step.step_type == StepType.ACTION:
            at = step.metadata.get("action_type", "?")
            return f"Action: {at}"
        if step.step_type == StepType.PROMPT:
            inp = step.input[:60] if isinstance(step.input, str) else "?"
            return f"Prompt: {inp}"
        return str(step.step_type.value)

    def replay(self, step_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        for step_dict in self.get_trace():
            if step_callback:
                step_callback(step_dict)
            else:
                ts = step_dict["timestamp"][:19]
                dtype = step_dict["step_type"]
                inp = str(step_dict["input"])[:80]
                out = str(step_dict["output"])[:80]
                print(f"[{ts}] Step {step_dict['step']} ({dtype}):")
                print(f"  Input:  {inp}")
                print(f"  Output: {out}")
                print(f"  Duration: {step_dict['duration']}s")

    def export_json(self, indent: int = 2) -> str:
        data = self.to_dict()
        return json.dumps(data, indent=indent, default=str)

    def export_jsonl(self) -> str:
        lines = []
        for step in self.get_trace():
            lines.append(json.dumps(step, default=str))
        return "\n".join(lines)

    def export_html(self, title: Optional[str] = None) -> str:
        title = title or f"Agent Session: {self.session_id}"
        steps_html = ""
        for step in self.get_trace():
            steps_html += f"""
            <div class="step {step['step_type']}">
                <div class="step-header">
                    <span class="step-num">#{step['step']}</span>
                    <span class="step-type">{step['step_type']}</span>
                    <span class="step-duration">{step['duration']}s</span>
                </div>
                <div class="step-detail">
                    <strong>Input:</strong> <pre>{self._escape(str(step['input']))}</pre>
                    <strong>Output:</strong> <pre>{self._escape(str(step['output']))}</pre>
                </div>
            </div>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; background: #f5f5f5; }}
  .session {{ max-width: 900px; margin: auto; }}
  .header {{ background: #1a1a2e; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
  .header h1 {{ margin: 0; }}
  .stats {{ display: flex; gap: 15px; margin: 15px 0; flex-wrap: wrap; }}
  .stat {{ background: white; padding: 15px; border-radius: 8px; flex: 1; min-width: 120px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .stat-value {{ font-size: 24px; font-weight: bold; }}
  .step {{ background: white; margin: 10px 0; padding: 15px; border-radius: 8px; border-left: 4px solid #ccc; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .step.tool_call {{ border-left-color: #4CAF50; }}
  .step.memory_access {{ border-left-color: #2196F3; }}
  .step.decision {{ border-left-color: #FF9800; }}
  .step.action {{ border-left-color: #f44336; }}
  .step.prompt {{ border-left-color: #9C27B0; }}
  .step-header {{ display: flex; gap: 15px; align-items: center; margin-bottom: 8px; }}
  .step-num {{ font-weight: bold; color: #666; }}
  .step-type {{ background: #e0e0e0; padding: 2px 8px; border-radius: 4px; font-size: 12px; text-transform: uppercase; }}
  .step-duration {{ margin-left: auto; color: #999; font-size: 12px; }}
  .step-detail pre {{ background: #f8f8f8; padding: 8px; border-radius: 4px; overflow-x: auto; font-size: 13px; }}
</style>
</head>
<body>
<div class="session">
  <div class="header">
    <h1>{title}</h1>
    <p>Agent: {self.agent_id} | Session: {self.session_id}</p>
    <p>Duration: {self.duration:.1f}s | Steps: {len(self.steps)}</p>
  </div>
  <div class="stats">
    <div class="stat"><div class="stat-value">{self.tool_call_count}</div>Tool Calls</div>
    <div class="stat"><div class="stat-value">{self.memory_access_count}</div>Memory Ops</div>
    <div class="stat"><div class="stat-value">{self.decision_count}</div>Decisions</div>
    <div class="stat"><div class="stat-value">{self.action_count}</div>Actions</div>
  </div>
  {steps_html}
</div>
</body>
</html>"""

    def _escape(self, text: str) -> str:
        return (
            text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "goal": self.goal,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": round(self.duration, 2),
            "steps": self.get_trace(),
            "timeline": self.get_timeline(),
            "tool_call_count": self.tool_call_count,
            "action_count": self.action_count,
            "decision_count": self.decision_count,
            "memory_access_count": self.memory_access_count,
            "failed_action_count": self.failed_action_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentAuditSession:
        session = cls(
            agent_id=data["agent_id"],
            session_id=data.get("session_id"),
            goal=data.get("goal", ""),
            metadata=data.get("metadata", {}),
        )
        session.start_time = datetime.fromisoformat(data["start_time"])
        if data.get("end_time"):
            session.end_time = datetime.fromisoformat(data["end_time"])
        for step_data in data.get("steps", []):
            step = TraceStep(
                step=step_data["step"],
                step_type=StepType(step_data["step_type"]),
                input=step_data["input"],
                output=step_data["output"],
                duration=step_data["duration"],
                timestamp=datetime.fromisoformat(step_data["timestamp"]),
                metadata=step_data.get("metadata", {}),
            )
            session.steps.append(step)
            session._step_counter = max(session._step_counter, step.step)
        return session

    def copy(self) -> AgentAuditSession:
        return copy.deepcopy(self)
