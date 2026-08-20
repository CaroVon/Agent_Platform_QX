"""Mock 适配器 —— 离线开发/单测用（0 credits）。"""
from __future__ import annotations

from amazon_matrix_mod.metrics import parse_recent_sales

# 模拟 "wireless mouse" 竞品池（真实 ASIN/价格量级，主图用 media-amazon 占位图）
_MOCK_PRODUCTS = [
    {"asin": "B0MOCK001", "title": "Logitech M185 Compact Wireless Mouse", "brand": "Logitech",
     "current_price": 13.79, "rating": 4.5, "review_count": 44557,
     "recent_sales_raw": "7K+ bought in past month", "bsr": 1, "bsr_category": "Computer Mice",
     "is_fba": True, "main_image_url": "https://m.media-amazon.com/images/I/61C31dzk6pL._AC_SL1500_.jpg"},
    {"asin": "B0MOCK002", "title": "TECKNET Wireless Mouse 2.4G Ergonomic", "brand": "TECKNET",
     "current_price": 9.99, "rating": 4.5, "review_count": 78985,
     "recent_sales_raw": "9K+ bought in past month", "bsr": 4, "bsr_category": "Computer Mice",
     "is_fba": True, "main_image_url": "https://m.media-amazon.com/images/I/71tqvuHg5aL._AC_SL1500_.jpg"},
    {"asin": "B0MOCK003", "title": "Amazon Basics 2.4 GHz Wireless Mouse", "brand": "Amazon Basics",
     "current_price": 12.99, "rating": 4.5, "review_count": 69567,
     "recent_sales_raw": "6K+ bought in past month", "bsr": 280, "bsr_category": "Computer Mice",
     "is_fba": True, "main_image_url": "https://m.media-amazon.com/images/I/61YQeAUIhJL._AC_SL1500_.jpg"},
    {"asin": "B0MOCK004", "title": "Logitech G305 LIGHTSPEED Wireless Gaming Mouse", "brand": "Logitech",
     "current_price": 27.99, "rating": 4.6, "review_count": 39634,
     "recent_sales_raw": "5K+ bought in past month", "bsr": 7, "bsr_category": "Gaming Mice",
     "is_fba": True, "main_image_url": "https://m.media-amazon.com/images/I/51sg9BLSvjL._AC_SL1500_.jpg"},
    {"asin": "B0MOCK005", "title": "Afaartcci Rechargeable Wireless Mouse", "brand": "Afaartcci",
     "current_price": 5.99, "rating": 4.3, "review_count": 4674,
     "recent_sales_raw": "4K+ bought in past month", "bsr": 10, "bsr_category": "Computer Mice",
     "is_fba": False, "main_image_url": "https://m.media-amazon.com/images/I/61167CbmhGL._AC_SL1500_.jpg"},
    {"asin": "B0MOCK006", "title": "memzuoix 2.4G Wireless Mouse Silent", "brand": "memzuoix",
     "current_price": 15.99, "rating": 4.7, "review_count": 11,
     "recent_sales_raw": None, "bsr": 692, "bsr_category": "Computer Mice",
     "is_fba": False, "main_image_url": "https://m.media-amazon.com/images/I/51Z2e4e2zqL._AC_SL1500_.jpg"},
    {"asin": "B0MOCK007", "title": "INPHIC Wireless Mouse for Laptop", "brand": "INPHIC",
     "current_price": 15.99, "rating": 4.5, "review_count": 14,
     "recent_sales_raw": None, "bsr": 409, "bsr_category": "Computer Mice",
     "is_fba": False, "main_image_url": "https://m.media-amazon.com/images/I/51CWhVpdM2L._AC_SL1500_.jpg"},
    {"asin": "B0MOCK008", "title": "Logitech M240 Silent Wireless Mouse", "brand": "Logitech",
     "current_price": 18.99, "rating": 4.4, "review_count": 11267,
     "recent_sales_raw": "10K+ bought in past month", "bsr": 1, "bsr_category": "Computer Mice",
     "is_fba": True, "main_image_url": "https://m.media-amazon.com/images/I/51zmcWKpQyL._AC_SL1500_.jpg"},
    {"asin": "B0MOCK009", "title": "TECKNET Compact Ambidextrous Wireless Mouse", "brand": "TECKNET",
     "current_price": 8.99, "rating": 4.6, "review_count": 6962,
     "recent_sales_raw": "9K+ bought in past month", "bsr": 2, "bsr_category": "Computer Mice",
     "is_fba": True, "main_image_url": "https://m.media-amazon.com/images/I/51QcJV8PfbL._AC_SL1500_.jpg"},
    {"asin": "B0MOCK010", "title": "Logitech MX Master 4 Advanced Wireless Mouse", "brand": "Logitech",
     "current_price": 119.99, "rating": 4.2, "review_count": 1848,
     "recent_sales_raw": "1K+ bought in past month", "bsr": 14, "bsr_category": "Computer Mice",
     "is_fba": True, "main_image_url": "https://m.media-amazon.com/images/I/61z3ENJuXyL._AC_SL1500_.jpg"},
    {"asin": "B0MOCK011", "title": "Apple Magic Mouse - White", "brand": "Apple",
     "current_price": 69.0, "rating": 4.4, "review_count": 3386,
     "recent_sales_raw": None, "bsr": None, "bsr_category": None,
     "is_fba": True, "main_image_url": "https://m.media-amazon.com/images/I/516a630b1RL._AC_SL1500_.jpg"},
    {"asin": "B0MOCK012", "title": "Razer Viper V3 Pro SE Wireless Gaming Mouse", "brand": "Razer",
     "current_price": 119.99, "rating": None, "review_count": None,
     "recent_sales_raw": None, "bsr": 4503, "bsr_category": "Gaming Mice",
     "is_fba": True, "main_image_url": "https://m.media-amazon.com/images/I/61Ayc1B1pUL._AC_SL1500_.jpg"},
]


def fetch_competitors(keyword: str, limit: int = 50, **kwargs) -> list[dict]:
    """返回模拟竞品（截取 limit 个）。"""
    rows = []
    for p in _MOCK_PRODUCTS:
        row = dict(p)
        row["est_monthly_sales"] = parse_recent_sales(row.get("recent_sales_raw"))
        row["seller_type"] = "FBA" if row.get("is_fba") else "FBM"
        row["fetched_at"] = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows.append(row)
        if len(rows) >= limit:
            break
    return rows
