"""
Role-Based Access Control for multi-user deployments.

Defines roles, permissions, and an access control layer so that
different operators can have different levels of access to the
audit system (scanning, scheduling, user management, etc.).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

import yaml

log = logging.getLogger(__name__)

# ── Built-in role definitions ──────────────────────────────────

DEFAULT_ROLES: Dict[str, List[str]] = {
    "admin": ["*"],
    "auditor": [
        "scan:run",
        "scan:view",
        "audit:run",
        "audit:view",
        "schedule:view",
        "results:view",
        "results:export",
    ],
    "viewer": [
        "scan:view",
        "audit:view",
        "schedule:view",
        "results:view",
    ],
}

DEFAULT_CONFIG_PATH = Path("~/.community-ai-audit/rbac.yaml").expanduser()


# ── Custom Exception ───────────────────────────────────────────


class PermissionError(Exception):
    """Raised when a user lacks the required permission for an action."""

    def __init__(self, user: str, permission: str) -> None:
        self.user = user
        self.permission = permission
        super().__init__(f"User '{user}' lacks permission '{permission}'")


# ── User Model ─────────────────────────────────────────────────


@dataclass
class User:
    """Represents a single operator in the system.

    Attributes:
        username: Unique login / display name.
        role: Role name this user belongs to (e.g. ``"admin"``).
        api_key: Optional API key for programmatic authentication.
        enabled: Whether the account is active.
    """

    username: str
    role: str
    api_key: Optional[str] = None
    enabled: bool = True


# ── Configuration ──────────────────────────────────────────────


class RBACConfig:
    """Loads / saves user and role definitions from a YAML file.

    When no config file exists, a sensible default is created with a
    single ``admin`` user (no API key requirement).

    Attributes:
        roles: Mapping of role name → list of permission strings.
        users: Mapping of username → User instance.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """Load RBAC config from a YAML file or use defaults.

        Args:
            config_path: Path to the RBAC YAML file.  Falls back to
                ``~/.community-ai-audit/rbac.yaml``.
        """
        self.roles: Dict[str, List[str]] = dict(DEFAULT_ROLES)
        self.users: Dict[str, User] = {}

        self._config_path: Path = (
            Path(config_path).expanduser()
            if config_path
            else DEFAULT_CONFIG_PATH
        )

        if self._config_path.exists():
            self.load(self._config_path)
        else:
            self._create_default()

    # ── Public API ──────────────────────────────────────────────

    def load(self, path: Path) -> None:
        """Load RBAC definitions from a YAML file.

        Args:
            path: Path to the YAML file.

        Raises:
            yaml.YAMLError: If the file is malformed.
        """
        with open(path) as f:
            data: Dict[str, Any] = yaml.safe_load(f) or {}

        self.roles.update(data.get("roles", {}))
        self.users.clear()

        for username, info in data.get("users", {}).items():
            self.users[username] = User(
                username=username,
                role=info.get("role", "viewer"),
                api_key=info.get("api_key"),
                enabled=info.get("enabled", True),
            )

        log.info("Loaded RBAC config from %s (%d users)", path, len(self.users))

    def save(self, path: Optional[Path] = None) -> None:
        """Persist current roles and users to a YAML file.

        Args:
            path: Destination path.  Defaults to the path used during
                initialisation.
        """
        dest = Path(path) if path else self._config_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        user_data: Dict[str, Dict[str, Any]] = {}
        for name, user in self.users.items():
            entry: Dict[str, Any] = {"role": user.role, "enabled": user.enabled}
            if user.api_key:
                entry["api_key"] = user.api_key
            user_data[name] = entry

        data = {
            "roles": self.roles,
            "users": user_data,
        }

        with open(dest, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        log.info("Saved RBAC config to %s", dest)

    # ── Internal Helpers ────────────────────────────────────────

    def _create_default(self) -> None:
        """Seed an ``admin`` user so the system is immediately usable."""
        self.users["admin"] = User(username="admin", role="admin")
        self.save()
        log.info(
            "Created default RBAC config at %s with an 'admin' user",
            self._config_path,
        )


# ── Access Control Layer ───────────────────────────────────────


class AccessControl:
    """Main interface for permission checks and user authentication.

    Usage::

        config = RBACConfig()
        acl = AccessControl(config)

        if acl.check_permission("alice", "scan:run"):
            ...

        acl.require_permission("bob", "admin:manage")
    """

    DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_PATH

    def __init__(self, config: RBACConfig) -> None:
        """Initialise the access control layer.

        Args:
            config: An ``RBACConfig`` instance holding roles and users.
        """
        self.config = config

    # ── Permission Checks ───────────────────────────────────────

    def check_permission(self, user: str, permission: str) -> bool:
        """Check whether a user has a given permission.

        The ``"*"`` wildcard (used by the ``admin`` role) grants every
        permission implicitly.

        Args:
            user: The username to check.
            permission: The permission string (e.g. ``"scan:run"``).

        Returns:
            ``True`` if the user or their role is unknown, :meth:`check_permission`
            returns ``False`` so that callers always get a safe default.
        """
        user_obj = self.config.users.get(user)
        if user_obj is None:
            return False
        if not user_obj.enabled:
            return False

        role_perms = self.config.roles.get(user_obj.role, [])
        return "*" in role_perms or permission in role_perms

    def require_permission(self, user: str, permission: str) -> None:
        """Assert that a user has the required permission.

        Args:
            user: The username to check.
            permission: The required permission string.

        Raises:
            PermissionError: If the user lacks the permission or does
                not exist.
        """
        if not self.check_permission(user, permission):
            raise PermissionError(user, permission)

    # ── Authentication ──────────────────────────────────────────

    def authenticate(self, username: str, api_key: Optional[str] = None) -> bool:
        """Verify that a user exists, is enabled, and optionally matches
        the provided API key.

        Args:
            username: The username to authenticate.
            api_key: If provided, must match the user's stored API key.

        Returns:
            ``True`` if the user is valid and the API key (if any)
            matches.
        """
        user_obj = self.config.users.get(username)
        if user_obj is None:
            return False
        if not user_obj.enabled:
            return False
        if api_key is not None and user_obj.api_key is not None:
            return api_key == user_obj.api_key
        return True

    # ── User Queries ────────────────────────────────────────────

    def get_user(self, username: str) -> Optional[User]:
        """Look up a user by username.

        Args:
            username: The username to look up.

        Returns:
            The ``User`` instance, or ``None`` if not found.
        """
        return self.config.users.get(username)

    def list_users(self) -> List[str]:
        """Return a list of all registered usernames."""
        return list(self.config.users.keys())
