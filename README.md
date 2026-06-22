# Website Automation Agent

An intelligent browser-automation agent — a mini version of tools like
[Browser Use](https://github.com/browser-use/browser-use). It controls a real
Chromium browser through [Playwright](https://playwright.dev/) and autonomously
fills a web form.

**No API key. No LLM. No cost.** Element detection is fully deterministic, so the
agent runs anywhere, every time — ideal for a reliable live demo.

Given a target page, the agent:

1. Opens a browser and navigates to the URL.
2. Intelligently identifies the form's **Name** and **Description** fields.
3. Fills them in — no hard-coded selectors, no manual intervention.

> **Target task:** navigate to
> `https://ui.shadcn.com/docs/forms/react-hook-form`, find the Name and
> Description fields, and fill them automatically.
>
> On the live page the primary field is labelled **"Bug Title"** (not literally
> "Name"). The agent handles this — it matches the closest equivalent field by
> label/placeholder/name and falls back to the form's primary text input, so it
> still completes the task.

---

## How it works (in one picture)

```
            ┌──────────────────────────────────────────────┐
            │                  main.py                      │
            │   load config · setup logging · run agent     │
            └───────────────┬──────────────────────────────┘
                            │
              ┌─────────────▼─────────────┐      composes the tools:
              │     AutomationAgent       │  ───────────────────────────────►
              │  deterministic decision   │   open_browser, navigate_to_url,
              │  logic: detect → score →  │   take_screenshot, get_form_fields,
              │  decide → fill → verify   │   click_on_screen, double_click,
              └─────────────┬─────────────┘   send_keys, scroll
                            │  field data + screenshots
              ┌─────────────▼─────────────┐  ◄───────────────────────────────
              │     BrowserController      │
              │   (Playwright / Chromium) │
              └───────────────────────────┘
```

The agent **detects** every field (via the page's own DOM: labels, placeholders,
names, types + centre coordinates), **scores** each one to decide which is the
Name field and which is the Description field, then **acts** (coordinate click +
type) and **verifies** the result. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for
the full design write-up.

---

## Required capabilities (assignment checklist)

| Required tool      | Where it lives                                            |
| ------------------ | --------------------------------------------------------- |
| `open_browser`     | `BrowserController.open_browser`                          |
| `navigate_to_url`  | `BrowserController.navigate_to_url`                       |
| `take_screenshot`  | `BrowserController.take_screenshot`                       |
| `click_on_screen(x, y)` | `BrowserController.click_on_screen`                  |
| `double_click`     | `BrowserController.double_click`                          |
| `send_keys`        | `BrowserController.send_keys`                             |
| `scroll`           | `BrowserController.scroll`                                |
| *(bonus)* `get_form_fields` | intelligent element detection used to find fields |

All seven required tools are real, composable methods. The agent uses
`click_on_screen(x, y)` with coordinates discovered by `get_form_fields`,
`scroll` when a field is below the fold, and `double_click` when a field already
contains text (to select it before overwriting).

---

## Setup

### 1. Prerequisites
- **Python 3.10+** (tested on 3.13)
- That's it — **no API key required.**

### 2. Install dependencies

```bash
# (optional but recommended) create a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

# Download the Chromium browser Playwright drives
python -m playwright install chromium
```

### 3. (Optional) Configure

The agent runs with sensible defaults. Only create a `.env` if you want to change
the target URL, the values it types, or the browser mode:

```bash
cp .env.example .env      # Windows: copy .env.example .env
```

See `.env.example` for every option.

---

## Run

```bash
python main.py
```

With `HEADLESS=false` (the default) a real browser window opens so you can watch
the agent work — ideal for a live demo. Set `HEADLESS=true` to run invisibly.

### What you'll see
- Live, structured logs of every decision and action in the terminal.
- An `artifacts/` folder containing:
  - **screenshots** before and after filling (`01_before_fill.png`, `02_after_fill.png`),
  - a `final_state.png`,
  - a full `agent.log`.

Real log excerpt from a run against the live page:

```
INFO agent.browser Navigating to https://ui.shadcn.com/docs/forms/react-hook-form
INFO agent.brain   Loaded page: React Hook Form - shadcn/ui
INFO agent.browser Saved screenshot -> artifacts/01_before_fill.png
INFO agent.brain   No description field visible yet; scrolling to look further down.
INFO agent.browser Scroll down by 400
INFO agent.brain   Detected description field -> label='Description' at (640, 524) [score=12.0]
INFO agent.brain   Detected name field -> label='Bug Title' at (640, 398) [score=5.0]
INFO agent.browser Click at (640, 398)
INFO agent.browser Typing 'Login button broken on mobile' (clear_first=True)
INFO agent.brain   Verify name field -> value now: 'Login button broken on mobile'
INFO agent.brain   ✅ Filled 2 field(s): Name, Description.
```

---

## Project layout

```
.
├── main.py               # entry point: config, logging, run the agent
├── config.py             # env-var driven settings (Settings dataclass)
├── requirements.txt
├── .env.example          # optional configuration template
├── README.md
├── ARCHITECTURE.md       # design decisions & agent workflow
└── agent/
    ├── __init__.py
    ├── browser_tools.py  # Playwright wrapper = the tool implementations
    └── agent.py          # deterministic detect → decide → fill logic
```

---

## Configuration reference

| Variable            | Default                                               | Meaning                                  |
| ------------------- | ----------------------------------------------------- | ---------------------------------------- |
| `TARGET_URL`        | `https://ui.shadcn.com/docs/forms/react-hook-form`    | Page to automate                         |
| `NAME_VALUE`        | `Jane Doe`                                             | Text typed into the Name field           |
| `DESCRIPTION_VALUE` | *(a default sentence)*                                | Text typed into the Description field     |
| `HEADLESS`          | `false`                                               | Show (`false`) or hide (`true`) the browser |
| `VIEWPORT_WIDTH`    | `1280`                                                | Browser width (px)                       |
| `VIEWPORT_HEIGHT`   | `800`                                                 | Browser height (px)                      |
| `ACTION_TIMEOUT_MS` | `30000`                                               | Per-action timeout (ms)                  |
| `ARTIFACTS_DIR`     | `artifacts`                                           | Where screenshots + logs are written     |

---

## Troubleshooting

| Symptom | Fix |
| ------- | --- |
| `playwright ... Executable doesn't exist` | Run `python -m playwright install chromium`. |
| Browser never opens | Ensure `HEADLESS=false`; check the log for launch errors. |
| The page label isn't literally "Name" | Expected — the live page uses "Bug Title". The agent matches by keyword (name/title/subject) and falls back to the primary text input, so it still fills the form. |
| Page slow to load / timeout | Increase `ACTION_TIMEOUT_MS` in `.env`. |

---

## Notes on safety & scope

- The agent **does not submit** the form — it only fills the fields, matching the
  assignment.
- Errors (timeouts, missing elements, out-of-viewport clicks) are caught and
  logged so the agent fails gracefully instead of crashing.
- No secrets, no network calls to any third-party API.
