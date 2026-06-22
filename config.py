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

# Fallback chain tried in order. Each Gemini model has its own separate free-tier
# quota, so when one is exhausted (HTTP 429) the agent rotates to the next. All of
# these support vision + function calling.
_DEFAULT_MODEL_CHAIN = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
]


def _get_model_chain() -> list[str]:
    """Build the ordered list of models to try.

    Priority:
      1. ``GEMINI_MODELS`` — explicit comma-separated chain, used as-is.
      2. ``GEMINI_MODEL``  — primary model, placed first, then the default chain.
      3. The default chain.
    Duplicates are removed while preserving order.
    """
    explicit = os.getenv("GEMINI_MODELS", "").strip()
    if explicit:
        chain = [m.strip() for m in explicit.split(",") if m.strip()]
    else:
        primary = os.getenv("GEMINI_MODEL", "").strip()
        chain = ([primary] if primary else []) + _DEFAULT_MODEL_CHAIN

    seen: set[str] = set()
    ordered: list[str] = []
    for m in chain:
        if m not in seen:
            seen.add(m)
            ordered.append(m)
    return ordered


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
    # Ordered fallback chain. The first entry is the primary model; the rest are
    # tried in turn when a model returns a quota / overload error.
    models: list[str] = field(default_factory=_get_model_chain)

    @property
    def model(self) -> str:
        """The primary (first) model — used for logging and as the starting point."""
        return self.models[0] if self.models else "gemini-2.5-flash"

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
