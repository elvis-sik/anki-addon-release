from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from anki_addon_release.credentials import resolve_env_credentials
from anki_addon_release.errors import PublishError


class CredentialTests(unittest.TestCase):
    def test_no_env_names_means_manual_login(self) -> None:
        self.assertIsNone(resolve_env_credentials(email_env=None, password_env=None))

    def test_resolves_credentials_from_environment(self) -> None:
        with patch.dict(os.environ, {"ANKIWEB_EMAIL": "user@example.com", "ANKIWEB_PASSWORD": "secret"}):
            credentials = resolve_env_credentials(
                email_env="ANKIWEB_EMAIL",
                password_env="ANKIWEB_PASSWORD",
            )

        self.assertIsNotNone(credentials)
        self.assertEqual(credentials.email, "user@example.com")
        self.assertEqual(credentials.password, "secret")

    def test_requires_env_names_together(self) -> None:
        with self.assertRaises(PublishError):
            resolve_env_credentials(email_env="ANKIWEB_EMAIL", password_env=None)

    def test_missing_env_value_is_error(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(PublishError):
                resolve_env_credentials(
                    email_env="ANKIWEB_EMAIL",
                    password_env="ANKIWEB_PASSWORD",
                )


if __name__ == "__main__":
    unittest.main()

