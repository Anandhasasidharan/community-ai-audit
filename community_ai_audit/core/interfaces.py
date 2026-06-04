"""
Abstract base classes defining all integration interfaces.
Every adapter, connector, and plugin implements one of these.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar
from enum import Enum

# ─────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────

class ModelType(Enum):
    TEXT = "text"
    IMAGE = "image"
    MULTIMODAL = "multimodal"
    EMBEDDING = "embedding"
    UNKNOWN = "unknown"


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    UNKNOWN = "unknown"


# ─────────────────────────────────────────────────────────────
# Type helpers
# ─────────────────────────────────────────────────────────────

T = TypeVar("T", bound="ModelAdapter")


# ─────────────────────────────────────────────────────────────
# Model Adapter Interface
# ─────────────────────────────────────────────────────────────

class ModelAdapter(ABC):
    """Abstract base for all model provider adapters.

    Implement this to add support for a new model provider.
    The AuditEngine uses this interface regardless of which
    provider backs the model.
    """

    name: str = "base"
    provider: str = "unknown"  # e.g. "huggingface", "openai", "aws"
    supported_types: List[ModelType] = []

    @abstractmethod
    def connect(self, config: Dict[str, Any]) -> None:
        """Initialize the connection to the model provider.

        Args:
            config: Provider-specific connection config (API keys, endpoints, etc.)
        """
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        """Clean up the connection."""
        raise NotImplementedError

    @abstractmethod
    def get_model(self, model_id: str, **kwargs) -> Any:
        """Load / retrieve a model.

        Args:
            model_id: Provider-specific identifier (e.g. 'gpt-4o',
                      'meta-llama/Llama-3-8B-Instruct', 's3://bucket/model.onnx')
            **kwargs: Additional provider-specific args (device, quantization, etc.)

        Returns:
            Model object compatible with the audit framework.
        """
        raise NotImplementedError

    @abstractmethod
    def predict(self, model: Any, inputs: Any, **kwargs) -> Any:
        """Run inference.

        Args:
            model: Model object from get_model().
            inputs: Input data (format depends on model type).
            **kwargs: Additional inference args.

        Returns:
            Raw model output (logits, embeddings, etc.).
        """
        raise NotImplementedError

    @abstractmethod
    def get_input_spec(self, model: Any) -> Dict[str, Any]:
        """Return the model's input specification.

        Returns:
            Dict with keys like 'type', 'shape', 'dtype', 'tokenizer'.
        """
        raise NotImplementedError

    @abstractmethod
    def supports_model_type(self, model_type: ModelType) -> bool:
        """Check if this adapter supports a given model type."""
        raise NotImplementedError

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Return the JSON schema for this adapter's config fields."""
        return {"type": "object", "properties": {}}

    @classmethod
    def auto_config(cls) -> Dict[str, Any]:
        """Attempt to auto-detect config from environment variables."""
        return {}


class TextModelAdapter(ModelAdapter):
    """Specialization for text / LLM models."""

    @abstractmethod
    def tokenize(self, text: str, **kwargs) -> Any:
        """Tokenize text input."""
        raise NotImplementedError

    @abstractmethod
    def generate(self, model: Any, prompt: str, **kwargs) -> str:
        """Generate a text completion."""
        raise NotImplementedError

    @abstractmethod
    def get_logits(self, model: Any, tokens: Any, **kwargs) -> Any:
        """Get raw logits over vocabulary."""
        raise NotImplementedError

    @abstractmethod
    def get_attention_weights(self, model: Any, tokens: Any, **kwargs) -> Any:
        """Extract attention weight matrices for interpretability."""
        raise NotImplementedError


class ImageModelAdapter(ModelAdapter):
    """Specialization for image models."""

    @abstractmethod
    def preprocess_image(self, image: Any, **kwargs) -> Any:
        """Preprocess an image for the model."""
        raise NotImplementedError

    @abstractmethod
    def get_layer_activations(self, model: Any, image: Any, layer_names: List[str]) -> Dict[str, Any]:
        """Extract intermediate layer activations."""
        raise NotImplementedError


class MultiModalAdapter(ModelAdapter):
    """Specialization for multimodal models (vision + language, etc.)."""

    @abstractmethod
    def tokenize(self, text: str, **kwargs) -> Any:
        raise NotImplementedError

    @abstractmethod
    def preprocess_image(self, image: Any, **kwargs) -> Any:
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────
# SIEM Connector Interface
# ─────────────────────────────────────────────────────────────

