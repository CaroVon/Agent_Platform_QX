"""
============================================================
本地 PDF 解析模块
—— 使用 PyMuPDF (fitz) 提取文本 → chunk_text 切片
   每条切片以 local://{filename} 作为伪装 URL
============================================================
"""

import fitz  # PyMuPDF
from app.rag.chunker import chunk_text


def parse_local_pdf(file_path: str, filename: str) -> list[dict]:
    """
    解析本地 PDF 文件，提取全文文本，切片后返回结构化列表。

    Args:
        file_path: PDF 文件的磁盘绝对路径
        filename:  原始文件名（用于构造 local:// 伪装 URL）

    Returns:
        [{"content": "...", "url": "local://xxx.pdf"}, ...]
    """
    doc = fitz.open(file_path)
    full_text_parts: list[str] = []

    for page in doc:
        text = page.get_text()
        if text:
            full_text_parts.append(text)

    doc.close()
    full_text = "\n".join(full_text_parts)

    chunks = chunk_text(full_text)

    results: list[dict] = []
    for chunk in chunks:
        results.append({
            "content": chunk,
            "url": f"local://{filename}",
        })

    return results
