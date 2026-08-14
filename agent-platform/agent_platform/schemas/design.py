"""
UX 设计 —— Design Agent 的结构化输出

Design Agent 输出契约（对齐产品需求）:
  {
    "user_flow": [],
    "pages": [],
    "components": []
  }
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class UserFlowStep(BaseModel):
    """用户旅程中的单个步骤。"""

    step: str = Field(description="步骤名（如：注册 → 测评 → 生成计划）")
    description: str = Field(default="", description="步骤说明")
    is_entry: bool = Field(default=False, description="是否为旅程入口")
    is_exit: bool = Field(default=False, description="是否为旅程终点")


class PageSpec(BaseModel):
    """页面规格（信息架构层面，不含视觉实现）。"""

    name: str = Field(description="页面名（如：训练计划页）")
    purpose: str | None = Field(default=None, description="页面目的")
    key_elements: list[str] = Field(default_factory=list, description="核心页面元素")


class ComponentSpec(BaseModel):
    """UI 组件规格（结构化描述，前端负责视觉实现）。"""

    name: str = Field(description="组件名（如：训练强度滑块）")
    kind: str = Field(default="", description="组件类型（input / chart / card / list ...）")
    description: str | None = Field(default=None, description="交互与用途说明")


class UXDesign(BaseModel):
    """Design Agent 完整输出。"""

    user_flow: list[UserFlowStep] = Field(default_factory=list)
    pages: list[PageSpec] = Field(default_factory=list)
    components: list[ComponentSpec] = Field(default_factory=list)
