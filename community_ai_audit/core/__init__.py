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
    # Scanner / Interpreter plugins
    ScannerPlugin,
    InterpreterPlugin,
    ReporterPlugin,
)

from .registry import (
    PluginRegistry,
    AdapterRegistry,
    ConnectorRegistry,
)

from .audit import AuditEngine

__all__ = [
    # Interfaces
    "ModelAdapter",
    "TextModelAdapter",
    "ImageModelAdapter",
    "MultiModalAdapter",
    "SIEMConnector",
    "SecurityToolConnector",
    "ThreatIntelConnector",
    "ScannerPlugin",
    "InterpreterPlugin",
    "ReporterPlugin",
    # Registries
    "PluginRegistry",
    "AdapterRegistry",
    "ConnectorRegistry",
    # Engine
    "AuditEngine",
]
