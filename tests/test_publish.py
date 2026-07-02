from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from anki_addon_release.config import AnkiWebConfig, ReleaseConfig
from anki_addon_release.errors import PublishError
from anki_addon_release.manifest import ManifestReport
from anki_addon_release.publish import build_publish_plan, default_profile_dir, describe_publish_plan


class PublishPlanTests(unittest.TestCase):
    def test_auto_mode_uses_update_when_addon_id_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = ReleaseConfig(
                project_root=root,
                source_dir=root,
                manifest=root / "manifest.json",
                artifact_dir=root / "dist",
                artifact_name="study-triage.ankiaddon",
                ankiweb=AnkiWebConfig(addon_id="123456789", title="Study Triage"),
            )
            manifest = ManifestReport(
                path=root / "manifest.json",
                data={"package": "study_triage", "name": "Study Triage"},
                warnings=(),
            )

            plan = build_publish_plan(config, manifest, mode="auto", submit=False)

            self.assertEqual(plan.mode, "update")
            self.assertEqual(plan.addon_id, "123456789")
            self.assertEqual(plan.upload_url, "https://ankiweb.net/shared/upload?id=123456789")
            self.assertEqual(plan.title, "Study Triage")
            self.assertFalse(plan.submit)

    def test_auto_mode_uses_create_without_addon_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = ReleaseConfig(
                project_root=root,
                source_dir=root,
                manifest=root / "manifest.json",
                artifact_dir=root / "dist",
            )
            manifest = ManifestReport(
                path=root / "manifest.json",
                data={
                    "package": "new_addon",
                    "name": "New Add-on",
                    "min_point_version": 55,
                    "max_point_version": 250902,
                },
                warnings=(),
            )

            plan = build_publish_plan(config, manifest, mode="auto", base_url="http://127.0.0.1:9999")

            self.assertEqual(plan.mode, "create")
            self.assertEqual(plan.base_url, "http://127.0.0.1:9999")
            self.assertEqual(plan.upload_url, "http://127.0.0.1:9999/shared/upload")
            self.assertEqual(plan.title, "New Add-on")
            self.assertIsNone(plan.support_url)
            self.assertEqual(plan.branch_min_version, "2.1.55")
            self.assertEqual(plan.branch_max_version, "25.09.2")

    def test_update_mode_requires_addon_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = ReleaseConfig(
                project_root=root,
                source_dir=root,
                manifest=root / "manifest.json",
                artifact_dir=root / "dist",
            )
            manifest = ManifestReport(
                path=root / "manifest.json",
                data={"package": "new_addon", "name": "New Add-on"},
                warnings=(),
            )

            with self.assertRaises(PublishError):
                build_publish_plan(config, manifest, mode="update")

    def test_description_and_changelog_files_are_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            description = root / "README.md"
            changelog = root / "CHANGELOG.md"
            description.write_text("# Description\n", encoding="utf-8")
            changelog.write_text("## Changes\n", encoding="utf-8")
            config = ReleaseConfig(
                project_root=root,
                source_dir=root,
                manifest=root / "manifest.json",
                artifact_dir=root / "dist",
                ankiweb=AnkiWebConfig(
                    description_file=description,
                    changelog_file=changelog,
                ),
            )
            manifest = ManifestReport(
                path=root / "manifest.json",
                data={"package": "new_addon", "name": "New Add-on"},
                warnings=(),
            )

            plan = build_publish_plan(config, manifest)

            self.assertEqual(plan.description, "# Description\n")
            self.assertEqual(plan.changelog, "## Changes\n")

    def test_describe_publish_plan_avoids_dumping_long_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = ReleaseConfig(
                project_root=root,
                source_dir=root,
                manifest=root / "manifest.json",
                artifact_dir=root / "dist",
                ankiweb=AnkiWebConfig(description="long description", changelog="changes"),
            )
            manifest = ManifestReport(
                path=root / "manifest.json",
                data={"package": "new_addon", "name": "New Add-on"},
                warnings=(),
            )

            lines = describe_publish_plan(build_publish_plan(config, manifest))

            self.assertIn("description: 16 chars", lines)
            self.assertIn("changelog: 7 chars", lines)

    def test_default_profile_dir_is_project_local(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = ReleaseConfig(
                project_root=root,
                source_dir=root,
                manifest=root / "manifest.json",
                artifact_dir=root / "dist",
            )

            self.assertEqual(
                default_profile_dir(config),
                root / ".anki-addon-release" / "browser-profile",
            )


if __name__ == "__main__":
    unittest.main()
