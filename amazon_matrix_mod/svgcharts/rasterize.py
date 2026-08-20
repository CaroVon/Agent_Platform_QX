"""SVG → PNG 光栅化（Playwright/Chromium，CJK 安全）—— M3 审图前置。

环境适配（WSL Ubuntu 无 root 场景）：
  - libasound 缺失时通过 ~/.local/lib-pw 本地解包 + LD_LIBRARY_PATH 注入
  - 优先使用完整版 chromium 二进制（headless_shell 可能缺库）
失败返回 None（审图为增强层，不阻塞主流程）。
"""
from __future__ import annotations

import glob
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

_LOCAL_LIB = str(Path.home() / ".local" / "lib-pw" / "usr" / "lib" / "x86_64-linux-gnu")


def _prepare_env() -> None:
    if os.path.isdir(_LOCAL_LIB):
        existing = os.environ.get("LD_LIBRARY_PATH", "")
        if _LOCAL_LIB not in existing:
            os.environ["LD_LIBRARY_PATH"] = f"{_LOCAL_LIB}:{existing}" if existing else _LOCAL_LIB


def _chromium_executable() -> str | None:
    for cand in sorted(glob.glob(str(Path.home() / ".cache" / "ms-playwright"
                                       / "chromium-*" / "chrome-linux*" / "chrome"))):
        if os.access(cand, os.X_OK):
            return cand
    return None


def svg_to_png(svg_path: str, png_path: str, width: int = 1280,
               timeout_ms: int = 30000) -> str | None:
    """渲染 SVG 文件为 PNG（device_scale_factor=2 高清）。失败返回 None。"""
    try:
        _prepare_env()
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            kwargs = {"headless": True}
            exe = _chromium_executable()
            if exe:
                kwargs["executable_path"] = exe
            browser = p.chromium.launch(**kwargs)
            try:
                page = browser.new_page(
                    viewport={"width": width, "height": 720},
                    device_scale_factor=2)
                # 内联 SVG（<img src=svg> 方式在外链尺寸/裁剪上不可靠）
                svg = Path(svg_path).read_text(encoding="utf-8")
                page.set_content(
                    f'<html><body style="margin:0;background:#fff">{svg}</body></html>',
                    wait_until="load")
                page.wait_for_timeout(300)
                page.screenshot(path=png_path, full_page=True)
            finally:
                browser.close()
        return png_path if os.path.isfile(png_path) else None
    except Exception as exc:  # noqa: BLE001 —— 审图增强层降级
        log.warning("svg_to_png 失败(%s): %s", Path(svg_path).name, str(exc)[:120])
        return None
