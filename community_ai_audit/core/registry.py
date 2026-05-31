"""
Plugin Registry — the heart of the plug-and-play system.
Discovers adapters, connectors, and plugins from:
  1. Built-in modules in this package
  2. Entry points (pip-installed plugins)
  3. Config-specified plugin directories
  4. Environment variables for quick config
"""

from __future__ import annotations

import os
import sys
import importlib
import importlib.util
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, get_type_hints, get_origin, get_args
from importlib.metadata import entry_points, EntryPoint

from .interfaces import (
    ModelAdapter,
    SIEMConnector,
    SecurityToolConnector,
    ThreatIntelConnector,
    ScannerPlugin,
    InterpreterPlugin,
    ReporterPlugin,
)

log = logging.getLogger(__name__)

# Type variable for generic registry lookups
T_Plugin = TypeVar("T_Plugin")


class Registry:
    """Base registry with discovery, registration, and lookup."""

    base_type: type = object
    entry_point_group: Optional[str] = None
    builtin_module_prefix: str = ""

    def __init__(self):
        self._plugins: Dict[str, Type] = {}
        self._instances: Dict[str, Any] = {}
        self._discovered: bool = False

    # ── Discovery ─────────────────────────────────────────────

    def discover(self, extra_paths: Optional[List[str]] = None) -> None:
        """Discover all available plugins from all sources.

        Discovery order (later sources override earlier ones):
          1. Built-in plugins in this package
          2. Entry points registered via setuptools
          3. Extra paths from config (e.g. ~/.community-ai-audit/plugins/)
        """
        self._discover_builtins()
        self._discover_entry_points()
        if extra_paths:
            self._discover_paths(extra_paths)
        self._discovered = True
        log.debug("Discovered %d %s plugins: %s", len(self._plugins), self.base_type.__name__, list(self._plugins.keys()))

    def _discover_builtins(self) -> None:
        """Auto-import all subclasses from the builtin module subtree."""
        if not self.builtin_module_prefix:
            return
        try:
            pkg = importlib.import_module(self.builtin_module_prefix)
        except ImportError:
            return

        for importer, mod_name, is_pkg in pkgutil_iter_modules(pkg.__path__, f"{self.builtin_module_prefix}."):
            try:
                mod = importlib.import_module(mod_name)
            except ImportError as e:
                log.warning("Could not import %s: %s", mod_name, e)
                continue
            self._register_from_module(mod)
            # Also check subpackages
            if is_pkg:
                self._discover_subpackage(mod_name)

    def _discover_subpackage(self, pkg_name: str) -> None:
        """Recursively discover plugins in subpackages."""
        try:
            pkg = importlib.import_module(pkg_name)
        except ImportError:
            return
        if not hasattr(pkg, "__path__"):
            return
        for item in os.listdir(os.path.dirname(pkg.__file__ or "")):
            if item.startswith("_") or item.startswith("."):
                continue
            item_path = os.path.join(os.path.dirname(pkg.__file__ or ""), item)
            if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "__init__.py")):
                submod_name = f"{pkg_name}.{item}"
                try:
                    submod = importlib.import_module(submod_name)
                    self._register_from_module(submod)
                except ImportError:
                    pass

    def _discover_entry_points(self) -> None:
        """Load plugins registered via setuptools/pip entry points."""
        if self.entry_point_group and sys.version_info >= (3, 10):
            try:
                eps = entry_points(group=self.entry_point_group)
            except Exception as e:
                log.warning("Could not load entry points for %s: %s", self.entry_point_group, e)
                return
            for ep in eps:
                try:
                    cls = ep.load()
                    self.register(ep.name, cls)
                    log.debug("Loaded entry point plugin: %s", ep.name)
                except Exception as e:
                    log.warning("Could not load entry point %s: %s", ep.name, e)

    def _discover_paths(self, paths: List[str]) -> None:
        """Load plugins from arbitrary file-system paths (for dev / user plugins)."""
        for path_str in paths:
            p = Path(path_str).expanduser()
            if not p.exists():
                log.warning("Plugin path does not exist: %s", p)
                continue
            if p.is_file():
                self._load_file_as_module(p)
            else:
                for py_file in p.rglob("*.py"):
                    if py_file.stem.startswith("_"):
                        continue
                    self._load_file_as_module(py_file)

    def _load_file_as_module(self, path: Path) -> None:
        """Load a single .py file as a module and register its plugin classes."""
        module_name = f"external_{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            return
        try:
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)
            self._register_from_module(mod)
        except Exception as e:
            log.warning("Could not load plugin file %s: %s", path, e)

    def _register_from_module(self, mod: Any) -> None:
        """Find and register all subclasses of base_type in a module."""
        for name in dir(mod):
            if name.startswith("_"):
                continue
            obj = getattr(mod, name, None)
            if obj is None:
                continue
            # Filter out non-plugin types
            if not isinstance(obj, type):
                continue
            if not issubclass(obj, self.base_type) or obj is self.base_type:
                continue
            # Verify the type is actually defined in this module (not imported)
            defined_in = getattr(obj, '__module__', '')
            if defined_in.startswith('typing') or defined_in.startswith('builtins'):
                continue
            # Only register types defined in the adapter/plugin package (not core.interfaces)
            mod_name = getattr(mod, '__name__', '')
            if defined_in != mod_name and not defined_in.startswith(mod_name + '.'):
                continue
            # Use class attribute or name derived from class name
            plugin_name = getattr(obj, "name", None) or _snake_to_kebab(name)
            self.register(plugin_name, obj)

    # ── Registration ───────────────────────────────────────────

    def register(self, name: str, cls: Type, replace: bool = False) -> None:
        """Register a plugin class under a given name."""
        if name in self._plugins and not replace:
            log.debug("Plugin '%s' already registered, skipping (use replace=True to override)", name)
            return
        self._plugins[name] = cls
        log.debug("Registered plugin: %s -> %s", name, cls.__name__)

    def unregister(self, name: str) -> None:
        if name in self._plugins:
            del self._plugins[name]
        if name in self._instances:
            del self._instances[name]

    # ── Lookup ─────────────────────────────────────────────────

    def get(self, name: str, config: Optional[Dict[str, Any]] = None) -> Any:
        """Get (and lazily instantiate) a plugin by name.

        Args:
            name: Plugin name.
            config: Optional config passed to the instance's __init__.

        Returns:
            Plugin instance (singleton per name).
        """
        if name not in self._plugins:
            raise KeyError(f"Plugin '{name}' not found. Available: {list(self._plugins.keys())}")

        if name not in self._instances:
            cls = self._plugins[name]
            self._instances[name] = cls(config=config) if config is not None else cls()

        return self._instances[name]

    def create(self, name: str, config: Optional[Dict[str, Any]] = None) -> Any:
        """Create a fresh instance (non-singleton) of a plugin."""
        if name not in self._plugins:
            raise KeyError(f"Plugin '{name}' not found. Available: {list(self._plugins.keys())}")
        cls = self._plugins[name]
        return cls(config=config) if config is not None else cls()

    def list_available(self) -> List[str]:
        """Return list of all registered plugin names."""
        return sorted(self._plugins.keys())

    def list_with_info(self) -> List[Dict[str, Any]]:
        """Return plugins with their metadata."""
        result = []
        for name, cls in self._plugins.items():
            result.append({
                "name": name,
                "class": cls.__name__,
                "module": cls.__module__,
                "description": getattr(cls, "description", ""),
                "version": getattr(cls, "version", "unknown"),
            })
        return result


