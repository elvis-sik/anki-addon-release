from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from anki_addon_release.config import ReleaseConfig
from anki_addon_release.handoff import write_handoff
from anki_addon_release.manifest import ManifestReport
from anki_addon_release.packager import ArchiveEntry
from anki_addon_release.publish import PublishPlan


class HandoffTests(unittest.TestCase):
    def test_writes_browser_operator_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "handoff"
            config = ReleaseConfig(
                project_root=root,
                source_dir=root,
                manifest=root / "manifest.json",
                artifact_dir=root / "dist",
            )
            manifest = ManifestReport(
                path=root / "manifest.json",
                data={"package": "study_triage", "name": "Study Triage"},
                warnings=(),
            )
            plan = PublishPlan(
                mode="create",
                base_url="https://ankiweb.net",
                upload_url="https://ankiweb.net/shared/addons",
                login_url="https://ankiweb.net/account/login",
                artifact_path=root / "dist" / "study-triage.ankiaddon",
                addon_id=None,
                title="Study Triage",
                support_url="https://github.com/ritornello-labs/study-triage",
                description="Description text",
                changelog="Change text",
                submit=False,
            )

            result = write_handoff(
                config=config,
                manifest=manifest,
                publish_plan=plan,
                archive_entries=(
                    ArchiveEntry(filename="__init__.py", file_size=10),
                    ArchiveEntry(filename="manifest.json", file_size=20),
                ),
                out_dir=out_dir,
            )

            self.assertEqual(result.out_dir, out_dir)
            self.assertTrue((out_dir / "release-handoff.json").exists())
            self.assertEqual((out_dir / "description.txt").read_text(encoding="utf-8"), "Description text")
            self.assertEqual((out_dir / "changelog.txt").read_text(encoding="utf-8"), "Change text")
            prompt = (out_dir / "codex-browser-prompt.md").read_text(encoding="utf-8")
            self.assertIn("Do not click the final publish", prompt)

            metadata = json.loads((out_dir / "release-handoff.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["mode"], "create")
            self.assertEqual(metadata["title"], "Study Triage")
            self.assertEqual(metadata["support_url"], "https://github.com/ritornello-labs/study-triage")
            self.assertTrue(metadata["safety"]["final_submit_requires_confirmation"])
            self.assertTrue(metadata["safety"]["record_addon_id_after_create"])


if __name__ == "__main__":
    unittest.main()
