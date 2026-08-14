"""
============================================================
LLM 客户端 —— 文本引擎 (DeepSeek) + 图像引擎 (硅基流动 图像模型)
============================================================

所有配置从集中式 Settings 读取，消除了模块级 load_dotenv() 副作用。
当 backend 包不可用时（CLI 模式），回退到环境变量读取。
"""

from __future__ import annotations

import base64
import logging
import os
import threading
import time

import requests
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# 配置解析 —— 优先 Settings 单例，回退环境变量
# ══════════════════════════════════════════════════════════

def _get_config() -> dict:
    """
    从集中式 Settings 或环境变量获取所有 LLM 相关配置。

    返回字典避免模块级副作用——调用方在函数体内调用此函数。
    """
    try:
        from app.core.config import get_settings
        s = get_settings()
        return {
            "deepseek_api_key": s.DEEPSEEK_API_KEY,
            "deepseek_base_url": s.DEEPSEEK_BASE_URL,
            "deepseek_model": s.DEEPSEEK_MODEL,
            "siliconflow_api_key": s.SILICONFLOW_API_KEY,
            "siliconflow_image_model": (
                getattr(s, "SILICONFLOW_IMAGE_MODEL", None)
                or "Qwen/Qwen-Image"
            ),
            "image_width": int(s.CONCEPT_IMAGE_WIDTH),
            "image_height": int(s.CONCEPT_IMAGE_HEIGHT),
        }
    except ImportError:
        # CLI 模式回退（backend 包不在 sys.path）
        return {
            "deepseek_api_key": os.getenv("DEEPSEEK_API_KEY", ""),
            "deepseek_base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            "deepseek_model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            "siliconflow_api_key": os.getenv("SILICONFLOW_API_KEY", ""),
            "siliconflow_image_model": os.getenv(
                "SILICONFLOW_IMAGE_MODEL",
                "Tongyi-MAI/Z-Image-Turbo",
            ),
            "image_width": int(os.getenv("CONCEPT_IMAGE_WIDTH", "1024")),
            "image_height": int(os.getenv("CONCEPT_IMAGE_HEIGHT", "576")),
        }


# ══════════════════════════════════════════════════════════
# 文本引擎：DeepSeek Chat（惰性初始化单例）
# ══════════════════════════════════════════════════════════

_llm_instance = None


def get_llm():
    """
    文本引擎：调用 DeepSeek 官方 API，用于分析报告大纲规划 + 章节撰写。

    惰性初始化 —— 首次调用时创建并缓存实例，避免模块 import 时的副作用。
    """
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    cfg = _get_config()
    api_key = cfg["deepseek_api_key"]
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY 未配置。请在 .env 文件中设置，"
            "或通过环境变量 DEEPSEEK_API_KEY 提供。"
        )

    _llm_instance = ChatOpenAI(
        api_key=api_key,
        base_url=cfg["deepseek_base_url"],
        model=cfg["deepseek_model"],
        temperature=0.2,
        max_tokens=4096,  # 显式给足输出预算，避免内容被默认上限截断
    )
    logger.info("DeepSeek LLM 客户端已初始化 (model=%s)", cfg["deepseek_model"])
    return _llm_instance


# ══════════════════════════════════════════════════════════
# 图像引擎：硅基流动 (SiliconFlow) 图像生成模型
# ══════════════════════════════════════════════════════════

SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"


def _wrap_prompt(raw_prompt: str) -> str:
    """
    对原始图片描述 Prompt 进行高规格商业 PPT 封面的风格强化。
    目标：生成极具视觉冲击力的横版路演封面配图。
    """
    return (
        f"Premium business presentation cover slide, cinematic 16:9 widescreen composition, "
        f"minimalist corporate aesthetic, futuristic technology atmosphere with elegant negative space, "
        f"dark sophisticated background with subtle gradient, high-end commercial keynote visual, "
        f"photorealistic hyper-detailed 8K render. Subject: {raw_prompt}"
    )


def _wrap_prompt_industrial(raw_prompt: str) -> str:
    """
    工业设计概念渲染风格包装器。
    目标：生成专业级产品设计概念渲染图，适合设计评审 Portfolio。
    """
    return (
        f"Professional industrial design concept rendering, "
        f"photorealistic product visualization on neutral studio background, "
        f"precise geometric forms with defined material transitions, "
        f"controlled soft-key lighting revealing surface texture and chamfer details, "
        f"16:9 widescreen composition suitable for design portfolio review, "
        f"8K high-fidelity render with subtle ambient occlusion. "
        f"Subject: {raw_prompt}"
    )


# ══════════════════════════════════════════════════════════
# 图像生成限流（线程安全）
# ══════════════════════════════════════════════════════════

_last_image_call_time: float = 0.0
_image_call_lock = threading.Lock()


def _rate_limit_wait(min_interval: float = 3.0):
    """强制 API 调用最小间隔，避免 429 限流。"""
    global _last_image_call_time
    with _image_call_lock:
        elapsed = time.time() - _last_image_call_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_image_call_time = time.time()


