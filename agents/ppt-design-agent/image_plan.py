"""
PptDesign Agent —— 图片资产管理（product architecture + design 重点）
====================================================================

按用户强调：
- 生图能力**完全释放**：每页都生成对应图片（不只是 cover + 几张）
- 生图**聚焦产品架构**（architecture）与**产品设计**（design mockup）
- 图片**存放在每个项目的 design studio**（outputs/assets/{product_id}/）

设计要点：
1. 必出图（每项目必生成 3 张）：
   - hero.png  — 封面主视觉（大气氛围）
   - architecture.png — 产品架构图（核心：传感器/边缘/云/UI 四层栈 + 数据流箭头）
   - design.png — 产品工业设计图（核心：三视图/等距视图 mockup）
2. 上下文图（按页类型生成 6-10 张）：
   - cover.png — 封面装饰（与 hero 区分，可作底纹层）
   - scene.png — 产品使用场景（生活/工作场景）
   - icon_*.png — 组件库图标（替代 chunk-filled）
   - page_*.png — 页面配图（按主题语境生成）
3. 失败/降级：任何失败不阻断流程，缺图时走纯 SVG 兜底

图片存放路径：
- 临时工作目录：{project_dir}/images/   （SVG 引用 images/xxx.png）
- 设计工作室：{OUTPUT_DIR}/assets/{product_id}/   （前端 DesignStudioPage 通过 /api/v1/files/assets/{product_id}/ 访问）

prompt-master image_gen.py 兼容：
- REQUIRED: filename, prompt, aspect_ratio, status
- OPTIONAL: image_size, page_role (local/hero_page/full_page), purpose, text_policy, slice_grid
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────
# 1. 图片提示词模板（核心：以产品架构 + 工业设计为重点）
# ─────────────────────────────────────────────────────────────────

# 系统级提示词前置语（确保商业摄影质感 + 无文字）
_STYLE_PREFIX = (
    "高端商业摄影质感，柔光摄影棚打光，无任何文字，无水印，无 logo，"
    "主体居中偏左，浅景深，超高清细节，"
)

# ── 必出图（3 张，每项目必生成） ──

HERO_PROMPT = (
    _STYLE_PREFIX +
    "演示封面主视觉：{idea}，氛围感强，留白构图，"
    "{theme}色调，带有{accent}点缀，"
    "前景虚化、中景主体、远景延伸的空间层次感，"
    "暗示产品科技属性，"
    "16:9，宽画幅电影质感"
)

# 产品架构图（核心：突出**产品架构**）
ARCHITECTURE_PROMPT = (
    _STYLE_PREFIX +
    "**{idea} 产品技术架构图**：分层等距视图（isometric layered stack），"
    "四层结构从下到上：硬件层（传感器/芯片/电池）→ 感知层（数据采集）→ 智能层（算法/推理）→ 服务层（API/UI），"
    "每层用半透明色块区分，层间有数据流动箭头连接，"
    "背景纯白或极浅灰，"
    "左侧标注层级名称（无文字则保持干净），"
    "整体呈现高端工业风技术蓝图，"
    "16:9"
)

# 产品工业设计图（核心：突出**产品设计**）
DESIGN_PROMPT = (
    _STYLE_PREFIX +
    "**{idea} 产品工业设计图**：产品三视图或等距视图（isometric mockup），"
    "产品外观精致、细节丰富、质感真实（金属/塑料/玻璃材质感），"
    "放在干净的工作台上，配以暖色调灯光，"
    "可适度露出内部模块暗示产品内部结构（如电路板/传感器），"
    "整体呈现工业设计渲染图风格，"
    "16:9"
)

# ── 上下文图（按页类型生成） ──

COVER_DECORATIVE_PROMPT = (
    _STYLE_PREFIX +
    "演示封面装饰底纹：{idea}产品概念氛围，"
    "抽象几何纹理（点/线/面），"
    "{theme}色调，单色或双色，"
    "低饱和度，留白多，"
    "16:9"
)

SCENE_PROMPT = (
    _STYLE_PREFIX +
    "{idea}产品的真实使用场景：{scene_topic}，"
    "人物与产品的自然交互，"
    "环境真实可信（家居/办公/户外），"
    "自然光线（晨光/午后/夜晚室内），"
    "情感氛围积极温暖，"
    "16:9"
)

ICON_PROMPT = (
    "极简线性图标：{topic}，"
    "白底，单色（{color}），"
    "2px 描边，圆角端点，"
    "风格统一（与 Lucide / Feather 一致），"
    "正方形画布 1:1"
)

# 通用页面配图（保留向后兼容）
PAGE_GENERIC_PROMPT = (
    _STYLE_PREFIX +
    "{idea}演示页面配图：{topic}，"
    "{theme}色调，"
    "抽象信息图形氛围，留白多，"
    "商业摄影质感，"
    "16:9"
)


# ─────────────────────────────────────────────────────────────────
# 2. 提示词工厂
# ─────────────────────────────────────────────────────────────────

def _clean(s: str, max_len: int = 80) -> str:
    """清理论点主题，用于嵌入 prompt。"""
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s[:max_len]


def _detect_visual_topic(page: dict, idea: str) -> str:
    """从页面 DSL 中推断视觉主题（用于 SCENE/PAGE 配图）。"""
    # 优先级：page.title > page.subtitle > page.insight > page.type
    candidates = [
        page.get("title"),
        page.get("subtitle"),
        page.get("insight"),
        page.get("type"),
    ]
    for c in candidates:
        if c and len(str(c).strip()) >= 4:
            return _clean(c)
    return _clean(idea)


def _detect_scene_topic(page: dict, idea: str) -> str:
    """推断使用场景（人物 + 产品 + 动作）。"""
    page_type = (page.get("type") or "").lower()
    title = _clean(page.get("title") or "", 30)

    # 场景关键词映射
    scene_hints = {
        "cover": "产品首次亮相仪式感",
        "user_persona": "目标用户在日常生活中使用产品",
        "user_journey": "用户完整体验产品的流程",
        "product_architecture": "产品内部结构与工作原理",
        "feature_priority": "产品核心功能特写",
        "scenario": "产品在真实环境中的应用",
        "market": "产品在行业市场中的定位",
        "competitor": "竞品对比场景",
    }

    hint = scene_hints.get(page_type)
    if hint:
        return f"{hint}（{title}）" if title else hint
    return f"产品使用场景（{title}）" if title else "产品日常使用"


# ─────────────────────────────────────────────────────────────────
# 3. 构造完整 image_prompts.json
# ─────────────────────────────────────────────────────────────────

def build_image_manifest(
    presentation: dict,
    idea: str,
    product_id: str,
    theme_name: str = "咨询风",
    accent_color: str = "#3D6491",
    max_pages: int = 10,
) -> dict:
    """构造项目级 image_prompts.json，传递给 ppt-master image_gen.py。

    返回 dict（可直接 json.dumps），结构：
    {
      "project": "...",
      "product_id": "...",
      "items": [ {filename, prompt, aspect_ratio, image_size, status, purpose, page_role}, ... ]
    }
    """
    items: list[dict] = []

    # ── 1) 必出图：cover + architecture + design ──
    items.append({
        "filename": "hero.png",
        "prompt": HERO_PROMPT.format(idea=_clean(idea, 40), theme=theme_name, accent=accent_color),
        "aspect_ratio": "16:9",
        "image_size": "1K",
        "status": "Pending",
        "purpose": "封面主视觉（产品氛围）",
        "page_role": "hero_page",
        "asset_kind": "hero",
    })
    items.append({
        "filename": "cover.png",
        "prompt": COVER_DECORATIVE_PROMPT.format(idea=_clean(idea, 40), theme=theme_name),
        "aspect_ratio": "16:9",
        "image_size": "1K",
        "status": "Pending",
        "purpose": "封面装饰底纹（与 hero 区分）",
        "page_role": "full_page",
        "asset_kind": "cover_decorative",
    })
    items.append({
        "filename": "architecture.png",
        "prompt": ARCHITECTURE_PROMPT.format(idea=_clean(idea, 40), theme=theme_name),
        "aspect_ratio": "16:9",
        "image_size": "1K",
        "status": "Pending",
        "purpose": "产品技术架构图（四层等距栈 + 数据流）",
        "page_role": "local",
        "asset_kind": "architecture",
    })
    items.append({
        "filename": "design.png",
        "prompt": DESIGN_PROMPT.format(idea=_clean(idea, 40), theme=theme_name),
        "aspect_ratio": "16:9",
        "image_size": "1K",
        "status": "Pending",
        "purpose": "产品工业设计图（三视图/等距 mockup）",
        "page_role": "local",
        "asset_kind": "design",
    })
    items.append({
        "filename": "scene.png",
        "prompt": SCENE_PROMPT.format(
            idea=_clean(idea, 40),
            scene_topic="目标用户在典型使用场景中与产品的自然交互",
        ),
        "aspect_ratio": "16:9",
        "image_size": "1K",
        "status": "Pending",
        "purpose": "产品真实使用场景（人物 + 产品 + 环境）",
        "page_role": "local",
        "asset_kind": "scene",
    })

    # ── 2) 上下文图：按 page.type 分配 image asset_kind ──
    pages = presentation.get("pages") or []
    for i, page in enumerate(pages):
        page_no = i + 1
        page_type = page.get("type", "content")
        topic = _detect_visual_topic(page, idea)

        # 不同页类型配不同图
        if page_type in ("cover",):
            # 封面已有 hero+architecture+design，跳过
            continue
        elif page_type == "product_architecture":
            # 产品架构页：直接用 architecture.png（已有），不重复生成
            continue
        elif page_type in ("user_persona", "scenario"):
            # 用户画像/场景：使用场景图
            fname = f"page_{page_no:02d}_scene.png"
            scene_topic = _detect_scene_topic(page, idea)
            items.append({
                "filename": fname,
                "prompt": SCENE_PROMPT.format(idea=_clean(idea, 40), scene_topic=scene_topic),
                "aspect_ratio": "16:9",
                "image_size": "1K",
                "status": "Pending",
                "purpose": f"P{page_no:02d} {page_type} 场景图",
                "page_role": "local",
                "asset_kind": "scene",
            })
        elif page_type == "competitor_matrix":
            # 竞品矩阵：抽象信息图
            fname = f"page_{page_no:02d}_concept.png"
            items.append({
                "filename": fname,
                "prompt": PAGE_GENERIC_PROMPT.format(
                    idea=_clean(idea, 40), topic=f"竞品对比矩阵 — {topic}",
                ),
                "aspect_ratio": "16:9",
                "image_size": "1K",
                "status": "Pending",
                "purpose": f"P{page_no:02d} 竞品分析配图",
                "page_role": "local",
                "asset_kind": "page_concept",
            })
        elif page_type == "feature_priority":
            # 功能优先级：产品特写
            fname = f"page_{page_no:02d}_feature.png"
            items.append({
                "filename": fname,
                "prompt": PAGE_GENERIC_PROMPT.format(
                    idea=_clean(idea, 40), topic=f"核心功能特写 — {topic}",
                    theme=theme_name,
                ),
                "aspect_ratio": "16:9",
                "image_size": "1K",
                "status": "Pending",
                "purpose": f"P{page_no:02d} 功能优先级配图",
                "page_role": "local",
                "asset_kind": "feature",
            })
        else:
            # 默认：通用配图
            fname = f"page_{page_no:02d}.png"
            items.append({
                "filename": fname,
                "prompt": PAGE_GENERIC_PROMPT.format(
                    idea=_clean(idea, 40), topic=topic, theme=theme_name,
                ),
                "aspect_ratio": "16:9",
                "image_size": "1K",
                "status": "Pending",
                "purpose": f"P{page_no:02d} {page_type} 配图 — {topic}",
                "page_role": "local",
                "asset_kind": "page_concept",
            })

        # 限制总数（避免无谓消耗）
        if len([i for i in items if i.get("asset_kind", "").startswith("page_")]) >= max_pages:
            break

    return {
        "project": idea,
        "product_id": product_id,
        "items": items,
    }


# ─────────────────────────────────────────────────────────────────
# 4. 资产入库（Design Studio）
# ─────────────────────────────────────────────────────────────────

def sync_to_design_studio(
    image_dir: Path,
    output_dir: Path,
    product_id: str,
    items: list[dict],
) -> dict:
    """把生成的图片同步到 design studio（{OUTPUT_DIR}/assets/{product_id}/）。

    Returns:
        {
          "asset_dir": "/abs/path/to/assets/{product_id}/",
          "assets": [ {"name": "hero.png", "url": "/api/v1/files/assets/{product_id}/hero.png",
                       "size": 12345, "asset_kind": "hero"}, ... ],
          "hero": "images/hero.png"  (svg_ref 供 SVG 引用)
          "by_kind": {"hero": "images/hero.png", "architecture": "images/architecture.png", ...}
        }
    """
    asset_root = output_dir / "assets" / str(product_id)
    asset_root.mkdir(parents=True, exist_ok=True)

    assets_list: list[dict] = []
    by_kind: dict[str, str] = {}
    hero_rel: str | None = None

    for item in items:
        fname = item.get("filename")
        if not fname:
            continue
        src = image_dir / fname
        if not src.is_file():
            continue
        dst = asset_root / fname
        # 避免重复复制（已存在且大小一致）
        try:
            if not dst.exists() or dst.stat().st_size != src.stat().st_size:
                dst.write_bytes(src.read_bytes())
        except Exception as exc:  # noqa: BLE001
            logger.warning("同步 %s 到 design studio 失败: %s", fname, exc)
            continue

        size = dst.stat().st_size
        asset_kind = item.get("asset_kind", "page_concept")
        entry = {
            "name": fname,
            "url": f"/api/v1/files/assets/{product_id}/{fname}",
            "size": size,
            "asset_kind": asset_kind,
            "purpose": item.get("purpose", ""),
            "page_role": item.get("page_role", "local"),
        }
        assets_list.append(entry)

        # SVG 引用相对路径（svg_output/ 视下，../images/{fname} 或 images/{fname}）
        svg_ref = f"images/{fname}"
        if asset_kind == "hero":
            hero_rel = svg_ref
        by_kind[asset_kind] = svg_ref

    return {
        "asset_dir": str(asset_root),
        "assets": assets_list,
        "hero": hero_rel,
        "by_kind": by_kind,
    }


# ─────────────────────────────────────────────────────────────────
# 5. 按页选图（供 svg_author / cross_page 使用）
# ─────────────────────────────────────────────────────────────────

def select_image_for_page(page: dict, page_index: int, by_kind: dict[str, str]) -> str | None:
    """根据 page.type 选择最合适的图片 SVG 引用路径。"""
    if not by_kind:
        return None

    page_type = page.get("type", "content")
    page_no = page_index + 1

    # 优先级映射
    type_to_kind = [
        ("cover", "hero"),
        ("cover", "cover_decorative"),
        ("product_architecture", "architecture"),
        ("design", "design"),
        ("user_persona", "scene"),
        ("user_journey", "scene"),
        ("scenario", "scene"),
        ("competitor_matrix", "page_concept"),
        ("feature_priority", "feature"),
        ("conclusion", "hero"),
    ]
    for ptype, kind in type_to_kind:
        if page_type == ptype and kind in by_kind:
            return by_kind[kind]

    # 兜底：page_NN_xxx.png
    for kind, ref in by_kind.items():
        if kind.startswith(f"page_{page_no:02d}"):
            return ref

    # 再次兜底：hero
    return by_kind.get("hero") or by_kind.get("cover_decorative")