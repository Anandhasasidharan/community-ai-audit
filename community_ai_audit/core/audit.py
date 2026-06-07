"""
AuditEngine — the main entry point for the plug-and-play framework.
Takes a model ID, finds the right adapter, runs selected scanners/interpreters,
and optionally pushes results to SIEM/security tools.

Example usage:
    engine = AuditEngine()
    engine.load_model("meta-llama/Llama-3-8B-Instruct", provider="huggingface")
    results = engine.audit(
        scanners=["backdoor", "adversarial"],
        interpreters=["integrated-gradients"],
        connectors=["splunk", "threat-intel"],
    )
    report = engine.generate_report(results, format="markdown")
"""

from __future__ import annotations

import concurrent.futures
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from datetime import datetime, timezone

from community_ai_audit.cache import ModelCache

from .interfaces import (
    Finding,
    ModelAdapter,
    ScanResult,
    InterpretationResult,
    Severity,
    SIEMConnector,
    SecurityToolConnector,
)
from .registry import adapters, connectors, plugins

log = logging.getLogger(__name__)


# Lazy import to avoid circular imports
def _load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from YAML file and environment overrides."""
    defaults = Path(__file__).parent.parent.parent / "config" / "default.yaml"
    config: Dict[str, Any] = {}

    if defaults.exists():
        with open(defaults) as f:
            config = yaml.safe_load(f) or {}

    if config_path:
        p = Path(config_path).expanduser()
        if p.exists():
            with open(p) as f:
                user = yaml.safe_load(f) or {}
                config = _deep_merge(config, user)

    # Environment overrides — e.g. COMMUNITY_AI_AUDIT_SPLUNK_URL
    prefix = "COMMUNITY_AI_AUDIT_"
    for key, value in config.items():
        if isinstance(value, dict):
            for subkey, subvalue in value.items():
                env_key = f"{prefix}{key.upper()}_{subkey.upper()}"
                if env_key in os.environ:
                    config[key][subkey] = _env_parse(os.environ[env_key])

    return config


def _deep_merge(base: Dict, overlay: Dict) -> Dict:
    result = base.copy()
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _env_parse(value: str) -> Any:
    if value.lower() in ("true", "yes", "1"):
        return True
    if value.lower() in ("false", "no", "0"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


class AuditEngine:
    """Main orchestrator — discover, connect, scan, interpret, report, push."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        extra_plugin_paths: Optional[List[str]] = None,
        discovery_on_init: bool = True,
    ):
        """
        Args:
            config_path: Path to YAML config file. Falls back to config/default.yaml.
            extra_plugin_paths: Extra directories to scan for plugins.
            discovery_on_init: If True, discover all plugins immediately.
        """
        self.config = _load_config(config_path)
        self.extra_plugin_paths = extra_plugin_paths or []
        self._model = None
        self._model_id: Optional[str] = None
        self._adapter: Optional[ModelAdapter] = None
        self._siem_connections: Dict[str, Any] = {}
        self._tool_connections: Dict[str, Any] = {}
        self._session_id = f"audit-{int(time.time())}"
        self._started_at: Optional[datetime] = None

        cache_cfg = self.config.get("cache", {})
        self.cache = ModelCache(
            max_size=cache_cfg.get("max_size", 1000),
            ttl_seconds=cache_cfg.get("ttl_seconds", 3600),
            enabled=cache_cfg.get("enabled", True),
        )

        if discovery_on_init:
            self.discover()

    # ── Discovery ───────────────────────────────────────────────

    def discover(self) -> None:
        """Discover all adapters, connectors, and plugins."""
        adapters.discover()
        connectors.discover()
        plugins.discover(self.extra_plugin_paths)
        log.info(
            "Discovered: %d adapters, %d connectors, %d scanners, %d interpreters, %d reporters",
            len(adapters.list_available()),
            len(connectors.list_available()),
            len(plugins.list_scanners()),
            len(plugins.list_interpreters()),
            len(plugins.list_reporters()),
        )

    # ── Model Loading ──────────────────────────────────────────

    def load_model(
        self,
        model_id: str,
        provider: Optional[str] = None,
        adapter_config: Optional[Dict[str, Any]] = None,
        **model_kwargs,
    ) -> Any:
        """Load a model using the appropriate adapter.

        Args:
            model_id: Model identifier (e.g. 'gpt-4o', 'meta-llama/Llama-3-8B',
                      '/path/to/model.onnx', 's3://bucket/model.bin').
            provider: Explicit adapter name ('huggingface', 'openai', 'local', etc.)
                     If None, auto-detects based on model_id pattern.
            adapter_config: Adapter-specific config (API key, endpoint, etc.)
            **model_kwargs: Additional args forwarded to the adapter's get_model().

        Returns:
            Loaded model object.
        """
        adapter_config = adapter_config or {}

        # Auto-detect provider if not specified
        if provider is None:
            provider = self._auto_detect_provider(model_id)
            log.info("Auto-detected provider '%s' for model '%s'", provider, model_id)

        # Get adapter instance
        self._adapter = adapters.get(provider, config=adapter_config)
        self._adapter.connect(adapter_config)

        # Load model
        self._model = self._adapter.get_model(model_id, **model_kwargs)
        self._model_id = model_id

        # Wrap predict with cache if enabled (unwrap first to avoid double-wrapping)
        if self.cache.enabled:
            raw_predict = getattr(self._adapter.predict, '__wrapped__', self._adapter.predict)
            self._adapter.predict = self.cache.make_predict_wrapper(raw_predict)
            log.debug("Predict caching enabled (max_size=%d, ttl=%ds)", self.cache.max_size, self.cache.ttl_seconds)

        log.info("Loaded model '%s' with adapter '%s'", model_id, provider)
        return self._model

    def _auto_detect_provider(self, model_id: str) -> str:
        """Heuristic to pick the right adapter based on model_id format."""
        if model_id.startswith("gpt-") or model_id.startswith("o1") or model_id.startswith("o3"):
            return "openai"
        if model_id.startswith("claude-"):
            return "anthropic"
        if "/" in model_id or model_id in ("llama", "llama2", "llama3"):
            return "huggingface"
        if (
            model_id.startswith("s3://")
            or model_id.startswith("gs://")
            or model_id.startswith("https://")
        ):
            return "local"  # cloud URI or direct URL
        if os.path.exists(model_id) or model_id.endswith((".pt", ".pth", ".onnx", ".safetensors")):
            return "local"
        if ":" in model_id and "/" not in model_id:
            return "ollama"
        return "huggingface"  # default fallback

    # ── Scanning ────────────────────────────────────────────────

    def scan(
        self,
        scanners: Optional[List[str]] = None,
        config_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[ScanResult]:
        """Run vulnerability scanners.

        Args:
            scanners: List of scanner names to run. If None, runs all discovered.
            config_overrides: Per-scanner config dict, e.g. {'backdoor': {'threshold': 0.9}}.

        Returns:
            List of ScanResult objects.
        """
        self._ensure_model_loaded()
        scanner_names = scanners or plugins.list_scanners()
        config_overrides = config_overrides or {}
        results = []

        for name in scanner_names:
            if name not in plugins.list_scanners():
                log.warning("Scanner '%s' not found, skipping", name)
                continue

            try:
                scanner = plugins.scanners.get(name)
                cfg = self._get_scanner_config(name, overrides=config_overrides.get(name))
                result = scanner.scan(self._model, self._adapter, config=cfg)
                results.append(result)
                log.info("Scanner '%s' completed: %d findings", name, len(result.findings))
            except Exception as e:
                log.error("Scanner '%s' failed: %s", name, e)
                results.append(
                    ScanResult(
                        scanner_name=name,
                        scanner_version=getattr(plugins.scanners.get(name), "version", "unknown"),
                        error=str(e),
                    )
                )

        return results

    # ── Interpretation ──────────────────────────────────────────

    def interpret(
        self,
        inputs: Any,
        interpreters: Optional[List[str]] = None,
        targets: Optional[Dict[str, Any]] = None,
        config_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[InterpretationResult]:
        """Run interpretability methods.

        Args:
            inputs: Input data (text, image, etc.) to explain.
            interpreters: List of interpreter names. If None, runs all discovered.
            targets: Per-interpreter target (e.g. class index, token position).
            config_overrides: Per-interpreter config overrides.

        Returns:
            List of InterpretationResult objects.
        """
        self._ensure_model_loaded()
        interpreter_names = interpreters or plugins.list_interpreters()
        config_overrides = config_overrides or {}
        targets = targets or {}
        results = []

        for name in interpreter_names:
            if name not in plugins.list_interpreters():
                log.warning("Interpreter '%s' not found, skipping", name)
                continue

            try:
                interp = plugins.interpreters.get(name)
                cfg = self._get_interpreter_config(name, overrides=config_overrides.get(name))
                result = interp.interpret(
                    self._model,
                    self._adapter,
                    inputs,
                    target=targets.get(name),
                    config=cfg,
                )
                results.append(result)
                log.info("Interpreter '%s' completed", name)
            except Exception as e:
                log.error("Interpreter '%s' failed: %s", name, e)
                results.append(
                    InterpretationResult(
                        interpreter_name=name,
                        interpreter_version=getattr(
                            plugins.interpreters.get(name), "version", "unknown"
                        ),
                        error=str(e),
                    )
                )

        return results

    # ── Batch Scanning ─────────────────────────────────────────

    def batch_scan(
        self,
        probe_inputs: List[Any],
        scanners: Optional[List[str]] = None,
        config_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
        batch_size: int = 1,
    ) -> List[ScanResult]:
        self._ensure_model_loaded()
        scanner_names = scanners or plugins.list_scanners()
        config_overrides = config_overrides or {}
        aggregated: Dict[str, ScanResult] = {}

        for scanner_name in scanner_names:
            if scanner_name not in plugins.list_scanners():
                log.warning("Scanner '%s' not found, skipping", scanner_name)
                continue

            try:
                scanner = plugins.scanners.get(scanner_name)
                cfg = self._get_scanner_config(scanner_name, overrides=config_overrides.get(scanner_name))

                all_findings: List[Finding] = []
                total_duration = 0.0

                for i in range(0, len(probe_inputs), batch_size):
                    batch = probe_inputs[i : i + batch_size]
                    batch_start = time.time()
                    batch_cfg = {**cfg, "probe_inputs": batch}
                    result = scanner.scan(self._model, self._adapter, config=batch_cfg)
                    all_findings.extend(result.findings)
                    total_duration += time.time() - batch_start

                aggregated[scanner_name] = ScanResult(
                    scanner_name=scanner_name,
                    scanner_version=scanner.version,
                    findings=all_findings,
                    metadata={"batches": (len(probe_inputs) + batch_size - 1) // batch_size,
                              "total_probes": len(probe_inputs),
                              "total_duration_s": round(total_duration, 3)},
                )
                log.info("Batch scan '%s' completed: %d findings across %d probes",
                         scanner_name, len(all_findings), len(probe_inputs))
            except Exception as e:
                log.error("Batch scan '%s' failed: %s", scanner_name, e)
                aggregated[scanner_name] = ScanResult(
                    scanner_name=scanner_name,
                    scanner_version=getattr(plugins.scanners.get(scanner_name), "version", "unknown"),
                    error=str(e),
                )

        return list(aggregated.values())

    # ── Full Audit ──────────────────────────────────────────────

    def audit(
        self,
        scanners: Optional[List[str]] = None,
        interpreters: Optional[List[str]] = None,
        inputs: Optional[Any] = None,
        connectors: Optional[List[str]] = None,
        connector_configs: Optional[Dict[str, Dict[str, Any]]] = None,
        config_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
        run_metadata: Optional[Dict[str, Any]] = None,
        parallel_connectors: bool = False,
        connector_max_workers: int = 4,
    ) -> AuditSession:
        """Run a full audit: scan + interpret + push to connectors.

        Args:
            scanners: Scanners to run.
            interpreters: Interpreters to run. Requires 'inputs'.
            inputs: Input data for interpreters.
            connectors: SIEM/security tool names to push results to.
            connector_configs: Per-connector config (API keys, URLs, etc.)
            config_overrides: Per-component config overrides.
            run_metadata: Optional reproducibility metadata to embed in the session/report.

        Returns:
            AuditSession containing all results and metadata.
        """
        self._started_at = datetime.now(timezone.utc)
        results = AuditSession(
            session_id=self._session_id,
            model_id=self._model_id,
            adapter_name=self._adapter.name if self._adapter else None,
            started_at=self._started_at,
            metadata=run_metadata or {},
        )

        # Run scanners
        results.scan_results = self.scan(scanners, config_overrides)

        # Run interpreters if inputs provided
        if inputs is not None:
            results.interpret_results = self.interpret(
                inputs, interpreters, config_overrides=config_overrides
            )

        # Push to connectors
        if connectors:
            if parallel_connectors:
                results.connector_results = self._push_to_connectors_parallel(
                    results.scan_results, results.interpret_results,
                    connectors, connector_configs, max_workers=connector_max_workers,
                )
            else:
                results.connector_results = self._push_to_connectors(
                    results.scan_results, results.interpret_results, connectors, connector_configs
                )

        results.completed_at = datetime.now(timezone.utc)
        results.duration_seconds = (results.completed_at - self._started_at).total_seconds()

        return results

    # ── Connector Management ───────────────────────────────────

    def connect_siem(self, name: str, config: Dict[str, Any]) -> SIEMConnector:
        """Connect to a SIEM by name and return the connector."""
        conn = connectors.get_siem(name)
        conn.connect(config)
        self._siem_connections[name] = conn
        log.info("Connected to SIEM '%s'", name)
        return conn

    def connect_security_tool(self, name: str, config: Dict[str, Any]) -> SecurityToolConnector:
        """Connect to a security tool and return the connector."""
        conn = connectors.get_security_tool(name)
        conn.connect(config)
        self._tool_connections[name] = conn
        log.info("Connected to security tool '%s'", name)
        return conn

    def _push_to_connectors(
        self,
        scan_results: List[ScanResult],
        interpret_results: List[InterpretationResult],
        connector_names: List[str],
        connector_configs: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Push audit results to configured connectors."""
        connector_results = {}
        audit_data = _format_audit_for_connector(scan_results, interpret_results, self._session_id)
        connector_configs = connector_configs or {}

        for name in connector_names:
            try:
                # Get connector with its config
                config = connector_configs.get(name, {})
                conn = connectors.get(name, config=config)
                # Connect first if config provided
                if config:
                    conn.connect(config)
                # Determine connector type by capability
                if hasattr(conn, "send_batch"):
                    outcome = conn.send_batch(audit_data.get("events", []))
                elif hasattr(conn, "push_finding"):
                    outcome = conn.push_finding(audit_data)
                else:
                    raise TypeError(f"Connector '{name}' does not support send_batch/push_finding")
                connector_results[name] = {"status": "success", "result": outcome}
                log.info("Pushed results to connector '%s'", name)
            except Exception as e:
                log.error("Connector '%s' failed: %s", name, e)
                connector_results[name] = {"status": "failed", "error": str(e)}

        return connector_results

    def _push_to_connectors_parallel(
        self,
        scan_results: List[ScanResult],
        interpret_results: List[InterpretationResult],
        connector_names: List[str],
        connector_configs: Optional[Dict[str, Dict[str, Any]]] = None,
        max_workers: int = 4,
    ) -> Dict[str, Any]:
        connector_results: Dict[str, Any] = {}
        audit_data = _format_audit_for_connector(scan_results, interpret_results, self._session_id)
        connector_configs = connector_configs or {}

        def _push_one(name: str) -> tuple:
            try:
                config = connector_configs.get(name, {})
                conn = connectors.get(name, config=config)
                if config:
                    conn.connect(config)
                if hasattr(conn, "send_batch"):
                    outcome = conn.send_batch(audit_data.get("events", []))
                elif hasattr(conn, "push_finding"):
                    outcome = conn.push_finding(audit_data)
                else:
                    raise TypeError(f"Connector '{name}' does not support send_batch/push_finding")
                return name, {"status": "success", "result": outcome}
            except Exception as e:
                log.error("Connector '%s' failed: %s", name, e)
                return name, {"status": "failed", "error": str(e)}

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_push_one, name): name for name in connector_names}
            for future in concurrent.futures.as_completed(futures):
                name, result = future.result()
                connector_results[name] = result

        return connector_results

    # ── Report Generation ───────────────────────────────────────

    def generate_report(
        self,
        session: AuditSession,
        format: str = "markdown",
    ) -> str:
        """Generate an audit report.

        Args:
            session: AuditSession from audit().
            format: One of 'markdown', 'json', 'html'.

        Returns:
            Formatted report string.
        """
        # Lazy import to keep core clean
        from community_ai_audit.reporting import ReportGenerator

        reporter = ReportGenerator()
        return reporter.render_session(session, fmt=format)

    # ── Utility ─────────────────────────────────────────────────

    def _ensure_model_loaded(self) -> None:
        if self._model is None:
            raise RuntimeError("No model loaded. Call load_model() first.")

    def _get_scanner_config(
        self, name: str, overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        base = self.config.get("scanners", {})
        cfg = base.get(name, base.get(name.replace("-", "_"), {})).copy()
        if overrides:
            cfg.update(overrides)
        return cfg

    def _get_interpreter_config(
        self, name: str, overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        base = self.config.get("interpreters", {})
        cfg = base.get(name, base.get(name.replace("-", "_"), {})).copy()
        if overrides:
            cfg.update(overrides)
        return cfg

    # ── Cache Management ────────────────────────────────────────

    def enable_cache(
        self,
        enabled: bool = True,
        max_size: Optional[int] = None,
        ttl_seconds: Optional[float] = None,
    ) -> None:
        self.cache.enabled = enabled
        if max_size is not None:
            self.cache.max_size = max_size
        if ttl_seconds is not None:
            self.cache.ttl_seconds = ttl_seconds

    def clear_cache(self) -> None:
        self.cache.clear()

    @property
    def cache_stats(self) -> Dict[str, Any]:
        return self.cache.stats

    def list_capabilities(self) -> Dict[str, List[str]]:
        """Return a summary of all discovered capabilities."""
        return {
            "adapters": adapters.list_available(),
            "siem_connectors": [
                n for n in connectors.list_available() if n in _get_siem_connector_names()
            ],
            "security_tools": [
                n for n in connectors.list_available() if n not in _get_siem_connector_names()
            ],
            "scanners": plugins.list_scanners(),
            "interpreters": plugins.list_interpreters(),
            "reporters": plugins.list_reporters(),
        }


class AuditSession:
    """Container for a complete audit run's results and metadata."""

    def __init__(
        self,
        session_id: str,
        model_id: Optional[str],
        adapter_name: Optional[str],
        started_at: datetime,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.session_id = session_id
        self.model_id = model_id
        self.adapter_name = adapter_name
        self.started_at = started_at
        self.metadata: Dict[str, Any] = metadata or {}
        self.scan_results: List[ScanResult] = []
        self.interpret_results: List[InterpretationResult] = []
        self.connector_results: Dict[str, Any] = {}
        self.completed_at: Optional[datetime] = None
        self.duration_seconds: float = 0.0

    @property
    def total_findings(self) -> int:
        return sum(len(r.findings) for r in self.scan_results)

    @property
    def highest_severity(self) -> Severity:
        """The most severe finding across all scanners."""
        severities = [r.overall_severity for r in self.scan_results]
        priority = {Severity.CRITICAL: 4, Severity.HIGH: 3, Severity.MEDIUM: 2, Severity.LOW: 1}
        return (
            max(severities, key=lambda s: priority.get(s, -1)) if severities else Severity.UNKNOWN
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "model_id": self.model_id,
            "adapter": self.adapter_name,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "scanners_run": [r.scanner_name for r in self.scan_results],
            "interpreters_run": [r.interpreter_name for r in self.interpret_results],
            "total_findings": self.total_findings,
            "highest_severity": self.highest_severity.value,
            "metadata": self.metadata,
            "scan_results": [r.to_dict() for r in self.scan_results],
            "interpret_results": [r.to_dict() for r in self.interpret_results],
            "connector_results": self.connector_results,
        }

    def summary(self) -> str:
        """Human-readable one-line summary."""
        return (
            f"Audit {self.session_id} | Model: {self.model_id} | "
            f"Scanners: {len(self.scan_results)} | "
            f"Findings: {self.total_findings} ({self.highest_severity.value}) | "
            f"Duration: {self.duration_seconds:.1f}s"
        )


def _format_audit_for_connector(
    scan_results: List[ScanResult],
    interpret_results: List[InterpretationResult],
    session_id: str,
) -> Dict[str, Any]:
    """Format audit results into a normalized structure for SIEM/tools.
    
    Each finding becomes a separate event with required fields (title, severity).
    """
    events = []
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Emit each finding as a separate event
    for scan_result in scan_results:
        for finding in scan_result.findings:
            finding_dict = finding.to_dict()
            finding_dict.update({
                "event_type": "scan_finding",
                "session_id": session_id,
                "scanner": scan_result.scanner_name,
                "scanner_version": scan_result.scanner_version,
                "model_id": getattr(scan_result, 'model_id', None),
                "timestamp": timestamp,
            })
            events.append(finding_dict)
    
    # Also emit scan summary events
    for scan_result in scan_results:
        events.append({
            "event_type": "scan_summary",
            "session_id": session_id,
            "scanner": scan_result.scanner_name,
            "scanner_version": scan_result.scanner_version,
            "overall_severity": scan_result.overall_severity.value,
            "finding_count": len(scan_result.findings),
            "error": scan_result.error,
            "metadata": scan_result.metadata,
            "timestamp": timestamp,
        })
    
    # Interpretation results
    for interp_result in interpret_results:
        events.append({
            "event_type": "interpretation_result",
            "session_id": session_id,
            "interpreter": interp_result.interpreter_name,
            "interpreter_version": interp_result.interpreter_version,
            "summary": interp_result.summary,
            "error": interp_result.error,
            "metadata": interp_result.metadata,
            "timestamp": timestamp,
        })
    
    return {
        "session_id": session_id,
        "timestamp": timestamp,
        "events": events,
    }


def _get_siem_connector_names() -> set:
    """Names of all SIEM-type connectors (heuristic by class inheritance)."""
    from .interfaces import SIEMConnector

    siem_names = set()
    for name, cls in connectors._plugins.items():
        try:
            if issubclass(cls, SIEMConnector):
                siem_names.add(name)
        except TypeError:
            pass
    return siem_names