class SIEMConnector(ABC):
    """Abstract base for SIEM (Security Information and Event Management) integrations.

    Implement this to send audit findings to any SIEM platform
    (Splunk, Elastic, Sentinel, Chronicle, etc.).
    """

    name: str = "base_siem"

    @abstractmethod
    def connect(self, config: Dict[str, Any]) -> None:
        """Initialize connection to the SIEM.

        Args:
            config: Connector-specific config (URL, API key, index/workspace, etc.)
        """
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        """Clean up the connection."""
        raise NotImplementedError

    @abstractmethod
    def send_event(self, event: Dict[str, Any], event_type: str = "audit") -> bool:
        """Send a single event / alert to the SIEM.

        Args:
            event: Event data conforming to the SIEM's schema.
            event_type: Category of event (e.g. 'vulnerability', 'finding', 'alert').

        Returns:
            True if the event was accepted, False otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def send_batch(self, events: List[Dict[str, Any]], event_type: str = "audit") -> Dict[str, Any]:
        """Send multiple events in one request.

        Returns:
            Dict with 'success' and 'failed' counts.
        """
        raise NotImplementedError

    @abstractmethod
    def query(self, query: str, time_range: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query existing events from the SIEM.

        Args:
            query: Platform-specific query language (SPL, KQL, Lucene, etc.).
            time_range: Time window filter (e.g. '-24h', '-7d').

        Returns:
            List of matching events.
        """
        raise NotImplementedError

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Return the JSON schema for this connector's config fields."""
        return {"type": "object", "properties": {}}


# ─────────────────────────────────────────────────────────────
# Security Tool Connector Interface
# ─────────────────────────────────────────────────────────────

