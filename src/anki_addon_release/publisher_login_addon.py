from __future__ import annotations

import os

from aqt import gui_hooks, mw
from aqt.qt import QTimer
from aqt.sync import sync_login


LOGIN_FLAG = "ANKI_ADDON_RELEASE_PUBLISHER_LOGIN"
EMAIL_ENV = "ANKI_ADDON_RELEASE_PUBLISHER_EMAIL"
PASSWORD_ENV = "ANKI_ADDON_RELEASE_PUBLISHER_PASSWORD"
CHECK_DATABASE_FLAG = "ANKI_ADDON_RELEASE_PUBLISHER_CHECK_DATABASE"
CLEAN_MEDIA_FLAG = "ANKI_ADDON_RELEASE_PUBLISHER_CLEAN_MEDIA"


def _login_from_environment() -> None:
    if os.environ.pop(LOGIN_FLAG, None) != "1":
        return
    email = os.environ.pop(EMAIL_ENV, "")
    password = os.environ.pop(PASSWORD_ENV, "")
    if not email or not password:
        return
    sync_login(mw, mw.on_sync_button_clicked, email, password)


def _check_database_from_environment() -> None:
    if os.environ.pop(CHECK_DATABASE_FLAG, None) != "1":
        return
    if mw.col is not None:
        mw.col.fix_integrity()


def _clean_media_from_environment() -> None:
    if os.environ.pop(CLEAN_MEDIA_FLAG, None) != "1":
        return
    if mw.col is None:
        return
    result = mw.col.media.check()
    if result.unused:
        mw.col.media.trash_files(list(result.unused))
    mw.col.media.empty_trash()


def _on_profile_open() -> None:
    def run_requested_maintenance() -> None:
        _check_database_from_environment()
        _clean_media_from_environment()
        _login_from_environment()

    QTimer.singleShot(0, run_requested_maintenance)


gui_hooks.profile_did_open.append(_on_profile_open)
