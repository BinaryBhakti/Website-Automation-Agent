# Architecture & Design

This document explains the design decisions behind the Website Automation Agent
and walks through how the agent perceives, thinks, and acts.

---

## 1. Goal

Build an autonomous agent that drives a real browser to complete a web task —
finding and filling the **Name** and **Description** form fields on
`https://ui.shadcn.com/docs/forms/react-hook-form` — without hard-coded scripts
or human intervention. Crucially, the *decisions* (which element is which, what
to type, when to scroll, when it is done) are made by an **AI model**, not by
fixed rules in our code.

---

## 2. Design principles

1. **The AI does the thinking.** The agent code is "hands and eyes"; Google
   Gemini is the "brain". We never hard-code which field is the Name field or
   what to type — the model reasons it out from what it sees.
2. **Separation of concerns.** Browser control and decision-making are
   independent modules. You can swap the model or the browser layer in isolation.
3. **Modular, composable tools.** Each capability is a small, single-purpose
   function exposed to the model as a typed tool — exactly the toolbox the
   assignment asks for.
4. **Perceive → decide → act loop.** After every action the model receives a
   fresh screenshot, so it always reasons over the current page state.
5. **Fail soft & observable.** Tool failures become feedback to the model (not
   crashes); every decision, action and the model's own reasoning is logged, and
   each step is saved as a screenshot for a fully auditable run.

---

## 3. Component overview

```
config.py              Settings dataclass sourced from environment variables.
agent/browser_tools.py BrowserController — the Playwright-backed tool implementations.
agent/tool_schemas.py  Gemini function declarations for those tools.
agent/agent.py         AutomationAgent — the Gemini reasoning / function-calling loop.
main.py                Wiring: config + logging + lifecycle.
```

### 3.1 `BrowserController` (the hands & eyes)
A stateful wrapper around a single Playwright Chromium page, used as a context
manager so the browser is always cleaned up. It implements the required tools:

| Tool | Implementation detail |
| ---- | --------------------- |
| `open_browser` | Launches Chromium with `device_scale_factor=1` so screenshot pixels map **1:1** to click coordinates. |
| `navigate_to_url` | `goto(..., wait_until="domcontentloaded")` then settles on network idle. |
| `take_screenshot` | Returns base64 PNG (sent to the model as an image) **and** saves a numbered file to `artifacts/`. |
| `click_on_screen(x, y)` | `mouse.click`, guarded against out-of-viewport coordinates. |
| `double_click(x, y)` | `mouse.dblclick` — to select existing text before overwriting. |
| `send_keys(text, …)` | Types into the focused element; optional `clear_first` / `press_enter`. |
| `scroll(direction, amount)` | `mouse.wheel` in any direction. |
| `get_form_fields` | Runs JS in the page to enumerate visible inputs/textareas with label, placeholder, name, id, type, value **and centre coordinates** — raw data the model reasons over. |

### 3.2 `tool_schemas.py` (the contract)
Gemini `FunctionDeclaration` definitions, one per tool. The descriptions are
written *for the model*: they explain what each tool does and nudge it to read
`get_form_fields` and decide for itself which field is which. The model picks the
tool and the arguments — the schemas never encode the answer.

### 3.3 `AutomationAgent` (the brain loop)
A manual [function-calling loop](https://ai.google.dev/gemini-api/docs/function-calling)
against the Gemini API (`google-genai` SDK):

- **System prompt** frames the task and the general method, then explicitly hands
  the decisions to the model ("you — not any script — decide which element is
  which and what to type").
- Each turn we send the running conversation; Gemini returns one or more
  `function_call` parts (plus optional reasoning text, which we log).
- We dispatch each call to the matching `BrowserController` method and return a
  `function_response`. For visually-significant actions we also attach a **fresh
  screenshot** so the model perceives the new state.
- The loop ends when the model calls `finish`, or at `MAX_STEPS` (a safety cap).

Because the SDK is given *declarations* (not Python callables), automatic
function calling is off — we run the manual loop, which keeps every action
logged and lets us inject screenshots between turns.

---

## 4. Agent workflow (a typical run)

```
[model] open_browser
[model] navigate_to_url(TARGET_URL)             ← screenshot returned
[model] get_form_fields()                        ← raw fields + coordinates
[model] reasons: "Bug Title" = primary/name, "Description" textarea = description
[model] click_on_screen(name.x, name.y) → send_keys("…", clear_first=true)
[model] scroll(down) → get_form_fields()         ← description was below the fold
[model] click_on_screen(desc.x, desc.y) → send_keys("…")
[model] get_form_fields() / take_screenshot()    ← verifies the values
[model] finish("Filled the title and description fields.")
```

The exact sequence is the model's choice — the above is just a representative
trajectory. On the live page the Description field is below the fold, so the
model has to scroll and re-read the fields, which it works out on its own.

---

## 5. Why these choices

- **Playwright over Puppeteer/Selenium.** First-class Python sync API, robust
  auto-waiting, reliable screenshots, simple Chromium management. Recommended by
  the assignment.
- **Gemini with function calling + vision.** Coordinate-based control
  (`click_on_screen`) is a *computer-use*-style problem; a multimodal model that
  can both see screenshots and call typed tools is the natural fit, and function
  calling keeps every action structured and logged.
- **`get_form_fields` as perception, not decision.** Rather than make the model
  guess pixel positions from an image, we let the page report each element's
  centre and labels. The model still decides *which* field is which and *what* to
  type — we only feed it accurate raw data to act on. This combines selector-grade
  reliability with the required coordinate-based clicking.
- **Screenshots in the loop.** Feeding the model a fresh image after each action
  closes the perceive→decide→act loop, so it can recover from surprises (a field
  scrolled out of view, an unexpected layout) rather than following a fixed plan.

---

## 6. Error handling & robustness

| Risk | Mitigation |
| ---- | ---------- |
| Network / navigation timeout | Per-action timeout; `ToolError` returned to the model as a tool error. |
| Element not found / off-screen | Out-of-viewport click guard; the model scrolls and re-reads fields. |
| Field labelled differently than "Name" | The model reasons from labels/types (e.g. treats "Bug Title" as the primary field). |
| Model loops without finishing | `MAX_STEPS` cap ends the run gracefully. |
| Model replies with text but no tool call | The loop nudges it to continue or finish. |
| Any unexpected exception in a tool | Caught, logged with traceback, returned as an error tool result. |
| Resource leaks | `BrowserController` is a context manager; the browser is always closed. |

---

## 7. Possible extensions

- A `press_key` tool for Tab-between-fields navigation and arbitrary shortcuts.
- Optional form submission + post-submit verification as a separate step.
- Caching/condensing old screenshots to reduce token usage on long runs.
- Letting the model drive entirely from screenshots (drop `get_form_fields`) for
  a pure computer-use experiment.
- Parameterising richer tasks via the `TASK` setting (the loop is already
  task-driven).
