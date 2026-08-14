"""
============================================================
全流程研究编排器 —— 从信息搜集到 PPT 级横版 PDF 一键生成
============================================================
"""
import logging
import os
import re

from app.planner.outline_generator import generate_outline
from app.report.section_writer import write_section
from app.report.markdown_formatter import build_report
from app.report.pdf_generator import markdown_to_pdf
from app.rag.rag_pipeline import build_knowledge_base
from app.shared.outline_parser import extract_sections

logger = logging.getLogger(__name__)


def _safe_filename(topic: str) -> str:
    """移除文件名非法字符。"""
    return re.sub(r'[\\/:*?"<>|]', '_', topic)


def run_workflow(topic: str):
    """
    端到端研究 + 报告生成主流程。

    步骤:
      1. 构建知识库 (搜索 + 抓取 + 向量化)
      2. 生成大纲
      3. 逐章深度撰写 (含概念图生成)
      4. 拼装 Markdown 报告
      5. 渲染横版 PPT 级 PDF (含封面概念图)
    """
    safe_topic = _safe_filename(topic)

    # ── 1. 知识库构建 ──────────────────────────────────
    logger.info("[1/5] 构建知识库...")
    build_knowledge_base(topic)

    # ── 2. 大纲规划 ────────────────────────────────────
    logger.info("[2/5] 生成研究大纲...")
    outline = generate_outline(topic)
    logger.info(outline)

    section_titles = extract_sections(outline)

    # ── 3. 逐章撰写 (含多模态绘图) ──────────────────────
    completed_sections = []
    for section in section_titles:
        logger.info("[3/5] 撰写章节: %s", section)
        content = write_section(topic, section)
        completed_sections.append(content)

    # ── 4. 拼装 Markdown ───────────────────────────────
    logger.info("[4/5] 拼装最终报告...")
    report = build_report(topic, completed_sections)

    md_output_path = f"outputs/v2(citation)_{safe_topic}_report.md"
    os.makedirs("outputs", exist_ok=True)
    with open(md_output_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info("[OK] Markdown 报告: %s", md_output_path)

    # ── 5. 渲染横版 PPT PDF (传递封面图) ───────────────
    pdf_output_path = f"outputs/v2(citation)_{safe_topic}_report.pdf"

    # 封面概念图路径 (由 section_writer 在多模态章节生成)
    cover_image_path = f"outputs/images/{safe_topic}_concept.png"
    if not os.path.isfile(cover_image_path):
        cover_image_path = ""  # 无封面图时回退纯色封面

    logger.info("[5/5] 渲染横版 PPT PDF...")
    markdown_to_pdf(md_output_path, pdf_output_path, cover_image=cover_image_path)

    logger.info("[DONE] 全流程完成!")
    logger.info("  Markdown: %s", md_output_path)
    logger.info("  PDF:      %s", pdf_output_path)
    if cover_image_path:
        logger.info("  封面图:   %s", cover_image_path)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        topic = sys.argv[1]
    else:
        topic = "宋代青瓷元素新国潮软床"
        logger.warning("未提供命令行参数，使用默认主题: %s", topic)
    run_workflow(topic)