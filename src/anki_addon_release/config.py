from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
import tomllib

from .errors import ConfigError


ReleaseTarget = Literal["addon", "deck"]

DEFAULT_EXCLUDE = (
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "*.pyc",
    ".DS_Store",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".uv-cache",
    ".venv",
    "dist",
    "build",
    "tests",
)


@dataclass(frozen=True)
class AnkiWebConfig:
    base_url: str = "https://ankiweb.net"
    addon_id: str | None = None
    shared_id: str | None = None
    listing_file: Path | None = None
    title: str | None = None
    title_file: Path | None = None
    tags: str | None = None
    tags_file: Path | None = None
    support_url: str | None = None
    support_url_file: Path | None = None
    description: str | None = None
    description_file: Path | None = None
    changelog: str | None = None
    changelog_file: Path | None = None
    profile_dir: Path | None = None
    upload_path: str = "/shared/upload"
    login_email_env: str | None = None
    login_password_env: str | None = None


@dataclass(frozen=True)
class DeckConfig:
    source_deck_id: str | None = None
    source_deck_id_env: str | None = None
    source_deck_name: str | None = None
    source_deck_name_env: str | None = None
    anki_connect_url: str = "http://127.0.0.1:8765"
    share_path: str = "/decks/share"
    copyright_confirmed: bool = False


@dataclass(frozen=True)
class ReleaseConfig:
    project_root: Path
    artifact_dir: Path
    target: ReleaseTarget = "addon"
    source_dir: Path | None = None
    manifest: Path | None = None
    artifact_name: str | None = None
    include: tuple[str, ...] = field(default_factory=tuple)
    exclude: tuple[str, ...] = field(default_factory=lambda: DEFAULT_EXCLUDE)
    ankiweb: AnkiWebConfig = field(default_factory=AnkiWebConfig)
    deck: DeckConfig = field(default_factory=DeckConfig)

    @property
    def artifact_path(self) -> Path:
        if self.target != "addon":
            raise ConfigError("deck targets do not build .ankiaddon artifacts")
        if self.manifest is None:
            raise ConfigError("add-on targets require a manifest")
        name = self.artifact_name
        if name is None:
            name = f"{self.manifest.stem}.ankiaddon"
        if not name.endswith(".ankiaddon"):
            raise ConfigError("artifact_name must end with .ankiaddon")
        return self.artifact_dir / name


def load_config(
    project_root: Path,
    config_file: str = "pyproject.toml",
    *,
    local_config_file: str | None = ".anki-addon-release.local.toml",
) -> ReleaseConfig:
    root = project_root.resolve()
    config_path = root / config_file
    if not config_path.exists():
        raise ConfigError(f"config file not found: {config_path}")

    with config_path.open("rb") as file:
        data = tomllib.load(file)

    table = _release_table(data, required=True)
    if not isinstance(table, dict):
        raise ConfigError("missing [tool.anki-addon-release] in pyproject.toml")

    local_path = _optional_local_path(root, local_config_file)
    if local_path is not None and local_path.exists():
        with local_path.open("rb") as file:
            local_data = tomllib.load(file)
        local_table = _release_table(local_data, required=False)
        if not isinstance(local_table, dict):
            raise ConfigError(f"local config must be a TOML table: {local_path}")
        table = _merge_tables(table, local_table)

    target = _target(table)
    source_dir = _path_from_string(root, table, "source_dir", required=target == "addon")
    manifest_default = str(source_dir / "manifest.json") if source_dir is not None else None
    manifest = _path_from_string(root, table, "manifest", default=manifest_default, required=target == "addon")
    artifact_dir = _path_from_string(root, table, "artifact_dir", default="dist", required=False)

    artifact_name = table.get("artifact_name")
    if artifact_name is not None and not isinstance(artifact_name, str):
        raise ConfigError("artifact_name must be a string")

    include = _string_list(table, "include", default=())
    exclude = _string_list(table, "exclude", default=DEFAULT_EXCLUDE)
    ankiweb = _ankiweb_config(root, table.get("ankiweb"))
    deck = _deck_config(table.get("deck"))

    return ReleaseConfig(
        project_root=root,
        target=target,
        source_dir=source_dir,
        manifest=manifest,
        artifact_dir=artifact_dir,
        artifact_name=artifact_name,
        include=include,
        exclude=exclude,
        ankiweb=ankiweb,
        deck=deck,
    )


