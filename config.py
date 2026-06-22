"""
config.py
=========
Central configuration for the Website Automation Agent.

All tunable settings live here and are sourced from environment variables
(loaded from an optional ``.env`` file via python-dotenv). This satisfies the
assignment's "use environment variables / configuration files for settings"
guideline — and, importantly, the agent needs **no API key**: element detection
is fully deterministic, so there are no secrets to manage.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Load variables from a .env file (if present) into the process environment.
load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    """Parse a boolean environment variable in a forgiving way."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_int(name: str, default: int) -> int:
    """Parse an integer environment variable, falling back to a default."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class Settings:
    """Immutable bundle of runtime settings for the agent."""

    # --- Target task ---
    target_url: str = field(
        default_factory=lambda: os.getenv(
            "TARGET_URL", "https://ui.shadcn.com/docs/forms/react-hook-form"
        )
    )

    # --- Values to type into the detected fields ---
    name_value: str = field(default_factory=lambda: os.getenv("NAME_VALUE", "Jane Doe"))
    description_value: str = field(
        default_factory=lambda: os.getenv(
            "DESCRIPTION_VALUE",
            "An automated submission created by the Website Automation Agent.",
        )
    )

    # --- Browser ---
    headless: bool = field(default_factory=lambda: _get_bool("HEADLESS", False))
    viewport_width: int = field(default_factory=lambda: _get_int("VIEWPORT_WIDTH", 1280))
    viewport_height: int = field(default_factory=lambda: _get_int("VIEWPORT_HEIGHT", 800))

    # --- Agent ---
    action_timeout_ms: int = field(default_factory=lambda: _get_int("ACTION_TIMEOUT_MS", 30000))

    # --- Artifacts ---
    artifacts_dir: str = field(default_factory=lambda: os.getenv("ARTIFACTS_DIR", "artifacts"))

    def validate(self) -> None:
        """Raise a helpful error if mandatory settings are missing."""
        if not self.target_url:
            raise RuntimeError("TARGET_URL is empty. Set it in .env or the environment.")


# A single shared settings instance imported across the project.
settings = Settings()