class SecurityToolConnector(ABC):
    """Abstract base for integrations with security tools
    (SOAR, CVE feeds, threat intel, vulnerability scanners, etc.).

    Implement this to wire audit results into your existing security stack.
    """

    name: str = "base_security_tool"

    @abstractmethod
    def connect(self, config: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def push_finding(self, finding: Dict[str, Any]) -> bool:
        """Push a finding to the tool (SOAR, ticketing, etc.)."""
        raise NotImplementedError

    @abstractmethod
    def pull_context(self, indicator: str) -> Dict[str, Any]:
        """Pull threat intelligence / context for an indicator (IOC, CVE, hash, etc.)."""
        raise NotImplementedError

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {"type": "object", "properties": {}}


class ThreatIntelConnector(SecurityToolConnector):
    """Specialization for threat intelligence feeds (MISP, OTX, VirusTotal, etc.)."""

    @abstractmethod
    def enrich_finding(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich a finding with threat intel context."""
        raise NotImplementedError

    @abstractmethod
    def lookup_ioc(self, ioc: str, ioc_type: str) -> Dict[str, Any]:
        """Look up an Indicator of Compromise.

        Args:
            ioc: The indicator value (IP, hash, domain, etc.).
            ioc_type: Type of IOC ('ipv4', 'md5', 'domain', etc.).

        Returns:
            Enrichment data or empty dict if not found.
        """
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────
# Result Types (defined before plugins that use them)
# ─────────────────────────────────────────────────────────────

class Finding:
    """A single vulnerability / anomaly finding from a scanner."""

    def __init__(
        self,
        title: str,
        description: str,
        severity: Severity,
        evidence: Optional[Dict[str, Any]] = None,
        cwe_id: Optional[str] = None,       # MITRE CWE
        mitre_id: Optional[str] = None,     # ATLAS / ATT&CK ID
        nist_id: Optional[str] = None,      # NIST AI RMF category
        confidence: float = 0.5,            # 0.0–1.0
        recommendation: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
    ):
        self.title = title
        self.description = description
        self.severity = severity
        self.evidence = evidence or {}
        self.cwe_id = cwe_id
        self.mitre_id = mitre_id
        self.nist_id = nist_id
        self.confidence = confidence
        self.recommendation = recommendation
        self.raw_data = raw_data

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "evidence": self.evidence,
            "cwe_id": self.cwe_id,
            "mitre_id": self.mitre_id,
            "nist_id": self.nist_id,
            "confidence": self.confidence,
            "recommendation": self.recommendation,
        }


class ScanResult:
    """Container for all findings from a scanner run."""

    def __init__(
        self,
        scanner_name: str,
        scanner_version: str,
        findings: Optional[List[Finding]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        self.scanner_name = scanner_name
        self.scanner_version = scanner_version
        self.findings = findings or []
        self.metadata = metadata or {}
        self.error = error

    @property
    def has_findings(self) -> bool:
        return len(self.findings) > 0

    @property
    def overall_severity(self) -> Severity:
        """Return the highest severity across all findings."""
        if not self.findings:
            return Severity.UNKNOWN
        priority = {Severity.CRITICAL: 4, Severity.HIGH: 3, Severity.MEDIUM: 2, Severity.LOW: 1, Severity.INFO: 0}
        return max(self.findings, key=lambda f: priority.get(f.severity, 0)).severity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scanner": self.scanner_name,
            "version": self.scanner_version,
            "findings": [f.to_dict() for f in self.findings],
            "overall_severity": self.overall_severity.value,
            "finding_count": len(self.findings),
            "metadata": self.metadata,
            "error": self.error,
        }


class InterpretationResult:
    """Container for interpretability analysis results."""

    def __init__(
        self,
        interpreter_name: str,
        interpreter_version: str,
        attributions: Optional[Dict[str, Any]] = None,
        visualization: Optional[Any] = None,
        summary: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        self.interpreter_name = interpreter_name
        self.interpreter_version = interpreter_version
        self.attributions = attributions or {}
        self.visualization = visualization
        self.summary = summary
        self.metadata = metadata or {}
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interpreter": self.interpreter_name,
            "version": self.interpreter_version,
            "attributions": self.attributions,
            "summary": self.summary,
            "metadata": self.metadata,
            "error": self.error,
        }


# ─────────────────────────────────────────────────────────────
# Scanner Plugin Interface
# ─────────────────────────────────────────────────────────────

class ScannerPlugin(ABC):
    """Abstract base for vulnerability scanner plugins.

    Any class implementing this interface is automatically discovered
    and registered by the PluginRegistry.
    """

    name: str = "base_scanner"
    description: str = ""
    supported_model_types: List[ModelType] = []
    version: str = "0.1.0"

    @abstractmethod
    def scan(
        self,
        model: Any,
        adapter: ModelAdapter,
        config: Optional[Dict[str, Any]] = None,
    ) -> ScanResult:
        """Run the vulnerability scan.

        Args:
            model: The loaded model from the adapter.
            adapter: The ModelAdapter used (for predict, get_input_spec, etc.).
            config: Optional scanner-specific configuration overrides.

        Returns:
            ScanResult with findings, severity, and evidence.
        """
        raise NotImplementedError

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Return scanner-specific config fields."""
        return {"type": "object", "properties": {}}


# ─────────────────────────────────────────────────────────────
# Interpreter Plugin Interface
# ─────────────────────────────────────────────────────────────

class InterpreterPlugin(ABC):
    """Abstract base for interpretability method plugins."""

    name: str = "base_interpreter"
    description: str = ""
    supported_model_types: List[ModelType] = []
    version: str = "0.1.0"

    @abstractmethod
    def interpret(
        self,
        model: Any,
        adapter: ModelAdapter,
        inputs: Any,
        target: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> InterpretationResult:
        """Run interpretability analysis.

        Args:
            model: The loaded model.
            adapter: The ModelAdapter for inference.
            inputs: Input data to explain.
            target: Optional target class / token to attribute.
            config: Optional interpreter-specific configuration.

        Returns:
            InterpretationResult with attributions and metadata.
        """
        raise NotImplementedError

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {"type": "object", "properties": {}}


# ─────────────────────────────────────────────────────────────
# Reporter Plugin Interface
# ─────────────────────────────────────────────────────────────

class ReporterPlugin(ABC):
    """Abstract base for report format plugins."""

    name: str = "base_reporter"
    supported_formats: List[str] = []  # e.g. ["markdown", "html", "json", "pdf"]

    @abstractmethod
    def render(
        self,
        scan_results: List[ScanResult],
        interpret_results: List[InterpretationResult],
        metadata: Dict[str, Any],
    ) -> str:
        """Render audit results into the target format."""
        raise NotImplementedError

