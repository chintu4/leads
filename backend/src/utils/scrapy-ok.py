import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

class MySpider(scrapy.Spider):
    name = "myspider"
    start_urls = ["https://mmd.techzer.top"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta={"playwright": True}
            )

    async def start(self):
        """Async-compatible start() that yields the existing start_requests() for Scrapy 2.13+"""
        for req in self.start_requests():
            yield req

    def parse(self, response):
        title = response.css("title::text").get()
        print("TITLE:", title)

if __name__ == "__main__":
    process = CrawlerProcess(get_project_settings())
    process.crawl(MySpider)
    process.start()
