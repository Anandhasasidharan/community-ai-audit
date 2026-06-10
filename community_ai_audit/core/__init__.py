"""
Core abstraction layer — all integration points are ABCs.
Any adapter/connector implementing the right interface just works.
"""

from .interfaces import (
    # Model adapters
    ModelAdapter,
    TextModelAdapter,
    ImageModelAdapter,
    MultiModalAdapter,
    # SIEM / Security connectors
    SIEMConnector,
    SecurityToolConnector,
    ThreatIntelConnector,
)

from .registry import (
    PluginRegistry,
    AdapterRegistry,
    ConnectorRegistry,
)

from .audit import AuditEngine

from .scheduler import AuditScheduler
from .rbac import RBACConfig, AccessControl, PermissionError
from .agent_session import AgentAuditSession, TraceStep, StepType
from .tracing import ExecutionTrace, TraceStep as TracingTraceStep, Replayer, TraceExporter

__all__ = [
    # Interfaces
    "ModelAdapter",
    "TextModelAdapter",
    "ImageModelAdapter",
    "MultiModalAdapter",
    "SIEMConnector",
    "SecurityToolConnector",
    "ThreatIntelConnector",
    # Registries
    "PluginRegistry",
    "AdapterRegistry",
    "ConnectorRegistry",
    # Engine
    "AuditEngine",
    # Scheduler
    "AuditScheduler",
    # RBAC
    "RBACConfig",
    "AccessControl",
    "PermissionError",
    # Agent session
    "AgentAuditSession",
    "TraceStep",
    "StepType",
    # Tracing
    "ExecutionTrace",
    "Replayer",
    "TraceExporter",
]
