"""
============================================================
编辑器 AI 服务 —— Inline AI 局部改写 + 块级精准编辑
============================================================

支撑前端 Tiptap 编辑器中的"行间指令 (Inline AI Bubble)"功能。
支持三种交互模式:

1. 快速指令：扩写 / 精简 / 润色 / 补充竞品案例 / 语气改简练
2. 自定义指令：用户在 Bubble 中自由输入改写要求
3. 块级精准编辑：基于 DocumentBlock ID 的上下文感知改写

每次改写返回 revised_text，前端可做 Diff 对比后接受或拒绝。
"""

from __future__ import annotations

import uuid
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.document_block import DocumentBlock
from app.models.project import Project, ProjectStatus
from app.schemas import EditorChatRequest
from app.rag.rag_pipeline import retrieve_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/editor", tags=["editor"])


# ══════════════════════════════════════════════════════════
# 产品研究专用 Inline AI System Prompt
# ══════════════════════════════════════════════════════════
_INLINE_AI_SYSTEM = """你是一位资深产品经理兼技术文案专家，正在帮助团队打磨产品研究报告中的具体段落。

你的每一次改写都遵循以下原则：
1. **产品化思维**：始终保持"产品经理/设计师"视角，避免泛泛而谈
2. **精确性**：保留并强化原文中的具体数据、技术参数、设计决策
3. **可读性**：改写后的文本应当清晰、直接，适合路演和产品评审场景
4. **脚注保护**：原文中的脚注角标 (如 [^1][^2]) 必须原样保留，不可删除或改变编号
5. **仅返回改写文本**：不要添加任何解释、前缀或 Markdown 格式标注"""


# ── 快速指令映射 ──────────────────────────────────────────
_INSTRUCTION_HINTS: dict[str, str] = {
    "扩写": "请将以下段落扩写至原文的 1.5-2 倍长度。增加具体的产品设计细节、技术参数或用户行为数据，使论证更加充分。注意保留所有脚注角标。",
    "精简": "请将以下段落精简至原文的一半长度。保留核心论点和关键数据，删除冗余修饰词。注意保留所有脚注角标。",
    "润色": "请优化以下段落的表达，使其更具专业感、节奏感和可读性。不要改变原意和长度。注意保留所有脚注角标。",
    "补充竞品案例": "请在以下段落的基础上，补充 1-2 个具体的竞品案例或对标产品的设计决策（如已知），增强论证的说服力。注意保留所有脚注角标。",
    "语气改简练": "请将以下段落的语气改为更直接简练的风格，适合路演级汇报。去除冗余修饰，强化逻辑链。注意保留所有脚注角标。",
    "使表达更正式": "请将以下段落的语气升级为更正式的商业汇报风格，适合向高管层汇报。注意保留所有脚注角标。",
}


# ══════════════════════════════════════════════════════════
# Schemas
# ══════════════════════════════════════════════════════════

class EditorReviseRequest(BaseModel):
    """编辑器 AI 改写请求"""
    selected_text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="用户在编辑器中选中的文本内容",
    )
    instruction: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="改写指令（扩写/精简/润色/自定义）",
        examples=["扩写", "精简", "润色", "补充竞品案例"],
    )
    context: str | None = Field(
        None,
        max_length=20000,
        description="可选的前后文语境（帮助 LLM 保持风格一致）",
    )


class EditorReviseResponse(BaseModel):
    """编辑器 AI 改写响应"""
    revised_text: str = Field(..., description="LLM 改写后的纯文本")


class BlockReviseRequest(BaseModel):
    """块级精准改写请求 —— 基于 DocumentBlock ID"""
    instruction: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="改写指令",
    )
    context_selection: str | None = Field(
        None,
        max_length=5000,
        description="额外的上下文文本（可选）",
    )


# ══════════════════════════════════════════════════════════
# POST /api/v1/editor/revise —— AI 改写选中文本 (Inline AI Bubble)
# ══════════════════════════════════════════════════════════

