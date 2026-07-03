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
                    support_url = "https://github.com/elvis-sik/study-triage"
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
            self.assertEqual(config.ankiweb.support_url, "https://github.com/elvis-sik/study-triage")
            self.assertEqual(config.ankiweb.description_file, (root / "README.md").resolve())
            self.assertEqual(config.ankiweb.changelog_file, (root / "CHANGELOG.md").resolve())
            self.assertEqual(config.ankiweb.profile_dir, (root / ".browser-profile").resolve())
            self.assertEqual(config.ankiweb.login_email_env, "ANKIWEB_EMAIL")
            self.assertEqual(config.ankiweb.login_password_env, "ANKIWEB_PASSWORD")

    def test_loads_default_listing_file_from_release_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "addon").mkdir()
            release = root / "release"
            release.mkdir()
            (release / "ankiweb.md").write_text("# Description\n", encoding="utf-8")
            (root / "pyproject.toml").write_text(
                textwrap.dedent(
                    """
                    [tool.anki-addon-release]
                    source_dir = "addon"
                    manifest = "addon/manifest.json"

                    [tool.anki-addon-release.ankiweb]
                    addon_id = "123456789"
                    """
                ).strip(),
                encoding="utf-8",
            )

            config = load_config(root)

            self.assertEqual(config.ankiweb.listing_file, (release / "ankiweb.md").resolve())

    def test_loads_deck_config_with_private_local_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Deck\n", encoding="utf-8")
            (root / "pyproject.toml").write_text(
                textwrap.dedent(
                    """
                    [tool.anki-addon-release]
                    target = "deck"

                    [tool.anki-addon-release.ankiweb]
                    shared_id = "987654321"
                    title = "Geography Deck"
                    tags = "geography maps"
                    support_url = "https://github.com/example/geography-deck"
                    description_file = "README.md"

                    [tool.anki-addon-release.deck]
                    source_deck_id_env = "ANKIWEB_SOURCE_DECK_ID"
                    """
                ).strip(),
                encoding="utf-8",
            )
            (root / ".anki-addon-release.local.toml").write_text(
                textwrap.dedent(
                    """
                    [deck]
                    source_deck_id = "1650000000000"
                    copyright_confirmed = true
                    """
                ).strip(),
                encoding="utf-8",
            )

            config = load_config(root)

            self.assertEqual(config.target, "deck")
            self.assertIsNone(config.source_dir)
            self.assertIsNone(config.manifest)
            self.assertEqual(config.ankiweb.shared_id, "987654321")
            self.assertEqual(config.ankiweb.title, "Geography Deck")
            self.assertEqual(config.ankiweb.tags, "geography maps")
            self.assertEqual(config.ankiweb.description_file, (root / "README.md").resolve())
            self.assertEqual(config.deck.source_deck_id, "1650000000000")
            self.assertEqual(config.deck.source_deck_id_env, "ANKIWEB_SOURCE_DECK_ID")
            self.assertTrue(config.deck.copyright_confirmed)

    def test_can_disable_private_local_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                textwrap.dedent(
                    """
                    [tool.anki-addon-release]
                    target = "deck"

                    [tool.anki-addon-release.deck]
                    source_deck_id_env = "ANKIWEB_SOURCE_DECK_ID"
                    """
                ).strip(),
                encoding="utf-8",
            )
            (root / ".anki-addon-release.local.toml").write_text(
                "[deck]\nsource_deck_id = \"private-id\"\n",
                encoding="utf-8",
            )

            config = load_config(root, local_config_file=None)

            self.assertIsNone(config.deck.source_deck_id)
            self.assertEqual(config.deck.source_deck_id_env, "ANKIWEB_SOURCE_DECK_ID")


if __name__ == "__main__":
    unittest.main()
