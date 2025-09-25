from ddgs import DDGS

class GoogleSearch:
    def __init__(self):
        self.query_result = []

    def search(self, query):
        try:
            with DDGS() as ddgs:
                results = [r for r in ddgs.text(query, max_results=5)]
            self.query_result = [r['href'] for r in results]
            return self.query_result
        except Exception as err:
            print(f"Search error: {err}")
            self.query_result = []
            return []

    def get_first_link(self):
        if not self.query_result:
            return None
        return self.query_result[0]