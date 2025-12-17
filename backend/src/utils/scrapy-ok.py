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

    def parse(self, response):
        title = response.css("title::text").get()
        print("TITLE:", title)

if __name__ == "__main__":
    process = CrawlerProcess(get_project_settings())
    process.crawl(MySpider)
    process.start()
