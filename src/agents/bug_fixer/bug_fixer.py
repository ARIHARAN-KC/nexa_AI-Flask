import re
import json
from jinja2 import Environment, BaseLoader
from src.llm import LLM

bug_fixer_prompt = open("src/agents/bug_fixer/prompt.jinja2").read().strip()

class BugFixer:
    def __init__(self, base_model, api_key):
        self.llm = LLM(base_model, api_key)
        self.max_retries = 3
        self.code_block_pattern = re.compile(r"```(?:\w+\n)?(.*?)```", re.DOTALL)

    def render(self, code, error, context=None):
        env = Environment(loader=BaseLoader())
        template = env.from_string(bug_fixer_prompt)
        return template.render(
            code=code,
            error=error,
            context=context or {}
        )

    def validate_response(self, response):
        response = response.strip()
        
        # Handle code blocks
        if response.startswith("```") and response.endswith("```"):
            response = response[3:-3].strip()
        
        try:
            response = json.loads(response)
            if not all(k in response for k in ["analysis", "solution", "fixed_code"]):
                return False
            return response
        except json.JSONDecodeError:
            return False

    def analyze_error(self, code, error):
        """Analyze the error and return diagnostic information"""
        prompt = f"""
        Analyze the following error in the code:

        Error: {error}

        Code:
        {code}

        Provide:
        1. The likely cause of the error
        2. The specific components involved
        3. Potential impacts
        """
        
        for attempt in range(self.max_retries):
            try:
                response = self.llm.inference(prompt)
                return {
                    "cause": response.split("\n")[0].split(":", 1)[1].strip(),
                    "components": [x.strip() for x in response.split("\n")[1].split(":", 1)[1].split(",")],
                    "impacts": response.split("\n")[2].split(":", 1)[1].strip()
                }
            except Exception as e:
                if attempt == self.max_retries - 1:
                    return {
                        "cause": "Unknown",
                        "components": [],
                        "impacts": "Unable to determine"
                    }

    def propose_solution(self, code, error, analysis):
        """Propose a solution to the bug"""
        prompt = self.render(code, error, {
            "analysis": analysis,
            "step": "propose_solution"
        })
        
        for attempt in range(self.max_retries):
            try:
                response = self.llm.inference(prompt)
                valid_response = self.validate_response(response)
                if valid_response:
                    return valid_response["solution"]
            except Exception as e:
                if attempt == self.max_retries - 1:
                    return "I couldn't determine a solution for this error."

    def generate_fixed_code(self, code, error, solution):
        """Generate the actual fixed code"""
        prompt = self.render(code, error, {
            "solution": solution,
            "step": "generate_fixed_code"
        })
        
        for attempt in range(self.max_retries):
            try:
                response = self.llm.inference(prompt)
                valid_response = self.validate_response(response)
                if valid_response:
                    return valid_response["fixed_code"]
                
                # Fallback to extracting code blocks
                code_blocks = self.code_block_pattern.findall(response)
                if code_blocks:
                    return code_blocks[0].strip()
                
                return response
            except Exception as e:
                if attempt == self.max_retries - 1:
                    return code  # Return original code if we can't fix it