def generate_image(
    prompt: str,
    output_path: str,
    retries: int = 2,
    timeout: int = 120,
    style: str = "business",
) -> bool:
    """
    调用硅基流动图像生成模型生成 16:9 横版概念图。

    Args:
        prompt:      图片主题描述（中文/英文均可，内部会包一层风格 Prompt）
        output_path: 图片保存路径 (e.g. outputs/images/xxx_concept.png)
        retries:     失败重试次数 (default 2, total attempts = 3)
        timeout:     单次请求超时秒数 (default 120)
        style:       风格包装器 ("business" 商务封面 | "industrial_design" 工业设计渲染)

    Returns:
        bool: 生成成功返回 True，否则 False（调用方应使用 CSS 渐变兜底）
    """
    cfg = _get_config()
    api_key = cfg["siliconflow_api_key"]

    if not api_key:
        logger.warning(
            "未设置 SILICONFLOW_API_KEY，跳过封面图生成（报告将使用 CSS 渐变封面）"
        )
        return False

    if style == "industrial_design":
        full_prompt = _wrap_prompt_industrial(prompt)
    else:
        full_prompt = _wrap_prompt(prompt)
    image_width = cfg["image_width"]
    image_height = cfg["image_height"]

    payload = {
        "model": cfg["siliconflow_image_model"],
        "prompt": full_prompt,
        "n": 1,
        "size": f"{image_width}x{image_height}",  # 16:9 横版
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    url = f"{SILICONFLOW_BASE_URL}/images/generations"

    for attempt in range(1, retries + 2):  # total = retries + 1
        try:
            logger.info(
                "调用硅基流动 %s (%d×%d, 16:9) 第 %d/%d 次...",
                cfg["siliconflow_image_model"], image_width, image_height,
                attempt, retries + 1,
            )

            resp = requests.post(
                url, json=payload, headers=headers,
                timeout=(15, timeout),  # (connect_timeout, read_timeout)
            )

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except ValueError:
                    logger.warning("JSON 解析响应失败")
                    if attempt <= retries:
                        time.sleep(3 * attempt)
                        continue
                    return False

                image_url = None
                if "data" in data and len(data["data"]) > 0:
                    item = data["data"][0]
                    image_url = item.get("url")
                    b64_data = item.get("b64_json")

                    if image_url:
                        try:
                            img_resp = requests.get(image_url, timeout=(10, 60))
                            img_resp.raise_for_status()
                            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                            with open(output_path, "wb") as f:
                                f.write(img_resp.content)
                            file_size_kb = os.path.getsize(output_path) / 1024
                            logger.info("封面概念图已保存: %s (%.1f KB)", output_path, file_size_kb)
                            return True
                        except requests.exceptions.Timeout:
                            logger.warning("图片下载超时")
                        except requests.exceptions.HTTPError as e:
                            logger.warning("图片下载 HTTP 错误: %s", e)
                        except OSError as e:
                            logger.warning("写入图片文件失败: %s", e)
                        if attempt <= retries:
                            time.sleep(3 * attempt)
                            continue
                        return False

                    elif b64_data:
                        try:
                            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                            with open(output_path, "wb") as f:
                                f.write(base64.b64decode(b64_data))
                            file_size_kb = os.path.getsize(output_path) / 1024
                            logger.info("封面概念图已保存 (b64): %s (%.1f KB)", output_path, file_size_kb)
                            return True
                        except (base64.binascii.Error, OSError) as e:
                            logger.warning("Base64 解码/写文件失败: %s", e)
                            if attempt <= retries:
                                time.sleep(3 * attempt)
                                continue
                            return False

                logger.warning("响应中未找到图片数据: %s", str(data)[:200])
                if attempt <= retries:
                    time.sleep(3)
                    continue
                return False

            elif resp.status_code == 429:
                wait = 2 ** attempt
                logger.warning("速率限制 (429)，%ds 后重试...", wait)
                time.sleep(wait)
                continue
            elif resp.status_code >= 500:
                wait = 3 * attempt
                logger.error("服务器错误 %d: %s, %ds 后重试", resp.status_code, resp.text[:200], wait)
                time.sleep(wait)
                continue
            else:
                logger.error("API 返回 %d: %s", resp.status_code, resp.text[:300])
                if attempt <= retries:
                    time.sleep(3)
                continue

        except requests.exceptions.Timeout:
            logger.warning("请求超时 (连接 15s + 读取 %ds)", timeout)
            if attempt <= retries:
                wait = 3 * attempt
                logger.info("%ds 后重试...", wait)
                time.sleep(wait)
        except requests.exceptions.ConnectionError as e:
            logger.warning("连接错误: %s", e)
            if attempt <= retries:
                wait = 5 * attempt
                logger.info("%ds 后重试...", wait)
                time.sleep(wait)
        except Exception as e:
            logger.warning("未预期异常: %s: %s", type(e).__name__, e)
            if attempt <= retries:
                time.sleep(3 * attempt)

    logger.warning("所有 %d 次尝试均失败，将使用 CSS 渐变兜底封面", retries + 1)
    return False


def generate_images_batch(
    prompts_and_paths: list[tuple[str, str]],
    style: str = "industrial_design",
    retries: int = 2,
    timeout: int = 120,
    inter_call_delay: float = 3.0,
) -> list[bool]:
    """
    批量顺序生成多张图片，内置 API 调用限流。

    Args:
        prompts_and_paths: [(prompt, output_path), ...] 列表
        style:             风格包装器
        retries:           每张图片的重试次数
        timeout:           每张图片的超时秒数
        inter_call_delay:  调用间隔秒数（避免 429）

    Returns:
        list[bool]: 与输入顺序一致的生成结果（True=成功, False=失败）
    """
    results: list[bool] = []
    for i, (prompt, path) in enumerate(prompts_and_paths):
        if i > 0:
            _rate_limit_wait(inter_call_delay)
        ok = generate_image(
            prompt, path,
            retries=retries, timeout=timeout, style=style,
        )
        results.append(ok)
    return results
