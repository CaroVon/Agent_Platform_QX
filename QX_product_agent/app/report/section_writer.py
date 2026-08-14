"""
============================================================
产品研究报告章节撰写器
—— 人设：资深产品经理 / 工业设计师 / 用户体验专家
   严格保留脚注角标引用规则 [^1] 与 Markdown 排版要求
============================================================
"""
import logging
import re

from app.llm.client import get_llm, generate_image
from app.llm.prompts import PromptFactory
from app.rag.retriever import retrieve
from app.rag.citation_utils import build_context_with_citations, resolve_and_append_citations

logger = logging.getLogger(__name__)


def _safe_topic(topic: str) -> str:
    """移除文件名非法字符，确保与 workflow.py 路径一致。"""
    return re.sub(r'[\\/:*?"<>|]', '_', topic)


def _clean_llm_output(raw_content: str, section_title: str) -> str:
    """
    健壮地清理 LLM 输出：
    1. 截断首个 ## 之前的寒暄语/前缀文本
    2. 移除紧跟在首个章节标题后的重复标题（同一数字前缀或相同文本）
    3. 移除残留的寒暄语模式
    """
    # Step 1: 截断首个 ## 之前的所有内容
    match_idx = raw_content.find("##")
    if match_idx != -1:
        raw_content = raw_content[match_idx:]
    else:
        raw_content = f"## {section_title}\n\n" + raw_content.strip()
        return raw_content

    # Step 2: 移除重复的章节标题
    lines = raw_content.split("\n")
    cleaned_lines: list[str] = []
    first_heading_seen = False
    # 提取章节标题的数字前缀，如 "1." "2.1" 等
    title_num_prefix = re.match(r'^(\d+[\.\s])', section_title)

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") or stripped.startswith("### "):
            heading_text = re.sub(r'^#{1,6}\s+', '', stripped)
            if not first_heading_seen:
                first_heading_seen = True
                cleaned_lines.append(line)
            else:
                # 判断是否为重复标题
                heading_num_prefix = re.match(r'^(\d+[\.\s])', heading_text)
                is_duplicate = (
                    heading_text == section_title
                    or heading_text in section_title
                    or section_title in heading_text
                    or (title_num_prefix and heading_num_prefix
                        and title_num_prefix.group(1) == heading_num_prefix.group(1)
                        and len(heading_text) < len(section_title) * 2)
                )
                if is_duplicate:
                    continue  # 跳过重复标题
                else:
                    cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)

    raw_content = "\n".join(cleaned_lines)

    # Step 3: 移除残留的常见寒暄语模式
    raw_content = re.sub(
        r'^(好的[，,]?\s*|收到[，,]?\s*|以下是[，,]?\s*|以下为[，,]?\s*|这是[，,]?\s*)',
        '',
        raw_content,
        flags=re.MULTILINE,
    )

    return raw_content




# ══════════════════════════════════════════════════════════
# 多模态绘图关键词（用于路由到生图策略）
# ══════════════════════════════════════════════════════════
_IMAGE_SECTION_KEYWORDS = ["生图", "图鉴", "概念图"]


def _is_image_section(section_title: str) -> bool:
    """判断是否为多模态绘图章节。"""
    return any(kw in section_title for kw in _IMAGE_SECTION_KEYWORDS)


