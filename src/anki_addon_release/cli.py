from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .config import load_config
from .browser import AnkiWebBrowser
from .errors import ReleaseError
from .manifest import load_manifest
from .packager import build_plan, inspect_archive, write_package
from .publish import build_publish_plan, default_profile_dir, describe_publish_plan


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
    _add_browser_args(publish)
    publish.set_defaults(func=_publish)

    return parser


def _check(args: argparse.Namespace) -> int:
    config = load_config(args.project, args.config)
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
    config = load_config(args.project, args.config)
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
    config = load_config(args.project, args.config)
    manifest = load_manifest(config.manifest)
    plan = build_publish_plan(config, manifest, base_url=args.base_url or None)
    browser = _browser(args, config)
    result = browser.login(plan.login_url)
    print(f"status: {result.status}")
    print(f"final_url: {result.final_url}")
    if result.screenshot:
        print(f"screenshot: {result.screenshot}")
    return 0


def _publish(args: argparse.Namespace) -> int:
    config = load_config(args.project, args.config)
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
