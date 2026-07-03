from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Literal
from urllib.error import URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode

from .config import DeckConfig, ReleaseConfig
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
    support_url: str | None
    description: str | None
    changelog: str | None
    submit: bool
    branch_min_version: str | None = None
    branch_max_version: str | None = None


@dataclass(frozen=True)
class DeckPublishPlan:
    base_url: str
    share_url: str
    login_url: str
    source_deck_id: str
    shared_id: str | None
    title: str
    tags: str | None
    support_url: str | None
    description: str
    submit: bool
    copyright_confirmed: bool


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

    upload_url = _upload_url(
        base=base,
        upload_path=config.ankiweb.upload_path,
        mode=selected_mode,
        addon_id=config.ankiweb.addon_id,
    )

    return PublishPlan(
        mode=selected_mode,
        base_url=base,
        upload_url=upload_url,
        login_url=f"{base}/account/login",
        artifact_path=(artifact_path or config.artifact_path).resolve(),
        addon_id=config.ankiweb.addon_id,
        title=title,
        support_url=config.ankiweb.support_url,
        description=description,
        changelog=changelog,
        submit=submit,
        branch_min_version=_manifest_point_version(manifest, "min_point_version"),
        branch_max_version=_manifest_point_version(manifest, "max_point_version"),
    )


def build_deck_publish_plan(
    config: ReleaseConfig,
    *,
    base_url: str | None = None,
    submit: bool = False,
    confirm_copyright: bool = False,
) -> DeckPublishPlan:
    if config.target != "deck":
        raise PublishError("deck publishing requires target = 'deck'")

    base = (base_url or config.ankiweb.base_url).rstrip("/")
    source_deck_id = resolve_source_deck_id(config.deck)
    title = config.ankiweb.title
    if not title:
        raise PublishError("deck publishing requires ankiweb.title")
    description = _text_value(
        direct=config.ankiweb.description,
        file_path=config.ankiweb.description_file,
        field_name="description",
    )
    if not description or not description.strip():
        raise PublishError("deck publishing requires ankiweb.description or ankiweb.description_file")

    copyright_confirmed = config.deck.copyright_confirmed or confirm_copyright
    if submit and not copyright_confirmed:
        raise PublishError("deck publishing with --submit requires deck.copyright_confirmed = true or --confirm-copyright")

    share_url = f"{base}{config.deck.share_path}/{source_deck_id}"
    return DeckPublishPlan(
        base_url=base,
        share_url=share_url,
        login_url=f"{base}/account/login",
        source_deck_id=source_deck_id,
        shared_id=config.ankiweb.shared_id,
        title=title,
        tags=config.ankiweb.tags,
        support_url=config.ankiweb.support_url,
        description=description,
        submit=submit,
        copyright_confirmed=copyright_confirmed,
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
    if plan.support_url:
        lines.append(f"support_url: {plan.support_url}")
    if plan.description is not None:
        lines.append(f"description: {len(plan.description)} chars")
    if plan.changelog is not None:
        lines.append(f"changelog: {len(plan.changelog)} chars")
    if plan.branch_min_version is not None:
        lines.append(f"branch_min_version: {plan.branch_min_version}")
    if plan.branch_max_version is not None:
        lines.append(f"branch_max_version: {plan.branch_max_version}")
    return lines


def describe_deck_publish_plan(plan: DeckPublishPlan) -> list[str]:
    redacted_share_url = plan.share_url.replace(plan.source_deck_id, "<source-deck-id>")
    lines = [
        "target: deck",
        f"base_url: {plan.base_url}",
        f"share_url: {redacted_share_url}",
        f"login_url: {plan.login_url}",
        "source_deck_id: configured",
        f"title: {plan.title}",
        f"submit: {str(plan.submit).lower()}",
        f"copyright_confirmed: {str(plan.copyright_confirmed).lower()}",
        f"description: {len(plan.description)} chars",
    ]
    if plan.shared_id:
        lines.append(f"shared_id: {plan.shared_id}")
    if plan.tags:
        lines.append(f"tags: {plan.tags}")
    if plan.support_url:
        lines.append(f"support_url: {plan.support_url}")
    return lines


def resolve_source_deck_id(deck: DeckConfig) -> str:
    direct = _first_non_blank(
        deck.source_deck_id,
        _env_value(deck.source_deck_id_env),
    )
    if direct is not None:
        return direct

    deck_name = _first_non_blank(
        deck.source_deck_name,
        _env_value(deck.source_deck_name_env),
    )
    if deck_name is not None:
        return _resolve_deck_name_with_anki_connect(deck, deck_name)

    raise PublishError(
        "deck publishing requires a private source deck. Configure one in "
        ".anki-addon-release.local.toml as [deck] source_deck_id/source_deck_name, "
        "or set deck.source_deck_id_env/deck.source_deck_name_env in public config."
    )


def _select_mode(mode: str, addon_id: str | None) -> PublishMode:
    if mode == "auto":
        return "update" if addon_id else "create"
    if mode in ("create", "update"):
        return mode
    raise PublishError("publish mode must be auto, create, or update")


def _upload_url(*, base: str, upload_path: str, mode: PublishMode, addon_id: str | None) -> str:
    url = f"{base}{upload_path}"
    if mode == "update":
        return f"{url}?{urlencode({'id': addon_id or ''})}"
    return url


def _manifest_string(manifest: ManifestReport, key: str) -> str:
    value = manifest.data.get(key)
    return value if isinstance(value, str) else ""


def _manifest_point_version(manifest: ManifestReport, key: str) -> str | None:
    value = manifest.data.get(key)
    if not isinstance(value, int) or value == 0:
        return None
    return _format_point_version(value)


def _format_point_version(value: int) -> str:
    sign = "-" if value < 0 else ""
    point_version = abs(value)
    if point_version < 100:
        return f"{sign}2.1.{point_version}"

    major = point_version // 10_000
    minor = (point_version // 100) % 100
    patch = point_version % 100
    return f"{sign}{major:02d}.{minor:02d}.{patch}"


def _first_non_blank(*values: str | None) -> str | None:
    for value in values:
        if value is not None and value.strip():
            return value.strip()
    return None


def _env_value(name: str | None) -> str | None:
    if name is None:
        return None
    return os.environ.get(name)


def _resolve_deck_name_with_anki_connect(deck: DeckConfig, deck_name: str) -> str:
    payload = json.dumps({"action": "deckNamesAndIds", "version": 6}).encode("utf-8")
    request = Request(
        deck.anki_connect_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise PublishError(
            "could not resolve deck.source_deck_name through AnkiConnect; "
            "open Anki with AnkiConnect running, or configure source_deck_id instead"
        ) from exc

    if data.get("error"):
        raise PublishError(f"AnkiConnect deckNamesAndIds failed: {data['error']}")
    result = data.get("result")
    if not isinstance(result, dict):
        raise PublishError("AnkiConnect deckNamesAndIds returned an unexpected response")
    value = result.get(deck_name)
    if value is None:
        raise PublishError(f"deck not found through AnkiConnect: {deck_name}")
    return str(value)


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
