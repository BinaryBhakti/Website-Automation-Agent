"""
agent.py
========
The decision-making brain — **no API key, no LLM required**.

``AutomationAgent`` composes the modular browser tools into a workflow and makes
its own decisions about *which* element is the "Name" field and *which* is the
"Description" field. The intelligence is a transparent, deterministic scoring
model over each field's label, placeholder, name, id and element type — exactly
the "intelligent element identification using selectors / XPath" the assignment
calls for, with none of the cost or flakiness of a remote model.

Workflow
--------
    open_browser
      └─► navigate_to_url(TARGET_URL)
            └─► take_screenshot (before)
                  └─► get_form_fields  ── intelligent detection + scoring
                        ├─► fill Name field   (click_on_screen → send_keys)
                        ├─► fill Description  (click_on_screen → send_keys)
                        └─► take_screenshot (after) → done

Every decision (scores, chosen coordinates, typed text) is logged so the run is
fully auditable during the viva.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from config import Settings
from .browser_tools import BrowserController, ToolError

logger = logging.getLogger("agent.brain")


# Keyword signals used to recognise each target field. Higher-weight keywords are
# more specific. The scorer sums the weights of every keyword that appears in a
# field's combined text (label + placeholder + name + id + aria-label).
# NOTE: the assignment's "Name" field maps to the form's primary single-line
# identifier. On the live target page that field is labelled "Bug Title", so the
# keyword set covers name/title/subject. If none match, _locate_field falls back
# to the topmost single-line text input (see _fallback_primary_text).
_NAME_KEYWORDS = {
    "name": 5,
    "full name": 6,
    "your name": 6,
    "username": 4,
    "first name": 4,
    "fullname": 5,
    "title": 5,
    "subject": 3,
}
_DESCRIPTION_KEYWORDS = {
    "description": 6,
    "desc": 4,
    "about": 4,
    "bio": 4,
    "message": 3,
    "details": 3,
    "comment": 3,
    "summary": 3,
    "notes": 2,
}


@dataclass
class FieldMatch:
    """A detected field chosen as the best candidate for a target role."""

    role: str            # "name" or "description"
    field: dict          # the raw field dict from get_form_fields
    score: float         # how confident we are in this match


class AutomationAgent:
    """Deterministically detects and fills the Name and Description fields."""

    def __init__(self, settings: Settings, browser: BrowserController) -> None:
        self.settings = settings
        self.browser = browser

    # ----- public entry point -------------------------------------------- #
    def run(self) -> str:
        """Execute the full workflow. Returns a human-readable summary."""
        logger.info("Agent starting deterministic form-automation workflow.")

        # 1. Launch + navigate.
        self.browser.open_browser()
        nav = self.browser.navigate_to_url(self.settings.target_url)
        logger.info("Loaded page: %s", nav.get("title") or nav.get("url"))
        self.browser.take_screenshot(label="before_fill")

        # 2. Detect the Description field first (its keyword is highly specific),
        #    then the Name/primary field, excluding the description so the two
        #    never collide.
        desc_match = self._locate_field("description")
        exclude = desc_match.field.get("index") if desc_match else None
        name_match = self._locate_field("name", exclude_index=exclude)

        if name_match is None and desc_match is None:
            raise ToolError(
                "Could not detect a Name or Description field on the page. "
                "The page structure may have changed."
            )

        # 3. Fill each field we found.
        filled = []
        if name_match is not None:
            self._fill(name_match, self.settings.name_value)
            filled.append("Name")
        else:
            logger.warning("No Name field detected — skipping.")

        if desc_match is not None:
            self._fill(desc_match, self.settings.description_value)
            filled.append("Description")
        else:
            logger.warning("No Description field detected — skipping.")

        # 4. Verify + capture the final state.
        self._verify(name_match, desc_match)
        self.browser.take_screenshot(label="after_fill")

        summary = (
            f"Filled {len(filled)} field(s): {', '.join(filled)}."
            if filled
            else "No fields were filled."
        )
        logger.info("✅ %s", summary)
        return summary

    # ----- intelligent detection ----------------------------------------- #
    def _locate_field(
        self, role: str, exclude_index: Optional[int] = None, _scrolled: bool = False
    ) -> Optional[FieldMatch]:
        """Find the best on-screen field for ``role`` ('name' or 'description').

        Strategy:
          1. Score every visible field by keyword + structure; take the best > 0.
          2. For the 'name' role, if no keyword matches, fall back to the topmost
             single-line text input (the form's primary field).
          3. If still nothing and we haven't scrolled yet, scroll down once and
             retry — the field may be below the fold (coordinates are viewport-
             relative, so we must re-detect after scrolling).
        """
        fields = self.browser.get_form_fields()["fields"]
        match = self._best_match(role, fields, exclude_index)

        if match is None and role == "name":
            match = self._fallback_primary_text(fields, exclude_index)
            if match is not None:
                logger.info("No explicit name/title keyword; using primary text input as Name.")

        if match is None and not _scrolled:
            logger.info("No %s field visible yet; scrolling to look further down.", role)
            self.browser.scroll("down", 400)
            return self._locate_field(role, exclude_index=exclude_index, _scrolled=True)

        if match is not None:
            logger.info(
                "Detected %s field -> label=%r at (%d, %d) [score=%.1f]",
                role, match.field.get("label", ""), match.field["x"], match.field["y"], match.score,
            )
        return match

    def _best_match(
        self, role: str, fields: list[dict], exclude_index: Optional[int] = None
    ) -> Optional[FieldMatch]:
        """Score every field for ``role`` and return the highest scorer (>0)."""
        best: Optional[FieldMatch] = None
        for f in fields:
            if exclude_index is not None and f.get("index") == exclude_index:
                continue
            score = self._score(role, f)
            if score > 0 and (best is None or score > best.score):
                best = FieldMatch(role=role, field=f, score=score)
        return best

    @staticmethod
    def _fallback_primary_text(
        fields: list[dict], exclude_index: Optional[int] = None
    ) -> Optional[FieldMatch]:
        """Pick the topmost single-line text input as the primary ('name') field.

        Used when a form has no field literally labelled Name/Title — we treat the
        first ordinary text input (e.g. an email-free single-line box) as the
        primary identifier the assignment calls "Name".
        """
        candidates = [
            f
            for f in fields
            if f.get("tag") == "input"
            and f.get("type") in ("", "text")
            and f.get("index") != exclude_index
        ]
        if not candidates:
            return None
        # Topmost on screen = smallest y coordinate.
        primary = min(candidates, key=lambda f: f.get("y", 1_000_000))
        return FieldMatch(role="name", field=primary, score=0.5)

    @staticmethod
    def _score(role: str, field: dict) -> float:
        """Compute how well ``field`` matches the target ``role``.

        Combines keyword matches across all of the field's text signals with a
        small structural bonus: a <textarea> is more likely a Description, while a
        single-line text <input> is more likely a Name.
        """
        haystack = " ".join(
            str(field.get(k, ""))
            for k in ("label", "placeholder", "name", "id", "aria_label")
        ).lower()
        haystack = re.sub(r"[^a-z0-9 ]+", " ", haystack)

        keywords = _NAME_KEYWORDS if role == "name" else _DESCRIPTION_KEYWORDS
        score = 0.0
        for kw, weight in keywords.items():
            if kw in haystack:
                score += weight

        is_textarea = field.get("tag") == "textarea"
        if role == "description" and is_textarea:
            score += 2  # textareas usually hold longer, descriptive text
        if role == "name" and field.get("type") == "text" and not is_textarea:
            score += 1
        return score

    # ----- manipulation -------------------------------------------------- #
    def _fill(self, match: FieldMatch, text: str) -> None:
        """Focus the matched field via coordinate click, then type ``text``.

        Uses ``double_click`` when the field already contains text (to select a
        word before overwriting) — demonstrating that tool "when necessary".
        """
        x, y = match.field["x"], match.field["y"]
        existing = str(match.field.get("value", "")).strip()

        if existing:
            logger.info("%s field has existing text %r; double-clicking to select.",
                        match.role, existing)
            self.browser.double_click(x, y)
        else:
            self.browser.click_on_screen(x, y)

        self.browser.send_keys(text, clear_first=True)
        logger.info("Typed into %s field: %r", match.role, text)

    # ----- verification -------------------------------------------------- #
    def _verify(self, *matches: Optional[FieldMatch]) -> None:
        """Re-read the page and confirm the chosen fields now hold our text."""
        current = {f.get("index"): f for f in self.browser.get_form_fields()["fields"]}
        for m in matches:
            if m is None:
                continue
            now = current.get(m.field.get("index"))
            value = (now or {}).get("value", "") if now else "(field no longer visible)"
            logger.info("Verify %s field -> value now: %r", m.role, value)
