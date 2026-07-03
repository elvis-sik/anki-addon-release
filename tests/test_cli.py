from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from anki_addon_release.cli import main


class CliTests(unittest.TestCase):
    def test_check_warns_when_github_url_is_not_visible_in_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _addon_project(Path(tmp))
            listing = root / "release" / "ankiweb.md"
            listing.parent.mkdir()
            listing.write_text(
                "\n".join(
                    [
                        "---",
                        "support_url: https://github.com/example/addon",
                        "---",
                        "",
                        "[GitHub](https://github.com/example/addon)",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(["--project", str(root), "check"])

            self.assertEqual(exit_code, 0)
            self.assertIn("warning: AnkiWeb description should include", stdout.getvalue())

    def test_publish_preview_description_prints_exact_markdown_and_exits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = _addon_project(Path(tmp))
            listing = root / "release" / "ankiweb.md"
            listing.parent.mkdir()
            listing.write_text(
                "\n".join(
                    [
                        "---",
                        "title: Preview Add-on",
                        "---",
                        "",
                        "GitHub: [https://github.com/example/addon](https://github.com/example/addon)",
                        "",
                        "Body text.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(["--project", str(root), "publish", "--preview-description"])

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("--- BEGIN DESCRIPTION ---", output)
            self.assertIn(
                "GitHub: [https://github.com/example/addon](https://github.com/example/addon)\n\nBody text.\n",
                output,
            )
            self.assertIn("--- END DESCRIPTION ---", output)


def _addon_project(root: Path) -> Path:
    (root / "manifest.json").write_text(
        '{"package": "preview_addon", "name": "Preview Add-on"}',
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[tool.anki-addon-release]",
                'source_dir = "."',
                'manifest = "manifest.json"',
                'artifact_dir = "dist"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return root


if __name__ == "__main__":
    unittest.main()
