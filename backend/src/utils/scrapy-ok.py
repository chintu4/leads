import scrapy

class MySpider(scrapy.Spider):
    name = "myspider"

    def start_requests(self):
        yield scrapy.Request(
            url="https://example.com",
            meta={"playwright": True}  # <--- This triggers the headless browser
        )

    def parse(self, response):
        # This response now contains HTML rendered by JavaScript
        yield {"title": response.css("title::text").get()}

