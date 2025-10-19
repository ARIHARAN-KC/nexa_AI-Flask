import re
import json
from jinja2 import Environment, BaseLoader
from src.llm import LLM

project_creator_prompt = open("src/agents/project_creator/prompt.jinja2").read().strip()

class ProjectCreator:
    def __init__(self, base_model, api_key):
        self.llm = LLM(base_model, api_key)
        self.max_retries = 3
        self.code_block_pattern = re.compile(r"```(?:\w+\n)?(.*?)```", re.DOTALL)

    def render(self, project_name, full_code):
        env = Environment(loader=BaseLoader())
        template = env.from_string(project_creator_prompt)
        return template.render(
            project_name=project_name,
            full_code=full_code
        )

    def clean_file_path(self, file_path: str) -> str:
        """Clean and normalize file paths"""
        if not file_path:
            return ""
        cleaned_path = file_path.strip().strip('"').strip("'").strip("`")
        cleaned_path = cleaned_path.replace('\\', '/').strip('/')
        if not cleaned_path:
            return ""
        if '/' not in cleaned_path and cleaned_path not in ['README.md', 'package.json', '.gitignore']:
            if 'model' in cleaned_path.lower():
                cleaned_path = f"server/models/{cleaned_path}"
            elif 'route' in cleaned_path.lower():
                cleaned_path = f"server/routes/{cleaned_path}"
            elif 'controller' in cleaned_path.lower():
                cleaned_path = f"server/controllers/{cleaned_path}"
            elif 'component' in cleaned_path.lower():
                cleaned_path = f"client/src/components/{cleaned_path}"
            else:
                cleaned_path = f"src/{cleaned_path}"
        cleaned_path = re.sub(r'[<>:"|?*]', '', cleaned_path)
        return cleaned_path

    def validate_response(self, response):
        if not response:
            print("Empty response received")
            return False
        try:
            # Try parsing as JSON directly
            try:
                json_response = json.loads(response)
                if isinstance(json_response, dict):
                    if "reply" in json_response and "code" in json_response:
                        return self._extract_code_content(json_response)
            except json.JSONDecodeError:
                pass

            # Try extracting JSON from code blocks
            code_blocks = self.code_block_pattern.findall(response)
            for block in code_blocks:
                try:
                    json_response = json.loads(block.strip())
                    if isinstance(json_response, dict):
                        if "reply" in json_response and "code" in json_response:
                            return self._extract_code_content(json_response)
                except json.JSONDecodeError:
                    continue
            
            # Handle malformed JSON by attempting to fix common issues
            cleaned_response = response.strip().replace("```json", "").replace("```", "")
            try:
                json_response = json.loads(cleaned_response)
                if isinstance(json_response, dict):
                    if "reply" in json_response and "code" in json_response:
                        return self._extract_code_content(json_response)
            except json.JSONDecodeError:
                print("No valid JSON found in response after cleaning")
                return False

            print("No valid JSON found in response")
            return False
        except Exception as e:
            print(f"Validation error: {str(e)}")
            return False

    def _extract_code_content(self, json_response):
        if isinstance(json_response["code"], str):
            code_match = self.code_block_pattern.search(json_response["code"])
            if code_match:
                json_response["code"] = code_match.group(1).strip()
        if isinstance(json_response["code"], list):
            for file_data in json_response["code"]:
                if not file_data.get("file"):
                    print(f"Invalid file path in response: {file_data}")
                    return False
                file_path = self.clean_file_path(file_data["file"])
                if not file_path:
                    print(f"Malformed or unsafe file path: {file_data['file']}")
                    return False
                file_data["file"] = file_path
                # Ensure code content is cleaned
                if file_data.get("code") and isinstance(file_data["code"], str):
                    code_match = self.code_block_pattern.search(file_data["code"])
                    if code_match:
                        file_data["code"] = code_match.group(1).strip()
        return json_response

    def execute(self, project_name, full_code):
        # Normalize file paths in full_code
        for file_data in full_code:
            file_data["file"] = self.clean_file_path(file_data["file"])
        
        # Return the actual files instead of Python code
        return {
            "reply": f"Created project structure for {project_name} with {len(full_code)} files",
            "code": full_code
        }