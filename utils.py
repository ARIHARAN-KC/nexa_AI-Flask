
import json
import re
import time
from src.browser import GoogleSearch, Browser

browser = Browser()
google_search = GoogleSearch()

def stream_text(text):
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.005)

def search_queries(queries):
    results = {}
    for query in queries:
        query = query.strip().lower()
        google_search.search(query)
        link = google_search.get_first_link()
        if link is None:
            print(f"No search results found for: {query}")
            results[query] = {"link": None, "content": ""}
            continue
        if not link.startswith(("http://", "https://")):
            print(f"Invalid link found: {link}")
            results[query] = {"link": None, "content": ""}
            continue
        browser.go_to(link)
        results[query] = {"link": link, "content": browser.extract_text().strip()}
    return results

def clean_file_path(file_path: str) -> str:
    """Clean and normalize a file path, fixing flattened paths"""
    if not file_path:
        return ""
    cleaned_path = file_path.strip().strip('"').strip("'").strip("`")
    cleaned_path = cleaned_path.replace('\\', '/').strip('/')
    if not cleaned_path:
        return ""
    # Detect flattened paths
    if '/' not in cleaned_path and cleaned_path not in ['README.md', 'package.json', '.gitignore']:
        # Heuristic: Fix common flattened patterns
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
    # Remove invalid characters
    cleaned_path = re.sub(r'[<>:"|?*]', '', cleaned_path)
    return cleaned_path

def prepare_coding_files(coder_output):
    """Prepare coding files for project creation with better validation"""
    files = []
    for file_data in coder_output:
        if not file_data or not isinstance(file_data, dict):
            print(f"Skipping invalid file data: {file_data}")
            continue
            
        if not file_data.get('file') or not file_data.get('code'):
            print(f"Skipping incomplete file data: {file_data}")
            continue
            
        filename = clean_file_path(file_data['file'])
        if not filename:
            print(f"Skipping invalid filename: {file_data['file']}")
            continue
            
        code = file_data['code']
        if not isinstance(code, str):
            print(f"Skipping non-string code for file: {filename}")
            continue
            
        # Clean code content
        code = code.strip()
        if code.startswith('```') and code.endswith('```'):
            code = code[3:-3].strip()
            
        files.append({
            'file': filename,
            'code': code
        })
        
    if not files:
        raise ValueError("No valid files found in coder output")
        
    print("Prepared coding files:", json.dumps(files, indent=2))
    return files
