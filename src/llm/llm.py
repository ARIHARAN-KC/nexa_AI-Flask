# src/llm/llm.py
import os
import time
import google.generativeai as genai
from langchain_cohere import ChatCohere
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import RateLimitError


class RateLimiter:
    def __init__(self, max_calls: int, period: int):
        self.max_calls = max_calls
        self.period = period
        self.calls: list[float] = []

    def __enter__(self):
        while True:
            now = time.time()
            self.calls = [t for t in self.calls if now - t < self.period]
            if len(self.calls) < self.max_calls:
                self.calls.append(now)
                return
            sleep_time = self.period - (now - self.calls[0]) + 0.1
            time.sleep(max(sleep_time, 0.1))

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class LLM:
    def __init__(self, base_model: str, api_key: str) -> None:
        self.base_model = base_model
        self.rate_limiter = RateLimiter(max_calls=10, period=60)

        if base_model == "Gemini-Pro":
            os.environ["GOOGLE_API_KEY"] = api_key
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-pro")

        elif base_model == "Cohere":
            self.model = ChatCohere(cohere_api_key=api_key)

        elif base_model == "ChatGPT":
            self.model = ChatOpenAI(
                openai_api_key=api_key,
                model_name="gpt-3.5-turbo",
            )

        elif base_model == "DeepSeek":
            self.model = ChatOpenAI(
                openai_api_key=api_key,
                model_name="deepseek/deepseek-chat",
                base_url="https://openrouter.ai/api/v1",
            )
        else:
            raise ValueError(f"Unsupported base model: {base_model}")

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=20),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(RateLimitError),
        reraise=True,
    )
    def _invoke(self, chain, prompt: str):
        with self.rate_limiter:
            return chain.invoke(prompt)

    def inference(self, prompt: str) -> str:
        try:
            if self.base_model == "Gemini-Pro":
                return self.model.generate_content(prompt).text

            chain = self.model | StrOutputParser()
            return self._invoke(chain, prompt)

        except Exception as e:
            raise RuntimeError(
                f"LLM inference failed for model '{self.base_model}': {e}"
            )
