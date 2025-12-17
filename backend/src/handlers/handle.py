from src.utils.duck import duck
import importlib
import logging

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


def scrape(query, max_results=5):
    """
    Search using DuckDuckGo and scrape the top results for lead data.

    This runs the spider synchronously for each top result (blocking).
    For production, run Scrapy in a separate worker or use the async runner.

    Scrapy/Twisted imports are performed lazily so the app can start even if Twisted
    or platform-specific dependencies (e.g., pywin32) are not available.
    """
    # Get search results from DuckDuckGo
    search_results = duck(query)

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
                results.append(processed)
        except Exception:
            logging.exception("Failed to crawl %s", url)

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

    search_results = duck(query)

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
            reactor.stop()
        except Exception:
            pass

    d.addBoth(_stop)
    try:
        reactor.run()
    except Exception:
        # reactor may already be running in some environments; just return what we have
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
    linkedin_urls = scraped_data.get('linkedin_urls', [])
    linkedin_url = linkedin_urls[0] if linkedin_urls else ""
    
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
