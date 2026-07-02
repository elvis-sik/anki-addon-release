from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .config import ReleaseConfig
from .manifest import ManifestReport
from .packager import ArchiveEntry
from .publish import PublishPlan


@dataclass(frozen=True)
class HandoffResult:
    out_dir: Path
    files: tuple[Path, ...]


def write_handoff(
    *,
    config: ReleaseConfig,
    manifest: ManifestReport,
    publish_plan: PublishPlan,
    archive_entries: tuple[ArchiveEntry, ...],
    out_dir: Path,
) -> HandoffResult:
    out_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = out_dir / "release-handoff.json"
    checklist_path = out_dir / "browser-checklist.md"
    prompt_path = out_dir / "codex-browser-prompt.md"
    description_path = out_dir / "description.txt"
    changelog_path = out_dir / "changelog.txt"

    files = [metadata_path, checklist_path, prompt_path]
    description_file = None
    changelog_file = None

    if publish_plan.description is not None:
        description_path.write_text(publish_plan.description, encoding="utf-8")
        description_file = description_path.name
        files.append(description_path)

    if publish_plan.changelog is not None:
        changelog_path.write_text(publish_plan.changelog, encoding="utf-8")
        changelog_file = changelog_path.name
        files.append(changelog_path)

    metadata = {
        "project_root": str(config.project_root),
        "mode": publish_plan.mode,
        "base_url": publish_plan.base_url,
        "upload_url": publish_plan.upload_url,
        "login_url": publish_plan.login_url,
        "artifact_path": str(publish_plan.artifact_path),
        "addon_id": publish_plan.addon_id,
        "title": publish_plan.title,
        "support_url": publish_plan.support_url,
        "description_file": description_file,
        "description_chars": len(publish_plan.description or ""),
        "changelog_file": changelog_file,
        "changelog_chars": len(publish_plan.changelog or ""),
        "manifest": manifest.data,
        "archive_entries": [
            {"filename": entry.filename, "file_size": entry.file_size}
            for entry in archive_entries
        ],
        "safety": {
            "final_submit_requires_confirmation": True,
            "record_addon_id_after_create": publish_plan.mode == "create",
        },
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checklist_path.write_text(_checklist(metadata), encoding="utf-8")
    prompt_path.write_text(_codex_prompt(metadata), encoding="utf-8")

    return HandoffResult(out_dir=out_dir, files=tuple(files))


def _checklist(metadata: dict[str, object]) -> str:
    addon_id = metadata.get("addon_id") or "(first publish; no add-on id yet)"
    description_file = metadata.get("description_file") or "(none)"
    changelog_file = metadata.get("changelog_file") or "(none)"
    support_url = metadata.get("support_url") or "(none)"
    archive_entries = metadata["archive_entries"]
    archive_lines = "\n".join(
        f"- `{entry['filename']}` ({entry['file_size']} bytes)" for entry in archive_entries
    )

    return f"""# Anki Add-on Browser Handoff

## Release

- Mode: `{metadata['mode']}`
- Upload URL: {metadata['upload_url']}
- Login URL: {metadata['login_url']}
- Artifact: `{metadata['artifact_path']}`
- Title: {metadata['title']}
- Add-on ID: {addon_id}
- Support URL: {support_url}
- Description file: `{description_file}`
- Changelog file: `{changelog_file}`

## Archive Contents

{archive_lines}

## Browser Checklist

1. Open the upload URL in the user's regular logged-in browser.
2. Confirm the page is AnkiWeb and the account is correct.
3. Upload the artifact listed above.
4. Fill the title, support URL, and any add-on metadata fields AnkiWeb requires.
5. Paste the description from `description.txt` when present.
6. Paste the changelog from `changelog.txt` when present and supported by the page.
7. Stop before the final publish/save/submit action and ask the user to confirm.
8. After a successful first publish, record the numeric AnkiWeb add-on id in `pyproject.toml`.
"""


def _codex_prompt(metadata: dict[str, object]) -> str:
    mode = metadata["mode"]
    create_note = ""
    if mode == "create":
        create_note = (
            "\nAfter a successful first publish, capture the numeric AnkiWeb add-on id "
            "and update `[tool.anki-addon-release.ankiweb] addon_id` in the add-on project.\n"
        )

    return f"""# Codex Browser Operator Prompt

Use the user's regular logged-in browser to prepare an AnkiWeb add-on release.

Release metadata is in `release-handoff.json`.

Important paths:

- Artifact to upload: `{metadata['artifact_path']}`
- Description text: `{metadata.get('description_file') or '(none)'}`
- Changelog text: `{metadata.get('changelog_file') or '(none)'}`

Open this AnkiWeb URL:

{metadata['upload_url']}

Fill the AnkiWeb form for `{metadata['title']}` in `{mode}` mode.

Do not click the final publish, save, upload, or submit button until the user explicitly confirms.
{create_note}
If the form shape differs from expectations, stop, summarize what changed, and save screenshots or notes before proceeding.
"""
