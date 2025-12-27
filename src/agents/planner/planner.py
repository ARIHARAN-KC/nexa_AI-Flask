import logging
from pathlib import Path
from typing import Dict, Tuple

from jinja2 import Environment, BaseLoader
from src.llm import LLM

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Planner:
    """
    Generates a structured step-by-step plan for a user request.
    """

    REQUIRED_SECTIONS = {
        "project",
        "reply",
        "focus",
        "plans",
        "summary"
    }

    def __init__(self, base_model: str, api_key: str):
        self.llm = LLM(base_model, api_key)
        self.prompt_template = self._load_prompt()
        self.max_retries = 3

    # -------------------------
    # Internal helpers
    # -------------------------

    def _load_prompt(self) -> str:
        path = Path("src/agents/planner/prompt.jinja2")
        if not path.exists():
            raise FileNotFoundError(f"Planner prompt not found: {path}")
        return path.read_text(encoding="utf-8").strip()

    def _call_llm(self, prompt: str) -> str:
        for attempt in range(1, self.max_retries + 1):
            try:
                return self.llm.inference(prompt)
            except Exception as exc:
                logger.warning(
                    "Planner LLM failed (attempt %s/%s): %s",
                    attempt,
                    self.max_retries,
                    exc
                )
        raise RuntimeError("Planner LLM failed after max retries")

    # -------------------------
    # Rendering
    # -------------------------

    def render(self, user_prompt: str) -> str:
        env = Environment(loader=BaseLoader())
        template = env.from_string(self.prompt_template)
        return template.render(prompt=user_prompt)

    # -------------------------
    # Parsing & validation
    # -------------------------

    def validate_response(self, response: str) -> bool:
        required_markers = [
            "Project Name:",
            "Your Reply to the Human Prompter:",
            "Current Focus:",
            "Plan:",
            "Summary:"
        ]
        return all(marker in response for marker in required_markers)

    def parse_response(self, response: str) -> Tuple[str, Dict]:
        """
        Parse planner response into structured data.
        """
        result = {
            "project": "",
            "focus": "",
            "plans": {},
            "summary": ""
        }

        reply = ""
        current_section = None
        current_step = None

        for raw_line in response.splitlines():
            line = raw_line.strip()

            if line.startswith("Project Name:"):
                current_section = "project"
                result["project"] = line.split(":", 1)[1].strip()

            elif line.startswith("Your Reply to the Human Prompter:"):
                current_section = "reply"
                reply = line.split(":", 1)[1].strip()

            elif line.startswith("Current Focus:"):
                current_section = "focus"
                result["focus"] = line.split(":", 1)[1].strip()

            elif line.startswith("Plan:"):
                current_section = "plans"

            elif line.startswith("Summary:"):
                current_section = "summary"
                result["summary"] = line.split(":", 1)[1].strip()

            elif current_section == "reply":
                reply += " " + line

            elif current_section == "focus":
                result["focus"] += " " + line

            elif current_section == "plans":
                if line.startswith("- [ ] Step"):
                    step_num = int(line.split("Step")[1].split(":")[0].strip())
                    result["plans"][step_num] = line.split(":", 1)[1].strip()
                    current_step = step_num
                elif current_step:
                    result["plans"][current_step] += " " + line

            elif current_section == "summary":
                result["summary"] += " " + line.replace("```", "")

        result["project"] = result["project"].strip()
        result["focus"] = result["focus"].strip()
        result["summary"] = result["summary"].strip()

        return reply.strip(), result

    # -------------------------
    # Execution
    # -------------------------

    def execute(self, user_prompt: str):
        """
        Generate and parse a plan.
        """
        for attempt in range(1, self.max_retries + 1):
            logger.info("Planner attempt %s/%s", attempt, self.max_retries)

            prompt = self.render(user_prompt)
            response = self._call_llm(prompt)

            if not self.validate_response(response):
                logger.warning("Invalid planner response format, retrying...")
                continue

            reply, plan = self.parse_response(response)
            logger.info("Planner produced valid plan")
            return reply, plan

        raise RuntimeError("Planner failed after maximum retries")
