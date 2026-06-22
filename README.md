# Website Automation Agent

An intelligent, **AI-driven** browser-automation agent — a mini version of tools
like [Browser Use](https://github.com/browser-use/browser-use). It controls a
real Chromium browser through [Playwright](https://playwright.dev/) and uses
**Google Gemini** to do the actual thinking.

The agent is genuinely autonomous: **the model decides everything** — which
element is the Name field, which is the Description field, what to type, when to
scroll, and when the task is done. None of those decisions are hard-coded; the
Python code only carries out the browser actions the AI asks for and shows it the
result.

Given a target page, the agent:

1. Opens a browser and navigates to the URL.
2. Looks at the page (screenshots + raw field data) and **reasons** about the form.
3. Fills the Name and Description fields — no hard-coded selectors, no manual steps.

> **Target task:** navigate to
> `https://ui.shadcn.com/docs/forms/react-hook-form`, identify the Name and
> Description fields, and fill them automatically.
>
> On the live page the primary field is labelled **"Bug Title"** (not literally
> "Name"). The AI works that out on its own from the labels and field types.

---

## How it works (the agent loop)

```
            ┌──────────────────────────────────────────────┐
            │                  main.py                      │
            │   load config · setup logging · run loop      │
            └───────────────┬──────────────────────────────┘
                            │
              ┌─────────────▼─────────────┐   calls a tool each turn
              │     AutomationAgent       │  ───────────────────────────────►
              │  Gemini reasons over the  │   open_browser, navigate_to_url,
              │  screenshot + field data, │   take_screenshot, get_form_fields,
              │  then DECIDES the action  │   click_on_screen, double_click,
              └─────────────┬─────────────┘   send_keys, scroll, finish
                            │  result + fresh screenshot
              ┌─────────────▼─────────────┐  ◄───────────────────────────────
              │     BrowserController      │
              │   (Playwright / Chromium) │
              └───────────────────────────┘
```

Every turn: Gemini **sees** the page (the screenshot is sent to the model as an
image), **thinks**, and **acts** (emits a function call). We run that tool and
return the result — plus a fresh screenshot — so the model perceives the new
state. The loop repeats until the model calls `finish`. See
[`ARCHITECTURE.md`](ARCHITECTURE.md) for the full design write-up.

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
| *(bonus)* `get_form_fields` | raw element data the AI reasons over             |

The tools are exposed to Gemini as **function declarations**; the model chooses
which to call and with what arguments. It clicks via `click_on_screen(x, y)` using
coordinates from `get_form_fields`, `scroll`s when a field is below the fold, and
uses `double_click` when it judges it necessary.

---

## Setup

### 1. Prerequisites
- **Python 3.10+** (tested on 3.13)
- A **Google Gemini API key** — <https://aistudio.google.com/apikey>

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

### 3. Configure

```bash
# copy the template and fill in your key
cp .env.example .env      # Windows: copy .env.example .env
```

Edit `.env` and set at least:

```dotenv
GEMINI_API_KEY=AIza...
```

Everything else has sensible defaults (model, target URL, the free-form task,
headless mode, viewport, step limit). See `.env.example` for the full list.

---

## Run

```bash
python main.py
```

With `HEADLESS=false` (the default) a real browser window opens so you can watch
the agent reason and act — ideal for a live demo. Set `HEADLESS=true` to run
invisibly.

### What you'll see
- Live, structured logs of every decision and action — including the model's own
  reasoning text.
- An `artifacts/` folder with numbered **screenshots** per step, a
  `final_state.png`, and a full `agent.log`.

Example log excerpt:

```
INFO agent.brain   ─── Step 3/30 ───
INFO agent.brain   🤖 The form has a "Bug Title" input and a "Description" textarea.
                       I'll treat Bug Title as the Name field.
INFO agent.brain   Tool call: click_on_screen(x=640, y=398)
INFO agent.brain   Tool call: send_keys(text='Login button broken on mobile', clear_first=True)
INFO agent.brain   Tool call: scroll(direction='down', amount=400)
INFO agent.brain   Tool call: get_form_fields()
INFO agent.brain   Tool call: send_keys(text='The button does not respond on small screens.')
INFO agent.brain   ✅ Agent finished: Filled the Bug Title and Description fields.
```

---

## Project layout

```
.
├── main.py               # entry point: config, logging, run the agent
├── config.py             # env-var driven settings (Settings dataclass)
├── requirements.txt
├── .env.example          # configuration template
├── README.md
├── ARCHITECTURE.md       # design decisions & agent workflow
└── agent/
    ├── __init__.py
    ├── browser_tools.py  # Playwright wrapper = the tool implementations
    ├── tool_schemas.py   # function declarations handed to Gemini
    └── agent.py          # the Gemini reasoning loop (the "brain")
```

---

## Configuration reference

| Variable            | Default                                               | Meaning                                  |
| ------------------- | ----------------------------------------------------- | ---------------------------------------- |
| `GEMINI_API_KEY`    | *(required)*                                          | Your Google Gemini API key               |
| `GEMINI_MODEL`      | `gemini-2.5-flash`                                    | Model used for reasoning + vision        |
| `TARGET_URL`        | `https://ui.shadcn.com/docs/forms/react-hook-form`    | Page to automate                         |
| `TASK`              | *(fill Name + Description)*                            | Free-form goal the AI decides how to do  |
| `HEADLESS`          | `false`                                               | Show (`false`) or hide (`true`) the browser |
| `VIEWPORT_WIDTH`    | `1280`                                                | Browser width (px)                       |
| `VIEWPORT_HEIGHT`   | `800`                                                 | Browser height (px)                      |
| `MAX_STEPS`         | `30`                                                  | Safety cap on agent iterations           |
| `ACTION_TIMEOUT_MS` | `30000`                                               | Per-action timeout (ms)                  |
| `ARTIFACTS_DIR`     | `artifacts`                                           | Where screenshots + logs are written     |

---

## Troubleshooting

| Symptom | Fix |
| ------- | --- |
| `GEMINI_API_KEY is not set` | Create `.env` from `.env.example` and add your key. |
| `playwright ... Executable doesn't exist` | Run `python -m playwright install chromium`. |
| Browser never opens | Ensure `HEADLESS=false`; check the log for launch errors. |
| Agent loops or stops early | Raise `MAX_STEPS`, or try `GEMINI_MODEL=gemini-2.5-pro` for harder pages. |

---

## Notes on safety & scope

- The agent is instructed **not to submit** the form — it only fills the fields.
- The API key is read from the environment only and is never logged.
- Errors (timeouts, missing elements, out-of-viewport clicks) are caught and fed
  back to the model as tool errors so it can adapt instead of crashing.
