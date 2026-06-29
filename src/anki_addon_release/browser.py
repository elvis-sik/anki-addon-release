from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .errors import PublishError
from .publish import PublishPlan


@dataclass(frozen=True)
class BrowserPublishResult:
    status: str
    final_url: str
    screenshot: Path | None = None


def playwright_available() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
    except ModuleNotFoundError:
        return False
    return True


class AnkiWebBrowser:
    def __init__(
        self,
        *,
        profile_dir: Path,
        headless: bool = False,
        timeout_ms: int = 15_000,
        slow_mo_ms: int = 0,
        diagnostics_dir: Path | None = None,
    ) -> None:
        self.profile_dir = profile_dir
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.slow_mo_ms = slow_mo_ms
        self.diagnostics_dir = diagnostics_dir

    def login(self, login_url: str) -> BrowserPublishResult:
        sync_playwright = _sync_playwright()
        with sync_playwright() as playwright:
            context = None
            page = None
            try:
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_dir),
                    headless=self.headless,
                    slow_mo=self.slow_mo_ms,
                )
                page = context.new_page()
                page.set_default_timeout(self.timeout_ms)
                page.goto(login_url)
                if not self.headless:
                    input("Complete AnkiWeb login in the browser, then press Enter here to continue: ")
                screenshot = self._screenshot(page, "login")
                final_url = page.url
            except Exception as exc:
                raise self._failure("browser login failed", exc, page, "login-failed") from exc
            finally:
                if context is not None:
                    context.close()
        return BrowserPublishResult(status="login-opened", final_url=final_url, screenshot=screenshot)

    def publish(self, plan: PublishPlan) -> BrowserPublishResult:
        if not plan.artifact_path.exists():
            raise PublishError(f"artifact does not exist: {plan.artifact_path}")

        sync_playwright = _sync_playwright()
        with sync_playwright() as playwright:
            context = None
            page = None
            try:
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_dir),
                    headless=self.headless,
                    slow_mo=self.slow_mo_ms,
                )
                page = context.new_page()
                page.set_default_timeout(self.timeout_ms)
                page.goto(plan.upload_url)

                _ensure_upload_form(page)
                _fill_form(page, plan)

                if plan.submit:
                    _click_submit(page)
                    page.wait_for_load_state("networkidle")
                    status = "submitted"
                else:
                    status = "prepared"

                screenshot = self._screenshot(page, f"publish-{plan.mode}-{status}")
                final_url = page.url
            except Exception as exc:
                raise self._failure(
                    "browser publish failed",
                    exc,
                    page,
                    f"publish-{plan.mode}-failed",
                ) from exc
            finally:
                if context is not None:
                    context.close()
        return BrowserPublishResult(status=status, final_url=final_url, screenshot=screenshot)

    def _screenshot(self, page: object, stem: str) -> Path | None:
        if self.diagnostics_dir is None:
            return None
        self.diagnostics_dir.mkdir(parents=True, exist_ok=True)
        path = self.diagnostics_dir / f"{stem}.png"
        page.screenshot(path=str(path), full_page=True)
        return path

    def _html(self, page: object, stem: str) -> Path | None:
        if self.diagnostics_dir is None:
            return None
        self.diagnostics_dir.mkdir(parents=True, exist_ok=True)
        path = self.diagnostics_dir / f"{stem}.html"
        path.write_text(page.content(), encoding="utf-8")
        return path

    def _failure(self, message: str, exc: Exception, page: object | None, stem: str) -> PublishError:
        diagnostics = []
        if page is not None:
            screenshot = self._screenshot(page, stem)
            html = self._html(page, stem)
            if screenshot is not None:
                diagnostics.append(f"screenshot={screenshot}")
            if html is not None:
                diagnostics.append(f"html={html}")
        suffix = f" ({', '.join(diagnostics)})" if diagnostics else ""
        return PublishError(f"{message}: {exc}{suffix}")


def _sync_playwright() -> object:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise PublishError(
            "Playwright is required for browser publishing. "
            "Install with: pipx install 'anki-addon-release[browser]' "
            "or: python -m pip install '.[browser]'"
        ) from exc

    globals()["PlaywrightTimeoutError"] = PlaywrightTimeoutError
    return sync_playwright


def _ensure_upload_form(page: object) -> None:
    if _file_input_count(page) > 0:
        return

    upload_link = page.get_by_role("link", name=re.compile("upload", re.IGNORECASE))
    upload_button = page.get_by_role("button", name=re.compile("upload", re.IGNORECASE))
    for locator in (upload_link, upload_button):
        if _count(locator) > 0:
            locator.first.click()
            page.wait_for_load_state("domcontentloaded")
            if _file_input_count(page) > 0:
                return

    raise PublishError("could not find an upload form or upload button")


def _fill_form(page: object, plan: PublishPlan) -> None:
    file_input = page.locator('input[type="file"]').first
    file_input.set_input_files(str(plan.artifact_path))

    _fill_optional_text(page, _TITLE_CANDIDATES, plan.title)
    if plan.description is not None:
        _fill_optional_text(page, _DESCRIPTION_CANDIDATES, plan.description)
    if plan.changelog is not None:
        _fill_optional_text(page, _CHANGELOG_CANDIDATES, plan.changelog)
    if plan.addon_id is not None:
        _fill_optional_text(page, _ADDON_ID_CANDIDATES, plan.addon_id)


def _click_submit(page: object) -> None:
    submit = page.locator('button[type="submit"], input[type="submit"]').first
    if _count(submit) > 0:
        submit.click()
        return

    role_button = page.get_by_role("button", name=re.compile("upload|submit|save|publish", re.IGNORECASE))
    if _count(role_button) > 0:
        role_button.first.click()
        return

    raise PublishError("could not find a submit button")


def _fill_optional_text(page: object, candidates: tuple[str, ...], value: str) -> bool:
    for selector in candidates:
        locator = page.locator(selector)
        if _count(locator) > 0:
            locator.first.fill(value)
            return True
    return False


def _file_input_count(page: object) -> int:
    return _count(page.locator('input[type="file"]'))


def _count(locator: object) -> int:
    try:
        return locator.count()
    except Exception:
        return 0


_TITLE_CANDIDATES = (
    'input[name="title"]',
    'input[name="name"]',
    'input[id*="title" i]',
    'input[id*="name" i]',
)
_DESCRIPTION_CANDIDATES = (
    'textarea[name="description"]',
    'textarea[name="desc"]',
    'textarea[id*="description" i]',
    'textarea[id*="desc" i]',
)
_CHANGELOG_CANDIDATES = (
    'textarea[name="changes"]',
    'textarea[name="changelog"]',
    'textarea[name="release_notes"]',
    'textarea[id*="change" i]',
)
_ADDON_ID_CANDIDATES = (
    'input[name="addon_id"]',
    'input[name="id"]',
    'input[id*="addon" i]',
)
