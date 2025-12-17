from src.utils.duck import duck
import importlib
import logging
import os
from typing import Tuple
from urllib.parse import urlparse

# Note: avoid importing scrapy / twisted at module import time on Windows (reload/spawn issues).
# We'll import those libraries lazily inside functions that need them.


def _load_spider_settings(module_name='src.utils.settings'):
    """Load uppercase settings from the project's settings module into a Scrapy Settings object.

    If Scrapy isn't available (e.g., dev machine without Twisted/pywin32), return None so callers
    can gracefully handle absence of Scrapy.
    """
    try:
        mod = importlib.import_module(module_name)
        settings_dict = {k: v for k, v in vars(mod).items() if k.isupper()}
        try:
            from scrapy.settings import Settings
            s = Settings()
            s.setdict(settings_dict, priority='project')
            return s
        except Exception:
            # scrapy not importable or other issue
            return None
    except Exception:
        return None


def scrape(query, max_results=200):
    """
    Search using DuckDuckGo and scrape the top results for lead data.

    This runs the spider synchronously for each top result (blocking).
    For production, run Scrapy in a separate worker or use the async runner.

    Scrapy/Twisted imports are performed lazily so the app can start even if Twisted
    or platform-specific dependencies (e.g., pywin32) are not available.
    """
    # Get search results from DuckDuckGo (prefer site-restricted results)
    search_results = duck(query, inject_sources=True)

    # derive small set of high-level 'fields' from the query for quick identification
    fields = []
    q = (query or "").lower()
    if '3d' in q or 'in vitro' in q or 'in-vitro' in q:
        fields.extend(['3D cell cultures', 'Organoids', 'Microfluidic systems'])
    if 'toxic' in q or 'toxicology' in q:
        fields.append('Director of Toxicology')
    if 'liver' in q or 'dili' in q:
        fields.append('Drug-Induced Liver Injury')

    if not search_results:
        return {"query": query, "fields": fields, "results": []}

    # Limit results
    urls_to_scrape = [result['href'] for result in search_results[:max_results]]

    results = []
    try:
        # Import the crawler lazily; if unavailable, skip crawling and return search results
        from src.utils.scrapy_ok import crawl_url
        from src.utils.profile import is_profile_url
    except Exception as e:
        logging.info("Scrapy not available, skipping crawl: %s", e)
        return {
            "query": query,
            "search_results": search_results[:max_results],
            "results": [],
            "fields": fields
        }

    for url in urls_to_scrape:
        try:
            items = crawl_url(url)
            for item in items:
                processed = process(item, search_context={"query": query, "url": url})
                # Only include processed items that look like person profiles
                try:
                    is_profile = bool((processed.get('linkedin_url') or processed.get('profile_url'))) or is_profile_url((processed.get('url') or ''))[0]
                except Exception:
                    is_profile = bool((processed.get('linkedin_url') or processed.get('profile_url')))
                if not is_profile:
                    logging.debug("Scrape: skipping non-profile processed item from %s: %s", url, processed.get('url'))
                    continue
                results.append(processed)
        except Exception:
            logging.exception("Failed to crawl %s", url)

    return {
        "query": query,
        "search_results": search_results[:max_results],
        "results": results,
        "fields": fields
    }


