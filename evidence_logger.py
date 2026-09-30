"""
evidence_logger.py
 
Evidence and logging layer for the automation agent.
 
Every time a run happens (live discovery OR replay), this module:
  1. Saves a timestamped screenshot after each step
  2. Writes a detailed, structured log entry for each step
  3. Saves everything into a per-run folder under /evidence/
 
This gives reviewers (and you, later) a clear trail of exactly what
happened during any given run, without having to re-run anything.
"""
 
import json
import os
from datetime import datetime
 
 
class EvidenceLogger:
    def __init__(self, task_name, base_dir="evidence"):
        # Create a unique folder for this run, e.g. evidence/login_to_saucedemo_20260923_143000
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_id = f"{task_name}_{timestamp}"
        self.run_dir = os.path.join(base_dir, self.run_id)
        os.makedirs(self.run_dir, exist_ok=True)
 
        self.log_entries = []
        self.start_time = datetime.now().isoformat()
 
    def log_step(self, step_number, action, description, status, page=None, error=None):
        """
        Record one step's outcome and optionally save a screenshot of the
        page at that moment.
        """
        entry = {
            "step_number": step_number,
            "action": action,
            "description": description,
            "status": status,  # "success", "blocked", or "failed"
            "timestamp": datetime.now().isoformat(),
            "error": error,
        }
 
        # Save a screenshot alongside this step, if a page was provided.
        if page is not None:
            screenshot_name = f"step_{step_number:02d}_{status}.png"
            screenshot_path = os.path.join(self.run_dir, screenshot_name)
            try:
                page.screenshot(path=screenshot_path)
                entry["screenshot"] = screenshot_name
            except Exception as e:
                entry["screenshot"] = None
                entry["screenshot_error"] = str(e)
 
        self.log_entries.append(entry)
        print(f"  [logged] step {step_number}: {status}")
 
    def finalize(self, overall_status):
        """
        Write out the full run log as a single JSON file once the run
        (success, failure, or safety block) is complete.
        """
        summary = {
            "run_id": self.run_id,
            "overall_status": overall_status,
            "started_at": self.start_time,
            "finished_at": datetime.now().isoformat(),
            "steps": self.log_entries,
        }
 
        log_path = os.path.join(self.run_dir, "run_log.json")
        with open(log_path, "w") as f:
            json.dump(summary, f, indent=2)
 
        print(f"Evidence saved to: {self.run_dir}")
        return log_path