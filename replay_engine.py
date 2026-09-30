"""
replay_engine.py
 
Deterministic replay engine.
Reads a saved artifact (recipe file) produced by the agent loop
and replays the exact same steps using Playwright, WITHOUT calling
any AI model. This makes replay fast, cheap, and reliable.
"""
 
import json
import sys
from playwright.sync_api import sync_playwright
from safety_guardrails import validate_step, SafetyViolation
from evidence_logger import EvidenceLogger
from escalation import create_escalation
 
 
def load_artifact(path):
    """Load the saved recipe file (JSON) from disk."""
    with open(path, "r") as f:
        return json.load(f)
 
 
def replay_artifact(artifact_path, headless=False):
    artifact = load_artifact(artifact_path)
 
    print(f"Replaying task: {artifact['task_name']}")
    print(f"Goal: {artifact['goal']}")
    print(f"Total steps: {len(artifact['steps'])}")
    print("-" * 40)
 
    logger = EvidenceLogger(task_name=artifact["task_name"])
 
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
 
        for step in artifact["steps"]:
            step_num = step["step_number"]
            action = step["action"]
            description = step.get("description", "")
 
            print(f"Step {step_num}: {action} -- {description}")
 
            try:
                validate_step(step)
            except SafetyViolation as e:
                print(f"SAFETY BLOCK on step {step_num}: {e}")
                print("Stopping replay -- escalating to human review.")
                logger.log_step(step_num, action, description, status="blocked", page=page, error=str(e))
                logger.finalize(overall_status="blocked")
                create_escalation(
                    run_dir=logger.run_dir,
                    step_number=step_num,
                    reason=str(e),
                    category="safety_block",
                    screenshot=f"step_{step_num:02d}_blocked.png",
                    suggested_action="This step was blocked by a safety rule. Review whether the rule is too strict, or whether this step was genuinely unsafe.",
                )
                browser.close()
                return {"status": "blocked", "blocked_step": step_num, "reason": str(e)}
 
            try:
                if action == "goto":
                    page.goto(step["url"])
                    page.wait_for_load_state("networkidle")
 
                elif action == "type":
                    page.fill(step["selector"], step["value"])
 
                elif action == "click":
                    page.click(step["selector"])
                    page.wait_for_timeout(500)
 
                elif action == "finish":
                    print("Reached finish step. Goal achieved.")
                    logger.log_step(step_num, action, description, status="success", page=page)
                    break
 
                else:
                    print(f"WARNING: Unknown action type '{action}', skipping.")
                    logger.log_step(step_num, action, description, status="skipped", page=page)
                    continue
 
                logger.log_step(step_num, action, description, status="success", page=page)
 
            except Exception as e:
                print(f"ERROR on step {step_num}: {e}")
                print("Stopping replay -- escalating to human review.")
                logger.log_step(step_num, action, description, status="failed", page=page, error=str(e))
                logger.finalize(overall_status="failed")
                create_escalation(
                    run_dir=logger.run_dir,
                    step_number=step_num,
                    reason=str(e),
                    category="execution_error",
                    screenshot=f"step_{step_num:02d}_failed.png",
                    suggested_action="The page likely changed or the selector no longer matches. Check the screenshot, update the artifact's selector if needed, and retry.",
                )
                browser.close()
                return {"status": "failed", "failed_step": step_num, "error": str(e)}
 
        page.wait_for_timeout(2000)
        browser.close()
 
    print("-" * 40)
    print("Replay completed successfully.")
    logger.finalize(overall_status="success")
    return {"status": "success"}
 
 
if __name__ == "__main__":
    artifact_file = sys.argv[1] if len(sys.argv) > 1 else "sample_artifact.json"
    result = replay_artifact(artifact_file, headless=False)
    print(result)