def scrape_progress(query, max_results=200, allowed_sources=None, progress_callback=None):
    """Scrape like `scrape` but call `progress_callback` with events as work progresses.

    The `progress_callback` receives dicts with these example shapes:
      {"type": "progress", "percent": 30, "url": "...", "processed_so_far": 5}
      {"type": "item", "item": {...}, "percent": 45}
      {"type": "done", "percent": 100, "results": [...]} 
      {"type": "error", "msg": "..."}
    """
    def _looks_like_url(s: str) -> bool:
        if not s:
            return False
        try:
            p = urlparse(s)
            return p.scheme in ("http", "https") and bool(p.netloc)
        except Exception:
            return False

    # If the user pastes a URL, treat it as the direct crawl target.
    if _looks_like_url(query):
        search_results = [{"title": query, "href": query, "body": ""}]
    else:
        # Prefer site-restricted results when available and bias toward people profiles
        # (PubMed authors, LinkedIn profiles)
        search_results = duck(query, inject_sources=True, focus_people=True, allowed_sources=allowed_sources)

    # derive fields as above
    fields = []
    q = (query or "").lower()
    if '3d' in q or 'in vitro' in q or 'in-vitro' in q:
        fields.extend(['3D cell cultures', 'Organoids', 'Microfluidic systems'])
    if 'toxic' in q or 'toxicology' in q:
        fields.append('Director of Toxicology')
    if 'liver' in q or 'dili' in q:
        fields.append('Drug-Induced Liver Injury')

    # Inform the client about the raw search hits immediately so the UI can
    # show candidate leads before crawling/enrichment completes.
    # Separate profile links to send directly, and non-profile links for deep search.
    try:
        from src.utils.profile import is_profile_url
    except Exception:
        def is_profile_url(url: str, page_text=None, jsonld_texts=None) -> Tuple[bool, int]:
            return (False, 0)

    profile_results = []
    non_profile_urls = []
    for r in search_results:  # Check ALL search results for profiles
        href = r['href']
        try:
            is_prof, _ = is_profile_url(href)
        except Exception:
            is_prof = False
        if is_prof:
            profile_results.append(r)
        else:
            non_profile_urls.append(href)

    # Limit profile results to max_results for immediate display
    profile_results = profile_results[:max_results]

    logging.info("Found %d profile links and %d non-profile URLs for query=%s", len(profile_results), len(non_profile_urls), query)

    if progress_callback and profile_results:
        try:
            progress_callback({"type": "search_results", "results": profile_results})
        except Exception:
            logging.exception("progress_callback failed when sending search_results event")

    if not search_results:
        if progress_callback:
            progress_callback({"type": "done", "percent": 100, "results": []})
        return {"query": query, "fields": fields, "results": []}

    urls_to_scrape = non_profile_urls

    results = []
    # Scrapy crawl is optional; Playwright deep crawl can be used instead.
    try:
        from src.utils.scrapy_ok import crawl_url
    except Exception as e:
        crawl_url = None
        logging.info("Scrapy not available, skipping crawl: %s", e)

    total = max(len(urls_to_scrape), 1)
    processed_count = 0

    logging.info("Starting scrape_progress for query=%s (urls=%d)", query, len(urls_to_scrape))

    # Emit initial progress so the client sees that work started
    if progress_callback:
        try:
            progress_callback({"type": "progress", "percent": 0, "url": None, "processed_so_far": 0})
        except Exception:
            logging.exception("progress_callback failed on initial event")

    import concurrent.futures
    # Allow tuning via env; defaults raised for heavy sites like PubMed/LinkedIn.
    CRAWL_TIMEOUT = int(os.getenv("CRAWL_TIMEOUT", "120"))

    # Enable deep Playwright crawl by default; can be disabled via USE_PLAYWRIGHT_DEEP=0.
    use_deep = _looks_like_url(query) or (os.getenv("USE_PLAYWRIGHT_DEEP", "1").lower() in ("1", "true", "yes"))
    deep_max_pages = int(os.getenv("DEEP_MAX_PAGES", "25"))
    deep_max_depth = int(os.getenv("DEEP_MAX_DEPTH", "3"))
    deep_timeout_s = int(os.getenv("DEEP_TIMEOUT_S", "120"))
    deep_nav_timeout_ms = int(os.getenv("DEEP_NAV_TIMEOUT_MS", "45000"))
    deep_person_limit = int(os.getenv("DEEP_PERSON_LIMIT", "50"))
    allow_linkedin = os.getenv("ALLOW_LINKEDIN_DEEP", "0").lower() in ("1", "true", "yes")

    for idx, url in enumerate(urls_to_scrape, start=1):
        logging.info("Starting crawl for url=%s (idx=%d/%d)", url, idx, total)
        if progress_callback:
            try:
                progress_callback({"type": "progress", "percent": int(((idx-1) / total) * 100), "url": url, "processed_so_far": processed_count})
            except Exception:
                logging.exception("progress_callback failed when announcing url start")

        try:
            items = []

            if crawl_url is not None:
                # Run crawl_url in a worker thread with a timeout so a stuck crawl doesn't hang SSE
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(crawl_url, url)
                    try:
                        items = fut.result(timeout=CRAWL_TIMEOUT)
                    except concurrent.futures.TimeoutError:
                        logging.warning("Crawl timed out for %s after %s seconds", url, CRAWL_TIMEOUT)
                        try:
                            fut.cancel()
                        except Exception:
                            pass
                        items = []
                        if progress_callback:
                            progress_callback({"type": "error", "msg": f"Crawl timed out for {url}", "url": url})

                for item in items:
                    processed = process(item, search_context={"query": query, "url": url})
                    # Server-side filter: only include processed items that contain a profile-like link
                    is_profile = False
                    try:
                        is_profile = bool((processed.get('linkedin_url') or processed.get('profile_url')))
                        if not is_profile:
                            # fallback: consider the processed url itself
                            is_profile = is_profile_url((processed.get('url') or ''))[0]
                    except Exception:
                        is_profile = bool((processed.get('linkedin_url') or processed.get('profile_url')))

                    if not is_profile:
                        logging.debug("Skipping non-profile item from %s: %s", url, processed.get('url'))
                        continue

                    results.append(processed)
                    processed_count += 1
                    logging.debug("Processed item from %s: %s", url, processed.get('url'))
                    if progress_callback:
                        percent = int((idx / total) * 100)
                        logging.info("Progress: %d%% (%d/%d) for query=%s", percent, idx, total, query)
                        try:
                            progress_callback({"type": "item", "item": processed, "percent": percent})
                        except Exception:
                            logging.exception("progress_callback failed when sending item event")

            if use_deep:
                try:
                    from src.utils.playwright_deep import crawl_people_deep, CrawlConfig

                    def deep_cb(evt: dict):
                        # Optionally forward non-fatal deep progress into logs; we don't send unknown SSE event types.
                        if evt.get("type") == "error":
                            logging.info("deep crawl error: %s", evt)

                    cfg = CrawlConfig(
                        max_pages=deep_max_pages,
                        max_depth=deep_max_depth,
                        total_timeout_s=deep_timeout_s,
                        navigation_timeout_ms=deep_nav_timeout_ms,
                        same_domain_only=True,
                        deny_domains=() if allow_linkedin else (
                            "linkedin.com",
                            "www.linkedin.com",
                        ),
                    )
                    people = crawl_people_deep(url, config=cfg, progress_callback=deep_cb)

                    # Convert people to Lead-shaped items and emit
                    seen_local = set()
                    for p in (people or [])[:deep_person_limit]:
                        profile_url = (p.get("profile_url") or "").strip()
                        linkedin = (p.get("linkedin_url") or profile_url).strip()
                        email = (p.get("email") or "").strip()
                        key = profile_url or linkedin or email or (p.get("name") or "")
                        if key and key in seen_local:
                            continue
                        if key:
                            seen_local.add(key)

                        # Create a spider-like payload for consistent scoring
                        scraped_like = {
                            "url": p.get("page_url") or url,
                            "title": (p.get("title") or p.get("name") or p.get("page_title") or "").strip(),
                            "emails": [email] if email else (p.get("page_emails") or []),
                            "phones": [p.get("phone")] if p.get("phone") else (p.get("page_phones") or []),
                            # Existing pipeline expects linkedin_urls, so map profile_url into it.
                            "linkedin_urls": [linkedin] if linkedin else ([profile_url] if profile_url else []),
                            "location": [],
                            "company_info": {},
                            "text_content": p.get("page_text") or "",
                        }
                        processed = process(scraped_like, search_context={"query": query, "url": url})
                        # Filter deep crawl items server-side: only include profile-like results
                        try:
                            deep_is_profile = bool((processed.get('linkedin_url') or processed.get('profile_url'))) or is_profile_url((processed.get('url') or ''))[0]
                        except Exception:
                            deep_is_profile = bool((processed.get('linkedin_url') or processed.get('profile_url')))

                        if not deep_is_profile:
                            logging.debug("Skipping non-profile deep item from %s: %s", url, processed.get('url'))
                            continue

                        results.append(processed)
                        processed_count += 1
                        if progress_callback:
                            percent = int((idx / total) * 100)
                            try:
                                progress_callback({"type": "item", "item": processed, "percent": percent})
                            except Exception:
                                logging.exception("progress_callback failed when sending deep item event")

                except Exception as e:
                    logging.exception("Deep Playwright crawl failed for %s: %s", url, e)
                    if progress_callback:
                        try:
                            progress_callback({"type": "error", "msg": f"Deep crawl failed for {url}: {e}", "url": url})
                        except Exception:
                            logging.exception("progress_callback failed when sending deep error")
        except Exception:
            logging.exception("Failed to crawl %s", url)
            if progress_callback:
                try:
                    progress_callback({"type": "error", "msg": f"Failed to crawl {url}", "url": url})
                except Exception:
                    logging.exception("progress_callback failed when sending error event")
        # emit progress at the end of each URL
        if progress_callback:
            percent = int((idx / total) * 100)
            logging.info("URL complete: %s (percent=%d)", url, percent)
            try:
                progress_callback({"type": "progress", "percent": percent, "url": url, "processed_so_far": processed_count})
            except Exception:
                logging.exception("progress_callback failed when sending url completion event")

    logging.info("Scrape complete for query=%s, results=%d", query, len(results))

    if progress_callback:
        # Ensure final results include only profile-like items (defensive double-check)
        final_results = []
        for r in results:
            try:
                ok = bool((r.get('linkedin_url') or r.get('profile_url'))) or is_profile_url((r.get('url') or ''))[0]
            except Exception:
                ok = bool((r.get('linkedin_url') or r.get('profile_url')))
            if ok:
                final_results.append(r)
        progress_callback({"type": "done", "percent": 100, "results": final_results})

    return {
        "query": query,
        "search_results": search_results[:max_results],
        "results": results,
        "fields": fields
    }


