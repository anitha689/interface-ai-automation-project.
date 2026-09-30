# Report

## 1. Architecture

The system is split into two clearly separate paths, on purpose:

**Live path (uses AI):** `agent_loop.py` takes a screenshot of the current
page, extracts the interactive elements on it (buttons, inputs, links —
including their `data-test`, `id`, `name`, and visible text), and sends both
to an LLM along with the goal. The LLM responds with a single next action in
JSON (click, type, goto, or finish). The agent executes that action with
Playwright, logs it, and repeats until the goal is reached or a step limit is
hit. Every action taken during a successful run is recorded, in order, as an
**artifact** (see section 2).

**Replay path (no AI):** `replay_engine.py` takes a previously-saved
artifact and executes its steps directly with Playwright — no LLM call, no
"thinking." Before each step runs, it passes through `safety_guardrails.py`.
Every step's outcome (success, blocked, or failed) is recorded by
`evidence_logger.py`, and if something goes wrong, `escalation.py` writes a
ticket for a human to review.

The reason for this split: the LLM is only needed once, to *discover* how to
do something new. Once that path is known, repeating it should be fast,
cheap, and predictable — not re-decided by an AI every time.

## 2. Artifact schema

An artifact is a JSON file describing one successful task, as an ordered
list of steps:

```json
{
  "task_name": "login_to_saucedemo",
  "goal": "Log in and reach the products page",
  "target_site": "https://www.saucedemo.com",
  "created_at": "ISO timestamp",
  "status": "success",
  "steps": [
    {
      "step_number": 1,
      "action": "goto | type | click | finish",
      "selector": "CSS selector (or null for goto/finish)",
      "url": "used only for goto steps",
      "value": "text to type, or null",
      "description": "plain-language explanation of the step"
    }
  ]
}
```

Selectors prefer `data-test` attributes first (most stable), falling back to
`id`, then `name`, then visible text, since real apps don't always expose
`data-test` attributes the way Sauce Demo does.

## 3. Determinism & error handling

Replay is deterministic because it never asks an LLM what to do — it just
executes the saved selector/action/value triples in order, using Playwright.
The only variability comes from the live website itself (load times, etc.),
which is why each step is wrapped in error handling rather than assumed to
always succeed.

If a step fails (selector not found, timeout, element not clickable), the
replay engine stops immediately rather than guessing or skipping ahead — it
logs the failure with the exact error message and a screenshot, then raises
an escalation ticket. This was tested directly: a step's selector was
deliberately changed to a nonexistent one, and the system correctly stopped,
logged the failure, and produced an `ESCALATION.json` explaining what broke
and where (see `evidence/` for both a clean run and this induced-failure
run).

## 4. Heterogeneity & multi-tenant design

This prototype targets a single site (Sauce Demo) with a single set of test
credentials, but the design generalizes:

- **Different sites/tenants:** each artifact already stores its own
  `target_site` and selectors, so multiple artifacts (one per
  site/tenant/workflow) can coexist without code changes. A production
  version would key artifacts by `(tenant_id, task_name)` and store them in a
  small database or per-tenant folder instead of flat files.
- **Different accounts/credentials per tenant:** rather than hardcoding
  values like `standard_user` into the artifact, sensitive values (usernames,
  passwords, account numbers) should be referenced by placeholder name in the
  artifact (e.g. `"{{username}}"`) and substituted at replay time from a
  per-tenant secrets store, never stored in the artifact itself.
- **UI drift across tenants:** since the same logical task (e.g. "log in")
  may have different selectors on different tenants' instances of similar
  software, the discovery run (`agent_loop.py`) would need to run once per
  tenant to produce a tenant-specific artifact, rather than assuming one
  artifact works everywhere.

## 5. Escalation & handoff

Escalation is triggered in two cases: a safety rule blocking a step, or an
unexpected execution error. In both cases the system does not guess or
retry silently — it stops, saves the page screenshot at the moment of
failure, and writes an `ESCALATION.json` ticket containing: which step
failed, why, a suggested next action in plain language, and a status of
`awaiting_human_review`. This was verified with a real induced failure (see
`evidence/`), which correctly produced a ticket rather than crashing or
hanging.

In a production system, this ticket would be pushed to a queue or dashboard
a human operator monitors, rather than just written to disk.

## 6. Safety

Every step, whether from a live agent decision or a replayed artifact, passes
through `safety_guardrails.py` before execution:

- **Domain allowlist:** navigation is only permitted to pre-approved domains.
- **Action allowlist:** only recognized action types (`goto`, `type`,
  `click`, `finish`) are permitted; anything else is blocked.
- **Keyword blocklist:** steps whose description, selector, or value contain
  terms associated with irreversible actions (e.g. "delete," "pay now,"
  "purchase," "wire transfer") are blocked outright, regardless of what the
  AI or artifact says to do.

This means even if the LLM were to hallucinate a dangerous action, or an
artifact were tampered with, the guardrail layer would block it before
Playwright ever executes it.

## 7. Cuts

Given the scope of a take-home project, the following were deliberately
simplified or left out, and would be the next priorities in a production
version:

- **No credential vaulting:** the sample artifact stores test credentials
  in plain text for simplicity. A real version would never do this (see
  section 4).
- **Single demo site only:** only tested against Sauce Demo; multi-tenant
  selector drift handling is designed but not implemented.
- **Simple keyword-based safety, not semantic:** the safety blocklist is
  literal keyword matching, not a smarter intent classifier. This is
  intentionally conservative (fewer false negatives) but would need
  refinement to avoid over-blocking legitimate steps that happen to contain
  a blocked word.
- **No retry/self-healing logic:** if a selector breaks (e.g. the site
  changes its button IDs), the system escalates to a human rather than
  attempting to have the LLM re-discover a fix automatically. This was a
  deliberate choice for predictability within the project's time
  constraints, not a technical limitation.
- **Local file storage, not a queue/dashboard:** escalation tickets and
  evidence are written to local JSON files rather than pushed to a real
  monitoring system, appropriate for a prototype but not production scale.