import scrapy
import re
import importlib
from urllib.parse import urljoin
from scrapy.settings import Settings
from scrapy.utils.project import get_project_settings
import logging


class MySpider(scrapy.Spider):
    name = "myspider"
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    def __init__(self, start_url=None, collected=None, *args, **kwargs):
        super(MySpider, self).__init__(*args, **kwargs)
        # honor either start_url (single) or start_urls (list) if provided
        self.start_url = start_url or (getattr(self, 'start_urls', [None])[0]) or "https://example.com"
        self.extracted_data = {}
        # External collector (list) can be passed in for programmatic use
        self.collected = collected if isinstance(collected, list) else []
        self.logger = logging.getLogger(__name__)

    def start_requests(self):
        # If start_urls class attribute present, iterate those; otherwise use start_url
        urls = []
        if getattr(self, 'start_urls', None):
            urls = list(self.start_urls)
        else:
            urls = [self.start_url]

        for u in urls:
            self.logger.info("Starting request for URL: %s", u)
            yield scrapy.Request(
                url=u,
                callback=self.parse,
                errback=self.errback_handler,
                meta={"playwright": True}  # Triggers headless browser
            )

    def start_requests(self):
        # If start_urls class attribute present, iterate those; otherwise use start_url
        urls = []
        if getattr(self, 'start_urls', None):
            urls = list(self.start_urls)
        else:
            urls = [self.start_url]

        for u in urls:
            yield scrapy.Request(
                url=u,
                callback=self.parse,
                errback=self.errback_handler,
                meta={"playwright": True}  # Triggers headless browser
            )

    async def start(self):
        """Async-compatible start() for Scrapy 2.13+ (keeps backward compat with start_requests)."""
        for req in self.start_requests():
            yield req

    def parse(self, response):
        """Extract lead enrichment data from the webpage"""
        self.logger.info("Parsing response for URL: %s, status: %s", response.url, response.status)
        try:
            # Extract emails
            emails = self.extract_emails(response)
            self.logger.debug("Extracted emails: %s", emails)

            # Extract phone numbers
            phones = self.extract_phones(response)
            self.logger.debug("Extracted phones: %s", phones)

            # Extract LinkedIn URLs
            linkedin_urls = self.extract_linkedin(response)
            self.logger.debug("Extracted LinkedIn URLs: %s", linkedin_urls)

            # Extract location/HQ info
            location = self.extract_location(response)
            self.logger.debug("Extracted location: %s", location)

            # Extract company info
            company_info = self.extract_company_info(response)
            self.logger.debug("Extracted company info: %s", company_info)

            self.extracted_data = {
                "url": response.url,
                "title": response.css("title::text").get(default="").strip(),
                "emails": emails,
                "phones": phones,
                "linkedin_urls": linkedin_urls,
                "location": location,
                "company_info": company_info,
                "text_content": self.extract_text(response)
            }

            self.logger.info("Successfully extracted data for URL: %s", response.url)

            # Append to external collector if provided (useful for programmatic runs)
            if isinstance(self.collected, list):
                try:
                    self.collected.append(self.extracted_data)
                except Exception:
                    self.logger.exception("Failed to append extracted data to collector")

            yield self.extracted_data
        except Exception as e:
            self.logger.exception("Error during parsing for URL: %s", response.url)
            yield {"error": str(e), "url": response.url}

    def extract_emails(self, response):
        """Extract email addresses from page"""
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        text = response.text
        emails = list(set(re.findall(email_pattern, text)))
        # Filter out common false positives
        emails = [e for e in emails if not any(x in e.lower() for x in ['example.com', 'sentry.io', 'w3.org'])]
        return emails[:5]  # Limit to top 5

    def extract_phones(self, response):
        """Extract phone numbers from page"""
        phone_patterns = [
            r'\+?1?[-.]?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}',  # US format
            r'\+\d{1,3}[-.]?\d{1,4}[-.]?\d{1,4}[-.]?\d{1,9}',  # International
        ]
        phones = []
        for pattern in phone_patterns:
            phones.extend(re.findall(pattern, response.text))
        return list(set(phones))[:5]

    def extract_linkedin(self, response):
        """Extract LinkedIn profile URLs"""
        linkedin_urls = response.css('a[href*="linkedin.com"]::attr(href)').getall()
        linkedin_urls = [url for url in linkedin_urls if '/in/' in url or '/company/' in url]
        return list(set(linkedin_urls))[:5]

    def extract_location(self, response):
        """Extract location/HQ information"""
        # Look for common location keywords
        location_keywords = ['headquarters', 'hq', 'location', 'office', 'address', 'based in']
        text_lower = response.text.lower()

        locations = []
        for keyword in location_keywords:
            if keyword in text_lower:
                # Extract surrounding text
                idx = text_lower.find(keyword)
                snippet = response.text[max(0, idx-50):min(len(response.text), idx+100)]
                locations.append(snippet.strip())

        return locations[:3] if locations else []

    def extract_company_info(self, response):
        """Extract company information"""
        return {
            "meta_description": response.css('meta[name="description"]::attr(content)').get(default=""),
            "og_title": response.css('meta[property="og:title"]::attr(content)').get(default=""),
            "og_description": response.css('meta[property="og:description"]::attr(content)').get(default=""),
        }

    def extract_text(self, response):
        """Extract main text content for analysis"""
        # Remove script and style elements
        text = ' '.join(response.css('p::text, h1::text, h2::text, h3::text').getall())
        return text[:1000]  # Limit to first 1000 chars

    def errback_handler(self, failure):
        """Handle request failures"""
        url = failure.request.url if hasattr(failure, 'request') else "unknown"
        self.logger.error("Request failed for URL: %s, failure: %s", url, failure)
        self.logger.error("Failure type: %s, failure value: %s", type(failure), failure.value if hasattr(failure, 'value') else 'N/A')
        if hasattr(failure, 'request') and hasattr(failure.request, 'meta'):
            self.logger.error("Request meta: %s", failure.request.meta)
        self.extracted_data = {
            "error": str(failure),
            "url": url,
            "failure_type": str(type(failure)),
            "failure_value": str(failure.value) if hasattr(failure, 'value') else 'N/A'
        }

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings


def _load_spider_settings(module_name='src.utils.settings'):
    """Load uppercase settings from the project's settings module into a Scrapy Settings object."""
    try:
        mod = importlib.import_module(module_name)
        settings_dict = {k: v for k, v in vars(mod).items() if k.isupper()}
        s = Settings()
        s.setdict(settings_dict, priority='project')
        return s
    except Exception:
        # Fallback to project settings if explicit module not available
        return get_project_settings()


def crawl_url(start_url, settings=None, timeout=None):
    """Run MySpider synchronously against a single URL and return collected items.

    This convenience helper is suitable for local POCs. For production you
    should run Scrapy in a worker process or use a queue.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Starting crawl_url for URL: %s", start_url)
    collected = []
    # Reduce Scrapy logger noise for programmatic runs (avoid repeated startup messages)
    try:
        import logging
        logging.getLogger('scrapy').setLevel(logging.WARNING)
        logging.getLogger('scrapy.utils.log').setLevel(logging.WARNING)
    except Exception:
        pass

    if settings is None:
        try:
            proc_settings = _load_spider_settings()
            if proc_settings is None:
                proc_settings = get_project_settings()
        except NameError:
            # If helper is not present for any reason, fallback to project settings
            proc_settings = get_project_settings()
    else:
        s = Settings()
        s.setdict(settings)
        proc_settings = s

    logger.debug("Using settings: %s", dict(proc_settings))

    # Run using CrawlerRunner so we can control reactor startup safely across threads
    from scrapy.crawler import CrawlerRunner
    from twisted.internet import reactor, defer
    import threading

    runner = CrawlerRunner(settings=proc_settings)

    @defer.inlineCallbacks
    def _run():
        logger.info("CrawlerRunner starting crawl for URL: %s", start_url)
        yield runner.crawl(MySpider, start_url=start_url, collected=collected)

    d = _run()

    def _stop(_=None):
        try:
            logger.info("Stopping reactor for URL: %s", start_url)
            reactor.stop()
        except Exception as e:
            logger.exception("Error stopping reactor: %s", e)

    d.addBoth(_stop)

    try:
        # If we're in the main thread allow reactor to install signal handlers; otherwise avoid it.
        if threading.current_thread() is threading.main_thread():
            logger.debug("Running reactor in main thread for URL: %s", start_url)
            reactor.run()
        else:
            logger.debug("Running reactor in worker thread for URL: %s", start_url)
            reactor.run(installSignalHandlers=False)
    except Exception as e:
        # reactor may already be running in some environments; just return what we have
        logger.exception("Error running reactor for URL: %s", e)

    logger.info("Crawl completed for URL: %s, collected %d items", start_url, len(collected))
    return collected


if __name__ == "__main__":
    # Quick manual test
    items = crawl_url("https://mmd.techzer.top")
    print("Found items:", items)
