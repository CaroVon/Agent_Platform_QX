"""
文档工具 —— 本地文档文本提取
============================================================

支持 .txt / .md 原生读取，PDF 通过可选依赖 PyMuPDF 提取。
供 Research Agent 消化用户上传的参考资料。
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DocumentTool:
    """本地文档解析工具。"""

    name = "read_document"
    description = "读取本地文档（txt/md/pdf）并提取纯文本"

    def run(self, path: str, max_chars: int = 20000) -> str:
        """提取文档文本，超过 max_chars 截断。"""
        file = Path(path)
        if not file.is_file():
            raise FileNotFoundError(f"文档不存在: {path}")

        suffix = file.suffix.lower()
        try:
            if suffix in (".txt", ".md", ".markdown"):
                text = file.read_text(encoding="utf-8", errors="replace")
            elif suffix == ".pdf":
                text = self._extract_pdf(file)
            else:
                raise ValueError(f"不支持的文档类型: {suffix}")
        except (OSError, ValueError) as exc:
            logger.warning("read_document 失败 (%s): %s", path, exc)
            return ""

        return text[:max_chars]

    @staticmethod
    def _extract_pdf(file: Path) -> str:
        """PDF 文本提取（PyMuPDF 可选依赖）。"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.warning("PyMuPDF 未安装，无法解析 PDF: %s", file)
            return ""

        try:
            with fitz.open(str(file)) as doc:
                return "\n".join(page.get_text() for page in doc)
        except Exception as exc:  # noqa: BLE001 —— 损坏 PDF 降级为空文本
            logger.warning("PDF 解析失败 (%s): %s", file, exc)
            return ""
