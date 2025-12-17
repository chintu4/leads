# -*- coding: utf-8 -*-

import scrapy
from scrapy.crawler import CrawlerProcess

class MySpider(scrapy.Spider):
    name = "myspider"
    start_urls = ["https://mmd.techzer.top"]

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                }
            )

    async def parse(self, response):
        print("TITLE:", response.css("title::text").get())

        page = response.meta.get("playwright_page")
        if page:
            await page.close()

if __name__ == "__main__":
    settings = {
        "LOG_LEVEL": "INFO",
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
    }

    process = CrawlerProcess(settings)
    process.crawl(MySpider)
    process.start()