def _ankiweb_config(root: Path, raw: object) -> AnkiWebConfig:
    if raw is None:
        return AnkiWebConfig(listing_file=_default_listing_file(root))
    if not isinstance(raw, dict):
        raise ConfigError("ankiweb must be a table")

    base_url = _optional_string(raw, "base_url") or "https://ankiweb.net"
    addon_id = _optional_string(raw, "addon_id")
    shared_id = _optional_string(raw, "shared_id")
    listing_file = _optional_path(root, raw, "listing_file")
    if listing_file is None:
        listing_file = _default_listing_file(root)
    title = _optional_string(raw, "title")
    tags = _optional_string(raw, "tags")
    support_url = _optional_string(raw, "support_url")
    description = _optional_string(raw, "description")
    changelog = _optional_string(raw, "changelog")
    upload_path = _optional_string(raw, "upload_path") or "/shared/upload"
    login_email_env = _optional_string(raw, "login_email_env")
    login_password_env = _optional_string(raw, "login_password_env")

    title_file = _optional_path(root, raw, "title_file")
    tags_file = _optional_path(root, raw, "tags_file")
    support_url_file = _optional_path(root, raw, "support_url_file")
    description_file = _optional_path(root, raw, "description_file")
    changelog_file = _optional_path(root, raw, "changelog_file")
    profile_dir = _optional_path(root, raw, "profile_dir")

    return AnkiWebConfig(
        base_url=base_url.rstrip("/"),
        addon_id=addon_id,
        shared_id=shared_id,
        listing_file=listing_file,
        title=title,
        title_file=title_file,
        tags=tags,
        tags_file=tags_file,
        support_url=support_url,
        support_url_file=support_url_file,
        description=description,
        description_file=description_file,
        changelog=changelog,
        changelog_file=changelog_file,
        profile_dir=profile_dir,
        upload_path=_normalize_path(upload_path),
        login_email_env=login_email_env,
        login_password_env=login_password_env,
    )


def _deck_config(raw: object) -> DeckConfig:
    if raw is None:
        return DeckConfig()
    if not isinstance(raw, dict):
        raise ConfigError("deck must be a table")

    anki_connect_url = _optional_string(raw, "anki_connect_url") or "http://127.0.0.1:8765"
    share_path = _optional_string(raw, "share_path") or "/decks/share"
    return DeckConfig(
        source_deck_id=_optional_string(raw, "source_deck_id"),
        source_deck_id_env=_optional_string(raw, "source_deck_id_env"),
        source_deck_name=_optional_string(raw, "source_deck_name"),
        source_deck_name_env=_optional_string(raw, "source_deck_name_env"),
        anki_connect_url=anki_connect_url.rstrip("/"),
        share_path=_normalize_path(share_path),
        copyright_confirmed=_optional_bool(raw, "copyright_confirmed", default=False),
    )


def _path_from_string(
    root: Path,
    table: dict[str, object],
    key: str,
    *,
    required: bool = False,
    default: str | None = None,
) -> Path | None:
    raw = table.get(key, default)
    if raw is None:
        if required:
            raise ConfigError(f"{key} is required")
        return None
    if not isinstance(raw, str):
        raise ConfigError(f"{key} must be a string")
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _optional_path(root: Path, table: dict[str, object], key: str) -> Path | None:
    raw = table.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ConfigError(f"ankiweb.{key} must be a string")
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _default_listing_file(root: Path) -> Path | None:
    default = root / "release" / "ankiweb.md"
    if default.exists():
        return default.resolve()
    return None


def _optional_string(table: dict[str, object], key: str) -> str | None:
    raw = table.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ConfigError(f"ankiweb.{key} must be a string")
    return raw


def _optional_bool(table: dict[str, object], key: str, *, default: bool) -> bool:
    raw = table.get(key, default)
    if not isinstance(raw, bool):
        raise ConfigError(f"deck.{key} must be a boolean")
    return raw


def _target(table: dict[str, object]) -> ReleaseTarget:
    raw = table.get("target", table.get("type", "addon"))
    if raw not in ("addon", "deck"):
        raise ConfigError("target must be 'addon' or 'deck'")
    return raw


def _release_table(data: dict[str, object], *, required: bool) -> object:
    tool = data.get("tool")
    if isinstance(tool, dict):
        table = tool.get("anki-addon-release")
        if table is not None:
            return table
    if required:
        return None
    return data


def _merge_tables(public: dict[str, object], local: dict[str, object]) -> dict[str, object]:
    merged = dict(public)
    for key, value in local.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _merge_tables(existing, value)
        else:
            merged[key] = value
    return merged


def _optional_local_path(root: Path, local_config_file: str | None) -> Path | None:
    if not local_config_file:
        return None
    path = Path(local_config_file)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _normalize_path(path: str) -> str:
    if not path.startswith("/"):
        return f"/{path}"
    return path


def _string_list(
    table: dict[str, object],
    key: str,
    *,
    default: tuple[str, ...],
) -> tuple[str, ...]:
    raw = table.get(key)
    if raw is None:
        return tuple(default)
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ConfigError(f"{key} must be a list of strings")
    return tuple(raw)
