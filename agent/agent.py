"""
agent.py
========
The AI brain. ``AutomationAgent`` runs a manual Gemini function-calling loop in
which **the model decides everything** — what to look at, which element is the
Name field vs the Description field, what text to type, when to scroll, and when
the task is done. Nothing about those decisions is hard-coded; the agent code
only executes the tool calls the model asks for and feeds back the results.

    1. Gemini is given the task + the latest screenshot of the page.
    2. Gemini reasons and decides which browser tool to call (open_browser,
       navigate, get_form_fields, click_on_screen, send_keys, scroll, ...).
    3. We execute the tool via ``BrowserController`` and return the result —
       including a fresh screenshot — back to Gemini as a function response.
    4. Repeat until Gemini calls ``finish`` or we hit MAX_STEPS.

This is the "agent intelligence" layer: element detection and decision-making
are delegated to the model, which reasons over the screenshots and the structured
field data returned by ``get_form_fields``.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

from google import genai
from google.genai import types

from config import Settings
from .browser_tools import BrowserController, ToolError
from .tool_schemas import TOOLS

logger = logging.getLogger("agent.brain")

# Tools whose effect is visual: after running them we attach a fresh screenshot
# to the function response so the model always "sees" the current page state.
_VISUAL_TOOLS = {
    "navigate_to_url",
    "click_on_screen",
    "double_click",
    "send_keys",
    "scroll",
}

SYSTEM_PROMPT = """\
You are an autonomous website automation agent that controls a real Chromium \
browser through a small set of tools. You think for yourself: look at the page, \
reason about what you see, decide the single best next action, perform it, then \
look again. You — not any script — decide which element is which and what to type.

General method:
- Begin by calling open_browser, then navigate_to_url to the target URL.
- Use take_screenshot to SEE the page, and get_form_fields to read the raw list \
of fields (labels, placeholders, names, types and exact click coordinates).
- Reason about which field is the Name (or primary/title) field and which is the \
Description field. Labels may not be literally "Name" — use your judgement \
(e.g. a "Title"/"Bug Title" input is the primary/name field; a textarea is \
usually the description).
- To fill a field: click_on_screen at its (x, y) to focus it, then send_keys with \
your chosen text (use clear_first=true to overwrite any existing content).
- If a needed field is not visible, scroll to bring it into view, then call \
get_form_fields again (coordinates are viewport-relative and change after scrolling).
- After filling, verify with get_form_fields or a screenshot that the values are \
present, then call finish with a brief summary.
- Take exactly one logical step at a time and inspect the result before the next.

