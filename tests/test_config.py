from __future__ import annotations

from pathlib import Path
import tempfile
import textwrap
import unittest

from anki_addon_release.config import load_config


class ConfigTests(unittest.TestCase):
    def test_loads_release_config_from_pyproject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "addon").mkdir()
            (root / "pyproject.toml").write_text(
                textwrap.dedent(
                    """
                    [tool.anki-addon-release]
                    source_dir = "addon"
                    manifest = "addon/manifest.json"
                    artifact_dir = "dist"
                    artifact_name = "study-triage.ankiaddon"
                    include = ["__init__.py", "manifest.json"]
                    exclude = ["tests"]

                    [tool.anki-addon-release.ankiweb]
                    addon_id = "123456789"
                    title = "Study Triage"
                    support_url = "https://github.com/elvis-sik/anki-zero-today-new"
                    description_file = "README.md"
                    changelog_file = "CHANGELOG.md"
                    profile_dir = ".browser-profile"
                    login_email_env = "ANKIWEB_EMAIL"
                    login_password_env = "ANKIWEB_PASSWORD"
                    """
                ).strip(),
                encoding="utf-8",
            )
            (root / "README.md").write_text("# Study Triage\n", encoding="utf-8")
            (root / "CHANGELOG.md").write_text("## Next\n", encoding="utf-8")

            config = load_config(root)

            self.assertEqual(config.source_dir, (root / "addon").resolve())
            self.assertEqual(config.manifest, (root / "addon" / "manifest.json").resolve())
            self.assertEqual(config.artifact_path, (root / "dist" / "study-triage.ankiaddon").resolve())
            self.assertEqual(config.include, ("__init__.py", "manifest.json"))
            self.assertEqual(config.exclude, ("tests",))
            self.assertEqual(config.ankiweb.addon_id, "123456789")
            self.assertEqual(config.ankiweb.title, "Study Triage")
            self.assertEqual(config.ankiweb.support_url, "https://github.com/elvis-sik/anki-zero-today-new")
            self.assertEqual(config.ankiweb.description_file, (root / "README.md").resolve())
            self.assertEqual(config.ankiweb.changelog_file, (root / "CHANGELOG.md").resolve())
            self.assertEqual(config.ankiweb.profile_dir, (root / ".browser-profile").resolve())
            self.assertEqual(config.ankiweb.login_email_env, "ANKIWEB_EMAIL")
            self.assertEqual(config.ankiweb.login_password_env, "ANKIWEB_PASSWORD")


if __name__ == "__main__":
    unittest.main()
