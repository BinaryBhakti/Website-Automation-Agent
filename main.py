"""
main.py
=======
Entry point for the Website Automation Agent.

    python main.py

Sets up logging, validates configuration, launches the browser, and runs the
AI agent loop against the target URL defined in the configuration.
"""

from __future__ import annotations

import logging
import os
import sys

from agent.agent import AutomationAgent
from agent.browser_tools import BrowserController
from config import settings


def setup_logging(artifacts_dir: str) -> None:
    """Configure logging to both the console and a rotating-ish log file."""
    os.makedirs(artifacts_dir, exist_ok=True)
    log_path = os.path.join(artifacts_dir, "agent.log")

    fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    datefmt = "%H:%M:%S"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_path, encoding="utf-8"),
    ]
    logging.basicConfig(level=logging.INFO, format=fmt, datefmt=datefmt, handlers=handlers)

    # Quiet down noisy third-party loggers.
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> int:
    setup_logging(settings.artifacts_dir)
    log = logging.getLogger("agent.main")

    try:
        settings.validate()
    except RuntimeError as exc:
        log.error("Configuration error: %s", exc)
        return 1

    log.info("Website Automation Agent starting up (AI-driven via Gemini).")
    log.info("Model: %s | Target: %s", settings.model, settings.target_url)
    log.info("Headless: %s | Viewport: %sx%s",
             settings.headless, settings.viewport_width, settings.viewport_height)

    try:
        with BrowserController(
            headless=settings.headless,
            viewport_width=settings.viewport_width,
            viewport_height=settings.viewport_height,
            action_timeout_ms=settings.action_timeout_ms,
            artifacts_dir=settings.artifacts_dir,
        ) as browser:
            agent = AutomationAgent(settings, browser)
            summary = agent.run()
            # One final screenshot for the record.
            browser.take_screenshot(label="final_state")
            log.info("Done. Summary: %s", summary)
        return 0
    except KeyboardInterrupt:
        log.warning("Interrupted by user.")
        return 130
    except Exception:  # noqa: BLE001 - top-level guard, log full traceback
        log.exception("Fatal error while running the agent.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
