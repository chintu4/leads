import sys
import os
# Ensure the project 'backend' package is importable when running this script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.utils.duck import duck

queries = [
    "docking",
    "docking author",
    "docking ""related people profile""",
    "docking site:pubmed.ncbi.nlm.nih.gov",
    "docking site:linkedin.com \"linkedin.com/in/\"",
    "docking site:pubmed.ncbi.nlm.nih.gov author",
]

for q in queries:
    print("\n=== QUERY: ", q)
    try:
        res = duck(q, inject_sources=True, focus_people=True, max_results=10)
        if not res:
            print("  (no results or error)")
            continue
        for i, r in enumerate(res[:10], 1):
            url = r.get('href') or r.get('url') or ''
            title = r.get('title') or r.get('name') or ''
            print(f"  {i}. {title} -> {url}")
    except Exception as e:
        print("  ERROR:", e)
