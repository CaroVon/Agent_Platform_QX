import os

from dotenv import load_dotenv
from tavily import TavilyClient


load_dotenv()


def tavily_search(query: str, max_results: int = 5): #搜索召回量，后续调整为10-15

    api_key = os.getenv("TAVILY_API_KEY")

    client = TavilyClient(api_key=api_key)

    response = client.search(
        query=query,
        max_results=max_results,
    )

    return response


if __name__ == "__main__":

    result = tavily_search("AI眼镜行业")

    print(result)