def scrape_async(query, max_results=5):
    """
    Async-style facade that uses Scrapy's CrawlerRunner if available; otherwise returns an empty list.

    Note: kept as a normal function (no module-level decorator) to avoid importing Twisted during module import.
    """
    try:
        from scrapy.crawler import CrawlerRunner
        from scrapy.utils.project import get_project_settings
        from src.utils.scrapy_ok import MySpider
        from twisted.internet import defer
    except Exception as e:
        logging.info("Scrapy/Twisted not available for async crawling: %s", e)
        return []

    # Prefer site-restricted results when available
    search_results = duck(query, inject_sources=True)

    if not search_results:
        return []

    urls_to_scrape = [result['href'] for result in search_results[:max_results]]

    proc_settings = _load_spider_settings() or get_project_settings()
    runner = CrawlerRunner(settings=proc_settings)
    results = []

    @defer.inlineCallbacks
    def run_all():
        for url in urls_to_scrape:
            collected = []
            yield runner.crawl(MySpider, start_url=url, collected=collected)
            results.extend(collected)

    # Start the deferred and block until completion (this is a blocking call - use carefully)
    from twisted.internet import reactor
    d = run_all()
    done = []

    def _stop(_=None):
        try:
            reactor.stop()  # type: ignore[attr-defined]
        except AttributeError:
            pass

    d.addBoth(_stop)
    import threading
    try:
        if threading.current_thread() is threading.main_thread():
            reactor.run()  # type: ignore[attr-defined]
        else:
            reactor.run(installSignalHandlers=False)  # type: ignore[attr-defined]
    except AttributeError:
        # reactor may not have run method
        pass

    return results

