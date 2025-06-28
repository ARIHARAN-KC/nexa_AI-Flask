from googlesearch import search as s

class GoogleSearch:
    def __init__(self):
        self.query_result = []

    def search(self, query):
        try:
            self.query_result = list(s(query, num_results=5))  # Store results directly
            return self.query_result

        except Exception as err:
            print(f"Search error: {err}")  # Log the error
            self.query_result = []  # Ensure query_result is an empty list
            return []  # Return an empty list instead of an error object

    def get_first_link(self):
        if not self.query_result:  # Check if query_result is empty
            return None  # Return None or an empty string ""

        return self.query_result[0]
