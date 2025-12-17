import pytest

from src.utils import settings
from src.utils.duck import duck


def test_duck_inject_appends_site_clause(monkeypatch):
    captured = []

    class DummyDDGS:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def text(self, query):
            # capture the exact query passed to the search backend
            captured.append(query)
            return [
                {'href': 'https://www.linkedin.com/in/jane-doe', 'title': 'Jane'},
                {'href': 'https://pubmed.ncbi.nlm.nih.gov/12345', 'title': 'Sample Paper'},
                {'href': 'https://example.com/other', 'title': 'Other'},
            ]

    monkeypatch.setattr('src.utils.duck.DDGS', DummyDDGS)

    res = duck('liver toxicity', inject_sources=True)
    assert captured, "No query was captured from DDGS.text"
    # Should query one site at a time (order follows settings.SOURCES)
    assert any('site:pubmed.ncbi.nlm.nih.gov' in q.lower() for q in captured)
    assert any('site:linkedin.com' in q.lower() for q in captured)
    assert all(' or ' not in q.lower() for q in captured), "Queries should not combine multiple site: clauses"

    # the returned results should be filtered to only include allowed sources from settings.SOURCES
    hrefs = [r.get('href') or r.get('url') for r in res]
    assert any('linkedin.com' in h for h in hrefs)
    assert any('pubmed.ncbi.nlm.nih.gov' in h for h in hrefs)
    assert not any('example.com' in h for h in hrefs)



def test_duck_inject_with_explicit_allowed_sources(monkeypatch):
    captured = []

    class DummyDDGS2:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def text(self, query):
            captured.append(query)
            return [
                {'href': 'https://www.linkedin.com/in/jane-doe', 'title': 'Jane'},
                {'href': 'https://pubmed.ncbi.nlm.nih.gov/12345', 'title': 'Sample Paper'},
            ]

    monkeypatch.setattr('src.utils.duck.DDGS', DummyDDGS2)

    res = duck('toxicity', allowed_sources=['linkedin.com'], inject_sources=True)
    assert captured
    assert len(captured) == 1
    q = captured[0].lower()
    assert 'site:linkedin.com' in q
    # only linkedin result should remain after filtering
    hrefs = [r.get('href') or r.get('url') for r in res]
    assert all('linkedin.com' in h for h in hrefs)
