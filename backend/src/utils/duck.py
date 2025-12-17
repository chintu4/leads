import warnings
from urllib.parse import urlparse
import logging
import requests
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Attempt imports with compatibility handling
try:
    from ddgs import DDGS
    
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        raise ImportError("Could not import 'duckduckgo_search' or 'ddgs'. Please install it via pip.")


def _search_wikipedia_opensearch(query, limit=10):
    """Search using Wikipedia's opensearch API."""
    try:
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "opensearch",
            "search": query,
            "limit": limit,
            "namespace": 0,
            "format": "json"
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = []
        if len(data) > 3:
            titles = data[1]
            descriptions = data[2]
            urls = data[3]
            for title, desc, href in zip(titles, descriptions, urls):
                results.append({"title": title, "body": desc, "href": href})
        return results
    except Exception as e:
        logger.warning(f"Wikipedia search failed: {e}")
        return []


def _search_google(query, limit=10):
    """Search using Google Custom Search API."""
    api_key = os.getenv("GOOGLE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")
    if not api_key or not cse_id:
        logger.warning("Google API key or CSE ID not set, skipping Google search")
        return []
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": api_key,
            "cx": cse_id,
            "q": query,
            "num": limit
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = []
        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "body": item.get("snippet", ""),
                "href": item.get("link", "")
            })
        return results
    except Exception as e:
        logger.warning(f"Google search failed: {e}")
        return []


def _search_bing(query, limit=10):
    """Search using Bing Search API."""
    api_key = os.getenv("BING_API_KEY")
    if not api_key:
        logger.warning("Bing API key not set, skipping Bing search")
        return []
    try:
        url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": api_key}
        params = {"q": query, "count": limit}
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = []
        for item in data.get("webPages", {}).get("value", []):
            results.append({
                "title": item.get("name", ""),
                "body": item.get("snippet", ""),
                "href": item.get("url", "")
            })
        return results
    except Exception as e:
        logger.warning(f"Bing search failed: {e}")
        return []


# List of search backends
def _search_ddgs(query):
    with DDGS() as ddgs:
        return list(ddgs.text(query))

SEARCH_BACKENDS = [
    ("ddgs", _search_ddgs),
    ("google", _search_google),
    ("bing", _search_bing),
]


def duck(query, allowed_sources=None, max_results=200, inject_sources=False, focus_people=False):
    """
    Run a DuckDuckGo search and return results filtered by allowed_sources.

    Args:
        query (str): The search query.
        allowed_sources (list, optional): List of allowed hostnames/domains. 
                                          If None, attempts to load from settings.
        max_results (int): Maximum number of results to fetch.
        inject_sources (bool): If True and allowed sources are known, add site: clauses to the query.
    """

    # 1. Resolve Allowed Sources
    if allowed_sources is None:
        try:
            # Lazy import to keep function portable
            from src.utils import settings as _settings
            allowed_sources = getattr(_settings, 'SOURCES', None)
        except ImportError:
            pass # No settings module found, default to None (allow all)

    # 2. Normalize sources early so we can optionally inject site: clauses
    # Preserve original ordering of allowed_sources and avoid duplicates.
    normalized_hosts = []
    if allowed_sources:
        _seen_hosts = set()
        for s in allowed_sources:
            # Clean common prefixes/shorthands
            if 'linkedin' in s and '.' not in s: s = 'linkedin.com'
            if ('pubmed' in s or 'ncbi' in s) and '.' not in s: s = 'pubmed.ncbi.nlm.nih.gov'

            parsed = urlparse(s if '//' in s else f'//{s}')
            host = (parsed.netloc or parsed.path).replace('www.', '').lower()
            if host and host not in _seen_hosts:
                normalized_hosts.append(host)
                _seen_hosts.add(host)

    # 3. Optionally inject site: clauses to bias results
    query_to_use = query

    # Prepare containers for the sequential-source accumulation path
    filtered = []
    seen_urls = set()

    # 4. Execute search safely
    try:
        # Suppress specific runtime warnings from the library
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*renamed to.*")

            with DDGS() as ddgs:
                # If injecting sources, query each host individually (one site: clause per call)
                # and accumulate deduplicated results. This avoids issuing a single OR-query
                # and improves the chance of gathering more leads across multiple domains.
                if inject_sources and normalized_hosts:
                    for host in normalized_hosts:
                        # When focusing on people profiles, tweak the site: query per host
                        if focus_people:
                            if 'pubmed' in host or 'ncbi' in host:
                                # PubMed: prefer author pages / articles mentioning authors
                                site_queries = [f"{query} site:{host} author" if query else f"site:{host} author"]
                            elif 'linkedin' in host:
                                # LinkedIn: prefer profile paths (in/, pub/) for more results
                                site_queries = [
                                    f"{query} site:{host}/in/" if query else f"site:{host}/in/",
                                    f"{query} site:{host}/pub/" if query else f"site:{host}/pub/"
                                ]
                            else:
                                site_queries = [f"{query} site:{host}" if query else f"site:{host}"]
                        else:
                            site_queries = [f"{query} site:{host}" if query else f"site:{host}"]
                        
                        for site_query in site_queries:
                            try:
                                host_results = list(ddgs.text(site_query))[: (max_results + 5)]
                            except Exception as e:
                                logging.warning(f"Error querying {host} with {site_query}: {e}")
                                host_results = []
                            logging.info(f"Host {host}: {len(host_results)} results from query '{site_query}'")
                            for r in host_results:
                                url = r.get('href') or r.get('url')
                                if not url:
                                    continue
                                url_lower = url.lower()
                                if url_lower in seen_urls:
                                    continue
                                try:
                                    r_parsed = urlparse(url_lower)
                                    r_host = r_parsed.netloc.replace('www.', '').split(':')[0]
                                    if r_host == host or r_host.endswith('.' + host):
                                        filtered.append(r)
                                        seen_urls.add(url_lower)
                                except Exception:
                                    continue
                                if len(filtered) >= max_results:
                                    break
                            if len(filtered) >= max_results:
                                break
                else:
                    # Fetch from multiple backends and aggregate
                    raw_results = []
                    seen = set()
                    for name, search_func in SEARCH_BACKENDS:
                        try:
                            backend_results = search_func(query_to_use)[: (max_results // len(SEARCH_BACKENDS) + 5)]
                            for r in backend_results:
                                url = r.get('href') or r.get('url')
                                if url and url not in seen:
                                    raw_results.append(r)
                                    seen.add(url)
                        except Exception as e:
                            logger.warning(f"{name} search failed: {e}")
                    raw_results = raw_results[:max_results + 5]

    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        return []

    # If no explicit allowed_sources, just return raw results; otherwise return filtered list.
    if not allowed_sources:
        return raw_results[:max_results]

    return filtered

if __name__ == "__main__":
    # Test execution
    print("--- Searching 'AI agents' on LinkedIn ---")
    data = duck("AI agents", allowed_sources=['linkedin'])
    for item in data:
        print(f"- {item.get('title')}: {item.get('href', item.get('url'))}")