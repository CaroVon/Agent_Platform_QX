"""
============================================================
声明式 ORM 基类与公共工具
—— 所有模型均从此 Base 派生
============================================================
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, func, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ─── UUID 类型别名 ──────────────────────────────────────────────
UUIDType = Uuid(as_uuid=True)


# ─── 声明式基类 ─────────────────────────────────────────────────
class Base(DeclarativeBase):
    """所有 ORM 模型的统一基类"""
    pass


# ─── 公共工具函数 ───────────────────────────────────────────────
def orm_to_dict(obj: Base) -> dict[str, Any]:
    """
    安全地将 ORM 模型实例转换为纯 Python 字典。

    自动处理：
    - enum → value 字符串
    - UUID → 字符串
    - datetime → ISO 格式字符串
    - None → None（保留）

    用于 FastAPI response_model 的 model_validate 兼容。
    """
    result: dict[str, Any] = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.key)
        if value is None:
            result[column.key] = None
        elif isinstance(value, (uuid.UUID,)):
            result[column.key] = str(value)
        elif hasattr(value, "value"):  # enum
            result[column.key] = value.value
        elif isinstance(value, datetime):
            result[column.key] = value.isoformat()
        else:
            result[column.key] = value
    return result
