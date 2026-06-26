from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .config import load_config
from .errors import ReleaseError
from .manifest import load_manifest
from .packager import build_plan, inspect_archive, write_package


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

