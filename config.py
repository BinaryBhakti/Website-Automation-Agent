"""
config.py
=========
Central configuration for the Website Automation Agent.

All tunable settings live here and are sourced from environment variables
(loaded from a local ``.env`` file via python-dotenv). This keeps secrets such
as the Gemini API key out of the source code, as required by the assignment's
"use environment variables / configuration files" guideline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Load variables from a .env file (if present) into the process environment.
load_dotenv()

_DEFAULT_TASK = (
    "Identify the form's Name (or primary/title) field and its Description field, "
    "then fill both with sensible, realistic values. Do not submit the form."
)


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

    # --- Google Gemini / model ---
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))

    # --- Target task ---
    target_url: str = field(
        default_factory=lambda: os.getenv(
            "TARGET_URL", "https://ui.shadcn.com/docs/forms/react-hook-form"
        )
    )
    task: str = field(default_factory=lambda: os.getenv("TASK", _DEFAULT_TASK))

    # --- Browser ---
    headless: bool = field(default_factory=lambda: _get_bool("HEADLESS", False))
    viewport_width: int = field(default_factory=lambda: _get_int("VIEWPORT_WIDTH", 1280))
    viewport_height: int = field(default_factory=lambda: _get_int("VIEWPORT_HEIGHT", 800))

    # --- Agent loop ---
    max_steps: int = field(default_factory=lambda: _get_int("MAX_STEPS", 30))
    action_timeout_ms: int = field(default_factory=lambda: _get_int("ACTION_TIMEOUT_MS", 30000))

    # --- Artifacts ---
    artifacts_dir: str = field(default_factory=lambda: os.getenv("ARTIFACTS_DIR", "artifacts"))

    def validate(self) -> None:
        """Raise a helpful error if mandatory settings are missing."""
        if not self.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Copy .env.example to .env and add your "
                "Google Gemini API key, or export GEMINI_API_KEY in your shell."
            )


# A single shared settings instance imported across the project.
settings = Settings()
