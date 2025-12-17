import json
from fastapi.testclient import TestClient
import threading

from main import app


def fake_scrape_progress(query, max_results=5, allowed_sources=None, progress_callback=None):
    # Simulate initial search hits, a non-fatal error, then an item then completion
    if progress_callback:
        progress_callback({"type": "progress", "percent": 0})
        progress_callback({"type": "search_results", "results": [{"href": "https://example.com", "title": "Example"}]})
        progress_callback({"type": "error", "msg": "Crawl timed out for https://example.com", "url": "https://example.com"})
        progress_callback({"type": "item", "item": {"url": "https://example.com", "title": "Example", "emails": [], "phones": [], "linkedin_urls": [], "location": [], "text_content": ""}, "percent": 50})
        progress_callback({"type": "done", "percent": 100, "results": [{"url": "https://example.com", "title": "Example"}]})


def test_sse_allows_error_then_done(monkeypatch):
    # Patch the scrape_progress to avoid network calls
    monkeypatch.setattr('src.handlers.handle.scrape_progress', fake_scrape_progress)

    client = TestClient(app)

    with client.stream("GET", "/scrape/stream?input=test") as response:
        assert response.status_code == 200
        data = ""
        parts = []
        for chunk in response.iter_lines():
            if not chunk:
                continue
            # TestClient may yield str or bytes depending on environment
            if isinstance(chunk, bytes):
                line = chunk.decode('utf-8')
            else:
                line = chunk
            # SSE `data: ...` lines
            if line.startswith('data:'):
                payload = line.split('data: ', 1)[1]
                parts.append(json.loads(payload))

        # We expect to see progress, error, item, done in sequence
        types = [p.get('type') for p in parts]
        assert 'progress' in types
        assert 'search_results' in types
        assert 'error' in types
        assert 'item' in types
        assert 'done' in types
        # ensure search_results occurs before item
        assert types.index('search_results') < types.index('item')


def test_sse_stream_includes_error_item_done(monkeypatch):
    # Patch the scrape_progress to avoid network calls
    monkeypatch.setattr('src.handlers.handle.scrape_progress', fake_scrape_progress)

    client = TestClient(app)

    with client.stream("GET", "/scrape/stream?input=test") as response:
        assert response.status_code == 200
        data = ""
        parts = []
        for chunk in response.iter_lines():
            if not chunk:
                continue
            # TestClient may yield str or bytes depending on environment
            if isinstance(chunk, bytes):
                line = chunk.decode('utf-8')
            else:
                line = chunk
            # SSE `data: ...` lines
            if line.startswith('data:'):
                payload = line.split('data: ', 1)[1]
                parts.append(json.loads(payload))

        # We expect to see progress, error, item, done in sequence
        types = [p.get('type') for p in parts]
        assert 'progress' in types
        assert 'error' in types
        assert 'item' in types
        assert 'done' in types
