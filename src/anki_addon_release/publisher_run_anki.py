from __future__ import annotations

import os
import sys
import traceback
from typing import NoReturn

import aqt


def _status_from_system_exit(exc: SystemExit) -> int:
    if exc.code is None:
        return 0
    if isinstance(exc.code, int):
        return exc.code
    print(exc.code, file=sys.stderr)
    return 1


def _exit_after_anki_shutdown(status: int) -> NoReturn:
    if sys.platform == "darwin":
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        finally:
            os._exit(status)
    raise SystemExit(status)


def main() -> NoReturn:
    key = os.environ.get("ANKI_SINGLE_INSTANCE_KEY")
    if key:
        aqt.AnkiApp.KEY = key
    try:
        status = int(aqt.run() or 0)
    except SystemExit as exc:
        status = _status_from_system_exit(exc)
    except BaseException:
        traceback.print_exc()
        status = 1
    _exit_after_anki_shutdown(status)


main()
