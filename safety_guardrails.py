"""
safety_guardrails.py
 
Safety layer for the automation agent.
 
This module checks every action BEFORE it is executed (whether it
comes live from the AI agent, or from a replayed artifact) and blocks
anything that isn't explicitly allowed. This prevents the agent from
doing something dangerous or unintended, like submitting a real
payment, deleting an account, or navigating to an untrusted domain.
"""
 
# Only these URLs are allowed. The agent should never navigate anywhere else.
ALLOWED_DOMAINS = [
    "saucedemo.com",
    "www.saucedemo.com",
]
 
# Actions that are considered "safe" to perform without extra confirmation.
SAFE_ACTIONS = ["goto", "type", "click", "finish"]
 
# Selectors/text that should NEVER be clicked automatically, even if the
# AI suggests it -- these represent irreversible or sensitive actions.
BLOCKED_KEYWORDS = [
    "delete",
    "remove account",
    "pay now",
    "confirm payment",
    "submit payment",
    "wire transfer",
    "purchase",
    "buy now",
]
 
 
class SafetyViolation(Exception):
    """Raised when a proposed action violates a safety rule."""
    pass
 
 
def check_url(url):
    """Only allow navigation to pre-approved domains."""
    if not any(domain in url for domain in ALLOWED_DOMAINS):
        raise SafetyViolation(
            f"Blocked navigation to non-allowlisted URL: {url}"
        )
 
 
def check_action_type(action):
    """Only allow known, safe action types."""
    if action not in SAFE_ACTIONS:
        raise SafetyViolation(
            f"Blocked unknown/unsafe action type: {action}"
        )
 
 
def check_for_dangerous_keywords(step):
    """
    Scan the step's description and selector for keywords that suggest
    an irreversible or sensitive action (payments, deletions, etc).
    """
    text_to_check = " ".join([
        str(step.get("description", "")),
        str(step.get("selector", "")),
        str(step.get("value", "")),
    ]).lower()
 
    for keyword in BLOCKED_KEYWORDS:
        if keyword in text_to_check:
            raise SafetyViolation(
                f"Blocked step containing dangerous keyword '{keyword}': "
                f"{step.get('description', '')}"
            )
 
 
def validate_step(step):
    """
    Run all safety checks on a single step before it is executed.
    Raises SafetyViolation if the step should NOT be performed.
    Returns True if the step passes all checks.
    """
    action = step.get("action")
 
    check_action_type(action)
    check_for_dangerous_keywords(step)
 
    if action == "goto":
        check_url(step.get("url", ""))
 
    return True