#!/usr/bin/env python3
import sys
sys.path.append('backend')
from src.utils.duck import duck

query = "toxicology director"
results = duck(query, inject_sources=True, focus_people=True, max_results=10)
print(f"Query: {query}")
print(f"Results count: {len(results)}")
for i, r in enumerate(results):
    print(f"{i+1}: {r.get('title')} - {r.get('href')}")

# Also test without inject_sources
print("\nWithout inject_sources:")
results2 = duck(query, inject_sources=False, focus_people=False, max_results=10)
print(f"Results count: {len(results2)}")
for i, r in enumerate(results2):
    print(f"{i+1}: {r.get('title')} - {r.get('href')}")