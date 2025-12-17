"""Run a focused deep crawl for a specific URL and print progress and diagnostics."""
import os
import sys
# Ensure the backend package root is on sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.utils.playwright_deep import crawl_people_deep, CrawlConfig
import json
import traceback

URL = "https://pubmed.ncbi.nlm.nih.gov/40985657/"


def cb(evt):
    print("PROG:", evt)


if __name__ == "__main__":
    try:
        cfg = CrawlConfig(max_pages=6, max_depth=1, total_timeout_s=90, navigation_timeout_ms=45_000)
        people = crawl_people_deep(URL, config=cfg, progress_callback=cb)
        print("DONE: found people=", len(people))
        print(json.dumps(people, default=str)[:8000])
    except Exception:
        print("EXCEPTION during deep crawl:")
        traceback.print_exc()
