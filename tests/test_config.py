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
                    """
                ).strip(),
                encoding="utf-8",
            )

            config = load_config(root)

            self.assertEqual(config.source_dir, (root / "addon").resolve())
            self.assertEqual(config.manifest, (root / "addon" / "manifest.json").resolve())
            self.assertEqual(config.artifact_path, (root / "dist" / "study-triage.ankiaddon").resolve())
            self.assertEqual(config.include, ("__init__.py", "manifest.json"))
            self.assertEqual(config.exclude, ("tests",))


if __name__ == "__main__":
    unittest.main()

