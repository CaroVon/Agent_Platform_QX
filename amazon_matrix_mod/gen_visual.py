"""image-01 视觉生成（P3.4）—— 复用 ppt-master image_gen.py（子进程）。

产物（visuals/）：
  background.png   品类主题背景板（主海报底层，深色留白供数据叠加）
  cover.png        报告封面视觉
  zone_<zone>.png  4 区插画（价格缺口/性价比/需求热度/红海）
风格：商业科技风、低饱和蓝金、留白≥40%；提示词模板化（品类变量）。
失败策略：视觉为增强层——生成失败跳过，主报告仍完整（matplotlib 白底兜底）。
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

ZONE_PROMPTS = {
    "price_gap": "扁平线性插画：价格带中的空白缺口，金币与虚线标注的区间，深蓝背景，金色点缀，无文字",
    "value_opportunity": "扁平线性插画：性价比天秤，低价标签与高评分星形，深蓝背景，蓝金配色，无文字",
    "demand_heat": "扁平线性插画：火焰与上升箭头，热销热度计，深蓝背景，暖橙点缀，无文字",
    "red_ocean": "扁平线性插画：拥挤的红海与竞品小船，警示色调，深蓝背景，红橙点缀，无文字",
}


def _image_gen_script() -> Path:
    root = Path(__file__).resolve()
    # gen_visual.py 位于 <root>/amazon_matrix_mod/ → parents[1] = <root>
    base = root.parents[1]
    for cand in (
        base / "agents" / "ppt-design-agent" / "vendor" / "ppt-master" / "scripts" / "image_gen.py",
        base / "QX_product_agent" / "agents" / "ppt-design-agent" / "vendor" / "ppt-master" / "scripts" / "image_gen.py",
        base / "vendor" / "ppt-master" / "scripts" / "image_gen.py",
    ):
        if cand.is_file():
            return cand
    raise FileNotFoundError("未找到 image_gen.py")


def _env() -> dict:
    env = os.environ.copy()
    # 读取 QX backend/.env 的 MiniMax 配置
    env_path = Path(__file__).resolve().parents[3] / "QX_product_agent" / "backend" / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env.setdefault(k.strip(), v.strip())
    env.setdefault("IMAGE_BACKEND", "minimax")
    env.setdefault("MINIMAX_BASE_URL", "https://api.minimax.chat/v1")
    env.setdefault("MINIMAX_MODEL", "image-01")
    return env


def _generate(prompt: str, out_dir: str, name: str, aspect: str = "16:9",
              size: str = "2K", timeout: int = 300) -> str | None:
    """调用 image_gen.py 生成单张图。返回产物路径或 None。"""
    os.makedirs(out_dir, exist_ok=True)
    try:
        script = _image_gen_script()
        out = os.path.join(out_dir, name)
        cmd = [sys.executable, str(script), prompt,
               "--aspect_ratio", aspect, "--image_size", size, "-o", out_dir,
               "--filename", os.path.splitext(name)[0]]
        proc = subprocess.run(cmd, env=_env(), capture_output=True, text=True,
                              timeout=timeout, cwd=str(script.parent))
        if proc.returncode != 0:
            log.warning("image_gen 失败: %s", (proc.stderr or proc.stdout)[-300:])
            return None
        # 脚本可能输出带扩展名文件，检查
        for cand in (out, out + ".png", out + ".jpg", out.replace(".png", ".jpg")):
            if os.path.isfile(cand) and os.path.getsize(cand) > 10000:
                return cand
        return None
    except Exception as exc:  # noqa: BLE001
        log.warning("image_gen 异常: %s", exc)
        return None


def generate_visuals(keyword: str, out_dir: str, skip_zones: bool = False) -> dict:
    """生成背景/封面/4 区插画。返回 {background, cover, zones:{zone:path}}（缺失为 None）。"""
    os.makedirs(out_dir, exist_ok=True)
    result: dict = {"background": None, "cover": None, "zones": {}}

    bg_prompt = (f"{keyword} 亚马逊市场分析报告背景板，深色商务科技风（#0F1B2D 底），"
                 "产品主图悬浮氛围光效，低饱和蓝金配色，网格与数据光点装饰，"
                 "**留白≥40% 供数据图叠加**，16:9 高清，无文字无 Logo")
    result["background"] = _generate(bg_prompt, out_dir, "background.png", aspect="16:9", size="2K")

    cover_prompt = (f"{keyword} 竞品矩阵 MOD 报告封面视觉，产品剪影悬浮于抽象价格/销量数据流之上，"
                    "高端咨询风格，深蓝金配色，居中构图，大留白供标题排版，16:9，无文字")
    result["cover"] = _generate(cover_prompt, out_dir, "cover.png", aspect="16:9", size="2K")

    if not skip_zones:
        for zone, prompt in ZONE_PROMPTS.items():
            p = _generate(prompt, out_dir, f"zone_{zone}.png", aspect="1:1", size="1K", timeout=240)
            if p:
                result["zones"][zone] = p
    return result
