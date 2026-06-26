from __future__ import annotations

import unittest

from anki_addon_release.errors import ManifestError
from anki_addon_release.manifest import validate_manifest_data


class ManifestValidationTests(unittest.TestCase):
    def test_accepts_minimal_manifest(self) -> None:
        warnings = validate_manifest_data({"package": "study_triage", "name": "Study Triage"})

        self.assertEqual(warnings, [])

    def test_rejects_path_like_package(self) -> None:
        with self.assertRaises(ManifestError):
            validate_manifest_data({"package": "../bad", "name": "Bad"})

    def test_warns_about_legacy_version_keys(self) -> None:
        warnings = validate_manifest_data(
            {
                "package": "study_triage",
                "name": "Study Triage",
                "min_anki_version": "2.1.55",
            }
        )

        self.assertEqual(
            warnings,
            ["manifest uses legacy min_anki_version; prefer integer point-version keys"],
        )


if __name__ == "__main__":
    unittest.main()

