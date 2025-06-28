import os
import time
from langchain_cohere import ChatCohere
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
import google.generativeai as genai

class RateLimiter:
    def __init__(self, max_calls, period):
        self.max_calls = max_calls  # Max calls allowed in the period
        self.period = period  # Period in seconds (e.g., 60 for 1 minute)
        self.calls = []  # Timestamps of recent calls

    def __enter__(self):
        while True:
            current_time = time.time()
            self.calls = [t for t in self.calls if current_time - t < self.period]
            if len(self.calls) < self.max_calls:
                self.calls.append(current_time)
                break
            time_to_wait = self.period - (current_time - self.calls[0])
            time.sleep(time_to_wait)

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

class LLM:
    def __init__(self, base_model, api_key) -> None:
        self.base_model = base_model
        # Rate limiter: 10 calls per minute (adjust based on DeepSeek/OpenRouter limits)
        self.rate_limiter = RateLimiter(max_calls=10, period=60)

        if base_model == "Gemini-Pro":
            os.environ["GOOGLE_API_KEY"] = api_key
            genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
            self.model = genai.GenerativeModel("gemini-pro")
        elif base_model == "Cohere":
            self.model = ChatCohere(cohere_api_key=api_key)
        elif base_model == "ChatGPT":
            self.model = ChatOpenAI(openai_api_key=api_key, model_name="gpt-3.5-turbo")
        elif base_model == "DeepSeek":
            # Use OpenRouter's free DeepSeek endpoint (OpenAI-compatible)
            self.model = ChatOpenAI(
                openai_api_key=api_key,
                #model_name="deepseek/deepseek-r1:free",  # R1 free model via OpenRouter
                model_name = "deepseek/deepseek-prover-v2:free",
                #model_name = "meta-llama/llama-3.3-8b-instruct:free",
                base_url="https://openrouter.ai/api/v1"
            )

    def inference(self, prompt):
        try:
            if self.base_model == "Gemini-Pro":
                response = self.model.generate_content(prompt).text
            elif self.base_model in ["Cohere", "ChatGPT", "DeepSeek"]:
                with self.rate_limiter:
                    chain = self.model | StrOutputParser()
                    response = chain.invoke(prompt)
            return response
        except Exception as e:
            raise Exception(f"Error during inference with {self.base_model}: {str(e)}")