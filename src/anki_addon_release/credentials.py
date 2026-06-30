from __future__ import annotations

from dataclasses import dataclass
import os

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

    email = os.environ.get(email_env)
    password = os.environ.get(password_env)
    missing = [name for name, value in ((email_env, email), (password_env, password)) if not value]
    if missing:
        raise PublishError(f"missing required credential environment variable(s): {', '.join(missing)}")

    return LoginCredentials(email=email, password=password)

