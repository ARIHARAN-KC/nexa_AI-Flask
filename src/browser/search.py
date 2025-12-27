# src/browser/search.py
from ddgs import DDGS


class GoogleSearch:
    def __init__(self, max_results: int = 5):
        self.max_results = max_results
        self.query_result = []

    def search(self, query: str):
        self.query_result = []
        try:
            with DDGS() as ddgs:
                results = ddgs.text(query, max_results=self.max_results)
                self.query_result = [
                    r.get("href") for r in results if r.get("href")
                ]
            return self.query_result
        except Exception as err:
            print(f"Search error: {err}")
            return []

    def get_first_link(self):
        return self.query_result[0] if self.query_result else None
