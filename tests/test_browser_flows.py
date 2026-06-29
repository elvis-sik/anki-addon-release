from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import tempfile
from threading import Thread
import unittest

from anki_addon_release.browser import AnkiWebBrowser, playwright_available
from anki_addon_release.publish import PublishPlan


RUN_BROWSER_TESTS = os.environ.get("ANKI_ADDON_RELEASE_BROWSER_TESTS") == "1"


@unittest.skipUnless(
    RUN_BROWSER_TESTS and playwright_available(),
    "set ANKI_ADDON_RELEASE_BROWSER_TESTS=1 with playwright installed to run browser flows",
)
class BrowserFlowTests(unittest.TestCase):
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
                description="Description text",
                changelog="Initial upload",
                submit=True,
            )

            result = AnkiWebBrowser(
                profile_dir=Path(tmp) / "profile",
                headless=True,
                timeout_ms=10_000,
            ).publish(plan)

            self.assertEqual(result.status, "submitted")
            self.assertEqual(server.last_post_path, "/shared/addons/create")
            self.assertIn(b"Study Triage", server.last_post_body)
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
            self.assertIn(b"123456789", server.last_post_body)
            self.assertIn(b"Bug fixes", server.last_post_body)
            self.assertIn(b"fake addon", server.last_post_body)


class FakeAnkiWebServer:
    def __enter__(self) -> FakeAnkiWebServer:
        self.last_post_path = ""
        self.last_post_body = b""

        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(handler) -> None:
                if handler.path == "/shared/addons/create":
                    body = _create_form()
                elif handler.path == "/shared/addons/update":
                    body = _update_form()
                elif handler.path == "/account/login":
                    body = b"<html><body>login</body></html>"
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
                owner.last_post_body = handler.rfile.read(length)
                body = b"<html><body>ok</body></html>"
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


def _create_form() -> bytes:
    return b"""
    <html><body>
      <form method="post" enctype="multipart/form-data">
        <input type="file" name="file">
        <input name="title">
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
        <textarea name="changelog"></textarea>
        <button type="submit">Save</button>
      </form>
    </body></html>
    """


if __name__ == "__main__":
    unittest.main()

