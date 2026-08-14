from app.search.tavily_search import tavily_search
from app.crawler.firecrawl_crawler import crawl_url


def research_topic(query: str):

    search_results = tavily_search(query)

    results = search_results.get("results", [])

    collected_docs = []

    for idx, item in enumerate(results[:3], start=1):

        url = item.get("url")

        title = item.get("title")

        print(f"\n[{idx}] Crawling: {title}")
        print(url)

        try:

            crawl_result = crawl_url(url)

            markdown = getattr(crawl_result, "markdown", "")

            if markdown:

                collected_docs.append({
                    "title": title,
                    "url": url,
                    "content": markdown[:8000]
                })

                print(f"[OK] Content length: {len(markdown)}")

            else:

                print("[WARN] Empty content")

        except Exception as e:

            print(f"[ERROR] {e}")

    return collected_docs


if __name__ == "__main__":

    docs = research_topic("AI眼镜行业")

    print("\n========== RESULT ==========\n")

    for doc in docs:

        print(doc["title"])
        print(doc["content"][:1000])
        print("\n====================\n")