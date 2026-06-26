from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from .errors import ManifestError


PACKAGE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
LEGACY_VERSION_KEYS = ("min_anki_version", "max_anki_version")


@dataclass(frozen=True)
class ManifestReport:
    path: Path
    data: dict[str, Any]
    warnings: tuple[str, ...]


def load_manifest(path: Path) -> ManifestReport:
    if not path.exists():
        raise ManifestError(f"manifest not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ManifestError("manifest must be a JSON object")

    warnings = validate_manifest_data(data)
    return ManifestReport(path=path, data=data, warnings=tuple(warnings))


def validate_manifest_data(data: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    package = data.get("package")
    name = data.get("name")

    if not isinstance(package, str) or not package:
        raise ManifestError("manifest must include a non-empty string package")
    if not PACKAGE_RE.fullmatch(package):
        raise ManifestError(
            "manifest package should start with a lowercase letter and contain only "
            "lowercase letters, digits, and underscores"
        )

    if not isinstance(name, str) or not name.strip():
        raise ManifestError("manifest must include a non-empty string name")

    mod = data.get("mod")
    if mod is not None and not isinstance(mod, int):
        raise ManifestError("manifest mod must be an integer Unix timestamp when present")

    human_version = data.get("human_version")
    if human_version is not None and not isinstance(human_version, str):
        raise ManifestError("manifest human_version must be a string when present")
    if "version" in data and "human_version" not in data:
        warnings.append("manifest uses version; Anki public metadata should use human_version")

    for key in ("min_point_version", "max_point_version"):
        value = data.get(key)
        if value is not None and not isinstance(value, int):
            raise ManifestError(f"manifest {key} must be an integer when present")

    for key in LEGACY_VERSION_KEYS:
        if key in data:
            warnings.append(f"manifest uses legacy {key}; prefer integer point-version keys")

    return warnings

