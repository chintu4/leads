# Scrapy settings for the project

DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

# Respect robots.txt where feasible during development; disable for full crawl in controlled envs
ROBOTSTXT_OBEY = False

# Be polite by default
DOWNLOAD_DELAY = 0.5
CONCURRENT_REQUESTS = 8

# Playwright-specific settings (if using scrapy-playwright)
PLAYWRIGHT_LAUNCH_OPTIONS = {"headless": True}
PLAYWRIGHT_BROWSER_TYPE = "chromium"

LOG_LEVEL = "INFO"

# Useful sources for discovery/enrichment (not consumed automatically)
SOURCES = [
    "https://pubmed.ncbi.nlm.nih.gov/",
    "https://linkedin.com/",
]