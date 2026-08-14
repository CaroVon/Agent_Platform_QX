"""
============================================================
Product Studio 流水线冒烟测试（真实 LLM）
============================================================

绕过 Celery/Redis，直接内联调用 run_product_studio_pipeline 任务函数，
验证「QX 后端 → agent-platform → 四个专业 Agent → LangGraph 工作流」
的生产接线（真实 DeepSeek + Tavily 调用）。

用法（在 backend/ 目录下）:
    ../venv/bin/python ../scripts/studio_pipeline_smoke.py "AI 健身应用"

或直接使用默认想法:
    ../venv/bin/python ../scripts/studio_pipeline_smoke.py
"""

import sys
import uuid
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]  # QX_product_agent
_BACKEND_DIR = _PROJECT_ROOT / "backend"
_WORKSPACE_ROOT = _PROJECT_ROOT.parent

for _d in (str(_BACKEND_DIR), str(_PROJECT_ROOT),
           str(_WORKSPACE_ROOT / "agent-platform"), str(_WORKSPACE_ROOT)):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from sqlalchemy.orm import Session  # noqa: E402

from app.core.celery_db import get_sync_engine  # noqa: E402
from app.models import Base  # noqa: E402
from app.models.studio_product import StudioProduct, StudioProductStatus  # noqa: E402
from app.tasks.product_studio_tasks import run_product_studio_pipeline  # noqa: E402


def main() -> None:
    idea = sys.argv[1] if len(sys.argv) > 1 else "AI 健身应用"
    print(f"🚀 Product Studio 冒烟测试 | idea = {idea}")

    # ── 1. 建表 + 创建产品记录 ─────────────────────────────
    engine = get_sync_engine()
    Base.metadata.create_all(engine)
    product_id = uuid.uuid4()
    with Session(engine) as session:
        session.add(
            StudioProduct(id=product_id, idea=idea, status=StudioProductStatus.QUEUED)
        )
        session.commit()
    print(f"📦 产品记录已创建: {product_id}")

    # ── 2. 内联执行流水线任务（真实 LLM + Tavily 搜索） ─────
    print("▶ 执行流水线（真实 LLM 调用，预计 5-15 分钟）...")
    result = run_product_studio_pipeline(str(product_id))
    print("✅ 任务返回:", result)

    # ── 3. 汇总产物 ────────────────────────────────────────
    with Session(engine) as session:
        product = session.get(StudioProduct, product_id)
        import json

        package = json.loads(product.asset_package or "{}")
        meta = package.get("meta", {})
        print("\n═══ 结果汇总 ═══")
        print("状态:", product.status.value)
        print("节点状态:", meta.get("node_status"))
        print("节点错误:", meta.get("errors"))
        for key in ("requirement", "research", "competitor_analysis",
                    "strategy", "design", "presentation"):
            value = package.get(key)
            print(f"  {key}: {'✓ ' + str(len(value)) + ' 字段' if value else '✗ None'}")
        if product.status == StudioProductStatus.COMPLETED:
            print("\n🎉 资产包生成成功，可在前端 /studio 页面或 GET "
                  f"/api/v1/product/{product_id} 查看")


if __name__ == "__main__":
    main()