def process(scraped_data, search_context=None):
    """
    Process scraped data and return structured lead information with ranking.
    
    Args:
        scraped_data: Dictionary with scraped information from MySpider
        search_context: Optional context about the search query
    
    Returns:
        Dictionary with structured lead data and propensity score
    """
    if not scraped_data or isinstance(scraped_data, str):
        return {
            "email": "",
            "phone": "",
            "linkedin_url": "",
            "location_hq": "",
            "rank": 0,
            "error": "No data to process"
        }
    
    # Extract emails (prioritize business emails)
    emails = scraped_data.get('emails', [])
    primary_email = emails[0] if emails else ""
    
    # Extract phone numbers
    phones = scraped_data.get('phones', [])
    primary_phone = phones[0] if phones else ""
    
    # Extract LinkedIn URLs
    linkedin_urls = scraped_data.get('linkedin_urls', []) or []

    # Prefer a person profile link over other linkedin pages. Use the page-based
    # `is_profile_url` heuristic when available to be conservative about what we
    # consider a profile. Fall back to containing '/in/' as a simple fast check.
    try:
        from src.utils.profile import is_profile_url
    except Exception:
        # Fallback conservative check: treat '/in/' as profile-like
        def is_profile_url(url: str, page_text=None, jsonld_texts=None) -> Tuple[bool, int]:
            return (('/in/' in (url or '').lower()), 0)

    profile_like = [u for u in linkedin_urls if isinstance(u, str) and (('/in/' in u.lower()) or is_profile_url(u)[0])]
    linkedin_url = profile_like[0] if profile_like else (linkedin_urls[0] if linkedin_urls else "")

    # If we crawled a LinkedIn profile page directly, treat that as the person link
    # but only when it looks like a profile page.
    scraped_url = (scraped_data.get('url') or '').strip()
    scraped_url_l = scraped_url.lower()
    if not linkedin_url and 'linkedin.com' in scraped_url_l and (('/in/' in scraped_url_l) or is_profile_url(scraped_url)[0]):
        linkedin_url = scraped_data.get('url', '')
    
    # Extract location/HQ
    locations = scraped_data.get('location', [])
    location_hq = locations[0] if locations else ""
    
    # Calculate propensity to buy score (0-100)
    rank = calculate_propensity_score(scraped_data, search_context)
    
    return {
        "email": primary_email,
        "phone": primary_phone,
        "linkedin_url": linkedin_url,
        "location_hq": location_hq,
        "rank": rank,
        "title": scraped_data.get('title', ''),
        "url": scraped_data.get('url', ''),
        "all_emails": emails,
        "all_phones": phones,
        "all_linkedin": linkedin_urls,
    }

