"""Heuristics to detect person/profile pages from URLs and page content.

Provides a single function `is_profile_url(url, page_text=None, jsonld_texts=None)`
that returns (is_profile: bool, score: int).
"""
import json
import re
from typing import List, Optional, Tuple


_ORCID_RE = re.compile(r"orcid\.org/\d{4}-\d{4}-\d{4}-[\dX]{4}")
_NAME_RE = re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b")


def _looks_like_person_schema(jsonld_texts: Optional[List[str]]) -> bool:
    if not jsonld_texts:
        return False
    for raw in jsonld_texts:
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        # traverse simple cases where @type is Person
        def _iter(o):
            if isinstance(o, dict):
                t = o.get("@type") or o.get("type")
                if t:
                    if isinstance(t, list):
                        if any(str(x).lower() == "person" for x in t):
                            return True
                    else:
                        if str(t).lower() == "person":
                            return True
                for v in o.values():
                    if _iter(v):
                        return True
            elif isinstance(o, list):
                for it in o:
                    if _iter(it):
                        return True
            return False

        try:
            if _iter(obj):
                return True
        except Exception:
            continue
    return False


def is_profile_url(url: str, page_text: Optional[str] = None, jsonld_texts: Optional[List[str]] = None) -> Tuple[bool, int]:
    """Return (is_profile, score) where score >= 60 indicates a likely profile.

    The function is conservative and can be called with just a URL (fast), or with
    page_text and jsonld_texts for higher confidence.
    """
    if not url:
        return False, 0

    u = url.lower()
    score = 0

    # Strong URL patterns
    if "linkedin.com/in/" in u or "/in/" in u and "linkedin.com" in u:
        score += 60
    if "linkedin.com/pub/" in u or "linkedin.com/profile/view" in u:
        score += 50
    if _ORCID_RE.search(u):
        score += 60
    if "researchgate.net/profile/" in u:
        score += 55
    if "scholar.google.com/citations" in u:
        score += 55
    if "pubmed.ncbi.nlm.nih.gov/?term=" in u:
        score += 60

    # Path tokens indicating person pages
    path_tokens = ("/people/", "/person/", "/staff/", "/team/", "/profile/", "/users/", "/~")
    if any(t in u for t in path_tokens):
        score += 20

    # author tokens
    if "/author" in u or "?author=" in u or "&author=" in u:
        score += 10

    # content signals
    if page_text:
        if _NAME_RE.search(page_text[:200]):
            score += 10
        if "mailto:" in page_text or "@" in page_text:
            score += 10

    # JSON-LD / schema.org Person
    try:
        if _looks_like_person_schema(jsonld_texts):
            score += 40
    except Exception:
        pass

    return (score >= 60, score)
