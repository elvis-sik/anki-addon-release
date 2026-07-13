from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from .config import load_config
from .browser import AnkiWebBrowser
from .credentials import resolve_env_credentials, resolve_present_env_credentials
from .envfile import load_env_file
from .errors import ReleaseError
from .handoff import write_handoff
from .manifest import load_manifest
from .packager import build_plan, inspect_archive, write_package
from .publish import (
    ankiweb_description_warnings,
    build_deck_publish_plan,
    build_publish_plan,
    default_profile_dir,
    describe_deck_publish_plan,
    describe_publish_plan,
    resolve_addon_ankiweb_text,
    resolve_deck_ankiweb_text,
)
from .publisher import (
    DEFAULT_ANKI_CONNECT_URL,
    DEFAULT_PUBLISHER_ANKI_CONNECT_PORT,
    DEFAULT_PUBLISHER_ANKI_CONNECT_URL,
    PublisherPaths,
    backup_publisher_collection,
    apply_publisher_prune,
    build_publisher_prune_plan,
    deck_id_for_name,
    default_anki_bin,
    default_anki_connect_source,
    default_anki_python,
    default_publisher_base,
    default_publisher_profile,
    export_deck,
    import_deck,
    initialize_publisher,
    launch_publisher,
    publisher_decks,
    publisher_status,
    register_deck_id,
    start_sync,
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
    publish.add_argument(
        "--preview-description",
        action="store_true",
        help="print the exact AnkiWeb Markdown description and exit without opening a browser",
    )
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

    publisher = subparsers.add_parser(
        "publisher",
        help="manage the isolated, AnkiWeb-only publishing collection",
    )
    _add_publisher_args(publisher)
    publisher_subparsers = publisher.add_subparsers(dest="publisher_command", required=True)

    publisher_init = publisher_subparsers.add_parser("init", help="create the isolated publisher profile")
    publisher_init.add_argument("--anki-python", help="Anki's bundled Python interpreter")
    publisher_init.add_argument("--anki-connect-source", type=Path, help="existing AnkiConnect add-on directory")
    publisher_init.add_argument("--anki-connect-port", type=int, default=DEFAULT_PUBLISHER_ANKI_CONNECT_PORT)
    publisher_init.set_defaults(func=_publisher_init)

    publisher_status_command = publisher_subparsers.add_parser("status", help="report publisher-profile readiness")
    publisher_status_command.set_defaults(func=_publisher_status)

    publisher_backup = publisher_subparsers.add_parser("backup", help="write a portable publisher collection backup")
    publisher_backup.add_argument("--out", type=Path, help="destination .zip; defaults under the publisher base")
    publisher_backup.set_defaults(func=_publisher_backup)

    publisher_launch = publisher_subparsers.add_parser("launch", help="launch the isolated publisher Anki profile")
    publisher_launch.add_argument("--anki-bin", help="Anki launcher binary")
    publisher_launch.add_argument("--anki-connect-port", type=int, default=DEFAULT_PUBLISHER_ANKI_CONNECT_PORT)
    publisher_launch.add_argument("--login-email-env", help="environment variable with the AnkiWeb email for one-shot login")
    publisher_launch.add_argument("--login-password-env", help="environment variable with the AnkiWeb password for one-shot login")
    publisher_launch.add_argument("--check-database", action="store_true", help="run Anki's Check Database in the isolated profile after launch")
    publisher_launch.add_argument(
        "--clean-media",
        action="store_true",
        help="run Check Media in the isolated profile, permanently deleting unused Publisher media",
    )
    publisher_launch.set_defaults(func=_publisher_launch)

    publisher_deck_id = publisher_subparsers.add_parser("deck-id", help="print one publisher deck's id")
    publisher_deck_id.add_argument("--anki-connect-url", default=DEFAULT_PUBLISHER_ANKI_CONNECT_URL)
    publisher_deck_id.add_argument("--deck-name", required=True)
    publisher_deck_id.set_defaults(func=_publisher_deck_id)

    publisher_export = publisher_subparsers.add_parser("export", help="export a deck from an open Anki profile")
    publisher_export.add_argument("--anki-connect-url", default=DEFAULT_ANKI_CONNECT_URL)
    publisher_export.add_argument("--deck-name", required=True)
    publisher_export.add_argument("--out", type=Path, required=True)
    publisher_export.add_argument("--include-scheduling", action="store_true")
    publisher_export.set_defaults(func=_publisher_export)

    publisher_import = publisher_subparsers.add_parser("import", help="import an APKG into the open publisher profile")
    publisher_import.add_argument("package", type=Path)
    publisher_import.add_argument("--anki-connect-url", default=DEFAULT_PUBLISHER_ANKI_CONNECT_URL)
    publisher_import.add_argument("--deck-name", help="publisher deck name to verify and register after import")
    publisher_import.add_argument("--register-env-file", type=Path, help="private .env file to update with the publisher deck id")
    publisher_import.add_argument("--register-env-var", help="source-deck env variable to set")
    publisher_import.set_defaults(func=_publisher_import)

    publisher_sync = publisher_subparsers.add_parser("sync", help="ask the open publisher profile to start AnkiWeb sync")
    publisher_sync.add_argument("--anki-connect-url", default=DEFAULT_PUBLISHER_ANKI_CONNECT_URL)
    publisher_sync.set_defaults(func=_publisher_sync)

    publisher_verify = publisher_subparsers.add_parser("verify", help="list decks visible in the open publisher profile")
    publisher_verify.add_argument("--anki-connect-url", default=DEFAULT_PUBLISHER_ANKI_CONNECT_URL)
    publisher_verify.set_defaults(func=_publisher_verify)

    publisher_prune = publisher_subparsers.add_parser(
        "prune",
        help="plan or apply a leaf-first trim of the isolated publisher collection",
    )
    publisher_prune.add_argument("--anki-connect-url", default=DEFAULT_PUBLISHER_ANKI_CONNECT_URL)
    publisher_prune.add_argument("--keep-deck-id", action="append", default=[], help="publisher deck id to retain with all children")
    publisher_prune.add_argument(
        "--keep-deck-id-env",
        action="append",
        default=[],
        help="environment variable containing comma-separated publisher deck ids to retain",
    )
    publisher_prune.add_argument("--apply", action="store_true", help="delete the planned decks after an explicit backup check")
    publisher_prune.add_argument(
        "--backup",
        type=Path,
        help="completed Publisher backup archive made while the Publisher profile was closed; required with --apply",
    )
    publisher_prune.set_defaults(func=_publisher_prune)

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
        text = resolve_deck_ankiweb_text(config)
        _print_warnings(ankiweb_description_warnings(text.support_url, text.description))
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
    text = resolve_addon_ankiweb_text(config, manifest)
    _print_warnings(ankiweb_description_warnings(text.support_url, text.description))
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
        if args.preview_description:
            _print_description_preview(publish_plan.description)
            return 0
        if args.dry_run:
            return 0

        browser = _browser(args, config)
        _login_before_publish(config, browser, publish_plan.login_url)
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

    if args.preview_description:
        _print_description_preview(publish_plan.description)
        return 0

    if args.dry_run:
        return 0

    artifact = write_package(package_plan)
    print(f"built: {artifact}")

    browser = _browser(args, config)
    _login_before_publish(config, browser, publish_plan.login_url)
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


def _publisher_paths(args: argparse.Namespace) -> PublisherPaths:
    return PublisherPaths(base=args.publisher_base.expanduser(), profile=args.publisher_profile)


def _publisher_init(args: argparse.Namespace) -> int:
    paths = _publisher_paths(args)
    anki_bin = default_anki_bin()
    anki_python = args.anki_python or default_anki_python(anki_bin)
    if anki_python is None:
        raise ReleaseError("could not locate Anki's bundled Python; pass publisher init --anki-python")
    initialize_publisher(
        paths,
        anki_python=anki_python,
        anki_connect_source=args.anki_connect_source or default_anki_connect_source(),
        anki_connect_port=args.anki_connect_port,
    )
    print(f"initialized: {paths.base}")
    print(f"profile: {paths.profile}")
    print("sync_target: AnkiWeb (custom sync URL cleared)")
    return 0


def _publisher_status(args: argparse.Namespace) -> int:
    print(json.dumps(publisher_status(_publisher_paths(args)), indent=2, sort_keys=True))
    return 0


def _publisher_backup(args: argparse.Namespace) -> int:
    backup = backup_publisher_collection(_publisher_paths(args), output=args.out)
    print(backup)
    return 0


def _publisher_launch(args: argparse.Namespace) -> int:
    credentials = _publisher_login_credentials(args)
    process, command = launch_publisher(
        _publisher_paths(args),
        anki_bin=args.anki_bin or default_anki_bin(),
        login_credentials=credentials,
        login_credential_env_names=(args.login_email_env, args.login_password_env) if credentials is not None else None,
        check_database=args.check_database,
        clean_media=args.clean_media,
        anki_connect_port=args.anki_connect_port,
    )
    print(f"pid: {process.pid}")
    print(f"command: {' '.join(command)}")
    if credentials is not None:
        print("AnkiWeb login started from the process environment; choose Download if Anki asks for initial sync direction")
    if args.check_database:
        print("Anki Check Database started in the isolated publisher profile")
    if args.clean_media:
        print("Anki Check Media cleanup started in the isolated publisher profile")
    return 0


def _publisher_deck_id(args: argparse.Namespace) -> int:
    print(deck_id_for_name(args.anki_connect_url, args.deck_name))
    return 0


def _publisher_export(args: argparse.Namespace) -> int:
    output = export_deck(
        args.anki_connect_url,
        deck_name=args.deck_name,
        output=args.out,
        include_scheduling=args.include_scheduling,
    )
    print(output)
    return 0


def _publisher_import(args: argparse.Namespace) -> int:
    if bool(args.register_env_file) != bool(args.register_env_var):
        raise ReleaseError("publisher import registration requires both --register-env-file and --register-env-var")
    if args.register_env_file and not args.deck_name:
        raise ReleaseError("publisher import registration also requires --deck-name")

    import_deck(args.anki_connect_url, args.package)
    print(f"imported: {args.package.resolve()}")
    if args.deck_name:
        deck_id = deck_id_for_name(args.anki_connect_url, args.deck_name)
        print(f"deck_id: {deck_id}")
        if args.register_env_file and args.register_env_var:
            register_deck_id(args.register_env_file, variable=args.register_env_var, deck_id=deck_id)
            print(f"registered: {args.register_env_var} in {args.register_env_file}")
    return 0


def _publisher_sync(args: argparse.Namespace) -> int:
    start_sync(args.anki_connect_url)
    print("sync_started: wait for Anki to report completion before publishing")
    return 0


def _publisher_verify(args: argparse.Namespace) -> int:
    print(json.dumps(publisher_decks(args.anki_connect_url), indent=2, sort_keys=True))
    return 0


def _publisher_prune(args: argparse.Namespace) -> int:
    keep_deck_ids = list(args.keep_deck_id)
    for variable in args.keep_deck_id_env:
        value = os.environ.get(variable)
        if value is None:
            raise ReleaseError(f"publisher prune could not find {variable}")
        keep_deck_ids.extend(item.strip() for item in value.split(","))

    plan = build_publisher_prune_plan(publisher_decks(args.anki_connect_url), keep_deck_ids=keep_deck_ids)
    print(
        json.dumps(
            {
                "keep_roots": plan.keep_roots,
                "retained_decks": plan.retained_decks,
                "delete_stages": plan.delete_stages,
                "delete_count": len(plan.delete_decks),
                "missing_keep_deck_ids": plan.missing_keep_deck_ids,
            },
            indent=2,
        )
    )
    if not args.apply:
        return 0

    if args.backup is None:
        raise ReleaseError("publisher prune --apply requires --backup from a completed publisher backup")
    backup = args.backup.expanduser().resolve()
    if not backup.is_file():
        raise ReleaseError(f"publisher prune backup archive not found: {backup}")
    deleted = apply_publisher_prune(args.anki_connect_url, plan)
    print(f"backup: {backup}")
    print(f"deleted_decks: {deleted}")
    return 0


def _publisher_login_credentials(args: argparse.Namespace) -> tuple[str, str] | None:
    if bool(args.login_email_env) != bool(args.login_password_env):
        raise ReleaseError("publisher launch login requires both --login-email-env and --login-password-env")
    if not args.login_email_env:
        return None
    email = os.environ.get(args.login_email_env)
    password = os.environ.get(args.login_password_env)
    if not email or not password:
        raise ReleaseError("publisher launch could not find both requested login environment variables")
    return email, password


def _login_before_publish(config, browser: AnkiWebBrowser, login_url: str) -> None:
    credentials = resolve_present_env_credentials(
        email_env=config.ankiweb.login_email_env,
        password_env=config.ankiweb.login_password_env,
    )
    if credentials is None:
        return

    result = browser.login(login_url, credentials=credentials, submit=True)
    print(f"login_status: {result.status}")
    print(f"login_final_url: {result.final_url}")


def _print_description_preview(description: str | None) -> None:
    if description is None:
        print("description_markdown: (none)")
        return
    print("description_markdown:")
    print("--- BEGIN DESCRIPTION ---")
    print(description, end="" if description.endswith("\n") else "\n")
    print("--- END DESCRIPTION ---")


def _print_warnings(warnings: list[str]) -> None:
    for warning in warnings:
        print(f"warning: {warning}")


def _add_browser_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile-dir", type=Path, help="persistent browser profile directory")
    parser.add_argument("--headless", action="store_true", help="run browser without a visible window")
    parser.add_argument("--timeout-ms", type=int, default=15_000, help="browser action timeout")
    parser.add_argument("--slow-mo-ms", type=int, default=0, help="slow browser actions for observation")
    parser.add_argument("--diagnostics-dir", type=Path, help="write screenshots to this directory")


def _add_publisher_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--publisher-base",
        type=Path,
        default=default_publisher_base(),
        help="persistent Anki base directory for the isolated publishing collection",
    )
    parser.add_argument(
        "--publisher-profile",
        default=default_publisher_profile(),
        help="profile name inside the isolated publishing base",
    )


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
