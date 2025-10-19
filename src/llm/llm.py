import os
import time
from langchain_cohere import ChatCohere
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
import google.generativeai as genai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from openai import RateLimitError # Importing RateLimitError from openai

class RateLimiter:
    def __init__(self, max_calls, period):
        self.max_calls = max_calls  # Max calls allowed in the period
        self.period = period  # Period in seconds (e.g., 60 for 1 minute)
        self.calls = []  # Timestamps of recent calls

    def __enter__(self):
        while True:
            current_time = time.time()
            # Remove calls older than the period
            self.calls = [t for t in self.calls if current_time - t < self.period]
            if len(self.calls) < self.max_calls:
                self.calls.append(current_time)
                break
            # Calculate time to wait until a slot opens up
            time_to_wait = self.period - (current_time - self.calls[0]) + 0.1 # Add a small buffer
            time.sleep(time_to_wait)

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

class LLM:
    def __init__(self, base_model, api_key) -> None:
        self.base_model = base_model
        # Rate limiter: more conservative for free tiers, adjust as needed
        # For DeepSeek free tier, let's try 3 calls per minute initially
        # For other models, we can keep it at 10 or remove if not strictly necessary
        self.rate_limiter_deepseek = RateLimiter(max_calls=10, period=60) 
        self.rate_limiter_other = RateLimiter(max_calls=10, period=60) # General limiter for others

        if base_model == "Gemini-Pro":
            os.environ["GOOGLE_API_KEY"] = api_key
            genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
            self.model = genai.GenerativeModel("gemini-pro")
        elif base_model == "Cohere":
            self.model = ChatCohere(cohere_api_key=api_key)
        elif base_model == "ChatGPT":
            self.model = ChatOpenAI(openai_api_key=api_key, model_name="gpt-3.5-turbo")
        elif base_model == "DeepSeek":
            # Use OpenRouter's DeepSeek endpoint (OpenAI-compatible)
            self.model = ChatOpenAI(
                openai_api_key=api_key,
                model_name="deepseek/deepseek-chat",  # Use the paid model for better rate limits
                base_url="https://openrouter.ai/api/v1"
            )
            
    # Decorator for retrying API calls with exponential backoff
    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=20), # Wait 2^x * multiplier seconds
        stop=stop_after_attempt(5), # Max 5 attempts
        retry=retry_if_exception_type(RateLimitError), # Only retry on rate limit errors
        reraise=True # Re-raise the last exception if all retries fail
    )
    def _inference_with_retry(self, prompt, model_chain, use_rate_limiter=False):
        if use_rate_limiter:
            # Use the DeepSeek specific rate limiter if applicable
            with self.rate_limiter_deepseek if self.base_model == "DeepSeek" else self.rate_limiter_other:
                response = model_chain.invoke(prompt)
        else:
            response = model_chain.invoke(prompt)
        return response

    def inference(self, prompt):
        try:
            if self.base_model == "Gemini-Pro":
                # Gemini doesn't use the OpenRouter/OpenAI-compatible client,
                # so its rate limiting is handled by the genai library or Google's backend.
                response = self.model.generate_content(prompt).text
            elif self.base_model in ["Cohere", "ChatGPT"]:
                chain = self.model | StrOutputParser()
                # For Cohere/ChatGPT, use the general rate limiter
                response = self._inference_with_retry(prompt, chain, use_rate_limiter=True)
            elif self.base_model == "DeepSeek":
                chain = self.model | StrOutputParser()
                # For DeepSeek, explicitly use its rate limiter and retry mechanism
                response = self._inference_with_retry(prompt, chain, use_rate_limiter=True)
            return response
        except Exception as e:
            raise Exception(f"Error during inference with {self.base_model}: {str(e)}")