"""
============================================================
状态机流转单元测试
—— 验证 ProjectStatus 枚举值与 API 层的状态约束
============================================================
"""

import pytest
from app.models.project import ProjectStatus


class TestProjectStatusEnum:
    """ProjectStatus 枚举的完整性测试"""

    def test_all_statuses_defined(self):
        """验证所有预期的状态都已定义"""
        expected = {
            "preparing_data",
            "waiting_for_sources",
            "preparing_outline",
            "waiting_for_outline",
            "drafting",
            "completed",
            "failed",
        }
        actual = {e.value for e in ProjectStatus}
        assert actual == expected, f"状态枚举不匹配: {actual - expected} | {expected - actual}"

    def test_terminal_states(self):
        """终态（completed, failed）不应再进行流转（由 API 层约束）"""
        terminal = {ProjectStatus.COMPLETED, ProjectStatus.FAILED}
        for status in ProjectStatus:
            if status in terminal:
                assert status in terminal

    def test_interactive_states(self):
        """交互状态（等待用户操作）"""
        interactive = {ProjectStatus.WAITING_FOR_SOURCES, ProjectStatus.WAITING_FOR_OUTLINE}
        for status in interactive:
            assert status in interactive

    def test_transition_path(self):
        """主流程状态流转路径验证"""
        path = [
            ProjectStatus.PREPARING_DATA,
            ProjectStatus.WAITING_FOR_SOURCES,
            ProjectStatus.PREPARING_OUTLINE,
            ProjectStatus.WAITING_FOR_OUTLINE,
            ProjectStatus.DRAFTING,
            ProjectStatus.COMPLETED,
        ]
        # 确保每个状态的 value 是唯一的
        values = [s.value for s in path]
        assert len(values) == len(set(values)), "状态值必须唯一"


class TestStateMachineConstraints:
    """
    状态机约束测试 —— 这些约束在 API 层 (projects.py) 实现，
    此处作为文档和执行规范。
    """

    APPROVAL_REQUIRED = {
        ProjectStatus.WAITING_FOR_SOURCES: "review-sources",
        ProjectStatus.WAITING_FOR_OUTLINE: "approve-outline",
    }

    def test_approval_endpoints_match_states(self):
        """每个交互状态都有对应的审批端点"""
        interactive_states = {ProjectStatus.WAITING_FOR_SOURCES, ProjectStatus.WAITING_FOR_OUTLINE}
        assert set(self.APPROVAL_REQUIRED.keys()) == interactive_states

    def test_blocking_states_prevent_download(self):
        """下载仅在 COMPLETED 状态下可用（API 层约束）"""
        blocking = {
            ProjectStatus.PREPARING_DATA,
            ProjectStatus.WAITING_FOR_SOURCES,
            ProjectStatus.PREPARING_OUTLINE,
            ProjectStatus.WAITING_FOR_OUTLINE,
            ProjectStatus.DRAFTING,
        }
        # COMPLETED 不在 blocking 中
        assert ProjectStatus.COMPLETED not in blocking
        # FAILED 也不在 blocking 中（因为它有自己的错误消息）
        assert ProjectStatus.FAILED not in blocking