Be decisive and efficient. Choose realistic values yourself. Do not submit the \
form unless the task explicitly asks you to.\
"""


class AutomationAgent:
    """Orchestrates Gemini + the browser tools to complete the target task."""

    def __init__(self, settings: Settings, browser: BrowserController) -> None:
        self.settings = settings
        self.browser = browser
        self.client = genai.Client(api_key=settings.gemini_api_key)

        # Tool config handed to Gemini on every request.
        self._gen_config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[types.Tool(function_declarations=TOOLS)],
            temperature=0,
        )

        # Dispatch table: tool name -> bound BrowserController method.
        self._dispatch = {
            "open_browser": lambda **kw: self.browser.open_browser(),
            "navigate_to_url": lambda **kw: self.browser.navigate_to_url(kw["url"]),
            "take_screenshot": lambda **kw: self.browser.take_screenshot(kw.get("label", "step")),
            "get_form_fields": lambda **kw: self.browser.get_form_fields(),
            "click_on_screen": lambda **kw: self.browser.click_on_screen(int(kw["x"]), int(kw["y"])),
            "double_click": lambda **kw: self.browser.double_click(int(kw["x"]), int(kw["y"])),
            "send_keys": lambda **kw: self.browser.send_keys(
                kw["text"],
                clear_first=bool(kw.get("clear_first", False)),
                press_enter=bool(kw.get("press_enter", False)),
            ),
            "scroll": lambda **kw: self.browser.scroll(
                kw.get("direction", "down"), int(kw.get("amount", 500))
            ),
        }

    # ----- public entry point -------------------------------------------- #
    def run(self) -> str:
        """Drive the agent loop to completion. Returns the final summary text."""
        contents: list[types.Content] = [
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        text=(
                            "Start the task now.\n"
                            f"Target URL: {self.settings.target_url}\n"
                            f"Task: {self.settings.task}\n"
                            "Open the browser, navigate there, decide which fields to "
                            "fill, and complete the task."
                        )
                    )
                ],
            )
        ]

        for step in range(1, self.settings.max_steps + 1):
            logger.info("─── Step %d/%d ───", step, self.settings.max_steps)
            response = self.client.models.generate_content(
                model=self.settings.model,
                contents=contents,
                config=self._gen_config,
            )

            model_content = self._extract_content(response)
            if model_content is None:
                logger.warning("Model returned no content (possibly blocked). Stopping.")
                return "Stopped: the model returned no usable content."

            self._log_text_parts(model_content)
            # Preserve the model turn verbatim in the conversation history.
            contents.append(model_content)

            function_calls = [p.function_call for p in (model_content.parts or []) if p.function_call]

            if not function_calls:
                # Model replied with text only — nudge it to keep using tools.
                logger.info("Model produced no function call this turn; nudging.")
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                text=(
                                    "Continue by calling the browser tools to make "
                                    "progress, or call finish if the task is complete."
                                )
                            )
                        ],
                    )
                )
                continue

            reply_parts: list[types.Part] = []
            finished_summary: str | None = None

            for fc in function_calls:
                name = fc.name
                args = dict(fc.args) if fc.args else {}

                if name == "finish":
                    finished_summary = args.get("summary", "Task complete.")
                    reply_parts.append(
                        types.Part.from_function_response(
                            name=name, response={"status": "acknowledged"}
                        )
                    )
                    continue

                reply_parts.extend(self._execute_tool(name, args))

            contents.append(types.Content(role="user", parts=reply_parts))

            if finished_summary is not None:
                logger.info("✅ Agent finished: %s", finished_summary)
                return finished_summary

        logger.warning("Reached MAX_STEPS without an explicit finish.")
        return "Stopped after reaching the maximum number of steps."

    # ----- helpers ------------------------------------------------------- #
    def _execute_tool(self, name: str, args: dict) -> list[types.Part]:
        """Run a single tool call and build its function-response part(s).

        Returns a list because visual tools also append an image part so the
        model can see the resulting page state.
        """
        logger.info("Tool call: %s(%s)", name, _fmt_args(args))

        handler = self._dispatch.get(name)
        if handler is None:
            return [self._fn_response(name, {"status": "error", "message": f"Unknown tool: {name}"})]

        try:
            result = handler(**args)
        except ToolError as exc:
            logger.warning("Tool %s failed: %s", name, exc)
            return [self._fn_response(name, {"status": "error", "message": str(exc)})]
        except Exception as exc:  # noqa: BLE001 - report any failure back to model
            logger.exception("Unexpected error in tool %s", name)
            return [self._fn_response(name, {"status": "error", "message": f"Unexpected error: {exc}"})]

        return self._build_parts(name, result)

    def _build_parts(self, name: str, result: dict) -> list[types.Part]:
        """Turn a tool's dict result into function-response (+ optional image) parts."""
        parts: list[types.Part] = []

        if name == "take_screenshot":
            parts.append(self._fn_response(name, {"status": result["status"], "path": result["path"]}))
            parts.append(self._image_part(result))
            return parts

        # Strip base64 from the textual response to avoid duplicating big payloads.
        printable = {k: v for k, v in result.items() if k != "image_base64"}
        parts.append(self._fn_response(name, printable))

        # For visual actions, attach a fresh screenshot of the resulting state.
        if name in _VISUAL_TOOLS:
            try:
                shot = self.browser.take_screenshot(label=f"after_{name}")
                parts.append(self._image_part(shot))
            except ToolError:
                pass

        return parts

    @staticmethod
    def _fn_response(name: str, response: dict) -> types.Part:
        return types.Part.from_function_response(name=name, response=response)

    @staticmethod
    def _image_part(shot: dict) -> types.Part:
        png_bytes = base64.b64decode(shot["image_base64"])
        return types.Part.from_bytes(data=png_bytes, mime_type=shot["media_type"])

    @staticmethod
    def _extract_content(response: Any) -> types.Content | None:
        candidates = getattr(response, "candidates", None)
        if not candidates:
            return None
        return candidates[0].content

    @staticmethod
    def _log_text_parts(content: types.Content) -> None:
        for part in content.parts or []:
            if getattr(part, "text", None) and part.text.strip():
                logger.info("🤖 %s", part.text.strip())


# ----- module-level helpers ---------------------------------------------- #
def _fmt_args(args: dict) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in args.items())
