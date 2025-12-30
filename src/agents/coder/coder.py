import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

from jinja2 import Environment, BaseLoader
from src.llm import LLM

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Coder:
    """
    Generates complete multi-file projects based on user instructions.
    Handles malformed LLM output gracefully and validates requested pages.
    """

    def __init__(self, base_model: str, api_key: str):
        self.llm = LLM(base_model, api_key, agent_name="coder")

        self.code_block_pattern = re.compile(
            r"```(?:\w+)?\n(.*?)```",
            re.DOTALL
        )

        self.filename_pattern = re.compile(
            r"^file\s*:\s*`?([^`\n]+)`?",
            re.IGNORECASE
        )

        self.prompt_template = self._load_prompt()
        self.max_retries = 3

    # -------------------------
    # Internal helpers
    # -------------------------

    def _load_prompt(self) -> str:
        path = Path("src/agents/coder/prompt.jinja2")
        if not path.exists():
            raise FileNotFoundError(f"Prompt not found: {path}")
        return path.read_text(encoding="utf-8").strip()

    def _call_llm(self, prompt: str) -> str:
        for attempt in range(1, self.max_retries + 1):
            try:
                return self.llm.inference(prompt)
            except Exception as exc:
                logger.warning(
                    "LLM failed (attempt %s/%s): %s",
                    attempt,
                    self.max_retries,
                    exc
                )
        raise RuntimeError("LLM failed after max retries")

    # -------------------------
    # Rendering
    # -------------------------

    def render(self, step_by_step_plan: str, user_prompt: str, search_results: Dict) -> str:
        env = Environment(loader=BaseLoader())
        template = env.from_string(self.prompt_template)
        return template.render(
            step_by_step_plan=step_by_step_plan,
            user_prompt=user_prompt,
            search_results=search_results
        )

    # -------------------------
    # Parsing & validation
    # -------------------------

    def clean_filename(self, filename: str) -> str:
        if not filename:
            return "src/unnamed_file.txt"

        filename = filename.strip().strip("`'\"")
        filename = filename.replace("\\", "/")
        filename = re.sub(r'[<>:"|?*]', '', filename)

        if "/" not in filename:
            filename = f"src/{filename}"

        return filename

    def parse_response(self, response: str) -> List[Dict[str, str]]:
        """
        Parse markdown-style multi-file output into structured files.
        Handles missing code blocks or filenames gracefully.
        """
        files = []
        if not response or not response.strip():
            return files

        lines = response.splitlines()
        current_file = None
        current_code = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Detect file declaration
            file_match = self.filename_pattern.match(line)
            if file_match:
                if current_file and current_code:
                    files.append({
                        "file": self.clean_filename(current_file),
                        "code": "\n".join(current_code).rstrip()
                    })
                current_file = file_match.group(1)
                current_code = []
                i += 1
                continue

            # Detect code blocks
            if line.startswith("```"):
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    current_code.append(lines[i])
                    i += 1
                i += 1
                continue

            i += 1

        # Append last file if exists
        if current_file:
            files.append({
                "file": self.clean_filename(current_file),
                "code": "\n".join(current_code).rstrip() if current_code else ""
            })

        # Always return a list
        return files

    # -------------------------
    # Execution
    # -------------------------

    def execute(
        self,
        step_by_step_plan: str,
        user_prompt: str,
        search_results: Dict
    ) -> List[Dict[str, str]]:

        for attempt in range(1, self.max_retries + 1):
            logger.info("Coder attempt %s/%s", attempt, self.max_retries)

            prompt = self.render(step_by_step_plan, user_prompt, search_results)
            response = self._call_llm(prompt)
            files = self.parse_response(response)

            if not files:
                logger.warning("No files parsed from LLM output, retrying...")
                continue

            # Verify requested pages
            if self._verify_all_pages_generated(files, user_prompt):
                logger.info("All requested pages generated successfully")
                return files
            else:
                logger.warning("Some requested pages are missing, retrying...")

        # Return whatever was generated as fallback
        logger.warning("Returning partial files after max retries")
        return files

    # -------------------------
    # Page verification
    # -------------------------

    def _verify_all_pages_generated(self, files: List[Dict], user_prompt: str) -> bool:
        requested = self._extract_requested_pages(user_prompt)
        if not requested:
            return True

        filenames = " ".join(f["file"].lower() for f in files)
        content = " ".join(f["code"].lower() for f in files)

        missing = [
            page for page in requested
            if page not in filenames and page not in content
        ]

        if missing:
            logger.warning("Missing pages: %s", missing)
            return False

        return True

    def _extract_requested_pages(self, user_prompt: str) -> List[str]:
        prompt = user_prompt.lower()
        page_map = {
            "home": ["home", "index", "landing"],
            "login": ["login", "signin"],
            "signup": ["signup", "register"],
            "dashboard": ["dashboard"],
            "filter": ["filter", "search", "sort"],
            "admin": ["admin"],
            "settings": ["settings"]
        }

        found = []
        for page, keywords in page_map.items():
            if any(k in prompt for k in keywords):
                found.append(page)

        logger.info("Requested pages detected: %s", found)
        return found
