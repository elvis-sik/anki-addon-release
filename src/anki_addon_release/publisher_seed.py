from __future__ import annotations

import argparse
from pathlib import Path

from aqt.profiles import ProfileManager


def seed_publisher_base(base: Path, profile: str, lang: str) -> None:
    base.mkdir(parents=True, exist_ok=True)
    manager = ProfileManager(base)
    manager.setupMeta()
    manager.meta["defaultLang"] = lang
    manager.meta["firstRun"] = False
    # On current Anki builds, ProfileManager.profiles() lazily creates a
    # fallback profile through the GUI backend, which is unavailable here.
    # The caller only seeds an empty publisher base, so create directly.
    manager.create(profile)
    manager.load(profile)
    # A publisher profile must never inherit a self-hosted sync endpoint.
    manager.profile["customSyncUrl"] = None
    manager.profile["currentSyncUrl"] = None
    manager.save()
    assert manager.db is not None
    manager.db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--lang", default="en_US")
    args = parser.parse_args()
    seed_publisher_base(Path(args.base), args.profile, args.lang)


if __name__ == "__main__":
    main()
