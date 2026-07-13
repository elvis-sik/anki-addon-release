from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import zipfile

from anki_addon_release.errors import ReleaseError
from anki_addon_release.publisher import (
    PublisherPaths,
    backup_publisher_collection,
    configure_anki_connect,
    initialize_publisher,
    launch_publisher,
    publisher_status,
    register_deck_id,
)


class PublisherTests(unittest.TestCase):
    def test_backup_contains_consistent_database_media_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = PublisherPaths(base=root / "publisher", profile="Publisher")
            paths.profile_dir.mkdir(parents=True)
            with sqlite3.connect(paths.collection_path) as database:
                database.execute("create table sample (value text)")
                database.execute("insert into sample values ('ready')")
            paths.media_dir.mkdir()
            (paths.media_dir / "map.png").write_bytes(b"image")

            backup = backup_publisher_collection(paths)

            with zipfile.ZipFile(backup) as archive:
                self.assertEqual(set(archive.namelist()), {"collection.anki2", "collection.media/map.png", "publisher-backup.json"})
                self.assertEqual(archive.getinfo("collection.anki2").compress_type, zipfile.ZIP_STORED)
                manifest = archive.read("publisher-backup.json").decode("utf-8")
                self.assertIn('"media_file_count": 1', manifest)

    def test_register_deck_id_replaces_only_target_variable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            env_file = Path(temporary) / ".env"
            env_file.write_text("ANKIWEB_EMAIL=op://Personal/AnkiWeb/username\nTARGET=old\n", encoding="utf-8")

            register_deck_id(env_file, variable="TARGET", deck_id="123456")

            self.assertEqual(
                env_file.read_text(encoding="utf-8"),
                "ANKIWEB_EMAIL=op://Personal/AnkiWeb/username\nTARGET=123456\n",
            )

    def test_register_deck_id_rejects_invalid_variable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ReleaseError):
                register_deck_id(Path(temporary) / ".env", variable="123", deck_id="123456")

    def test_initialize_seeds_an_isolated_profile_and_copies_addon_without_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source-addon"
            source.mkdir()
            (source / "__init__.py").write_text("# addon\n", encoding="utf-8")
            (source / "config.json").write_text("{}\n", encoding="utf-8")
            (source / "meta.json").write_text("{}\n", encoding="utf-8")
            (source / "user_files").mkdir()
            (source / "user_files" / "state.txt").write_text("private\n", encoding="utf-8")
            paths = PublisherPaths(base=root / "publisher", profile="Publisher")

            with patch("anki_addon_release.publisher._seed_profile") as seed:
                initialize_publisher(paths, anki_python="anki-python", anki_connect_source=source)

            seed.assert_called_once_with(paths, "anki-python")
            self.assertTrue((paths.anki_connect_dir / "__init__.py").is_file())
            self.assertFalse((paths.anki_connect_dir / "meta.json").exists())
            self.assertFalse((paths.anki_connect_dir / "user_files").exists())

    def test_configure_anki_connect_uses_a_dedicated_port(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = PublisherPaths(base=Path(temporary) / "publisher", profile="Publisher")
            paths.anki_connect_dir.mkdir(parents=True)
            paths.anki_connect_config.write_text('{"webBindPort": 8765}\n', encoding="utf-8")

            configure_anki_connect(paths, port=8766)

            self.assertIn('"webBindPort": 8766', paths.anki_connect_config.read_text(encoding="utf-8"))

    def test_status_accepts_current_anki_preferences_filename(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = PublisherPaths(base=Path(temporary) / "publisher", profile="Publisher")
            paths.base.mkdir()
            (paths.base / "prefs21.db").write_bytes(b"prefs")

            self.assertEqual(publisher_status(paths)["initialized"], True)

    def test_launch_uses_an_isolated_direct_runner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = PublisherPaths(base=Path(temporary) / "publisher", profile="Publisher")
            paths.base.mkdir()
            (paths.base / "prefs21.db").write_bytes(b"prefs")
            paths.anki_connect_dir.mkdir(parents=True)
            paths.anki_connect_config.write_text('{"webBindPort": 8766}\n', encoding="utf-8")
            process = MagicMock(pid=42)

            with patch("anki_addon_release.publisher.default_anki_python", return_value="/anki/python"), patch(
                "anki_addon_release.publisher.subprocess.Popen", return_value=process
            ) as popen:
                returned, command = launch_publisher(paths, anki_bin="/anki/anki")

            self.assertIs(returned, process)
            self.assertEqual(command[0], "/anki/python")
            self.assertIn("publisher_run_anki.py", command[1])
            self.assertEqual(command[-4:], ["-p", "Publisher", "--lang", "en"])
            self.assertEqual(popen.call_args.kwargs["env"]["ANKI_SINGLE_INSTANCE_KEY"].startswith("anki-addon-release-publisher-"), True)

    def test_status_reports_missing_collection_without_claiming_initialized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = PublisherPaths(base=Path(temporary) / "publisher", profile="Publisher")
            self.assertEqual(
                publisher_status(paths)["initialized"],
                False,
            )


if __name__ == "__main__":
    unittest.main()
