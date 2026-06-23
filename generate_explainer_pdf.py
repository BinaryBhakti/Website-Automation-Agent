"""
generate_explainer_pdf.py
==========================
Renders a dark-mode, viva-ready explainer PDF for the Website Automation Agent.

It builds a styled HTML document and prints it to PDF using the same headless
Chromium that Playwright already manages (so there are no extra dependencies):

    python generate_explainer_pdf.py

Output: Website_Automation_Agent_Explained.pdf
"""

from __future__ import annotations

import os

from playwright.sync_api import sync_playwright

OUTPUT = "Website_Automation_Agent_Explained.pdf"

HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
  :root {
    --bg:        #0d1117;
    --bg-soft:   #161b22;
    --card:      #1c2230;
    --border:    #2b3343;
    --text:      #e6edf3;
    --muted:     #9aa7b4;
    --accent:    #58c4dc;   /* cyan  */
    --green:     #7ee787;
    --amber:     #f0c674;
    --pink:      #ff7b9c;
    --code-bg:   #0a0e14;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: var(--bg); }
  body {
    color: var(--text);
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 12px;
    line-height: 1.6;
    padding: 16mm 15mm;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }

  /* ---- cover header ---- */
  .cover {
    background: linear-gradient(135deg, #14304a 0%, #1c2230 60%, #241a33 100%);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 26px 28px;
    margin-bottom: 22px;
  }
  .cover .kicker { color: var(--accent); font-weight: 600; letter-spacing: .14em;
                   text-transform: uppercase; font-size: 10.5px; }
  .cover h1 { margin: 8px 0 6px; font-size: 27px; line-height: 1.2; }
  .cover p  { margin: 0; color: var(--muted); font-size: 12.5px; }
  .cover .tags { margin-top: 14px; display: flex; flex-wrap: wrap; gap: 7px; }
  .tag { font-size: 10px; padding: 3px 9px; border-radius: 999px;
         background: rgba(88,196,220,.12); border: 1px solid rgba(88,196,220,.35);
         color: var(--accent); }

  h2 { font-size: 16px; margin: 22px 0 8px; padding-bottom: 6px;
       border-bottom: 1px solid var(--border); color: #fff; }
  h2 .n { color: var(--accent); font-weight: 700; margin-right: 8px; }
  h3 { font-size: 12.8px; margin: 14px 0 4px; color: var(--green); }

  p { margin: 6px 0; }
  ul, ol { margin: 6px 0 6px 0; padding-left: 20px; }
  li { margin: 3px 0; }
  b, strong { color: #fff; }
  .muted { color: var(--muted); }

  code { font-family: "Consolas", "SF Mono", monospace; font-size: 11px;
         background: var(--code-bg); border: 1px solid var(--border);
         border-radius: 5px; padding: 1px 5px; color: #cfe9ef; }
  pre { background: var(--code-bg); border: 1px solid var(--border);
        border-radius: 10px; padding: 12px 14px; overflow: hidden;
        font-family: "Consolas", "SF Mono", monospace; font-size: 10.6px;
        line-height: 1.5; color: #cfe9ef; white-space: pre; }

  .card { background: var(--card); border: 1px solid var(--border);
          border-radius: 12px; padding: 14px 16px; margin: 10px 0; }

  table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 11px; }
  th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--border);
           vertical-align: top; }
  th { color: var(--accent); font-weight: 600; background: var(--bg-soft); }
  tr:last-child td { border-bottom: none; }

  .concept { margin: 9px 0; }
  .concept .badge { display: inline-block; min-width: 22px; text-align: center;
        font-weight: 700; color: #04222a; background: var(--accent);
        border-radius: 6px; padding: 1px 6px; margin-right: 8px; font-size: 11px; }
  .concept h3 { display: inline; color: #fff; }

  .callout { border-left: 3px solid var(--amber); background: rgba(240,198,116,.08);
             padding: 9px 14px; border-radius: 0 10px 10px 0; margin: 12px 0; }
  .callout.green { border-left-color: var(--green); background: rgba(126,231,135,.08); }

  .avoid-break { break-inside: avoid; }
  footer { margin-top: 24px; padding-top: 10px; border-top: 1px solid var(--border);
           color: var(--muted); font-size: 10px; text-align: center; }
</style>
</head>
<body>

  <div class="cover">
    <div class="kicker">Assignment 04 &middot; Viva Notes</div>
    <h1>Website Automation Agent</h1>
    <p>An autonomous, AI-driven browser agent that fills web forms by itself &mdash;
       powered by Google&nbsp;Gemini (a multimodal LLM) in a perceive&rarr;think&rarr;act loop.</p>
    <div class="tags">
      <span class="tag">Python</span>
      <span class="tag">Playwright</span>
      <span class="tag">Google Gemini</span>
      <span class="tag">Function Calling</span>
      <span class="tag">Vision / Multimodal</span>
      <span class="tag">Agentic Loop</span>
    </div>
  </div>

  <h2><span class="n">1</span>What the project is</h2>
  <p><b>An AI agent that controls a real web browser by itself to fill out a form.</b>
     It is a mini version of tools like "Browser Use" / computer-use agents. You give it
     a URL and a goal in plain English, and a <b>Generative-AI model (Gemini)</b> looks
     at the page, reasons about it, and drives Chromium &mdash; clicking, typing,
     scrolling &mdash; until the task is done. <b>Nothing is hardcoded</b>: the AI decides
     every action.</p>
  <p class="muted">Target task: open <code>https://ui.shadcn.com/docs/forms/react-hook-form</code>,
     identify the form fields, and fill the Name and Description fields automatically.</p>

  <h2><span class="n">2</span>The big idea: an "agent", not a script</h2>
  <p>A normal <b>script</b> is rigid ("click <code>#name</code>, type X") and breaks when the
     page changes. An <b>agent</b> follows a <b>perceive &rarr; think &rarr; act</b> loop,
     like a human:</p>
  <pre>   PERCEIVE  take a screenshot + read the form fields        &lt;---+
                          |                                         |
   THINK     Gemini reasons: "which field is Name? which is        |
             Description? what should I type?"                      |
                          |                                         |
   ACT       call a tool (click / type / scroll)  -----------------+
   repeat until the AI calls "finish"</pre>
  <p>This loop is the heart of the project and the core GenAI idea &mdash; an
     <b>agentic loop</b> (a ReAct-style "Reason + Act" agent).</p>

  <h2><span class="n">3</span>Architecture (files &amp; roles)</h2>
  <pre>main.py            entry point: loads config, logging, starts the agent
config.py          settings from .env (API key, model chain, URL, task)
agent/
 |- browser_tools.py   the "hands &amp; eyes": Playwright wrapper (the tools)
 |- tool_schemas.py    tool descriptions, written FOR the AI to read
 |- agent.py           the "brain": the Gemini reasoning loop</pre>
  <p>Think <b>brain + hands</b>: the model <i>decides</i>
     (<code>agent.py</code>), the code <i>executes</i> (<code>browser_tools.py</code>).
     This separation is a key agent-design principle.</p>

  <h2><span class="n">4</span>Generative-AI logic implemented</h2>
  <p class="muted">These are the GenAI concepts to know cold for the viva.</p>

  <div class="card avoid-break">
    <div class="concept"><span class="badge">1</span><h3>LLM-powered agentic loop (Reason + Act)</h3>
      <p>The model is called repeatedly in a loop; each turn it reasons and picks one
         action, the result is fed back, and it reasons again. Ends when it calls the
         <code>finish</code> tool. <code>MAX_STEPS</code> is a safety cap.</p></div>

    <div class="concept"><span class="badge">2</span><h3>Tool Use / Function Calling &mdash; the most important concept</h3>
      <p>Instead of plain text, the model outputs a structured <b>function call</b> such as
         <code>click_on_screen(x=640, y=398)</code>. Tools are <i>declared</i> to Gemini in
         <code>tool_schemas.py</code> (name + description + typed parameters). The model
         <b>chooses</b> which tool and which arguments &mdash; that is the intelligence.
         The 9 tools: open_browser, navigate_to_url, take_screenshot, get_form_fields,
         click_on_screen, double_click, send_keys, scroll, finish.</p></div>

    <div class="concept"><span class="badge">3</span><h3>Multimodal AI / Vision</h3>
      <p>Gemini can read images. After each action we send a fresh <b>screenshot</b> as an
         image, so the model literally <b>sees</b> the page and reasons over it &mdash; a
         "computer-use"-style agent.</p></div>

    <div class="concept"><span class="badge">4</span><h3>Prompt Engineering (system prompt)</h3>
      <p>The <code>SYSTEM_PROMPT</code> is the model's job description: it frames the task,
         the method (look&rarr;reason&rarr;act&rarr;verify), and hands decisions to the AI
         ("you &mdash; not any script &mdash; decide which element is which").</p></div>

    <div class="concept"><span class="badge">5</span><h3>Grounding with structured data</h3>
      <p>Guessing pixel coordinates from an image is unreliable, so
         <code>get_form_fields</code> runs JavaScript to return each field's label,
         placeholder, type and exact centre <code>(x, y)</code>. The model still
         <i>decides</i> which field is which; we only feed it accurate raw facts.</p></div>

    <div class="concept"><span class="badge">6</span><h3>Conversation-state management</h3>
      <p>The API is <b>stateless</b>, so each turn we resend the full history (messages,
         the model's prior tool calls, tool results, the latest screenshot). That is the
         agent's "memory" of what it has already done.</p></div>

    <div class="concept"><span class="badge">7</span><h3>Multi-model fallback (reliability)</h3>
      <p>Each Gemini model has its own quota. On <code>429 RESOURCE_EXHAUSTED</code> (or a
         500/503) the agent rotates to the next model in a chain
         (2.5-flash &rarr; 2.0-flash &rarr; 2.5-flash-lite &rarr; 2.0-flash-lite),
         "sticky" once it falls back.</p></div>

    <div class="concept"><span class="badge">8</span><h3>Token-aware context management</h3>
      <p>Old screenshots are pruned from history so only the <b>latest</b> image is resent
         each turn &mdash; images are token-heavy, and this keeps the free-tier quota from
         draining. The model still sees the current page.</p></div>

    <div class="concept"><span class="badge">9</span><h3>Robust, self-correcting behaviour</h3>
      <p>Tool errors (timeout, off-screen element) are returned to the model <b>as
         feedback</b>, so it adapts (e.g. scroll and retry) instead of crashing.</p></div>
  </div>

  <h2><span class="n">5</span>How one full run plays out</h2>
  <p>On the live page the field is labelled <b>"Bug Title"</b>, not literally "Name" &mdash;
     the AI works that out itself. A typical trajectory:</p>
  <ol>
    <li><code>open_browser</code> &rarr; Chromium launches.</li>
    <li><code>navigate_to_url(target)</code> &rarr; page loads; screenshot returned to model.</li>
    <li><code>get_form_fields()</code> &rarr; a "Bug Title" input + a "Description" textarea, with coordinates.</li>
    <li>Model <b>reasons</b>: "Bug Title is the primary/name field; the textarea is the description."</li>
    <li><code>click_on_screen(x, y)</code> on Bug Title &rarr; <code>send_keys("Login button broken on mobile")</code>.</li>
    <li>Description is below the fold &rarr; <code>scroll</code> down, then <code>get_form_fields()</code> again
        (coordinates change after scrolling &mdash; the model knows to re-check).</li>
    <li><code>click_on_screen</code> + <code>send_keys</code> on Description.</li>
    <li><code>get_form_fields()</code> again to <b>verify</b> the values.</li>
    <li><code>finish("Filled the title and description fields.")</code> &rarr; loop ends.</li>
  </ol>
  <p class="muted">The exact steps are the model's choice each run &mdash; that's the point.
     It is not a fixed script.</p>

  <h2><span class="n">6</span>Design choices (likely questions)</h2>
  <ul>
    <li><b>Why Playwright?</b> First-class Python API, auto-waits for elements, reliable
        screenshots, easy Chromium management. (Recommended by the assignment.)</li>
    <li><b>Why feed coordinates instead of pure vision?</b> Reliability &mdash; the model still
        decides; we give it accurate pixel targets so <code>click_on_screen(x, y)</code> lands.
        <code>device_scale_factor=1</code> makes screenshot pixels map 1:1 to clicks.</li>
    <li><b>Why is this "intelligent"?</b> Element identification and decisions are done by AI
        reasoning over labels + types + the screenshot, not hardcoded <code>if</code> rules.</li>
    <li><b>Why a manual loop, not auto function-calling?</b> So we can inject a fresh screenshot
        between turns (vision feedback) and log every decision.</li>
  </ul>

  <h2><span class="n">7</span>The required tools &rarr; where they live</h2>
  <p class="muted">All in <code>agent/browser_tools.py</code>, exposed to the AI as function calls.</p>
  <table>
    <tr><th>Required tool</th><th>What it does</th></tr>
    <tr><td><code>open_browser</code></td><td>launches Chromium</td></tr>
    <tr><td><code>navigate_to_url</code></td><td>goes to a URL</td></tr>
    <tr><td><code>take_screenshot</code></td><td>captures the viewport (also fed to the AI as vision)</td></tr>
    <tr><td><code>click_on_screen(x, y)</code></td><td>mouse click at coordinates</td></tr>
    <tr><td><code>double_click</code></td><td>double-click (select existing text before overwriting)</td></tr>
    <tr><td><code>send_keys</code></td><td>type text into the focused field</td></tr>
    <tr><td><code>scroll</code></td><td>scroll to reveal hidden fields</td></tr>
    <tr><td><code>get_form_fields</code> <span class="muted">(bonus)</span></td><td>intelligent element detection feeding the AI</td></tr>
  </table>

  <h2><span class="n">8</span>30-second summary to open your viva</h2>
  <div class="callout green">
    "It's an autonomous AI agent that fills web forms. It uses Google Gemini &mdash; a
    multimodal LLM &mdash; in an agentic perceive-think-act loop. The required browser tools
    (open, navigate, screenshot, click, type, scroll, double-click) are exposed to the model
    via <b>function calling</b>; Gemini looks at a <b>screenshot</b> of the page plus structured
    field data, <b>reasons</b> about which field is which, and <b>decides</b> what action to take
    each step &mdash; nothing is hardcoded. It feeds errors back to the model so it self-corrects,
    and it falls back across multiple Gemini models if one hits its quota."
  </div>

  <footer>Website Automation Agent &mdash; Viva notes &middot; github.com/BinaryBhakti/Website-Automation-Agent</footer>

</body>
</html>
"""


def main() -> None:
    out_path = os.path.abspath(OUTPUT)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(HTML, wait_until="networkidle")
        page.pdf(
            path=out_path,
            format="A4",
            print_background=True,   # keep the dark background
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        browser.close()
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
