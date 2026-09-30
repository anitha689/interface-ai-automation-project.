# Computer-Use Automation System

A small automation system that operates a website the way a human would (via
screenshots and clicks, not an API), records a successful run as a reusable
artifact, and can replay that artifact deterministically without needing the
AI again.

Built against [Sauce Demo](https://www.saucedemo.com), a public demo
e-commerce site, used here as a stand-in for a real banking/business web app.

## What's in this repo

| File | Purpose |
|---|---|
| `agent_loop.py` | The live agent. Uses an LLM (Gemini) to look at the page and decide what to click/type, step by step, until the goal is reached. |
| `sample_artifact.json` | A saved "recipe" of a successful run (real output of `agent_loop.py`, in the format the replay engine expects). |
| `replay_engine.py` | Reads an artifact and replays it exactly, using Playwright only — no AI calls, so it's fast, cheap, and deterministic. |
| `safety_guardrails.py` | Checks every step before it runs: allowed domains only, no unrecognized action types, and a keyword blocklist for irreversible actions (payments, deletions, etc). |
| `evidence_logger.py` | Saves a screenshot and a structured log entry for every step of every run, into a timestamped folder under `evidence/`. |
| `escalation.py` | Writes a clear `ESCALATION.json` ticket whenever a run is blocked by a safety rule or fails unexpectedly, so a human can review and decide what to do next. |
| `evidence/` | Real run output: screenshots + logs from both a successful run and a deliberately-broken run (to prove escalation works). |

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install playwright google-generativeai
playwright install chromium
```

You'll also need a free Gemini API key (only required for `agent_loop.py`,
the live discovery run — replay does not need it).

## Running it

**Live discovery run** (uses the AI to figure out the steps, then saves an artifact):
```bash
python agent_loop.py
```

**Deterministic replay** (reads a saved artifact and repeats it, no AI needed):
```bash
python replay_engine.py sample_artifact.json
```

Each replay creates a new folder under `evidence/` with screenshots and a
`run_log.json`. If anything goes wrong, an `ESCALATION.json` file is written
in that same folder describing what happened and what to check.

See `REPORT.md` for design details, tradeoffs, and what was cut due to time.