# ─────────────────────────────────────────────────────────────
# Sub-Registries
# ─────────────────────────────────────────────────────────────

class AdapterRegistry(Registry):
    """Registry for ModelAdapter plugins."""

    base_type = ModelAdapter
    entry_point_group = "community_ai_audit.adapters"
    builtin_module_prefix = "community_ai_audit.adapters"

    def get_for_model_type(
        self,
        model_type: "ModelType",  # noqa: F821
        model_id: str,
    ) -> List[Type[ModelAdapter]]:
        """Find all adapters that support a given model type."""
        matches = []
        for name, cls in self._plugins.items():
            adapter = cls()
            if adapter.supports_model_type(model_type):
                matches.append(cls)
        return matches


class ConnectorRegistry(Registry):
    """Registry for SIEM and security tool connectors."""

    base_type = SIEMConnector
    entry_point_group = "community_ai_audit.connectors"
    builtin_module_prefix = "community_ai_audit.connectors"

    def get_siem(self, name: str) -> "SIEMConnector":  # noqa: F821
        """Get a SIEM connector by name."""
        return self.get(name)

    def get_security_tool(self, name: str) -> SecurityToolConnector:
        """Get a security tool connector by name."""
        return self.get(name)

    def get_threat_intel(self, name: str) -> "ThreatIntelConnector":  # noqa: F821
        """Get a threat intel connector by name."""
        return self.get(name)


