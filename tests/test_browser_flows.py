from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import tempfile
from threading import Thread
import unittest

from anki_addon_release.browser import AnkiWebBrowser, playwright_available
from anki_addon_release.credentials import LoginCredentials
from anki_addon_release.errors import PublishError
from anki_addon_release.publish import PublishPlan


RUN_BROWSER_TESTS = os.environ.get("ANKI_ADDON_RELEASE_BROWSER_TESTS") == "1"


@unittest.skipUnless(
    RUN_BROWSER_TESTS and playwright_available(),
    "set ANKI_ADDON_RELEASE_BROWSER_TESTS=1 with playwright installed to run browser flows",
)
class BrowserFlowTests(unittest.TestCase):
    def test_login_flow_fills_and_submits_credentials(self) -> None:
        with FakeAnkiWebServer() as server, tempfile.TemporaryDirectory() as tmp:
            result = AnkiWebBrowser(
                profile_dir=Path(tmp) / "profile",
                headless=True,
                timeout_ms=10_000,
            ).login(
                f"{server.url}/account/login",
                credentials=LoginCredentials(email="user@example.com", password="secret"),
                submit=True,
            )

            self.assertEqual(result.status, "login-submitted")
            self.assertEqual(server.last_post_path, "/account/login")
            self.assertIn(b"user%40example.com", server.last_post_body)
            self.assertIn(b"secret", server.last_post_body)

    def test_login_with_credentials_logs_out_existing_session(self) -> None:
        with FakeAnkiWebServer(login_is_logged_in=True) as server, tempfile.TemporaryDirectory() as tmp:
            result = AnkiWebBrowser(
                profile_dir=Path(tmp) / "profile",
                headless=True,
                timeout_ms=10_000,
            ).login(
                f"{server.url}/account/login",
                credentials=LoginCredentials(email="user@example.com", password="secret"),
                submit=True,
            )

            self.assertEqual(result.status, "login-submitted")
            self.assertEqual(server.logout_get_count, 1)
            self.assertEqual(server.last_post_path, "/account/login")
            self.assertIn(b"user%40example.com", server.last_post_body)

    def test_create_flow_uploads_artifact_and_metadata(self) -> None:
        with FakeAnkiWebServer() as server, tempfile.TemporaryDirectory() as tmp:
            artifact = _artifact(Path(tmp))
            plan = PublishPlan(
                mode="create",
                base_url=server.url,
                upload_url=f"{server.url}/shared/addons/create",
                login_url=f"{server.url}/account/login",
                artifact_path=artifact,
                addon_id=None,
                title="Study Triage",
                support_url="https://github.com/elvis-sik/anki-zero-today-new",
                description="Description text",
                changelog="Initial upload",
                submit=True,
                branch_min_version="2.1.55",
                branch_max_version="25.09.2",
            )

            result = AnkiWebBrowser(
                profile_dir=Path(tmp) / "profile",
                headless=True,
                timeout_ms=10_000,
            ).publish(plan)

            self.assertEqual(result.status, "submitted")
            self.assertEqual(server.last_post_path, "/shared/addons/create")
            self.assertIn(b"Study Triage", server.last_post_body)
            self.assertIn(
                b"https://github.com/elvis-sik/anki-zero-today-new",
                server.last_post_body,
            )
            self.assertIn(b"2.1.55", server.last_post_body)
            self.assertIn(b"25.09.2", server.last_post_body)
            self.assertIn(b"Description text", server.last_post_body)
            self.assertIn(b"Initial upload", server.last_post_body)
            self.assertIn(b"fake addon", server.last_post_body)

    def test_update_flow_uploads_artifact_and_addon_id(self) -> None:
        with FakeAnkiWebServer() as server, tempfile.TemporaryDirectory() as tmp:
            artifact = _artifact(Path(tmp))
            plan = PublishPlan(
                mode="update",
                base_url=server.url,
                upload_url=f"{server.url}/shared/addons/update",
                login_url=f"{server.url}/account/login",
                artifact_path=artifact,
                addon_id="123456789",
                title="Study Triage",
                support_url=None,
                description=None,
                changelog="Bug fixes",
                submit=True,
            )

            result = AnkiWebBrowser(
                profile_dir=Path(tmp) / "profile",
                headless=True,
                timeout_ms=10_000,
            ).publish(plan)

            self.assertEqual(result.status, "submitted")
            self.assertEqual(server.last_post_path, "/shared/addons/update")
            self.assertEqual(server.post_paths, ["/shared/addons/update", "/shared/addons/update"])
            self.assertIn(b"fake addon", server.post_bodies[0])
            self.assertIn(b"123456789", server.last_post_body)
            self.assertIn(b"Bug fixes", server.last_post_body)

    def test_account_too_new_blocker_is_reported(self) -> None:
        with FakeAnkiWebServer() as server, tempfile.TemporaryDirectory() as tmp:
            artifact = _artifact(Path(tmp))
            plan = PublishPlan(
                mode="create",
                base_url=server.url,
                upload_url=f"{server.url}/shared/addons/too-new",
                login_url=f"{server.url}/account/login",
                artifact_path=artifact,
                addon_id=None,
                title="Study Triage",
                support_url=None,
                description="Description text",
                changelog=None,
                submit=False,
            )

            with self.assertRaisesRegex(PublishError, "account is too new"):
                AnkiWebBrowser(
                    profile_dir=Path(tmp) / "profile",
                    headless=True,
                    timeout_ms=10_000,
                ).publish(plan)