@router.post("/revise", response_model=EditorReviseResponse)
async def revise_text(body: EditorReviseRequest):
    """
    对用户在 Tiptap 编辑器中选中的文本块执行 AI 改写。

    调用方式：
    - 前端用户选中一段文本 → 弹出 InlineAIBubble
    - 点击「扩写」「精简」「润色」等快速按钮，或输入自定义指令
    - 调用此 API，返回改写结果
    - 前端展示 Diff 对比，用户可选择接受或放弃

    参数:
    - **selected_text**: 用户选中的原文
    - **instruction**: 改写指令（支持中文快速指令 + 任意自定义描述）
    - **context**: （可选）段落前后文，用于保持语境连贯
    """
    try:
        settings = get_settings()

        # 解析快速指令
        hint = _INSTRUCTION_HINTS.get(body.instruction, body.instruction)
        if hint == body.instruction:
            # 自定义指令——包装一下，使其更规范
            hint = f"请根据以下指令改写文本：{body.instruction}。注意保留所有脚注角标。"

        user_message = f"【指令】{hint}\n\n【原文】\n{body.selected_text}"

        if body.context:
            user_message += (
                f"\n\n【上下文参考（仅用于理解语境，不要直接引用其中内容）】\n"
                f"{body.context}"
            )

        llm = ChatOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            model=settings.DEEPSEEK_MODEL,
            temperature=0.3,
        )

        response = llm.invoke([
            {"role": "system", "content": _INLINE_AI_SYSTEM},
            {"role": "user", "content": user_message},
        ])

        revised_text = response.content.strip()
        if not revised_text:
            raise ValueError("LLM 返回空内容")

        logger.info(
            "editor/revise OK | instruction=%s | original_len=%d | revised_len=%d",
            body.instruction, len(body.selected_text), len(revised_text),
        )

        return EditorReviseResponse(revised_text=revised_text)

    except Exception as e:
        logger.error("editor/revise FAIL | instruction=%s | %s", body.instruction, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI 改写失败: {str(e)}",
        )


# ══════════════════════════════════════════════════════════
# POST /api/v1/editor/revise-block/{block_id} —— 块级精准改写
# ══════════════════════════════════════════════════════════

