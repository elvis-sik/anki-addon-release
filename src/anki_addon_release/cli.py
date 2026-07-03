from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .config import load_config
from .browser import AnkiWebBrowser
from .credentials import resolve_env_credentials
from .envfile import load_env_file
from .errors import ReleaseError
from .handoff import write_handoff
from .manifest import load_manifest
from .packager import build_plan, inspect_archive, write_package
from .publish import (
    build_deck_publish_plan,
    build_publish_plan,
    default_profile_dir,
    describe_deck_publish_plan,
    describe_publish_plan,
)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    try:
        return args.func(args)
    except ReleaseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="anki-addon-release")
    parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="add-on project root containing pyproject.toml",
    )
    parser.add_argument(
        "--config",
        default="pyproject.toml",
        help="config file relative to project root",
    )
    parser.add_argument(
        "--local-config",
        default=".anki-addon-release.local.toml",
        help="private local TOML overlay relative to project root; ignored when absent",
    )
    parser.add_argument(
        "--no-local-config",
        action="store_true",
        help="do not load the private local config overlay",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="dotenv-style env file relative to project root; ignored when absent",
    )
    parser.add_argument(
        "--no-env-file",
        action="store_true",
        help="do not load an env file before resolving env-var config",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="validate config, manifest, and package plan")
    check.set_defaults(func=_check)

    package = subparsers.add_parser("package", help="build a .ankiaddon archive")
    package.add_argument("--dry-run", action="store_true", help="show planned files without writing")
    package.set_defaults(func=_package)

    inspect = subparsers.add_parser("inspect", help="list files inside a .ankiaddon archive")
    inspect.add_argument("archive", type=Path)
    inspect.set_defaults(func=_inspect)

    login = subparsers.add_parser("login", help="open AnkiWeb login in a persistent browser profile")
    login.add_argument("--base-url", help="override AnkiWeb base URL")
    login.add_argument("--email-env", help="environment variable containing the AnkiWeb email")
    login.add_argument("--password-env", help="environment variable containing the AnkiWeb password")
    login.add_argument("--submit-login", action="store_true", help="submit the login form after filling it")
    _add_browser_args(login)
    login.set_defaults(func=_login)

    publish = subparsers.add_parser("publish", help="prepare or submit an AnkiWeb add-on upload")
    publish.add_argument(
        "--mode",
        choices=("auto", "create", "update"),
        default="auto",
        help="publish flow to run; auto uses update when ankiweb.addon_id is configured",
    )
    publish.add_argument("--base-url", help="override AnkiWeb base URL, useful for fake-server tests")
    publish.add_argument("--dry-run", action="store_true", help="print the publish plan only")
    publish.add_argument("--submit", action="store_true", help="click the final submit button")
    publish.add_argument(
        "--confirm-copyright",
        action="store_true",
        help="confirm deck-sharing copyright declaration when publishing deck targets",
    )
    _add_browser_args(publish)
    publish.set_defaults(func=_publish)

    handoff = subparsers.add_parser(
        "handoff",
        help="build a release bundle for Codex or a human using a regular browser",
    )
    handoff.add_argument(
        "--mode",
        choices=("auto", "create", "update"),
        default="auto",
        help="handoff flow to describe; auto uses update when ankiweb.addon_id is configured",
    )
    handoff.add_argument("--base-url", help="override AnkiWeb base URL")
    handoff.add_argument("--out-dir", type=Path, help="handoff output directory")
    handoff.set_defaults(func=_handoff)

    return parser


def _check(args: argparse.Namespace) -> int:
    config = _load_runtime_config(args)

    if config.target == "deck":
        listing_fallback = "listing_file" if config.ankiweb.listing_file else None
        print(f"project: {config.project_root}")
        print("target: deck")
        print(f"listing_file: {config.ankiweb.listing_file or '(missing)'}")
        print(f"title: {_configured_text(config.ankiweb.title, config.ankiweb.title_file, fallback=listing_fallback)}")
        print(f"tags: {_configured_text(config.ankiweb.tags, config.ankiweb.tags_file, fallback=listing_fallback)}")
        print(
            f"support_url: {_configured_text(config.ankiweb.support_url, config.ankiweb.support_url_file, fallback=listing_fallback)}"
        )
        print(f"description: {_configured_text(config.ankiweb.description, config.ankiweb.description_file, fallback=listing_fallback)}")
        print(f"source_deck: {'configured' if _deck_source_configured(config) else 'not configured'}")
        return 0

    if config.manifest is None:
        raise ReleaseError("add-on target requires a manifest")
    manifest = load_manifest(config.manifest)
    plan = build_plan(config)

    print(f"project: {config.project_root}")
    print(f"source: {config.source_dir}")
    print(f"manifest: {manifest.path}")
    print(f"artifact: {plan.artifact_path}")
    print(f"files: {len(plan.files)}")
    for warning in manifest.warnings:
        print(f"warning: {warning}")
    return 0


def _package(args: argparse.Namespace) -> int:
    config = _load_runtime_config(args)
    if config.target != "addon":
        raise ReleaseError("package is only available for add-on targets; deck targets publish from AnkiWeb")
    if config.manifest is None:
        raise ReleaseError("add-on target requires a manifest")
    manifest = load_manifest(config.manifest)
    plan = build_plan(config)

    if args.dry_run:
        print(f"artifact: {plan.artifact_path}")
        for path in plan.files:
            print(path.relative_to(plan.source_dir).as_posix())
        for warning in manifest.warnings:
            print(f"warning: {warning}")
        return 0

    artifact = write_package(plan)
    print(artifact)
    for warning in manifest.warnings:
        print(f"warning: {warning}")
    return 0


