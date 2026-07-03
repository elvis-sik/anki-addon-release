# anki-addon-release

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab)](https://pypi.org/project/anki-addon-release/)
[![Source on GitHub](https://img.shields.io/badge/source-GitHub-24292f)](https://github.com/elvis-sik/anki-addon-release)

`anki-addon-release` is a small release helper for Anki add-ons.

It provides deterministic local release prep:

- read release config from `pyproject.toml`
- validate the add-on source tree and `manifest.json`
- build a clean `.ankiaddon` archive
- inspect archive contents before upload

For AnkiWeb, it can either write a regular-browser handoff bundle or drive the
upload form with Playwright. Browser publishing is review-first by default: the
final AnkiWeb save/submit button is clicked only when `--submit` is passed.

## Status

Early public release. It has been dogfooded against the
[Study Triage](https://ankiweb.net/shared/info/1850611434) add-on release flow,
including AnkiWeb login, create/update form filling, support URL filling,
branch compatibility fields, and local browser-flow regression tests.
It is published on PyPI via Trusted Publishing.

## Install

```bash
uvx anki-addon-release --help
```

For browser publishing support, include the browser extra and install the
Playwright browser runtime:

```bash
uvx --from "anki-addon-release[browser]" playwright install chromium
uvx --from "anki-addon-release[browser]" anki-addon-release --help
```

For unreleased changes on `main`, run directly from GitHub:

```bash
uvx --from "anki-addon-release @ git+https://github.com/elvis-sik/anki-addon-release.git" \
  anki-addon-release --help
```

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

### Credentials

The framework never calls 1Password, reads password-manager references, or stores
AnkiWeb credentials in config. If you want automated login, resolve secrets
outside the process and expose plain environment variables only for the command
that needs them:

```bash
export ANKIWEB_EMAIL="$(op read op://Private/AnkiWeb/email)"
export ANKIWEB_PASSWORD="$(op read op://Private/AnkiWeb/password)"
```

Then reference the variable names in project config:

```toml
[tool.anki-addon-release.ankiweb]
login_email_env = "ANKIWEB_EMAIL"
login_password_env = "ANKIWEB_PASSWORD"
```

or pass them on the command line:

```bash
anki-addon-release login \
  --email-env ANKIWEB_EMAIL \
  --password-env ANKIWEB_PASSWORD \
  --submit-login
```

Without `--submit-login`, the login command fills the fields and leaves the form
for review. In `--headless` mode, `--submit-login` is required.

### Separate Publishing Account

For real publishing, prefer a dedicated AnkiWeb account used only for add-ons.
This is an isolation pattern, not a framework requirement: it keeps release
automation separate from your personal synced collection and makes it easier to
reason about which account a browser profile is logged into.

Two AnkiWeb account lifecycle rules matter for that pattern:

- New-account publishing guard: AnkiWeb may send very new accounts to its
  [Account Too New](https://ankiweb.net/shared/too-new) page when they try to
  share add-ons. That public page says new accounts must meet certain criteria
  and can continue once the account is older, but it does not publish an exact
  wait period. Create the publishing account before you need it, or use an
  older dedicated account.
- Inactivity expiry: AnkiWeb's
  [terms](https://ankiweb.net/account/terms) and
  [account-removal article](https://anki.tenderapp.com/kb/anki-ecosystem/ankiweb-account-removal)
  say account data may be deleted if the account is not accessed or synced in
  the last 6 months. Log in to the dedicated account at least every few months
  to keep it active. The account-removal article notes that shared add-ons are
  not subject to the usual data expiry, but keeping the publishing account
  active avoids losing account access or release ownership context.

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
support_url = "https://github.com/example/study-triage"
description_file = "README.md"
changelog_file = "CHANGELOG.md"
login_email_env = "ANKIWEB_EMAIL"
login_password_env = "ANKIWEB_PASSWORD"
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

The final AnkiWeb save/submit button is not clicked unless `--submit` is passed.
That review-first behavior is the default. In headed browser mode, the prepared
form stays open until you press Enter in the terminal.

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

## Releasing

Releases publish to PyPI via GitHub Actions using **Trusted Publishing** (OIDC);
no API token is stored. To cut a release:

```bash
# 1. bump `version` in pyproject.toml, commit
# 2. tag and push -- the tag must match the version
git tag v0.1.1
git push origin v0.1.1
```

The [`release.yml`](.github/workflows/release.yml) workflow checks that the tag
matches `pyproject.toml`, builds the sdist + wheel with `uv build`, and publishes.

One-time setup on PyPI (Account -> Publishing -> Add a pending publisher):

- **PyPI Project Name:** `anki-addon-release`
- **Owner / Repository:** `elvis-sik/anki-addon-release`
- **Workflow name:** `release.yml`
- **Environment name:** `pypi`

## Roadmap

- Add saved HTML/screenshot diagnostics on every browser failure.
- Add public artifact verification by downloading/installing the published add-on into a disposable Anki profile, likely composed with `anki-addon-workbench`.
- Expand real-world compatibility coverage across more AnkiWeb form variants.
