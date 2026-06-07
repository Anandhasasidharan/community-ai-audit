"""Tests for the RBAC module."""

import unittest
from tempfile import TemporaryDirectory
from pathlib import Path


class TestRBACConfig(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.core.rbac import RBACConfig

        self.tmpdir = TemporaryDirectory()
        self.config_path = str(Path(self.tmpdir.name) / "rbac.yaml")
        self.config = RBACConfig(config_path=self.config_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_default_admin_user(self):
        """When no config file exists, a default admin user should be created."""
        self.assertIn("admin", self.config.users)
        self.assertEqual(self.config.users["admin"].role, "admin")

    def test_builtin_roles(self):
        """Should have admin, auditor, and viewer roles."""
        self.assertIn("admin", self.config.roles)
        self.assertIn("auditor", self.config.roles)
        self.assertIn("viewer", self.config.roles)

    def test_admin_has_wildcard(self):
        self.assertIn("*", self.config.roles["admin"])

    def test_save_and_load(self):
        """Save and reload the config."""
        self.config.save(self.config_path)
        from community_ai_audit.core.rbac import RBACConfig

        c2 = RBACConfig(config_path=self.config_path)
        self.assertEqual(len(c2.users), len(self.config.users))
        self.assertEqual(c2.users["admin"].role, "admin")


class TestAccessControl(unittest.TestCase):
    def setUp(self):
        from community_ai_audit.core.rbac import RBACConfig, AccessControl

        self.tmpdir = TemporaryDirectory()
        self.config_path = str(Path(self.tmpdir.name) / "rbac.yaml")
        config = RBACConfig(config_path=self.config_path)
        self.ac = AccessControl(config)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_admin_has_all_permissions(self):
        self.assertTrue(self.ac.check_permission("admin", "scan:run"))
        self.assertTrue(self.ac.check_permission("admin", "audit:run"))
        self.assertTrue(self.ac.check_permission("admin", "admin:manage"))
        self.assertTrue(self.ac.check_permission("admin", "nonexistent:perm"))

    def test_auditor_permissions(self):
        self.assertTrue(self.ac.check_permission("admin", "scan:run"))
        self.assertTrue(self.ac.check_permission("admin", "results:view"))

    def test_viewer_restricted(self):
        from community_ai_audit.core.rbac import User

        self.ac.config.users["viewer_user"] = User(
            username="viewer_user", role="viewer"
        )
        self.assertFalse(self.ac.check_permission("viewer_user", "scan:run"))
        self.assertFalse(self.ac.check_permission("viewer_user", "audit:run"))
        self.assertFalse(self.ac.check_permission("viewer_user", "schedule:manage"))
        self.assertTrue(self.ac.check_permission("viewer_user", "results:view"))

    def test_authenticate_valid_user(self):
        self.assertTrue(self.ac.authenticate("admin"))

    def test_authenticate_nonexistent_user(self):
        self.assertFalse(self.ac.authenticate("nonexistent"))

    def test_authenticate_disabled_user(self):
        from community_ai_audit.core.rbac import User

        self.ac.config.users["disabled_user"] = User(
            username="disabled_user", role="viewer", enabled=False
        )
        self.assertFalse(self.ac.authenticate("disabled_user"))

    def test_authenticate_with_api_key(self):
        from community_ai_audit.core.rbac import User

        self.ac.config.users["key_user"] = User(
            username="key_user", role="auditor", api_key="sk-test123"
        )
        self.assertTrue(self.ac.authenticate("key_user", "sk-test123"))
        self.assertFalse(self.ac.authenticate("key_user", "wrong-key"))

    def test_get_user(self):
        user = self.ac.get_user("admin")
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "admin")

    def test_get_user_nonexistent(self):
        self.assertIsNone(self.ac.get_user("nobody"))

    def test_list_users(self):
        users = self.ac.list_users()
        self.assertIn("admin", users)

    def test_require_permission_allowed(self):
        try:
            self.ac.require_permission("admin", "scan:run")
        except Exception as e:
            self.fail(f"require_permission raised {e}")

    def test_require_permission_denied(self):
        from community_ai_audit.core.rbac import PermissionError

        with self.assertRaises(PermissionError):
            self.ac.require_permission("viewer", "scan:run")

    def test_require_permission_nonexistent_user(self):
        from community_ai_audit.core.rbac import PermissionError

        with self.assertRaises(PermissionError):
            self.ac.require_permission("nobody", "scan:run")


if __name__ == "__main__":
    unittest.main()