def _write_image_section(topic: str, section_title: str) -> str:
    """
    多模态绘图章节——调用硅基流动图像生成模型生成 16:9 概念图。
    失败时输出 graceful degradation 提示。
    """
    safe = _safe_topic(topic)
    llm = get_llm()

    logger.info("→ [🎨 多模态绘图] 正在为章节【%s】生成概念图...", section_title)
    image_relative_path = f"outputs/images/{safe}_concept.png"

    # 让 LLM 生成英文工业设计级 Prompt
    prompt_generator = (
        f"你是一位资深工业设计师。请为主题为 '{topic}' 的前沿科技产品，"
        f"撰写一段用于 AI 文生图模型的英文视觉描述 (Prompt)。\n"
        f"要求：包含材质 (Material)、造型线条 (Form Language)、光影氛围 (Lighting Mood)、"
        f"摄影视角 (Camera Angle)。横版 16:9 构图。\n"
        f"直接输出英文 Prompt，严禁任何多余文字或解释。"
    )
    img_prompt = llm.invoke(prompt_generator).content.strip()

    success = generate_image(img_prompt, image_relative_path)

    if success:
        return (
            f"## {section_title}\n\n"
            f"本章节由多模态工业设计绘图引擎实时渲染生成。"
            f"以下是基于前述产品分析推演出的前沿概念设计：\n\n"
            f"![{topic}概念图](../{image_relative_path})\n\n"
            f"> *图注：由硅基流动 AI 图像引擎以 16:9 横版构图渲染的高精度产品概念图。"
            f"材质、光感与造型均基于前述 CMF 设计语言推演。*\n"
        )
    else:
        return (
            f"## {section_title}\n\n"
            f"[⚠️ 视觉概念图生成失败——请检查硅基流动 API Key 与网络连接。"
            f"如未配置，请在 .env 中设置 SILICONFLOW_API_KEY。]\n"
        )


def _write_text_section(
    topic: str,
    section_title: str,
    project_id: str | None = None,
    template_type: str = "product",
    search_depth: int = 10,
) -> str:
    llm = get_llm()
    logger.info("→ [📝 文本撰写] 正在深度撰写章节【%s】(template=%s, k=%d)...", section_title, template_type, search_depth)

    retriever_k = max(12, search_depth)  # 最少获取 12 篇，充分调用知识库
    docs = retrieve(f"{topic} {section_title}", k=retriever_k, project_id=project_id)
    context_str, ref_map = build_context_with_citations(docs)

    sys_prompt = PromptFactory.get_section_prompt(template_type)

    prompt = f"""{sys_prompt}

【产品研究主题】: {topic}
【当前撰写章节】: {section_title}

【参考资料】:
{context_str}

请直接输出 Markdown 内容，务必从 `## {section_title}` 开始，不要有任何前缀。

【内容深度要求（最高优先级）】：
- 充分综合上方【参考资料】中的**全部**信息，覆盖关键数据与事实，不得遗漏重要的数字、型号、价格、规格、份额、时间等硬信息。
- 每个要点都要有具体数据/事实/案例支撑，杜绝空泛口号；内容要丰富、信息密集。

【格式要求（为 PPT 排版优化，但不牺牲内容完整度）】：
1. 必须使用 Markdown 格式。
2. 以 Bullet points（无序列表 - ）为主拆解观点；单个 bullet 只表达一个主结论，尽量控制在 2-3 行内。若信息很多，拆成多个 bullet，禁止把多个并列事实塞进一个超长 bullet。
3. 单个段落控制在 2-4 行（约 100 字内）；优先使用短段落 + 多 bullet，而不是长段落堆叠。
4. 如有数据对比、参数差异、版本差异、竞品差异，强制使用 Markdown 表格输出，并尽量填满有意义的对比数据。
5. 若某个小节下存在 4 条以上并列要点，优先按“维度/结论/数据”方式组织为表格或更短的 bullet 序列，避免连续超长列表项。
6. 同一小节内，相同事实、相同参数、相同结论只表达一次；若多个来源支持同一事实，请融合到同一个 bullet 或同一行表格，不要重复复述。
7. 你的输出将直接转化为幻灯片，请兼顾排版呼吸感与内容充实度。
8. 【高优先级：结构要为后续排版服务】每个 ### 子主题下，优先写成“总括 + 并列子项”结构，而不是纯平铺长列表：
   - 先给 1 条总括性一级 bullet，概括该组主题
   - 再给 3-6 条并列二级 bullet，每条长度尽量接近、信息粒度一致
   - 如果是阶段/流程/路径/时间演进，请写成 3-5 条有顺序感的并列要点
   - 如果是能力、卖点、风险、用户分层、场景集合，请写成 4-8 条短句式并列要点
   - 如果是“维度：说明 / 指标：数据 / 方案：结论”结构，请统一使用“名称：说明”的格式，便于后续转成卡片、对比列或紧凑表格
   - 不要为了凑层级写无意义的 ####；只有真正细分维度时才使用 ####
9. 【最高优先级：数据表格规范】如果涉及到对比数据，必须使用标准 Markdown 表格语法（使用 `|` 分隔）。
绝不允许使用逗号分隔的 CSV 格式！
绝不允许使用引号 `" "` 包围单元格内容！
绝不允许输出 "The following table:" 这类前缀废话！
示例格式：
| 品牌型号 | 核心技术 | 价格 |
| :--- | :--- | :--- |
| 产品A | 追腰技术 | 1000元 |
10. 【最高优先级：引用格式】文内引用必须严格使用 [^1] 的角标格式，绝不允许使用 [1] 或其他变体格式！"""

    response = llm.invoke(prompt)
    raw_content = response.content

    # 健壮的输出清理：截断寒暄语 + 移除重复标题
    raw_content = _clean_llm_output(raw_content, section_title)

    final_content = resolve_and_append_citations(raw_content, ref_map)
    return final_content


