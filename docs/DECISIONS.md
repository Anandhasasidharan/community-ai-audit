# Design Decisions

## Why Plug-and-Play?

**Problem**: Every AI security tool ties you to a specific model provider or SIEM platform.

**Decision**: Abstract all components behind interfaces + registries. Adding a new adapter means writing one class and registering it — no changes to the core engine.

**Trade-off**: Slightly more boilerplate for simple use cases, but massive gains in extensibility.

## Why Centralized Retry?

**Problem**: Each SIEM connector was implementing its own retry logic with different backoff strategies.

**Decision**: A shared `retry` decorator with exponential backoff + jitter, configurable per connector.

**Trade-off**: All connectors share the same retry semantics. Custom retry behavior requires understanding the shared utility.

## Why Event Schema Validation?

**Problem**: Different connectors expected different event formats, causing silent data loss.

**Decision**: A `validate_events` function in the base connector that checks required fields (`title`, `severity`) and normalizes values.

**Trade-off**: Stricter schema means some edge-case events get logged to the dead-letter queue instead of passing through silently.

## Why Dead-Letter Logging?

**Problem**: Transient failures (network blips, rate limits) were losing events permanently.

**Decision**: Failed events are written to a DLQ log file for manual inspection and retry.

**Trade-off**: Extra I/O on every failed event. Acceptable for security audit data where reliability matters more than throughput.

## Why String-Based Forward References in Generator?

**Problem**: `reporting/generator.py` needs to reference `AuditSession` from `core/audit.py`, but importing it directly causes a circular dependency.

**Decision**: Use `TYPE_CHECKING` guard for the import, plus `from __future__ import annotations` to defer evaluation.

**Trade-off**: Small complexity at import time. Clean type hints without runtime circular imports.

## Why Adapter Registry at Package Level?

**Problem**: Adapters need to be discoverable without explicit imports.

**Decision**: A global registry populated by package-level `__init__` files and entry points.

**Trade-off**: Global state can make testing trickier. We mitigate with `clear()` and `reset()` methods on registries.

## Why Separate `adapters/` and `plugins/` Directories?

**Problem**: Built-in scanners and interpreters are conceptually different from model adapters.

**Decision**: `adapters/` for model providers, `plugins/` for scanners/interpreters/reporters.

**Trade-off**: Two plugin systems with slightly different discovery mechanisms. Unified by `core/registry.py`.

## Why Not TypeVar for Adapter Generics?

**Problem**: Adapters return different types (str, tensor, logits) depending on the model.

**Decision**: Use `Any` return types + duck typing rather than complex generics.

**Trade-off**: Less static type safety, but significantly simpler contributor experience.

## Why datetime.utcnow() Deprecation Warnings Exist

**Problem**: `utcnow()` is deprecated in Python 3.12+.

**Decision**: We accept the deprecation warning for now. Will migrate to `datetime.now(datetime.UTC)` in v0.2.0.

**Trade-off**: Cleaner output today vs. forward compatibility. Low priority fix.
