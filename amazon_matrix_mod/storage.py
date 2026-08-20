"""数据资产化存储（P3.1）—— 按任务完整落盘 Rainforest 全部抓取条目。

目录结构（{task_dir}/data/）：
  manifest.json          任务元数据（keyword/marketplace/fetched_at/source/credits/top_n）
  search_raw.json        search 原始响应（全字段）
  products/{ASIN}.json   每 ASIN product 原始响应（49 字段全量）
  reviews/{ASIN}.json    评论分页原始（可选）
  offers/{ASIN}.json     offers 原始（可选）
  products.parquet       归一化宽表（全部条目为列 + 派生列）
  products.csv           同宽表人类可读版
  image_cache/{ASIN}.jpg 主图本地缓存（重绘零网络）
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pandas as pd


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def task_data_dir(task_dir: str) -> str:
    d = os.path.join(task_dir, "data")
    os.makedirs(d, exist_ok=True)
    return d


def save_manifest(data_dir: str, manifest: dict) -> str:
    path = os.path.join(data_dir, "manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    return path


def save_search_raw(data_dir: str, search_raw: dict | None) -> str | None:
    if not search_raw:
        return None
    path = os.path.join(data_dir, "search_raw.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(search_raw, f, ensure_ascii=False, indent=1)
    return path


def save_product_raw(data_dir: str, asin: str, raw: dict) -> str:
    d = os.path.join(data_dir, "products")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{asin}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=1)
    return path


def save_reviews_raw(data_dir: str, asin: str, reviews: list[dict]) -> str | None:
    if not reviews:
        return None
    d = os.path.join(data_dir, "reviews")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{asin}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"asin": asin, "fetched_at": utcnow(), "reviews": reviews},
                  f, ensure_ascii=False, indent=1)
    return path


def save_wide_table(data_dir: str, df: pd.DataFrame) -> tuple[str | None, str]:
    """归一化宽表 → parquet（无引擎时跳过）+ csv。"""
    parquet_path = os.path.join(data_dir, "products.parquet")
    csv_path = os.path.join(data_dir, "products.csv")
    try:
        df.to_parquet(parquet_path, index=False)
    except Exception:  # noqa: BLE001 —— 无 pyarrow/fastparquet 时降级
        parquet_path = None
    df.to_csv(csv_path, index=False, encoding="utf-8")
    return parquet_path, csv_path


def _fail_mark(data_dir: str, asin: str) -> str:
    return os.path.join(data_dir, "image_cache", f"{asin}.fail")


def cache_image(data_dir: str, asin: str, url: str | None) -> str | None:
    """主图下载到 image_cache/{ASIN}.jpg；已存在或已失败则跳过。失败写 .fail 标记。"""
    if not url:
        return None
    d = os.path.join(data_dir, "image_cache")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{asin}.jpg")
    if os.path.isfile(path) and os.path.getsize(path) > 1000:
        return path
    if os.path.isfile(_fail_mark(data_dir, asin)):
        return None
    try:
        import requests
        r = requests.get(url, timeout=(2, 5))
        if r.status_code == 200 and r.content:
            with open(path, "wb") as f:
                f.write(r.content)
            return path
    except Exception:  # noqa: BLE001 —— 缓存失败不影响管道
        pass
    try:
        open(_fail_mark(data_dir, asin), "w").close()
    except OSError:
        pass
    return None


def cache_image_url(data_dir: str, asin: str) -> str | None:
    """读取已缓存主图（无/失败标记则 None）。"""
    path = os.path.join(data_dir, "image_cache", f"{asin}.jpg")
    if os.path.isfile(path) and os.path.getsize(path) > 1000:
        return path
    return None


def image_failed(data_dir: str, asin: str) -> bool:
    """该 ASIN 主图是否已确认下载失败（跳过重试）。"""
    return os.path.isfile(_fail_mark(data_dir, asin))
