# Scrapy settings for the project

DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

# Respect robots.txt where feasible during development; disable for full crawl in controlled envs
ROBOTSTXT_OBEY = False

# Be polite by default
DOWNLOAD_DELAY = 1.0
CONCURRENT_REQUESTS = 16

# Increase timeout for slow sites
DOWNLOAD_TIMEOUT = 300

# Retry settings
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Playwright-specific settings (if using scrapy-playwright)
PLAYWRIGHT_LAUNCH_OPTIONS = {"headless": True}
PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 120000  # 2 minutes

LOG_LEVEL = "INFO"

# Useful sources for discovery/enrichment (not consumed automatically)
SOURCES = [
    "https://pubmed.ncbi.nlm.nih.gov/",
    "https://linkedin.com/"
]