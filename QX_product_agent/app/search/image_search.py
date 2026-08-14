"""
============================================================
图片搜索引警 —— 基于 DuckDuckGo (免 API Key)
============================================================
"""
import logging
from typing import List
from ddgs import DDGS

logger = logging.getLogger(__name__)

def search_images(query: str, max_results: int = 3) -> List[dict]:
    """
    根据关键词搜索相关图片。

    Args:
        query: 搜索关键词
        max_results: 最大返回数量

    Returns:
        包含图片元数据的字典列表：[{"title": "...", "image": "https://...", "url": "..."}]
    """
    logger.info("[ImageSearch] 开始搜索图片: %s", query)
    try:
        ddgs = DDGS()
        results = ddgs.images(
            query,
            region="wt-wt",
            safesearch="moderate",
            max_results=max_results,
        )

        valid_images = []
        for res in results:
            if "image" in res and res["image"]:
                valid_images.append({
                    "title": res.get("title", ""),
                    "image": res.get("image", ""),     # 图片直链
                    "url": res.get("url", ""),         # 来源网页
                })

        logger.info("[ImageSearch] 成功获取 %d 张图片", len(valid_images))
        return valid_images

    except Exception as e:
        logger.error("[ImageSearch] 图片搜索失败 | query=%s | error=%s", query, str(e))
        return []

if __name__ == "__main__":
    # 模块自测
    imgs = search_images("Apple Vision Pro product design", max_results=2)
    for img in imgs:
        print(f"Title: {img['title']}\nImage URL: {img['image']}\n")
