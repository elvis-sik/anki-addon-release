# anki-addon-release

`anki-addon-release` is a small release helper for Anki add-ons.

The first milestone is deterministic local release prep:

- read release config from `pyproject.toml`
- validate the add-on source tree and `manifest.json`
- build a clean `.ankiaddon` archive
- inspect archive contents before upload

The next milestone is browser-driven AnkiWeb publishing. That layer should remain optional and should use a logged-in browser session rather than storing AnkiWeb credentials.

## Status

Private prototype. The first real target is releasing the Study Triage add-on.

## Install For Local Development

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

No runtime dependencies are required for the initial local package/check workflow.

## Configure An Add-on

Add a section like this to the add-on repository's `pyproject.toml`:

```toml
[tool.anki-addon-release]
source_dir = "."
manifest = "manifest.json"
artifact_dir = "dist"
artifact_name = "study-triage.ankiaddon"
include = ["__init__.py", "manifest.json", "README.md"]
exclude = [
  ".git",
  "__pycache__",
  ".mypy_cache",
  ".pytest_cache",
  ".ruff_cache",
  ".uv-cache",
  "dist",
  "tests",
  "user_files",
]
```

`include` is optional. When omitted, the whole `source_dir` is considered and `exclude` filters out development files.

## Commands

From an add-on repository:

```bash
anki-addon-release check
anki-addon-release package
anki-addon-release inspect dist/study-triage.ankiaddon
```

Without installation, from this repository:

```bash
PYTHONPATH=src python -m anki_addon_release --project /path/to/addon check
```

## Development

```bash
make check
```

## Roadmap

- Add a `publish --dry-run` command that prepares an AnkiWeb release plan without touching the browser.
- Add a Playwright-backed browser driver for updating an existing AnkiWeb add-on page.
- Add a supervised first-publish flow for brand-new add-ons.
- Add public artifact verification by downloading/installing the published add-on into a disposable Anki profile, likely composed with `anki-addon-workbench`.

