def build_search_context(search_results):

    results = search_results.get("results", [])

    context = ""

    for idx, item in enumerate(results, start=1):

        title = item.get("title", "")
        content = item.get("content", "")
        url = item.get("url", "")

        context += f"""
[Source {idx}]
Title: {title}

Content:
{content}

URL:
{url}

"""
    return context