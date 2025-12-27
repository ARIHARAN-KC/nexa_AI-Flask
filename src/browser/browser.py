# src/browser/browser.py
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md


class Browser:
    def __init__(self, timeout: int = 15):
        self.session = requests.Session()
        self.timeout = timeout
        self.response = None
        self.soup = None

    def go_to(self, url: str):
        self.response = self.session.get(url, timeout=self.timeout)
        self.response.raise_for_status()
        self.soup = BeautifulSoup(self.response.text, "html.parser")

    def get_html(self):
        return self.response.text if self.response else None

    def get_markdown(self):
        html = self.get_html()
        return md(html) if html else None

    def extract_text(self):
        return self.soup.get_text(separator=" ", strip=True) if self.soup else None

    def close(self):
        self.session.close()
