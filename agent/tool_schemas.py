"""
tool_schemas.py
===============
Function declarations for every tool exposed to Gemini. The model reads these
descriptions to decide *which* tool to call and *how* to fill its arguments — the
decision-making is the model's, not ours, so the wording here is the only place
we "teach" the agent how its hands work.

Format note
-----------
These dicts follow Gemini's ``FunctionDeclaration`` schema (a subset of OpenAPI):
``type`` values are the upper-case Gemini ``Type`` enum (``OBJECT``, ``STRING``,
``INTEGER``, ``BOOLEAN``). No-argument tools omit ``parameters`` entirely. The
list is wrapped into a ``types.Tool`` inside agent.py.

Each ``name`` maps 1:1 to a method on ``BrowserController`` (see agent.py for the
dispatch table).
"""

from __future__ import annotations

TOOLS: list[dict] = [
    {
        "name": "open_browser",
        "description": (
            "Initialise and launch the Chromium browser instance. Must be called "
            "once before any other browser tool. Safe to call again (it is a no-op "
            "if the browser is already running)."
        ),
    },
    {
        "name": "navigate_to_url",
        "description": "Direct the browser to a specific URL and wait for the page to load.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": {"type": "STRING", "description": "The fully-qualified URL to open."}
            },
            "required": ["url"],
        },
    },
    {
        "name": "take_screenshot",
        "description": (
            "Capture the current state of the browser viewport. The resulting image "
            "is returned to you so you can visually inspect the page and decide what "
            "to do next. Take a screenshot whenever you are unsure what the page shows."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "label": {
                    "type": "STRING",
                    "description": "Short label used in the saved screenshot filename.",
                }
            },
        },
    },
    {
        "name": "get_form_fields",
        "description": (
            "Inspect the page and return every visible input, textarea and editable "
            "field, each with its label, placeholder, name, id, type, current value "
            "and the exact centre (x, y) pixel coordinates to click. Use this raw page "
            "data to REASON about which field is which — you decide which one is the "
            "Name/primary field and which is the Description. It gives you reliable "
            "coordinates to pass to click_on_screen."
        ),
    },
    {
        "name": "click_on_screen",
        "description": (
            "Perform a single left-mouse click at viewport pixel coordinates (x, y). "
            "Use this to focus a form field (using coordinates from get_form_fields) or "
            "to press a button visible in the screenshot."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "x": {"type": "INTEGER", "description": "Horizontal pixel coordinate."},
                "y": {"type": "INTEGER", "description": "Vertical pixel coordinate."},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "double_click",
        "description": (
            "Perform a double-click at viewport pixel coordinates (x, y). Useful for "
            "selecting an existing word inside a field before overwriting it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "x": {"type": "INTEGER", "description": "Horizontal pixel coordinate."},
                "y": {"type": "INTEGER", "description": "Vertical pixel coordinate."},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "send_keys",
        "description": (
            "Type text into the currently focused element. Click a field first to focus "
            "it. Set clear_first=true to overwrite any existing content, and "
            "press_enter=true to submit after typing."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "text": {"type": "STRING", "description": "The text to type."},
                "clear_first": {
                    "type": "BOOLEAN",
                    "description": "Select-all and delete before typing (overwrite).",
                },
                "press_enter": {
                    "type": "BOOLEAN",
                    "description": "Press Enter after typing.",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "scroll",
        "description": (
            "Scroll the page to reveal hidden elements. Direction is one of "
            "'down', 'up', 'left', 'right'. amount is in pixels. Re-run get_form_fields "
            "after scrolling because coordinates are viewport-relative."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "direction": {
                    "type": "STRING",
                    "enum": ["down", "up", "left", "right"],
                    "description": "Scroll direction.",
                },
                "amount": {"type": "INTEGER", "description": "Distance in pixels."},
            },
            "required": ["direction"],
        },
    },
    {
        "name": "finish",
        "description": (
            "Call this only when you have verified the task is complete (the target "
            "fields contain your text). Provide a short summary of what you did."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "summary": {
                    "type": "STRING",
                    "description": "A short summary of the completed task.",
                }
            },
            "required": ["summary"],
        },
    },
]
