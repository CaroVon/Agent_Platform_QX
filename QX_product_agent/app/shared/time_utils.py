"""
============================================================
统一时间戳工厂 —— 全项目唯一的 UTC 时间获取入口
============================================================

使用方式：
    from app.shared.time_utils import utcnow
    now = utcnow()  # 返回 timezone-aware UTC datetime

规则：
    - 所有数据库写入的时间字段必须使用 utcnow()
    - 所有 API 响应的时间字段必须是 UTC（由序列化层处理）
    - 前端根据用户时区进行本地化显示
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """
    返回带 UTC 时区标记的当前时间。

    替代项目中散落的 datetime.now() (naive) 和
    datetime.now(timezone.utc) 调用，确保全项目时间处理一致。
    """
    return datetime.now(timezone.utc)
