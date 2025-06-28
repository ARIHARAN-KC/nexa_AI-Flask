
import re
import json
from jinja2 import Environment, BaseLoader
from src.llm import LLM

coder_prompt = open("src/agents/coder/prompt.jinja2").read().strip()

class Coder:
    def __init__(self, base_model, api_key):
        self.llm = LLM(base_model, api_key)
        self.code_block_pattern = re.compile(r"```(?:\w+\n)?(.*?)```", re.DOTALL)
        self.filename_pattern = re.compile(r"^(?:file|filename):\s*([^\n]+)", re.IGNORECASE)

    def render(self, step_by_step_plan, user_prompt, search_results):
        env = Environment(loader=BaseLoader())
        template = env.from_string(coder_prompt)
        return template.render(
            step_by_step_plan=step_by_step_plan,
            user_prompt=user_prompt,
            search_results=search_results,
        )

    def clean_filename(self, filename):
        """Clean and normalize filenames, ensuring valid format and directory structure"""
        if not filename:
            return "unnamed_file.txt"
        filename = filename.strip().strip('"').strip("'").strip("`")
        filename = filename.replace('\\', '/').strip('/')
        # Remove invalid characters
        filename = re.sub(r'[<>:"|?*]', '', filename)
        # Detect flattened paths and attempt to fix
        if '/' not in filename and filename not in ['README.md', 'package.json', '.gitignore']:
            # Heuristic: Split camelCase or concatenated names
            if 'model' in filename.lower():
                filename = f"server/models/{filename}"
            elif 'route' in filename.lower():
                filename = f"server/routes/{filename}"
            elif 'controller' in filename.lower():
                filename = f"server/controllers/{filename}"
            elif 'component' in filename.lower():
                filename = f"client/src/components/{filename}"
            else:
                filename = f"src/{filename}"
        return filename

    def validate_response(self, response):
        """Parse and validate LLM response, handling multiple code blocks and filenames"""
        if not response or not response.strip():
            return None

        result = []
        current_file = None
        current_code = []
        lines = response.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Check for filename marker
            filename_match = self.filename_pattern.match(line)
            if filename_match:
                if current_file and current_code:
                    result.append({
                        "file": self.clean_filename(current_file),
                        "code": "\n".join(current_code).strip()
                    })
                current_file = filename_match.group(1)
                current_code = []
                i += 1
                continue

            # Check for code block start
            if line.startswith("```"):
                code_block = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    code_block.append(lines[i])
                    i += 1
                if i < len(lines) and lines[i].strip().startswith("```"):
                    i += 1  # Skip closing ```
                if current_file:
                    current_code.extend(code_block)
                continue

            # Collect lines as code if we're in a file context
            if current_file and line:
                current_code.append(line)
            i += 1

        # Save the last file
        if current_file and current_code:
            result.append({
                "file": self.clean_filename(current_file),
                "code": "\n".join(current_code).strip()
            })

        # Filter out empty or invalid entries
        result = [entry for entry in result if entry["file"] and entry["code"]]

        # Log for debugging
        print("Coder validate_response output:", json.dumps(result, indent=2))

        return result if result else None

    def execute(self, step_by_step_plan: str, user_prompt: str, search_results: dict):
        max_retries = 3
        retries = 0

        while retries < max_retries:
            prompt = self.render(step_by_step_plan, user_prompt, search_results)
            response = self.llm.inference(prompt)
            valid_response = self.validate_response(response)

            if valid_response:
                return valid_response

            retries += 1
            print(f"Invalid response from the model (attempt {retries}/{max_retries}): {response[:100]}...")
            if retries == max_retries:
                raise ValueError("Failed to get valid response after multiple attempts")
