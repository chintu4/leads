from src.handlers.handle import process


def test_process_sets_linkedin_url_when_scraped_url_is_profile():
    scraped = {
        "url": "https://www.linkedin.com/in/jane-doe",
        "title": "Jane Doe | LinkedIn",
        "emails": [],
        "phones": [],
        "linkedin_urls": [],
        "location": [],
        "text_content": "",
    }
    out = process(scraped)
    assert out.get("linkedin_url") == scraped["url"]


def test_process_prefers_in_profile_over_company():
    scraped = {
        "url": "https://example.com",
        "title": "Example",
        "emails": [],
        "phones": [],
        "linkedin_urls": [
            "https://www.linkedin.com/company/acme",
            "https://www.linkedin.com/in/jane-doe",
        ],
        "location": [],
        "text_content": "",
    }
    out = process(scraped)
    assert out.get("linkedin_url") == "https://www.linkedin.com/in/jane-doe"