class PluginRegistry(Registry):
    """Registry for scanner and interpreter plugins."""

    base_type = object  # abstract, split below
    entry_point_group = "community_ai_audit.plugins"
    builtin_module_prefix = "community_ai_audit.plugins"

    def __init__(self):
        super().__init__()
        self.scanners = _SubRegistry(ScannerPlugin, "community_ai_audit.plugins.scanners", "community_ai_audit.plugins.scanners")
        self.interpreters = _SubRegistry(InterpreterPlugin, "community_ai_audit.plugins.interpreters", "community_ai_audit.plugins.interpreters")
        self.reporters = _SubRegistry(ReporterPlugin, "community_ai_audit.plugins.reporters", "community_ai_audit.plugins.reporters")

    def discover(self, extra_paths: Optional[List[str]] = None) -> None:
        self.scanners.discover(extra_paths)
        self.interpreters.discover(extra_paths)
        self.reporters.discover(extra_paths)
        # Also discover our own subclasses
        super().discover(extra_paths)

    def list_scanners(self) -> List[str]:
        return self.scanners.list_available()

    def list_interpreters(self) -> List[str]:
        return self.interpreters.list_available()

    def list_reporters(self) -> List[str]:
        return self.reporters.list_available()


class _SubRegistry(Registry):
    """Scoped sub-registry for scanner / interpreter / reporter types."""

    def __init__(self, base_type: type, entry_point_group: str, builtin_prefix: str = ""):
        self._base_type = base_type
        self.entry_point_group = entry_point_group
        self.builtin_module_prefix = builtin_prefix
        self._plugins: Dict[str, Type] = {}
        self._instances: Dict[str, Any] = {}
        self._discovered = False

    @property
    def base_type(self) -> type:
        return self._base_type

    def discover(self, extra_paths: Optional[List[str]] = None) -> None:
        self._discover_entry_points()
        if extra_paths:
            self._discover_paths(extra_paths)
        # Also try built-in subpackage discovery
        if self.builtin_module_prefix:
            try:
                pkg = importlib.import_module(self.builtin_module_prefix)
                self._register_from_module(pkg)
                # Also try iterating submodules
                if hasattr(pkg, '__path__'):
                    for importer, mod_name, is_pkg in pkgutil.iter_modules(pkg.__path__, f"{self.builtin_module_prefix}."):
                        try:
                            mod = importlib.import_module(mod_name)
                            self._register_from_module(mod)
                        except ImportError:
                            pass
            except ImportError:
                pass
        self._discovered = True


# ─────────────────────────────────────────────────────────────
# Global registry instances
# ─────────────────────────────────────────────────────────────

# Singleton registries — import these anywhere
adapters = AdapterRegistry()
connectors = ConnectorRegistry()
plugins = PluginRegistry()


# ─────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────

def _snake_to_kebab(s: str) -> str:
    """Convert SnakeCase class name to kebab-case plugin name."""
    import re
    s = re.sub(r"(?<!^)(?=[A-Z])", "-", s).lower()
    return s


# Import helper for pkgutil (needed for Python < 3.12 compat)
try:
    from importlib.resources import files
except ImportError:
    files = None


import pkgutil


def pkgutil_iter_modules(path: Optional[List[str]], prefix: str = ""):
    """Yield (importer, name, is_pkg) tuples for modules in path."""
    return pkgutil.iter_modules(path, prefix)