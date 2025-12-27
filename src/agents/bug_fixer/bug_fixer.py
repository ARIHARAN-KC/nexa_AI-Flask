import re
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, BaseLoader
from src.llm import LLM

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class BugFixer:
    """
    Uses an LLM to analyze errors, propose solutions,
    and generate fixed code.
    """

    REQUIRED_KEYS = {"analysis", "solution", "fixed_code"}

    def __init__(self, base_model: str, api_key: str):
        self.llm = LLM(base_model, api_key)
        self.max_retries = 3

        self.code_block_pattern = re.compile(
            r"```(?:json|python|[\w]+)?\n(.*?)```",
            re.DOTALL | re.IGNORECASE
        )

        self.prompt_template = self._load_prompt()

    # -------------------------
    # Internal helpers
    # -------------------------

    def _load_prompt(self) -> str:
        """Safely load Jinja2 prompt template."""
        prompt_path = Path("src/agents/bug_fixer/prompt.jinja2")

        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

        return prompt_path.read_text(encoding="utf-8").strip()

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to extract JSON from raw LLM output.
        Handles:
        - Raw JSON
        - ```json blocks
        - Text + JSON mixed output
        """
        text = text.strip()

        # Try direct JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from code blocks
        for block in self.code_block_pattern.findall(text):
            try:
                return json.loads(block.strip())
            except json.JSONDecodeError:
                continue

        return None

    def _call_llm(self, prompt: str) -> str:
        """Centralized LLM call with retries."""
        for attempt in range(1, self.max_retries + 1):
            try:
                return self.llm.inference(prompt)
            except Exception as exc:
                logger.warning(
                    "LLM call failed (attempt %s/%s): %s",
                    attempt,
                    self.max_retries,
                    exc
                )
        raise RuntimeError("LLM failed after maximum retries")

    # -------------------------
    # Public methods
    # -------------------------

    def render(self, code: str, error: str, context: Optional[Dict] = None) -> str:
        env = Environment(loader=BaseLoader())
        template = env.from_string(self.prompt_template)
        return template.render(
            code=code,
            error=error,
            context=context or {}
        )

    def validate_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Validate and normalize LLM response.
        Returns parsed dict or None.
        """
        data = self._extract_json(response)
        if not data:
            return None

        if not self.REQUIRED_KEYS.issubset(data.keys()):
            logger.warning("Missing required keys in response: %s", data.keys())
            return None

        return data

    def analyze_error(self, code: str, error: str) -> Dict[str, Any]:
        """
        Analyze the error and return structured diagnostics.
        """
        prompt = f"""
Analyze the following error in the code and respond in JSON format.

Required JSON keys:
- cause
- components
- impacts

Error:
{error}

Code:
{code}
"""

        try:
            response = self._call_llm(prompt)
            data = self._extract_json(response)
            if data:
                return {
                    "cause": data.get("cause", "Unknown"),
                    "components": data.get("components", []),
                    "impacts": data.get("impacts", "Unknown"),
                }
        except Exception as exc:
            logger.error("Error analysis failed: %s", exc)

        return {
            "cause": "Unknown",
            "components": [],
            "impacts": "Unable to determine",
        }

    def propose_solution(self, code: str, error: str, analysis: Dict[str, Any]) -> str:
        """
        Propose a solution for the bug.
        """
        prompt = self.render(
            code,
            error,
            {
                "analysis": analysis,
                "step": "propose_solution"
            }
        )

        try:
            response = self._call_llm(prompt)
            data = self.validate_response(response)
            if data:
                return data["solution"]
        except Exception as exc:
            logger.error("Solution proposal failed: %s", exc)

        return "Unable to determine a reliable solution."

    def generate_fixed_code(self, code: str, error: str, solution: str) -> str:
        """
        Generate corrected code based on solution.
        """
        prompt = self.render(
            code,
            error,
            {
                "solution": solution,
                "step": "generate_fixed_code"
            }
        )

        try:
            response = self._call_llm(prompt)

            data = self.validate_response(response)
            if data:
                return data["fixed_code"]

            # Fallback: extract first code block
            blocks = self.code_block_pattern.findall(response)
            if blocks:
                return blocks[0].strip()

            logger.warning("Returning raw LLM response as fallback.")
            return response.strip()

        except Exception as exc:
            logger.error("Code generation failed: %s", exc)
            return code  # Safe fallback
