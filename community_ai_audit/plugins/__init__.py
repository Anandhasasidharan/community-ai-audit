"""
Plugin system. All audit plugins (scanners, interpreters, reporters)
inherit from the ABCs in core.interfaces and are auto-discovered by
PluginRegistry via setuptools entry points or explicit paths.
"""

# Re-export registry for convenience
from community_ai_audit.core.registry import plugins as plugin_registry

__all__ = ["plugin_registry"]