"""
browser_tools.py
================
A thin, well-documented wrapper around Playwright that exposes the modular set
of browser "tools" the agent composes together:

    open_browser      - launch a Chromium instance
    navigate_to_url   - go to a URL
    take_screenshot   - capture the current viewport
    click_on_screen   - click at pixel coordinates (x, y)
    double_click      - double-click at pixel coordinates (x, y)
    send_keys         - type text into the currently focused element
    scroll            - scroll the page
    get_form_fields   - intelligent element detection (inputs/textareas + labels)

Each tool returns a plain ``dict`` describing the outcome. Coordinate-based
tools operate in CSS-pixel space that maps 1:1 to the screenshots we hand to the
model (we force ``device_scale_factor=1``), so the model can reliably translate
"that field is at (640, 320)" into a real click.

The class is deliberately stateful (it owns the browser/page lifecycle) and is
used as a context manager so resources are always cleaned up.
"""

from __future__ import annotations

import base64
import logging
import os
import sys
from typing import Any, Optional

from playwright.sync_api import (
    Browser,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

logger = logging.getLogger("agent.browser")


class ToolError(Exception):
    """Raised when a browser tool fails in an expected, recoverable way.

    The agent loop catches this and feeds the message back to the model as a
    tool error so it can adapt (e.g. retry, pick different coordinates, etc.).
    """


# JavaScript that collects all visible, interactive form fields together with
# their on-screen centre coordinates and best-guess label text. Running this in
# the page is far more reliable than guessing element positions from pixels.
_COLLECT_FIELDS_JS = r"""
() => {
  const labelFor = (el) => {
    // 1) <label for="id">
    if (el.id) {
      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (l && l.innerText.trim()) return l.innerText.trim();
    }
    // 2) wrapping <label>
    const wrap = el.closest('label');
    if (wrap && wrap.innerText.trim()) return wrap.innerText.trim();
    // 3) aria-label / placeholder / name
    return (
      el.getAttribute('aria-label') ||
      el.getAttribute('placeholder') ||
      el.getAttribute('name') ||
      ''
    ).trim();
  };

  const out = [];
  const nodes = document.querySelectorAll(
    'input:not([type=hidden]):not([type=submit]):not([type=button]), textarea, [contenteditable="true"]'
  );
  nodes.forEach((el, i) => {
    const r = el.getBoundingClientRect();
    // Only report fields that are actually visible within the viewport.
    const visible =
      r.width > 0 &&
      r.height > 0 &&
      r.bottom > 0 &&
      r.right > 0 &&
      r.top < window.innerHeight &&
      r.left < window.innerWidth;
    if (!visible) return;
    out.push({
      index: i,
      tag: el.tagName.toLowerCase(),
      type: (el.getAttribute('type') || '').toLowerCase(),
      label: labelFor(el),
      name: el.getAttribute('name') || '',
      id: el.id || '',
      placeholder: el.getAttribute('placeholder') || '',
      aria_label: el.getAttribute('aria-label') || '',
      value: el.value || el.innerText || '',
      x: Math.round(r.left + r.width / 2),
      y: Math.round(r.top + r.height / 2),
    });
  });
  return out;
}
"""


class BrowserController:
    """Owns the Playwright browser/page and exposes the agent's tool surface."""

    def __init__(
        self,
        headless: bool = False,
        viewport_width: int = 1280,
        viewport_height: int = 800,
        action_timeout_ms: int = 30_000,
        artifacts_dir: str = "artifacts",
    ) -> None:
        self.headless = headless
        self.viewport = {"width": viewport_width, "height": viewport_height}
        self.action_timeout_ms = action_timeout_ms
        self.artifacts_dir = artifacts_dir

        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self._screenshot_count = 0

        os.makedirs(self.artifacts_dir, exist_ok=True)

    # ----- context-manager plumbing -------------------------------------- #
    def __enter__(self) -> "BrowserController":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        """Tear down the page, browser and Playwright driver (idempotent)."""
        for closer, label in (
            (lambda: self._browser and self._browser.close(), "browser"),
            (lambda: self._pw and self._pw.stop(), "playwright"),
        ):
            try:
                closer()
            except Exception as exc:  # pragma: no cover - best-effort cleanup
                logger.debug("Error closing %s: %s", label, exc)
        self._browser = None
        self._pw = None
        self.page = None

    # ----- internal helpers ---------------------------------------------- #
    def _require_page(self) -> Page:
        if self.page is None:
            raise ToolError("Browser is not open yet. Call open_browser first.")
        return self.page

    def _settle(self, ms: int = 600) -> None:
        """Give the page a brief moment to react to an action / animate."""
        page = self._require_page()
        try:
            page.wait_for_load_state("networkidle", timeout=3_000)
        except PlaywrightTimeoutError:
            pass  # Not fatal; some pages keep long-lived connections open.
        page.wait_for_timeout(ms)

    # ----- TOOLS --------------------------------------------------------- #
    def open_browser(self) -> dict:
        """Launch Chromium and create a single page/tab.

        ``device_scale_factor=1`` keeps screenshot pixels aligned 1:1 with the
        click coordinate system the model reasons about.
        """
        if self.page is not None:
            return {"status": "already_open", "message": "Browser is already running."}

        logger.info("Launching Chromium (headless=%s)…", self.headless)
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        context = self._browser.new_context(
            viewport=self.viewport,
            device_scale_factor=1,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
        )
        context.set_default_timeout(self.action_timeout_ms)
        self.page = context.new_page()
        return {
            "status": "ok",
            "message": "Browser launched.",
            "viewport": self.viewport,
        }

    def navigate_to_url(self, url: str) -> dict:
        """Direct the browser to ``url`` and wait for the DOM to be ready."""
        page = self._require_page()
        logger.info("Navigating to %s", url)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=self.action_timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise ToolError(f"Timed out loading {url}: {exc}") from exc
        self._settle()
        return {"status": "ok", "url": page.url, "title": page.title()}

    def take_screenshot(self, label: str = "step") -> dict:
        """Capture the current viewport.

        Returns both a base64 PNG (handed to the model as an image) and the path
        of the saved file so there is a durable artifact trail for the viva.
        """
        page = self._require_page()
        self._screenshot_count += 1
        safe_label = "".join(c if c.isalnum() else "_" for c in label)[:40]
        filename = f"{self._screenshot_count:02d}_{safe_label}.png"
        path = os.path.join(self.artifacts_dir, filename)

        png_bytes = page.screenshot(full_page=False)
        with open(path, "wb") as fh:
            fh.write(png_bytes)

        logger.info("Saved screenshot -> %s", path)
        return {
            "status": "ok",
            "path": path,
            "image_base64": base64.standard_b64encode(png_bytes).decode("ascii"),
            "media_type": "image/png",
        }

    def click_on_screen(self, x: int, y: int) -> dict:
        """Perform a left mouse click at viewport pixel coordinates (x, y)."""
        page = self._require_page()
        self._assert_in_viewport(x, y)
        logger.info("Click at (%s, %s)", x, y)
        page.mouse.click(x, y)
        self._settle(400)
        return {"status": "ok", "action": "click", "x": x, "y": y}

    def double_click(self, x: int, y: int) -> dict:
        """Perform a double-click at viewport pixel coordinates (x, y).

        Useful for selecting an existing word in a field so the next ``send_keys``
        overwrites it instead of appending.
        """
        page = self._require_page()
        self._assert_in_viewport(x, y)
        logger.info("Double-click at (%s, %s)", x, y)
        page.mouse.dblclick(x, y)
        self._settle(400)
        return {"status": "ok", "action": "double_click", "x": x, "y": y}

    def send_keys(self, text: str, clear_first: bool = False, press_enter: bool = False) -> dict:
        """Type ``text`` into the currently focused element.

        Args:
            text: the literal text to type.
            clear_first: select-all + delete before typing (overwrite contents).
            press_enter: press Enter after typing (e.g. to submit).
        """
        page = self._require_page()
        if clear_first:
            modifier = "Meta" if sys.platform == "darwin" else "Control"
            page.keyboard.press(f"{modifier}+A")
            page.keyboard.press("Delete")
        logger.info("Typing %r (clear_first=%s, press_enter=%s)", text, clear_first, press_enter)
        page.keyboard.type(text, delay=25)
        if press_enter:
            page.keyboard.press("Enter")
        self._settle(300)
        return {"status": "ok", "action": "send_keys", "text": text}

    def scroll(self, direction: str = "down", amount: int = 500) -> dict:
        """Scroll the page vertically (``down``/``up``) or horizontally.

        ``amount`` is in CSS pixels.
        """
        page = self._require_page()
        dx, dy = 0, 0
        d = direction.lower()
        if d == "down":
            dy = amount
        elif d == "up":
            dy = -amount
        elif d == "right":
            dx = amount
        elif d == "left":
            dx = -amount
        else:
            raise ToolError(f"Unknown scroll direction: {direction!r}")
        logger.info("Scroll %s by %s", direction, amount)
        page.mouse.wheel(dx, dy)
        self._settle(300)
        return {"status": "ok", "action": "scroll", "direction": direction, "amount": amount}

    def get_form_fields(self) -> dict:
        """Intelligent element detection.

        Returns every visible input/textarea/contenteditable element along with
        its label text and the exact centre coordinates to click. The agent uses
        this to translate "the Name field" into a precise (x, y) for
        ``click_on_screen`` — far more reliable than estimating from pixels.
        """
        page = self._require_page()
        fields = page.evaluate(_COLLECT_FIELDS_JS)
        logger.info("Detected %d form field(s).", len(fields))
        return {"status": "ok", "count": len(fields), "fields": fields}

    # ----- guards -------------------------------------------------------- #
    def _assert_in_viewport(self, x: int, y: int) -> None:
        if not (0 <= x <= self.viewport["width"] and 0 <= y <= self.viewport["height"]):
            raise ToolError(
                f"Coordinates ({x}, {y}) are outside the viewport "
                f"{self.viewport['width']}x{self.viewport['height']}. "
                "Scroll the target into view or pick coordinates inside the viewport."
            )