# ══════════════════════════════════════════════════════════
# 工业设计推演：概念图标签提取与批量生图
# ══════════════════════════════════════════════════════════

_IMAGE_PROMPT_PATTERN = re.compile(r'\[IMAGE_PROMPT:\s*(.+?)\]', re.DOTALL)


def _extract_image_prompts(content: str) -> list[tuple[str, str]]:
    """
    从 LLM 输出中提取 [IMAGE_PROMPT: ...] 标签。

    Returns:
        [(full_tag_text, prompt_body), ...] 按出现顺序排列
    """
    return [(m.group(0), m.group(1).strip()) for m in _IMAGE_PROMPT_PATTERN.finditer(content)]


def _process_design_images(
    content: str,
    topic: str,
    section_title: str,
) -> str:
    """
    后处理设计模板章节输出：提取 [IMAGE_PROMPT:...] 标签 → 调用图像生成 → 替换为图片引用。

    - 每张图片独立生成，单张失败不影响其他
    - 内置 API 限流间隔
    - 无标签时为 no-op，直接返回原文
    """
    matches = list(_IMAGE_PROMPT_PATTERN.finditer(content))

    if not matches:
        return content

    safe = _safe_topic(topic)
    section_slug = re.sub(r'[^a-zA-Z0-9一-鿿]', '_', section_title)[:30]

    result_parts: list[str] = []
    last_end = 0

    for idx, match in enumerate(matches, start=1):
        # 追加标签之前的文本
        result_parts.append(content[last_end:match.start()])

        prompt_text = match.group(1).strip()
        image_path = f"outputs/images/{safe}_{section_slug}_concept_{idx}.png"

        logger.info(
            "→ [工业设计生图 %d/%d] %s...",
            idx, len(matches), prompt_text[:80],
        )

        # API 限流：除第一张外等待间隔
        if idx > 1:
            from app.llm.client import _rate_limit_wait
            _rate_limit_wait(3.0)

        from app.llm.client import generate_image
        success = generate_image(
            prompt_text, image_path,
            retries=2, timeout=120,
            style="industrial_design",
        )

        if success:
            result_parts.append(
                f"\n\n![概念方案{idx} - {section_title}](../{image_path})\n\n"
                f"> *图注：AI 工业设计概念渲染 —— 方案{idx}。"
                f"16:9 横版高精度产品概念图，由硅基流动图像引擎生成。*\n"
            )
        else:
            result_parts.append(
                f"\n\n> ⚠️ *[概念方案{idx} 生图失败 —— "
                f"请检查 SILICONFLOW_API_KEY 与网络连接]*\n"
            )

        last_end = match.end()

    # 追加剩余文本
    result_parts.append(content[last_end:])

    return ''.join(result_parts)


