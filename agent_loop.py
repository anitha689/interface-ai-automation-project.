"""
Goal-driven agent loop (Section 3.1 of the assignment).

Observes the page (screenshot + interactive elements), asks Gemini what to do next,
executes that action with Playwright, and repeats until the goal is met or we hit a
stopping condition (max steps / stuck).

Every step taken is recorded in `self.step_log`, which is exactly what gets turned
into the reusable artifact (Section 3.2) once a run succeeds.

Run with:
    python agent_loop.py
"""

import os
import json
import base64
import google.generativeai as genai
from playwright.sync_api import sync_playwright, Page

MODEL = "gemini-3.6-flash"
MAX_STEPS = 15


def get_interactive_elements(page: Page) -> list[dict]:
    """
    Pulls a simplified list of clickable/typeable elements from the page so the
    model has concrete, stable selectors to act on instead of guessing coordinates.
    This is the 'no clean DOM' hedge -- works even on ugly legacy markup because
    we fall back through several identifying attributes.
    """
    elements = page.eval_on_selector_all(
        "button, input, a, select, [role=button]",
        """
        (nodes) => nodes.map((el, i) => {
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) return null; // skip hidden
            return {
                tag: el.tagName.toLowerCase(),
                id: el.id || null,
                name: el.getAttribute('name') || null,
                type: el.getAttribute('type') || null,
                placeholder: el.getAttribute('placeholder') || null,
                text: (el.innerText || el.value || '').trim().slice(0, 60),
                data_test: el.getAttribute('data-test') || null,
                index: i
            };
        }).filter(Boolean)
        """,
    )
    return elements


def build_selector(el: dict) -> str:
    """Prefer the most stable identifier available, in order of robustness."""
    if el.get("data_test"):
        return f"[data-test='{el['data_test']}']"
    if el.get("id"):
        return f"#{el['id']}"
    if el.get("name"):
        return f"[name='{el['name']}']"
    if el.get("text"):
        return f"text={el['text']}"
    return f"{el['tag']}:nth-of-type({el['index']})"


class Agent:
    def __init__(self, goal: str, start_url: str):
        self.goal = goal
        self.start_url = start_url
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        self.client = genai.GenerativeModel(MODEL)
        self.step_log = []  # <-- this becomes the artifact after a successful run

    def observe(self, page: Page) -> tuple[str, list[dict]]:
        screenshot_bytes = page.screenshot()
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        elements = get_interactive_elements(page)
        return screenshot_b64, elements

    def decide(self, screenshot_b64: str, elements: list[dict], page_url: str) -> dict:
        """Ask Gemini what to do next, given the current screen. Returns a structured action."""
        elements_text = json.dumps(elements, indent=2)

        system_prompt = f"""You are controlling a web browser to accomplish a goal.
Goal: {self.goal}
Current URL: {page_url}

You will be shown a screenshot and a list of interactive elements on the page.
Respond with ONLY a JSON object (no other text) describing the single next action to take:

{{"action": "click", "element_index": <int>, "reasoning": "why"}}
{{"action": "type", "element_index": <int>, "value": "text to type", "reasoning": "why"}}
{{"action": "goto", "url": "https://...", "reasoning": "why"}}
{{"action": "finish", "success": true/false, "output": {{...any extracted data...}}, "reasoning": "why"}}

Use "finish" once the goal has clearly been reached (or if it's truly impossible).
element_index must match the "index" field from the elements list provided.
"""

        image_bytes = base64.b64decode(screenshot_b64)
        image_part = {"mime_type": "image/png", "data": image_bytes}

        full_prompt = f"{system_prompt}\n\nInteractive elements on this page:\n{elements_text}"

        response = self.client.generate_content([full_prompt, image_part])

        raw_text = response.text.strip()
        # Gemini sometimes wraps JSON in ```json fences -- strip those defensively
        raw_text = raw_text.replace("```json", "").replace("```", "").strip()
        return json.loads(raw_text)

    def act(self, page: Page, action: dict, elements: list[dict]):
        """Executes the action Gemini chose, and records it for the artifact/log."""
        step_record = {"action": action, "url_before": page.url}

        if action["action"] == "click":
            el = elements[action["element_index"]]
            selector = build_selector(el)
            page.click(selector, timeout=5000)
            step_record["selector"] = selector

        elif action["action"] == "type":
            el = elements[action["element_index"]]
            selector = build_selector(el)
            page.fill(selector, action["value"], timeout=5000)
            step_record["selector"] = selector
            step_record["value"] = action["value"]

        elif action["action"] == "goto":
            page.goto(action["url"])
            step_record["target_url"] = action["url"]

        page.wait_for_timeout(800)  # small settle time between actions
        step_record["url_after"] = page.url
        self.step_log.append(step_record)

    def run(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto(self.start_url)

            for step_num in range(MAX_STEPS):
                print(f"\n--- Step {step_num + 1} ---")
                screenshot_b64, elements = self.observe(page)
                action = self.decide(screenshot_b64, elements, page.url)
                print(f"Action: {action}")

                if action["action"] == "finish":
                    self.step_log.append({"action": action})
                    print(f"\nFinished. Success: {action['success']}")
                    print(f"Output: {action.get('output')}")
                    browser.close()
                    return {
                        "success": action["success"],
                        "output": action.get("output"),
                        "steps": self.step_log,
                    }

                self.act(page, action, elements)

            print("\nHit max steps without finishing.")
            browser.close()
            return {"success": False, "output": None, "steps": self.step_log}


if __name__ == "__main__":
    agent = Agent(
        goal="Log in with username 'standard_user' and password 'secret_sauce', "
        "then reach the products page.",
        start_url="https://www.saucedemo.com",
    )
    result = agent.run()

    # Save the raw run log -- this is what Step 3.2 will turn into a proper artifact
    with open("run_log.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\nSaved run_log.json")