class FakeAnkiWebServer:
    def __init__(self, *, login_is_logged_in: bool = False) -> None:
        self.login_is_logged_in = login_is_logged_in

    def __enter__(self) -> FakeAnkiWebServer:
        self.last_post_path = ""
        self.last_post_body = b""
        self.post_paths = []
        self.post_bodies = []
        self.login_get_count = 0
        self.logout_get_count = 0

        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(handler) -> None:
                if handler.path == "/shared/addons/create":
                    body = _create_form()
                elif handler.path == "/shared/addons/update":
                    body = _update_form()
                elif handler.path == "/shared/addons/too-new":
                    body = _account_too_new_page()
                elif handler.path == "/account/login":
                    owner.login_get_count += 1
                    if owner.login_is_logged_in and owner.login_get_count == 1:
                        body = _logged_in_page()
                    else:
                        body = _login_form()
                elif handler.path == "/account/logout":
                    owner.logout_get_count += 1
                    body = b"<html><body>Logged out</body></html>"
                else:
                    body = b"<html><body><a href='/shared/addons/create'>Upload</a></body></html>"
                handler.send_response(200)
                handler.send_header("Content-Type", "text/html; charset=utf-8")
                handler.send_header("Content-Length", str(len(body)))
                handler.end_headers()
                handler.wfile.write(body)

            def do_POST(handler) -> None:
                length = int(handler.headers.get("Content-Length", "0"))
                owner.last_post_path = handler.path
                owner.post_paths.append(handler.path)
                owner.last_post_body = handler.rfile.read(length)
                owner.post_bodies.append(owner.last_post_body)
                body = _logged_in_page()
                handler.send_response(200)
                handler.send_header("Content-Type", "text/html; charset=utf-8")
                handler.send_header("Content-Length", str(len(body)))
                handler.end_headers()
                handler.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.url = f"http://{host}:{port}"
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def _artifact(root: Path) -> Path:
    path = root / "addon.ankiaddon"
    path.write_bytes(b"fake addon")
    return path


def _login_form() -> bytes:
    return b"""
    <html><body>
      <form method="post" action="/account/login">
        <input type="email" name="email">
        <input type="password" name="password">
        <button type="submit">Log In</button>
      </form>
    </body></html>
    """


def _logged_in_page() -> bytes:
    return b"""
    <html><body>
      <main>Decks</main>
      <a href="/account/logout">Log Out</a>
    </body></html>
    """


def _create_form() -> bytes:
    return b"""
    <html><body>
      <form method="post" enctype="multipart/form-data">
        <input type="file" name="file">
        <input name="title">
        <input name="support_url">
        <input name="branch_min_version" maxlength="9">
        <input name="branch_max_version" maxlength="9">
        <textarea name="description"></textarea>
        <textarea name="changes"></textarea>
        <button type="submit">Publish</button>
      </form>
    </body></html>
    """


def _update_form() -> bytes:
    return b"""
    <html><body>
      <form method="post" enctype="multipart/form-data">
        <input type="file" name="file">
        <input name="addon_id">
        <input name="branch_min_version" maxlength="9">
        <input name="branch_max_version" maxlength="9">
        <textarea name="changelog"></textarea>
        <button type="submit" formaction="/shared/addons/add-branch">Add New Branch</button>
        <button type="submit">Save</button>
      </form>
    </body></html>
    """


def _account_too_new_page() -> bytes:
    return b"""
    <html><head><title>Account Too New - AnkiWeb</title></head>
      <body>
        <h4>Sorry, your account is too new for this action.</h4>
      </body>
    </html>
    """


if __name__ == "__main__":
    unittest.main()
