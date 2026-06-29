from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .config import ReleaseConfig
from .errors import PublishError
from .manifest import ManifestReport


PublishMode = Literal["create", "update"]


@dataclass(frozen=True)
class PublishPlan:
    mode: PublishMode
    base_url: str
    upload_url: str
    login_url: str
    artifact_path: Path
    addon_id: str | None
    title: str
    description: str | None
    changelog: str | None
    submit: bool


def build_publish_plan(
    config: ReleaseConfig,
    manifest: ManifestReport,
    *,
    mode: str = "auto",
    artifact_path: Path | None = None,
    base_url: str | None = None,
    submit: bool = False,
) -> PublishPlan:
    selected_mode = _select_mode(mode, config.ankiweb.addon_id)
    base = (base_url or config.ankiweb.base_url).rstrip("/")
    title = config.ankiweb.title or _manifest_string(manifest, "name")
    description = _text_value(
        direct=config.ankiweb.description,
        file_path=config.ankiweb.description_file,
        field_name="description",
    )
    changelog = _text_value(
        direct=config.ankiweb.changelog,
        file_path=config.ankiweb.changelog_file,
        field_name="changelog",
    )

    if selected_mode == "update" and not config.ankiweb.addon_id:
        raise PublishError("update mode requires ankiweb.addon_id")
    if selected_mode == "create" and not title:
        raise PublishError("create mode requires a title or manifest name")

    upload_path = config.ankiweb.upload_path
    upload_url = f"{base}{upload_path}"

    return PublishPlan(
        mode=selected_mode,
        base_url=base,
        upload_url=upload_url,
        login_url=f"{base}/account/login",
        artifact_path=(artifact_path or config.artifact_path).resolve(),
        addon_id=config.ankiweb.addon_id,
        title=title,
        description=description,
        changelog=changelog,
        submit=submit,
    )


def default_profile_dir(config: ReleaseConfig) -> Path:
    return config.ankiweb.profile_dir or (config.project_root / ".anki-addon-release" / "browser-profile")


def describe_publish_plan(plan: PublishPlan) -> list[str]:
    lines = [
        f"mode: {plan.mode}",
        f"base_url: {plan.base_url}",
        f"upload_url: {plan.upload_url}",
        f"login_url: {plan.login_url}",
        f"artifact: {plan.artifact_path}",
        f"title: {plan.title}",
        f"submit: {str(plan.submit).lower()}",
    ]
    if plan.addon_id:
        lines.append(f"addon_id: {plan.addon_id}")
    if plan.description is not None:
        lines.append(f"description: {len(plan.description)} chars")
    if plan.changelog is not None:
        lines.append(f"changelog: {len(plan.changelog)} chars")
    return lines


def _select_mode(mode: str, addon_id: str | None) -> PublishMode:
    if mode == "auto":
        return "update" if addon_id else "create"
    if mode in ("create", "update"):
        return mode
    raise PublishError("publish mode must be auto, create, or update")


def _manifest_string(manifest: ManifestReport, key: str) -> str:
    value = manifest.data.get(key)
    return value if isinstance(value, str) else ""


def _text_value(*, direct: str | None, file_path: Path | None, field_name: str) -> str | None:
    if direct is not None and file_path is not None:
        raise PublishError(f"ankiweb.{field_name} and ankiweb.{field_name}_file cannot both be set")
    if direct is not None:
        return direct
    if file_path is None:
        return None
    if not file_path.exists():
        raise PublishError(f"{field_name}_file not found: {file_path}")
    return file_path.read_text(encoding="utf-8")

