# anki-addon-release

`anki-addon-release` is a small release helper for Anki add-ons.

The first milestone is deterministic local release prep:

- read release config from `pyproject.toml`
- validate the add-on source tree and `manifest.json`
- build a clean `.ankiaddon` archive
- inspect archive contents before upload

The preferred AnkiWeb path is a browser handoff: the tool builds a clean
release bundle, then Codex or a human uses the user's regular logged-in browser
to operate AnkiWeb. The Playwright publishing layer remains optional for later
automation.

## Status

Private prototype. The first real target is releasing the Study Triage add-on.

## Install For Local Development

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

No runtime dependencies are required for the initial local package/check workflow.

For browser publishing:

```bash
python -m pip install -e ".[browser]"
python -m playwright install chromium
```

Use `sfw` when installing from public registries in this workspace.

From GitHub, `uv` can run or install the package without a PyPI release once the
repository is public or otherwise accessible to the local Git credentials:

```bash
uvx --from "anki-addon-release @ git+https://github.com/elvis-sik/anki-addon-release.git" \
  anki-addon-release --help
```

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

[tool.anki-addon-release.ankiweb]
# Omit addon_id for a first publish; set it for updates.
addon_id = "1234567890"
title = "Study Triage"
description_file = "README.md"
changelog_file = "CHANGELOG.md"
```

`include` is optional. When omitted, the whole `source_dir` is considered and `exclude` filters out development files.

## Commands

From an add-on repository:

```bash
anki-addon-release check
anki-addon-release package
anki-addon-release inspect dist/study-triage.ankiaddon
```

Prepare an AnkiWeb publish plan without opening a browser:

```bash
anki-addon-release publish --dry-run
```

Build a regular-browser handoff bundle for Codex or a human:

```bash
anki-addon-release handoff
```

The handoff bundle is written to `.anki-addon-release/handoff/` by default and
contains:

- `release-handoff.json`: machine-readable release metadata
- `browser-checklist.md`: human browser checklist
- `codex-browser-prompt.md`: prompt for a Codex browser-operator session
- `description.txt` and `changelog.txt` when configured

This path does not require Playwright. Use it when you want Codex to operate
your regular logged-in Chrome session.

Open an AnkiWeb login page using a persistent project-local browser profile:

```bash
anki-addon-release login
```

Prepare an upload with Playwright without clicking the final submit button:

```bash
anki-addon-release publish --diagnostics-dir out/release-diagnostics
```

Click the final submit button only when the flow is trusted:

```bash
anki-addon-release publish --submit --diagnostics-dir out/release-diagnostics
```

Use `--mode create` for first-publish testing and `--mode update` for updating a configured `addon_id`. `--mode auto` uses update when `ankiweb.addon_id` is present and create otherwise.

Without installation, from this repository:

```bash
PYTHONPATH=src python -m anki_addon_release --project /path/to/addon check
```

## Development

```bash
make check
```

Browser-flow stress tests are opt-in because they need Playwright and a local fake AnkiWeb server:

```bash
ANKI_ADDON_RELEASE_BROWSER_TESTS=1 python -m unittest tests.test_browser_flows -v
```

or:

```bash
make test-browser
```

Those tests exercise separate create and update forms against a local HTTP server and verify that Playwright uploads the `.ankiaddon` artifact plus the expected metadata.

## Roadmap

- Use the handoff bundle to publish Study Triage through regular Chrome.
- Capture the first published add-on id in Study Triage's release config.
- Decide whether the Playwright driver is still worthwhile after the regular-browser path works.
- Add saved HTML/screenshot diagnostics on every browser failure.
- Add public artifact verification by downloading/installing the published add-on into a disposable Anki profile, likely composed with `anki-addon-workbench`.
