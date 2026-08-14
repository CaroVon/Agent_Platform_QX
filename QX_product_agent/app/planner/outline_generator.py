"""
============================================================
产品研究大纲生成器 —— 由 LLM 动态生成，支持多态模板切换
============================================================
"""
from app.llm.client import get_llm
from app.llm.prompts import PromptFactory


def generate_outline(topic: str, template_type: str = "product") -> str:
    """
    调用 LLM 为给定的产品主题动态生成研究大纲。

    Args:
        topic:         产品主题
        template_type: 模板类型（"product" 或 "design"），
                       由 PromptFactory 路由到对应 System Prompt

    Returns:
        Markdown 格式的大纲文本。
    """
    llm = get_llm()
    sys_prompt = PromptFactory.get_outline_prompt(template_type)

    if template_type == "design":
        user_prompt = (
            f"请为产品「{topic}」生成一份工业设计推演大纲。\n\n"
            f"要求：6-7 个章节，聚焦设计语言、人机工程、CMF、交互、结构堆叠、多概念方案对比与选型。"
        )
    else:
        user_prompt = (
            f"请为产品「{topic}」生成一份产品研究报告大纲。\n\n"
            f"要求：7-8 个章节，聚焦产品设计、用户体验与竞争定位。"
        )

    response = llm.invoke([
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ])

    outline = response.content.strip()

    # 确保以 # 标题开头
    if not outline.startswith("#"):
        if template_type == "design":
            outline = f"# {topic} - 工业设计推演\n\n" + outline
        else:
            outline = f"# {topic}\n\n" + outline

    return outline


if __name__ == "__main__":
    topic = "AI眼镜行业"
    outline = generate_outline(topic)
    print(outline)