def _inspect(args: argparse.Namespace) -> int:
    for entry in inspect_archive(args.archive):
        print(f"{entry.file_size:>8} {entry.filename}")
    return 0


def _login(args: argparse.Namespace) -> int:
    config = _load_runtime_config(args)
    base_url = (args.base_url or config.ankiweb.base_url).rstrip("/")
    credentials = resolve_env_credentials(
        email_env=args.email_env or config.ankiweb.login_email_env,
        password_env=args.password_env or config.ankiweb.login_password_env,
    )
    browser = _browser(args, config)
    result = browser.login(f"{base_url}/account/login", credentials=credentials, submit=args.submit_login)
    print(f"status: {result.status}")
    print(f"final_url: {result.final_url}")
    if result.screenshot:
        print(f"screenshot: {result.screenshot}")
    return 0


def _publish(args: argparse.Namespace) -> int:
    config = _load_runtime_config(args)
    if config.target == "deck":
        publish_plan = build_deck_publish_plan(
            config,
            base_url=args.base_url or None,
            submit=args.submit,
            confirm_copyright=args.confirm_copyright,
        )
        for line in describe_deck_publish_plan(publish_plan):
            print(line)
        if args.dry_run:
            return 0

        browser = _browser(args, config)
        result = browser.publish_deck(publish_plan)
        print(f"status: {result.status}")
        print(f"final_url: {result.final_url}")
        if result.screenshot:
            print(f"screenshot: {result.screenshot}")
        if not args.submit:
            print("final share was not clicked; rerun with --submit when ready")
        return 0

    if config.manifest is None:
        raise ReleaseError("add-on target requires a manifest")
    manifest = load_manifest(config.manifest)
    package_plan = build_plan(config)
    publish_plan = build_publish_plan(
        config,
        manifest,
        mode=args.mode,
        artifact_path=package_plan.artifact_path,
        base_url=args.base_url or None,
        submit=args.submit,
    )

    for line in describe_publish_plan(publish_plan):
        print(line)

    if args.dry_run:
        return 0

    artifact = write_package(package_plan)
    print(f"built: {artifact}")

    browser = _browser(args, config)
    result = browser.publish(publish_plan)
    print(f"status: {result.status}")
    print(f"final_url: {result.final_url}")
    if result.screenshot:
        print(f"screenshot: {result.screenshot}")
    if not args.submit:
        print("final submit was not clicked; rerun with --submit when ready")
    return 0


def _handoff(args: argparse.Namespace) -> int:
    config = _load_runtime_config(args)
    if config.target != "addon":
        raise ReleaseError("handoff is currently only available for add-on targets")
    if config.manifest is None:
        raise ReleaseError("add-on target requires a manifest")
    manifest = load_manifest(config.manifest)
    package_plan = build_plan(config)
    artifact = write_package(package_plan)
    archive_entries = inspect_archive(artifact)
    publish_plan = build_publish_plan(
        config,
        manifest,
        mode=args.mode,
        artifact_path=artifact,
        base_url=args.base_url or None,
        submit=False,
    )
    out_dir = args.out_dir or (config.project_root / ".anki-addon-release" / "handoff")
    result = write_handoff(
        config=config,
        manifest=manifest,
        publish_plan=publish_plan,
        archive_entries=archive_entries,
        out_dir=out_dir,
    )

    print(f"artifact: {artifact}")
    print(f"handoff_dir: {result.out_dir}")
    for path in result.files:
        print(f"wrote: {path}")
    return 0


def _add_browser_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile-dir", type=Path, help="persistent browser profile directory")
    parser.add_argument("--headless", action="store_true", help="run browser without a visible window")
    parser.add_argument("--timeout-ms", type=int, default=15_000, help="browser action timeout")
    parser.add_argument("--slow-mo-ms", type=int, default=0, help="slow browser actions for observation")
    parser.add_argument("--diagnostics-dir", type=Path, help="write screenshots to this directory")


def _browser(args: argparse.Namespace, config: object) -> AnkiWebBrowser:
    profile_dir = args.profile_dir or default_profile_dir(config)
    return AnkiWebBrowser(
        profile_dir=profile_dir,
        headless=args.headless,
        timeout_ms=args.timeout_ms,
        slow_mo_ms=args.slow_mo_ms,
        diagnostics_dir=args.diagnostics_dir,
    )


def _load_runtime_config(args: argparse.Namespace):
    if not args.no_env_file:
        load_env_file(_project_path(args.project, args.env_file))
    local_config = None if args.no_local_config else args.local_config
    return load_config(args.project, args.config, local_config_file=local_config)


def _project_path(project: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (project / path).resolve()


def _configured_text(direct: str | None, file_path: Path | None, *, fallback: str | None = None) -> str:
    if direct is not None:
        return f"{len(direct)} chars"
    if file_path is not None:
        return str(file_path)
    if fallback is not None:
        return fallback
    return "(missing)"


def _deck_source_configured(config: object) -> bool:
    deck = config.deck
    return any(
        value
        for value in (
            deck.source_deck_id,
            deck.source_deck_id_env,
            deck.source_deck_name,
            deck.source_deck_name_env,
        )
    )
