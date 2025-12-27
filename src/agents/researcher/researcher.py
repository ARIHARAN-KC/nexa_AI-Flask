import json
from jinja2 import Environment, BaseLoader
from src.llm import LLM


researcher_prompt = open("src/agents/researcher/prompt.jinja2").read().strip()


class Researcher:
    def __init__(self, base_model, api_key):
        self.llm = LLM(base_model, api_key)
        self.max_retries = 3

    def render(self, step_by_step_plan, contextual_keywords):
        env = Environment(loader=BaseLoader())
        template = env.from_string(researcher_prompt)
        return template.render(
            step_by_step_plan=step_by_step_plan,
            contextual_keywords=contextual_keywords,
        )

    def validate_response(self, response):
        if not response or not response.strip():
            return False

        response = response.strip().replace("```json", "```")

        if response.startswith("```") and response.endswith("```"):
            response = response[3:-3].strip()

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            return False

        # Normalize keys
        data = {k.replace("\\", ""): v for k, v in data.items()}

        if "queries" not in data or "ask_user" not in data:
            return False

        if not isinstance(data["queries"], list):
            return False
        if not isinstance(data["ask_user"], str):
            return False

        return {
            "queries": data["queries"],
            "ask_user": data["ask_user"],
        }

    def execute(self, step_by_step_plan, contextual_keywords):
        # Normalize keywords input
        if isinstance(contextual_keywords, (list, tuple)):
            contextual_keywords = ", ".join(
                k.capitalize() for k in contextual_keywords if isinstance(k, str)
            )

        retries = 0
        while retries < self.max_retries:
            prompt = self.render(step_by_step_plan, contextual_keywords)
            response = self.llm.inference(prompt)
            valid_response = self.validate_response(response)

            if valid_response:
                return valid_response

            print("Invalid response from the researcher, retrying...")
            retries += 1

        raise RuntimeError("Failed to get valid researcher response after retries")
