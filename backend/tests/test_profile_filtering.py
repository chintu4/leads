import os
import src.handlers.handle as handle


def test_search_results_only_profiles(monkeypatch):
    # fake duck results include mixed hrefs
    fake_results = [
        {"href": "https://example.com", "title": "Example"},
        {"href": "https://www.linkedin.com/in/jane-doe", "title": "Jane"},
        {"href": "https://researchgate.net/profile/john-smith", "title": "John"},
    ]

    def fake_duck(q, inject_sources=True, focus_people=False, allowed_sources=None):
        return fake_results

    import sys, types
    monkeypatch.setattr(handle, 'duck', fake_duck)
    # disable deep crawl to keep function short
    monkeypatch.setenv('USE_PLAYWRIGHT_DEEP', '0')
    # Ensure the `from src.utils.scrapy_ok import crawl_url` import raises ImportError
    # by providing an empty dummy module (no crawl_url symbol).
    sys.modules['src.utils.scrapy_ok'] = types.ModuleType('src.utils.scrapy_ok')

    events = []

    def cb(evt):
        events.append(evt)

    handle.scrape_progress('test-query', progress_callback=cb)

    # Find any search_results events and ensure only profile-like links are present
    search_events = [e for e in events if e.get('type') == 'search_results']
    assert len(search_events) <= 1
    if search_events:
        results = search_events[0].get('results', [])
        hrefs = [r.get('href') or r.get('url') or '' for r in results]
        # only the linkedin and researchgate links should be present
        assert 'https://www.linkedin.com/in/jane-doe' in hrefs
        assert 'https://researchgate.net/profile/john-smith' in hrefs
        assert 'https://example.com' not in hrefs


def test_scrape_filters_non_profile_results(monkeypatch):
    # Simulate crawling returning two items, one with profile-like url and one without
    def fake_duck(q, inject_sources=True):
        return [{"href": "https://a.com"}, {"href": "https://b.com"}]

    def fake_crawl_url(u):
        if 'a.com' in u:
            return [{"url": "https://www.linkedin.com/in/alice", "title": "Alice", "linkedin_urls": ["https://www.linkedin.com/in/alice"]}]
        else:
            return [{"url": "https://example.com/about", "title": "About", "linkedin_urls": []}]

    import sys, types
    monkeypatch.setattr(handle, 'duck', fake_duck)
    # Provide a dummy module so the import `from src.utils.scrapy_ok import crawl_url` will succeed
    mod = types.ModuleType('src.utils.scrapy_ok')
    # make a crawl_url function available that returns our fake crawl results
    mod.crawl_url = fake_crawl_url
    sys.modules['src.utils.scrapy_ok'] = mod

    out = handle.scrape('query', max_results=5)
    results = out.get('results', [])

    # Only the profile-like item should remain
    urls = [r.get('url') for r in results]
    assert 'https://www.linkedin.com/in/alice' in urls
    assert not any('example.com/about' in (u or '') for u in urls)
