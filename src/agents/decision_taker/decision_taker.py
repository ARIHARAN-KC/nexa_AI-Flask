import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, BaseLoader
from src.llm import LLM

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class DecisionTaker:
    """
    Determines the optimal function chain required to fulfill
    a user's code-related request.
    """

    REQUIRED_KEYS = {"function", "args", "reply"}

    def __init__(self, base_model: str, api_key: str) -> None:
        self.llm = LLM(base_model, api_key, agent_name="decision_taker")
        self.max_retries = 5
        self.prompt_template = self._load_prompt()

    # -------------------------
    # Internal helpers
    # -------------------------

    def _load_prompt(self) -> str:
        path = Path("src/agents/decision_taker/prompt.jinja2")
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        return path.read_text(encoding="utf-8").strip()

    def _call_llm(self, prompt: str) -> str:
        for attempt in range(1, self.max_retries + 1):
            try:
                return self.llm.inference(prompt)
            except Exception as exc:
                logger.warning(
                    "DecisionTaker LLM failed (attempt %s/%s): %s",
                    attempt,
                    self.max_retries,
                    exc
                )
        raise RuntimeError("DecisionTaker LLM failed after max retries")

    def _extract_json(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """
        Safely extract JSON array from LLM output.
        """
        text = text.strip()

        # Remove fenced blocks if present
        if text.startswith("```"):
            text = text.replace("```json", "```").strip("`").strip()

        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            return None

        return None

    # -------------------------
    # Rendering
    # -------------------------

    def render(self, user_prompt: str) -> str:
        env = Environment(loader=BaseLoader())
        template = env.from_string(self.prompt_template)
        return template.render(prompt=user_prompt)

    # -------------------------
    # Validation
    # -------------------------

    def validate_response(
        self, response: str
    ) -> Optional[List[Dict[str, Any]]]:
        data = self._extract_json(response)
        if not data:
            return None

        for item in data:
            if not self.REQUIRED_KEYS.issubset(item.keys()):
                logger.error("Invalid decision item schema: %s", item)
                return None

            if not isinstance(item["args"], dict):
                logger.error("Args must be an object: %s", item)
                return None

        return data

    # -------------------------
    # Execution
    # -------------------------

    def execute(self, prompt: str) -> List[Dict[str, Any]]:
        """
        Execute the decision-making process.
        """
        for attempt in range(1, self.max_retries + 1):
            logger.info("DecisionTaker attempt %s/%s", attempt, self.max_retries)

            rendered_prompt = self.render(prompt)
            response = self._call_llm(rendered_prompt)
            valid = self.validate_response(response)

            if valid:
                logger.info("DecisionTaker produced valid response")
                return valid

            logger.warning("Invalid decision response, retrying...")

        raise RuntimeError("DecisionTaker failed after maximum retries")