def calculate_propensity_score(data, context=None):
    """
    Calculate propensity to buy score based on weighted criteria.
    
    Scoring Logic:
    - Role Fit (title keywords): +30
    - Company Intent (funding, recent news): +20
    - Technographic (tech stack): +15
    - Location (hub locations): +10
    - Scientific Intent (publications): +40
    
    Returns:
        Score from 0-100
    """
    score = 0
    text_content = data.get('text_content', '').lower()
    title = data.get('title', '').lower()
    url = data.get('url', '').lower()
    
    # Role Fit: Check for relevant titles/roles (+30 max)
    role_keywords = [
        'toxicology', 'safety', 'hepatic', '3d', 'preclinical',
        'drug development', 'director', 'head of', 'vp', 'chief'
    ]
    role_score = sum(5 for keyword in role_keywords if keyword in text_content or keyword in title)
    score += min(role_score, 30)
    
    # Company Intent: Funding indicators (+20 max)
    funding_keywords = ['series a', 'series b', 'funding', 'raised', 'investment', 'ipo']
    funding_score = sum(5 for keyword in funding_keywords if keyword in text_content)
    score += min(funding_score, 20)
    
    # Technographic: Tech adoption (+15 max)
    tech_keywords = ['in vitro', '3d model', 'organ-on-chip', 'spheroid', 'nam', 'new approach methodologies']
    tech_score = sum(5 for keyword in tech_keywords if keyword in text_content)
    score += min(tech_score, 15)
    
    # Location: Hub detection (+10 max)
    hub_locations = ['boston', 'cambridge', 'bay area', 'basel', 'san francisco', 'uk']
    location_score = sum(5 for loc in hub_locations if loc in text_content)
    score += min(location_score, 10)
    
    # Scientific Intent: Publication indicators (+40 max)
    science_keywords = ['publication', 'published', 'research', 'dili', 'liver injury', 'toxicity']
    science_score = sum(8 for keyword in science_keywords if keyword in text_content)
    score += min(science_score, 40)
    
    # Bonus: Has LinkedIn profile (+5)
    if data.get('linkedin_urls'):
        score += 5
    
    # Bonus: Has business email (+5)
    emails = data.get('emails', [])
    if any('@' in email and not any(x in email.lower() for x in ['gmail', 'yahoo', 'hotmail']) for email in emails):
        score += 5
    
    return min(score, 100)  # Cap at 100
