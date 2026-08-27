"""vendor ppt-master 转换器进程内桥（P1 耗时优化）。

背景：finalize_svg.py / svg_to_pptx.py 此前以 subprocess 调用，
每次 Python 解释器启动+全量 import ≈ 2-5s，每副 deck 3-4 次
（主 deck 2 次 + 独立导出 2 次 + 逐页返工 2 次）。

本模块在首次调用时 import vendor 包（此后常驻），以函数调用替代
子进程：省去解释器启动/导入开销（每 deck 约 -10~15s），并保留
sys.argv / cwd 兼容（vendor 脚本按 CLI 习惯编写）。

失败语义与 subprocess 版一致：返回 (returncode, 输出尾部)。
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

_SCRIPTS_DIR = Path(__file__).resolve().parent / "vendor" / "ppt-master" / "scripts"
_lock = threading.Lock()  # vendor CLI 有全局态（argv/cwd），串行化调用


def _ensure_path() -> None:
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))


@contextmanager
def _cli_compat(argv: list[str], chdir: bool = True):
    """临时模拟 CLI 环境（sys.argv + cwd=scripts），退出恢复。"""
    old_argv = sys.argv
    old_cwd = os.getcwd()
    sys.argv = ["vendor"] + argv
    if chdir:
        os.chdir(_SCRIPTS_DIR)
    try:
        yield
    finally:
        sys.argv = old_argv
        try:
            os.chdir(old_cwd)
        except OSError:
            pass


def run_finalize(project_dir: str) -> tuple[int, str]:
    """finalize_svg：svg_output/ → svg_final/（内联）。Returns (rc, 输出尾)。"""
    import io
    from contextlib import redirect_stdout, redirect_stderr

    with _lock:
        _ensure_path()
        import finalize_svg  # 首次导入后常驻

        buf = io.StringIO()
        rc = 0
        with _cli_compat([str(project_dir)]), \
                redirect_stdout(buf), redirect_stderr(buf):
            try:
                finalize_svg.main()
            except SystemExit as exc:  # argparse/内部错误以 sys.exit 表达
                rc = int(exc.code or 0)
            except Exception as exc:  # noqa: BLE001 —— 与 subprocess rc!=0 等价
                logger.warning("[vendor_bridge] finalize 异常: %s", exc)
                buf.write(str(exc))
                rc = 1
        return rc, buf.getvalue()[-300:]


def run_svg_to_pptx(argv: list[str]) -> tuple[int, str]:
    """svg_to_pptx：svg_final/ → exports/*.pptx（内联）。argv 形如
    [project_dir, '-s', 'final', '-o', out_path]。Returns (rc, 输出尾)。"""
    import io
    from contextlib import redirect_stdout, redirect_stderr

    with _lock:
        _ensure_path()
        from svg_to_pptx import main as pptx_main  # 首次导入后常驻

        buf = io.StringIO()
        with _cli_compat(["svg_to_pptx.py"] + argv), \
                redirect_stdout(buf), redirect_stderr(buf):
            rc = pptx_main(argv)
        return int(rc or 0), buf.getvalue()[-300:]