@router.post("/revise-block/{block_id}", response_model=EditorReviseResponse)
async def revise_block(
    block_id: uuid.UUID,
    body: BlockReviseRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    🎯 块级精准改写 —— 基于 DocumentBlock ID 的上下文感知编辑。

    与 /revise 的区别：
    - /revise: 纯文本改写，不涉及数据库（轻量、无状态）
    - /revise-block: 从数据库加载目标块 + 前后相邻块作为上下文，
      改写完成后更新数据库中的 DocumentBlock 内容

    前端使用流程：
    1. 用户在 Tiptap 中点击某个块旁边的 "AI 改写" 按钮
    2. 弹出指令输入框（支持快速指令 + 自定义指令）
    3. 调用此 API，后端读取块的完整上下文后改写
    4. 返回 revised_text，前端展示 Diff 对比
    5. 用户接受 → 前端调用 PATCH /blocks/{block_id} 保存
       用户拒绝 → 无操作

    参数:
    - **block_id**: DocumentBlock 的 UUID
    - **instruction**: 改写指令
    - **context_selection**: （可选）额外上下文
    """
    try:
        settings = get_settings()

        # 1. 加载目标块
        block_result = await db.execute(
            select(DocumentBlock).where(DocumentBlock.id == block_id)
        )
        block = block_result.scalar_one_or_none()
        if block is None:
            raise HTTPException(status_code=404, detail=f"文档块 {block_id} 不存在")

        # 2. 加载前后相邻块作为上下文 (同 project 内按 order_index 排序)
        neighbors_result = await db.execute(
            select(DocumentBlock)
            .where(
                DocumentBlock.project_id == block.project_id,
                DocumentBlock.order_index.in_([
                    block.order_index - 1,
                    block.order_index + 1,
                ]),
            )
            .order_by(DocumentBlock.order_index)
        )
        neighbors = neighbors_result.scalars().all()

        # 3. 构建上下文
        context_parts: list[str] = []
        for nb in neighbors:
            context_parts.append(f"[前后文] {nb.content[:500]}")
        if body.context_selection:
            context_parts.append(f"[用户提供的参考] {body.context_selection}")

        # 4. LLM 改写
        hint = _INSTRUCTION_HINTS.get(body.instruction, body.instruction)
        if hint == body.instruction:
            hint = f"请根据以下指令改写文本：{body.instruction}。注意保留所有脚注角标。"

        user_message = (
            f"【指令】{hint}\n\n"
            f"【目标段落】\n{block.content}\n"
        )
        if context_parts:
            user_message += (
                f"\n【语境参考（仅用于保持风格一致，不要直接引用）】\n"
                + "\n".join(context_parts)
            )

        llm = ChatOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            model=settings.DEEPSEEK_MODEL,
            temperature=0.3,
        )

        response = llm.invoke([
            {"role": "system", "content": _INLINE_AI_SYSTEM},
            {"role": "user", "content": user_message},
        ])

        revised_text = response.content.strip()
        if not revised_text:
            raise ValueError("LLM 返回空内容")

        logger.info(
            "editor/revise-block OK | block_id=%s | section=%s | instruction=%s",
            block_id, block.section_title, body.instruction,
        )

        return EditorReviseResponse(revised_text=revised_text)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("editor/revise-block FAIL | block_id=%s | %s", block_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"块级改写失败: {str(e)}",
        )


# ══════════════════════════════════════════════════════════
# 🆕 POST /api/v1/editor/chat —— 侧边栏大模型流式对话
# ══════════════════════════════════════════════════════════

_CHAT_WORK_SYSTEM = (
    "你是一个专业的产品分析师与报告撰写助手。"
    "请务必优先基于【项目知识库参考】或【编辑器选中文本参考】中的信息来客观、严谨地回答用户问题。"
    "如果是提取或总结任务，请直接列出核心主题，不要包含多余的寒暄。"
)
_CHAT_GENERAL_SYSTEM = (
    "你是一个友好的 AI 助手，请自然、轻松地回答我的问题。"
)


@router.post("/chat")
async def chat_with_editor(body: EditorChatRequest):
    """
    侧边栏大模型对话（SSE 流式输出）。

    支持传入编辑器中选中的文本作为辅助上下文，
    支持工作模式 (work) 与聊天模式 (chat) 切换。
    """
    settings = get_settings()

    # 1. 确定 System Prompt
    sys_prompt = _CHAT_WORK_SYSTEM if body.chat_mode == "work" else _CHAT_GENERAL_SYSTEM

    # 2. 构建消息体
    messages = [{"role": "system", "content": sys_prompt}]

    for msg in body.history:
        messages.append({"role": msg.role, "content": msg.content})

    # 拼接当前用户提问与选中文本
    current_content = body.message
    if body.selected_text:
        current_content += f"\n\n【编辑器选中文本参考】\n{body.selected_text}"

    # 🚀 RAG 检索逻辑（仅在 work 模式下触发，避免闲聊浪费 Token 和耗时）
    if body.chat_mode == "work" or "test" in body.message.lower():  # 兼容聊天模式下强制测试文档
        try:
            pid = str(body.project_id) if body.project_id else None
            # 三层融合检索：任务库(L2) + 领域库(L1) + 全局库(L0)
            rag_context = retrieve_context(
                query=body.message,
                k=10,
                project_id=pid,
            )
            if rag_context and rag_context.strip():
                current_content += f"\n\n【知识库参考（任务+领域+全局三层）】\n{rag_context}"
                logger.info("editor/chat 成功召回知识库内容 (project_id=%s)", pid)
        except Exception as e:
            logger.warning("editor/chat RAG 检索异常: %s", str(e))

        # 🆕 相似任务经验注入（L1 领域知识：跨任务借用）
        if body.project_id:
            try:
                from app.rag.task_similarity import retrieve_experiences
                experiences = retrieve_experiences(str(body.project_id))
                if experiences:
                    current_content += f"\n\n{experiences}"
            except Exception as e:
                logger.warning("editor/chat 相似任务经验注入失败: %s", str(e))

        # 🆕 P4: 记忆图注入（跨任务实体/关系/洞察）
        try:
            from app.rag.memory_extraction import retrieve_memory_context
            memory_ctx = retrieve_memory_context(
                query=body.message,
                project_id=str(body.project_id) if body.project_id else None,
                k=10,
            )
            if memory_ctx:
                current_content += f"\n\n{memory_ctx}"
        except Exception as e:
            logger.warning("editor/chat 记忆图注入失败: %s", str(e))

    messages.append({"role": "user", "content": current_content})

    # 3. 实例化 LLM 客户端（开启 streaming）
    llm = ChatOpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        model=settings.DEEPSEEK_MODEL,
        temperature=0.7 if body.chat_mode == "chat" else 0.3,
        streaming=True,
    )

    async def event_generator():
        try:
            async for chunk in llm.astream(messages):
                if chunk.content:
                    data = json.dumps({"text": chunk.content}, ensure_ascii=False)
                    yield f"event: content\ndata: {data}\n\n"

            # 流结束标志
            yield f"event: done\ndata: {json.dumps({'finish_reason': 'stop'})}\n\n"
        except Exception as e:
            logger.error("editor/chat 流式输出失败 | error=%s", str(e))
            error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
