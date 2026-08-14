"""StructuredRunner 测试 —— 自愈重试与错误收敛。"""

import pytest
from pydantic import BaseModel

from agent_platform.harness.runner import StructuredRunner, StructuredOutputError
from agent_platform.llm.client import LLMOutputParseError

from agent_platform.testing import FakeLLM


class TinyModel(BaseModel):
    title: str
    count: int


def test_run_first_try_success():
    llm = FakeLLM(responses=[{"title": "ok", "count": 1}])
    model = StructuredRunner(llm).run("sys", "user", TinyModel)
    assert model.title == "ok"
    assert model.count == 1
    assert len(llm.calls) == 1


def test_run_self_heals_on_validation_error():
    """第一次输出缺字段 → 回传错误 → 第二次成功。"""
    llm = FakeLLM(responses=[{"title": "缺 count"}, {"title": "ok", "count": 2}])
    model = StructuredRunner(llm).run("sys", "user", TinyModel, max_retries=2)
    assert model.count == 2
    # 修正消息包含校验错误信息
    correction = llm.calls[-1]["messages"][-1]["content"]
    assert "count" in correction


def test_run_self_heals_on_parse_error():
    llm = FakeLLM(responses=["这不是 JSON", "```json\n{\"title\": \"ok\", \"count\": 3}\n```"])
    model = StructuredRunner(llm).run("sys", "user", TinyModel, max_retries=2)
    assert model.count == 3


def test_run_raises_after_retries_exhausted():
    llm = FakeLLM(responses=[{"title": "x"}, {"title": "y"}, {"title": "z"}])
    with pytest.raises(StructuredOutputError):
        StructuredRunner(llm).run("sys", "user", TinyModel, max_retries=2)
    assert len(llm.calls) == 3


def test_run_with_zero_retries_no_heal():
    llm = FakeLLM(responses=[{"title": "x"}])
    with pytest.raises(StructuredOutputError):
        StructuredRunner(llm).run("sys", "user", TinyModel, max_retries=0)
    assert len(llm.calls) == 1
