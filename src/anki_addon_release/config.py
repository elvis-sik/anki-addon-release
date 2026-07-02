from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tomllib

from .errors import ConfigError


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
    title: str | None = None
    support_url: str | None = None
    description: str | None = None
    description_file: Path | None = None
    changelog: str | None = None
    changelog_file: Path | None = None
    profile_dir: Path | None = None
    upload_path: str = "/shared/upload"
    login_email_env: str | None = None
    login_password_env: str | None = None


@dataclass(frozen=True)
class ReleaseConfig:
    project_root: Path
    source_dir: Path
    manifest: Path
    artifact_dir: Path
    artifact_name: str | None = None
    include: tuple[str, ...] = field(default_factory=tuple)
    exclude: tuple[str, ...] = field(default_factory=lambda: DEFAULT_EXCLUDE)
    ankiweb: AnkiWebConfig = field(default_factory=AnkiWebConfig)

    @property
    def artifact_path(self) -> Path:
        name = self.artifact_name
        if name is None:
            name = f"{self.manifest.stem}.ankiaddon"
        if not name.endswith(".ankiaddon"):
            raise ConfigError("artifact_name must end with .ankiaddon")
        return self.artifact_dir / name


def load_config(project_root: Path, config_file: str = "pyproject.toml") -> ReleaseConfig:
    root = project_root.resolve()
    config_path = root / config_file
    if not config_path.exists():
        raise ConfigError(f"config file not found: {config_path}")

    with config_path.open("rb") as file:
        data = tomllib.load(file)

    table = data.get("tool", {}).get("anki-addon-release")
    if not isinstance(table, dict):
        raise ConfigError("missing [tool.anki-addon-release] in pyproject.toml")

    source_dir = _path_from_string(root, table, "source_dir", required=True)
    manifest = _path_from_string(root, table, "manifest", default=str(source_dir / "manifest.json"))
    artifact_dir = _path_from_string(root, table, "artifact_dir", default="dist")

    artifact_name = table.get("artifact_name")
    if artifact_name is not None and not isinstance(artifact_name, str):
        raise ConfigError("artifact_name must be a string")

    include = _string_list(table, "include", default=())
    exclude = _string_list(table, "exclude", default=DEFAULT_EXCLUDE)
    ankiweb = _ankiweb_config(root, table.get("ankiweb"))

    return ReleaseConfig(
        project_root=root,
        source_dir=source_dir,
        manifest=manifest,
        artifact_dir=artifact_dir,
        artifact_name=artifact_name,
        include=include,
        exclude=exclude,
        ankiweb=ankiweb,
    )


def _ankiweb_config(root: Path, raw: object) -> AnkiWebConfig:
    if raw is None:
        return AnkiWebConfig()
    if not isinstance(raw, dict):
        raise ConfigError("ankiweb must be a table")

    base_url = _optional_string(raw, "base_url") or "https://ankiweb.net"
    addon_id = _optional_string(raw, "addon_id")
    title = _optional_string(raw, "title")
    support_url = _optional_string(raw, "support_url")
    description = _optional_string(raw, "description")
    changelog = _optional_string(raw, "changelog")
    upload_path = _optional_string(raw, "upload_path") or "/shared/upload"
    login_email_env = _optional_string(raw, "login_email_env")
    login_password_env = _optional_string(raw, "login_password_env")

    description_file = _optional_path(root, raw, "description_file")
    changelog_file = _optional_path(root, raw, "changelog_file")
    profile_dir = _optional_path(root, raw, "profile_dir")

    return AnkiWebConfig(
        base_url=base_url.rstrip("/"),
        addon_id=addon_id,
        title=title,
        support_url=support_url,
        description=description,
        description_file=description_file,
        changelog=changelog,
        changelog_file=changelog_file,
        profile_dir=profile_dir,
        upload_path=_normalize_path(upload_path),
        login_email_env=login_email_env,
        login_password_env=login_password_env,
    )


def _path_from_string(
    root: Path,
    table: dict[str, object],
    key: str,
    *,
    required: bool = False,
    default: str | None = None,
) -> Path:
    raw = table.get(key, default)
    if raw is None:
        if required:
            raise ConfigError(f"{key} is required")
        raise ConfigError(f"{key} is missing")
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


def _optional_string(table: dict[str, object], key: str) -> str | None:
    raw = table.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ConfigError(f"ankiweb.{key} must be a string")
    return raw


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