def _write_design_section(
    topic: str,
    section_title: str,
    project_id: str | None = None,
    search_depth: int = 10,
) -> str:
    """
    工业设计推演专用章节撰写器。

    流程：RAG 检索 → LLM 推演（含思维链路 + 多概念方案 + [IMAGE_PROMPT:...] 标签）
    → 图片后处理 → 引用溯源。
    """
    llm = get_llm()
    concept_count = 3  # 每章提出的概念方案数

    logger.info(
        "→ [工业设计推演] 正在深度推演章节【%s】(k=%d, concepts=%d)...",
        section_title, search_depth, concept_count,
    )

    retriever_k = max(12, search_depth)
    docs = retrieve(f"{topic} {section_title}", k=retriever_k, project_id=project_id)
    context_str, ref_map = build_context_with_citations(docs)

    # 将 {concept_count} 注入系统 Prompt
    sys_prompt = PromptFactory.get_section_prompt("design")
    if "{concept_count}" in sys_prompt:
        sys_prompt = sys_prompt.replace("{concept_count}", str(concept_count))

    prompt = f"""{sys_prompt}

【产品研究主题】: {topic}
【当前撰写章节】: {section_title}
【概念方案数量要求】: 请提出恰好 {concept_count} 个差异化的概念方案

【参考资料】:
{context_str}

请直接输出 Markdown 内容，务必从 `## {section_title}` 开始，不要有任何前缀。

【最高优先级提醒】：
1. 思维推演：展示完整的设计推理链路（从约束推导到形态决策的全过程）
2. 概念方案：{concept_count} 个差异化的方案，每个方案紧跟独占一行的 [IMAGE_PROMPT: ...]
3. 技术方向：给出结构堆叠、制造工艺、表面处理的具体路线
4. 设计需求总结：章节末尾用 "### 设计需求总结" 列出 4+ 条可量化的设计约束"""

    response = llm.invoke(prompt)
    raw_content = _clean_llm_output(response.content, section_title)

    # 后处理：提取 [IMAGE_PROMPT:...] 标签并生成实际图片
    processed_content = _process_design_images(raw_content, topic, section_title)

    # 引用溯源
    final_content = resolve_and_append_citations(processed_content, ref_map)
    return final_content


def write_section(
    topic: str,
    section_title: str,
    project_id: str | None = None,
    template_type: str = "product",
    search_depth: int = 10,
) -> str:
    """
    撰写单个章节。

    路由策略：
    - 工业设计推演模板 → 专用设计推演写入器（思维链路 + 多概念方案 + 批量生图）
    - 产品预研模板 + 绘图关键词章节 → 单图图像生成引擎
    - 产品预研模板 + 普通章节 → RAG 检索 + LLM 深度撰写

    Args:
        topic:         产品研究主题
        section_title: 当前章节标题
        project_id:    项目 UUID（用于 per-project 向量库隔离）
        template_type: 模板类型（"product" 或 "design"），
                       透传给 PromptFactory 选择对应的 System Prompt
        search_depth:  搜索强度 (5-20)，控制检索资料数量

    Returns:
        Markdown 格式的章节内容。
    """
    # 工业设计推演模板：所有章节走专用推演写入器
    if template_type == "design":
        return _write_design_section(
            topic, section_title,
            project_id=project_id,
            search_depth=search_depth,
        )

    # 产品预研模板：现有关键词路由
    if _is_image_section(section_title):
        return _write_image_section(topic, section_title)
    else:
        return _write_text_section(
            topic, section_title,
            project_id=project_id,
            template_type=template_type,
            search_depth=search_depth,
        )
