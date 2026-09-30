"""
escalation.py
 
Human-in-the-loop escalation layer.
 
Whenever the agent (live or replay) hits something it cannot safely
handle -- a safety violation, an unexpected error, or a step that
doesn't match what's on the page -- this module writes a clear
"escalation ticket" file. A human reviewer can open this file, see
exactly what happened and why, and decide what to do next, instead of
the agent guessing or failing silently.
"""
 
import json
import os
from datetime import datetime
 
 
def create_escalation(run_dir, step_number, reason, category, screenshot=None, suggested_action=None):
    """
    Write an escalation ticket to disk for a human to review.
 
    run_dir: the same evidence folder this run is already logging into
    step_number: which step triggered the escalation
    reason: human-readable explanation of what went wrong
    category: "safety_block", "execution_error", or "unrecognized_state"
    screenshot: filename of the screenshot at the moment of escalation (if any)
    suggested_action: a plain-language suggestion for what the human could try
    """
    ticket = {
        "escalation_id": f"esc_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "step_number": step_number,
        "category": category,
        "reason": reason,
        "screenshot": screenshot,
        "suggested_action": suggested_action or "Review the screenshot and decide whether to retry, edit the artifact, or abandon this run.",
        "status": "awaiting_human_review",
        "created_at": datetime.now().isoformat(),
    }
 
    ticket_path = os.path.join(run_dir, "ESCALATION.json")
    with open(ticket_path, "w") as f:
        json.dump(ticket, f, indent=2)
 
    print("=" * 50)
    print("ESCALATION RAISED -- HUMAN REVIEW NEEDED")
    print(f"  Step: {step_number}")
    print(f"  Category: {category}")
    print(f"  Reason: {reason}")
    print(f"  Details saved to: {ticket_path}")
    print("=" * 50)
 
    return ticket_path