from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess

from .errors import PublishError


@dataclass(frozen=True)
class LoginCredentials:
    email: str
    password: str


def resolve_env_credentials(
    *,
    email_env: str | None,
    password_env: str | None,
) -> LoginCredentials | None:
    if email_env is None and password_env is None:
        return None
    if not email_env or not password_env:
        raise PublishError("email and password environment variable names must be provided together")

    raw_email = os.environ.get(email_env)
    raw_password = os.environ.get(password_env)
    missing = [name for name, value in ((email_env, raw_email), (password_env, raw_password)) if not value]
    if missing:
        raise PublishError(f"missing required credential environment variable(s): {', '.join(missing)}")

    email = _resolve_secret_ref(email_env, raw_email)
    password = _resolve_secret_ref(password_env, raw_password)
    return LoginCredentials(email=email, password=password)


def resolve_present_env_credentials(
    *,
    email_env: str | None,
    password_env: str | None,
) -> LoginCredentials | None:
    if email_env is None and password_env is None:
        return None
    if not email_env or not password_env:
        raise PublishError("email and password environment variable names must be provided together")

    raw_email = os.environ.get(email_env)
    raw_password = os.environ.get(password_env)
    if raw_email is None and raw_password is None:
        return None
    if not raw_email or not raw_password:
        missing = [
            name
            for name, value in ((email_env, raw_email), (password_env, raw_password))
            if not value
        ]
        raise PublishError(f"missing required credential environment variable(s): {', '.join(missing)}")

    email = _resolve_secret_ref(email_env, raw_email)
    password = _resolve_secret_ref(password_env, raw_password)
    return LoginCredentials(email=email, password=password)


def _resolve_secret_ref(env_name: str, value: str | None) -> str:
    if value is None:
        raise PublishError(f"missing required credential environment variable: {env_name}")
    if not value.startswith("op://"):
        return value

    try:
        result = subprocess.run(
            ["op", "read", value],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise PublishError(
            f"{env_name} is a 1Password reference, but the 'op' CLI was not found"
        ) from exc

    if result.returncode != 0:
        message = result.stderr.strip() or "op read failed"
        raise PublishError(f"could not resolve 1Password reference in {env_name}: {message}")

    secret = result.stdout.rstrip("\r\n")
    if not secret:
        raise PublishError(f"1Password reference in {env_name} resolved to an empty value")
    return secret
