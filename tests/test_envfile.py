from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from anki_addon_release.envfile import load_env_file


class EnvFileTests(unittest.TestCase):
    def test_loads_simple_env_file_without_overriding_existing_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text(
                "\n".join(
                    [
                        "ANKIWEB_SOURCE_DECK_ID=1650000000000",
                        'ANKIWEB_EMAIL="user@example.com"',
                        "export ANKIWEB_PASSWORD='secret'",
                    ]
                ),
                encoding="utf-8",
            )
            old_email = os.environ.get("ANKIWEB_EMAIL")
            old_password = os.environ.get("ANKIWEB_PASSWORD")
            old_deck_id = os.environ.get("ANKIWEB_SOURCE_DECK_ID")
            os.environ["ANKIWEB_EMAIL"] = "already@example.com"
            try:
                load_env_file(path)

                self.assertEqual(os.environ["ANKIWEB_SOURCE_DECK_ID"], "1650000000000")
                self.assertEqual(os.environ["ANKIWEB_EMAIL"], "already@example.com")
                self.assertEqual(os.environ["ANKIWEB_PASSWORD"], "secret")
            finally:
                _restore_env("ANKIWEB_EMAIL", old_email)
                _restore_env("ANKIWEB_PASSWORD", old_password)
                _restore_env("ANKIWEB_SOURCE_DECK_ID", old_deck_id)


def _restore_env(key: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
