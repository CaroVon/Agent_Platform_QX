import os

from dotenv import load_dotenv
from firecrawl import FirecrawlApp


load_dotenv()


def crawl_url(url: str):

    api_key = os.getenv("FIRECRAWL_API_KEY")

    app = FirecrawlApp(api_key=api_key)

    result = app.scrape(
        url=url,
        formats=["markdown"]
    )

    return result


if __name__ == "__main__":

    test_url = "https://zhuanlan.zhihu.com/p/2026950345897653517"

    result = crawl_url(test_url)

    print(result)