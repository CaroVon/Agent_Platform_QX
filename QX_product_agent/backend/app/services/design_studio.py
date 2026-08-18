"""
====================================================================
Design Studio v2 —— 任务级「设计思路 + 图片」资产库服务
====================================================================

设计目标（替代旧的文本冗余展示）：
  1. 某任务的**所有生图**均保留在任务的 Design Studio 资产库中，
     按「设计思路（文字） + 图片」成对结构化存储；
  2. 用户可以修改某图附带的文字，并让生图模型**重新生成**该图；
  3. 支持**组件化架构**：组件1 文字+图 / 组件2 文字+图 / … / 组合总图，
     组件文字或整体文字可分别修改并分别重新生图；
  4. 生成/再生成的图片可下载（单张下载 + ZIP 打包）。

存储布局（静态目录 {OUTPUT_DIR} 已挂载于 /api/v1/files）：
  {OUTPUT_DIR}/design_studio/{product_id}/index.json   资产库索引（结构化）
  {OUTPUT_DIR}/design_studio/{product_id}/{item_id}_*.png  图片文件

资产条目结构：
  {
    "id":       稳定 ID（pipeline 导入 = 文件名主干；用户创建 = uuid4）
    "kind":     "standalone"（单图）| "component"（组件）| "composite"（组合总图）
    "name":     名称（可编辑）
    "text":     设计思路（用户可编辑，重新生图时作为 prompt 主体）
    "prompt":   实际发送给生图模型的完整 prompt（只读，由 text 派生）
    "api_text": 生图模型返回的文本输出（如 MiniMax data.text，无则 null）
    "image":    {"name","url","size"} | null（未生成时 null）
    "source":   "pipeline" | "user"
    "parent":   组件所属组合条目 id；组合/独立图为 null
    "children": 组合条目包含的组件 id 列表
    "created_at" / "updated_at": ISO 时间
    "versions": [{"ts","text","prompt","image"}, ...]  最近 5 版（不含当前）
  }
====================================================================
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
MAX_VERSIONS = 5

_STYLE_PREFIX = (
    "高端商业摄影质感，柔光摄影棚打光，无任何文字，无水印，无 logo，"
    "主体居中，浅景深，超高清细节，"
)


# ─────────────────────────────────────────────────────────────
# 基础路径与读写
# ─────────────────────────────────────────────────────────────

def _canonical_id(product_id: str) -> str:
    """规范化为带连字符的 UUID 字符串（资产库目录统一命名）。"""
    try:
        return str(uuid.UUID(str(product_id)))
    except (ValueError, AttributeError):
        return str(product_id)


def library_dir(product_id: str) -> Path:
    """Design Studio 资产库目录（图片与 index.json 同目录）。"""
    root = Path(get_settings().OUTPUT_DIR).resolve() / "design_studio"
    return root / _canonical_id(product_id)


def library_path(product_id: str) -> Path:
    return library_dir(product_id) / "index.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_library(product_id: str) -> dict:
    """读取资产库；不存在时返回空库结构。"""
    path = library_path(product_id)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "items" in data:
                return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Design Studio 索引损坏（重建）| product=%s | %s", product_id, exc)
    return {
        "schema_version": SCHEMA_VERSION,
        "product_id": str(product_id),
        "idea": "",
        "status": "pending",
        "created_at": _now(),
        "updated_at": _now(),
        "items": [],
    }


def save_library(library: dict) -> None:
    """原子写入资产库索引。"""
    library["updated_at"] = _now()
    path = library_path(library["product_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(library, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _find_item(library: dict, item_id: str) -> dict | None:
    return next((it for it in library["items"] if it["id"] == item_id), None)


def _image_url(product_id: str, fname: str) -> str:
    return f"/api/v1/files/design_studio/{product_id}/{fname}"


def _copy_into_library(product_id: str, src: Path) -> str | None:
    """复制图片文件到资产库目录，返回文件名；失败返回 None。"""
    if not src.is_file():
        return None
    try:
        dst_dir = library_dir(product_id)
        dst_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{uuid.uuid4().hex}{src.suffix.lower() or '.png'}"
        dst = dst_dir / fname
        dst.write_bytes(src.read_bytes())
        return fname
    except OSError as exc:
        logger.warning("Design Studio 图片入库失败 | product=%s | src=%s | %s", product_id, src, exc)
        return None


# ─────────────────────────────────────────────────────────────
# Pipeline 导入（任务完成后自动调用；GET 时惰性兜底）
# ─────────────────────────────────────────────────────────────

def import_from_product_package(product_id: str, package: dict | None) -> dict:
    """从产品资产包（ppt_design 节点产物）导入图片资产。

    - 读取 {project_dir}/images/image_prompts.json（含每张图的完整 prompt=设计思路）
    - 读取 ppt_design.images（已同步的图片清单），图片复制进资产库
    - 兼容旧任务：资产包无 ppt_design 记录但磁盘仍有产物（assets/ + ppt_projects/）
      时，按磁盘对账导入
    - 幂等：已存在的条目（同 id）跳过
    """
    library = load_library(product_id)
    package = package or {}
    ppt_design = package.get("ppt_design") or {}
    images = ppt_design.get("images") or []

    # 磁盘对账：资产包无图片记录时，扫描 assets/ 与 ppt_projects/ 恢复导入
    if not images:
        images = _recover_disk_assets(product_id)

    if not images:
        return library

    # 图片文件名 → manifest item（prompt / purpose / asset_kind）
    manifest_items: dict[str, dict] = {}
    project_dir = ppt_design.get("project_dir") or ""
    if project_dir:
        manifest_items = _load_manifest_items(Path(project_dir).resolve())
    if not manifest_items:
        # 尝试从 ppt_projects/ 下该产品目录恢复 manifest
        for manifest_path in _find_product_manifests(product_id):
            manifest_items = _load_manifest_items(manifest_path.parent.parent)
            if manifest_items:
                project_dir = str(manifest_path.parent.parent)
                break

    # 定位图片源文件（assets 目录或 project images 目录）
    candidates: list[Path] = []
    for form in _product_id_forms(product_id):
        asset_dir = Path(get_settings().OUTPUT_DIR).resolve() / "assets" / form
        if asset_dir.is_dir():
            candidates.append(asset_dir)
    if project_dir:
        p_images = Path(project_dir).resolve() / "images"
        if p_images.is_dir():
            candidates.append(p_images)

    existing_ids = {it["id"] for it in library["items"]}
    added = 0
    for entry in images:
        fname = entry.get("name") or ""
        if not fname:
            continue
        item_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(fname).stem)[:80] or f"img_{uuid.uuid4().hex[:8]}"
        if item_id in existing_ids:
            continue

        src = next((c / fname for c in candidates if (c / fname).is_file()), None)
        if src is None:
            continue
        new_fname = _copy_into_library(product_id, src)
        if new_fname is None:
            continue

        manifest = manifest_items.get(fname) or {}
        text = (manifest.get("prompt") or entry.get("purpose") or "").strip()
        name = manifest.get("purpose") or entry.get("asset_kind") or Path(fname).stem
        library["items"].append({
            "id": item_id,
            "kind": "standalone",
            "name": name,
            "text": text,
            "prompt": text,
            "api_text": _read_api_text_sidecar(src),
            "image": {"name": new_fname, "url": _image_url(product_id, new_fname),
                      "size": (library_dir(product_id) / new_fname).stat().st_size},
            "source": "pipeline",
            "parent": None,
            "children": [],
            "created_at": _now(),
            "updated_at": _now(),
            "versions": [],
        })
        existing_ids.add(item_id)
        added += 1

    if added:
        library["idea"] = package.get("idea") or library.get("idea") or ""
        library["status"] = (package.get("meta") or {}).get("status") or "completed"
        save_library(library)
        logger.info("Design Studio 导入完成 | product=%s | added=%d", product_id, added)
    return library


# ── 磁盘对账（旧任务恢复） ───────────────────────────────────

def _product_id_forms(product_id: str) -> list[str]:
    """兼容带/不带连字符两种 UUID 形式（历史产物目录两种命名都有）。"""
    forms = [str(product_id)]
    try:
        canonical = str(uuid.UUID(str(product_id)))
        if canonical not in forms:
            forms.append(canonical)
        compact = canonical.replace("-", "")
        if compact not in forms:
            forms.append(compact)
    except (ValueError, AttributeError):
        pass
    return forms


def _load_manifest_items(project_root: Path) -> dict[str, dict]:
    """读取项目 images/image_prompts.json → {filename: item}。"""
    manifest_path = project_root / "images" / "image_prompts.json"
    if not manifest_path.is_file():
        return {}
    try:
        items = json.loads(manifest_path.read_text(encoding="utf-8")).get("items", [])
        return {str(it.get("filename", "")): it for it in items}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Design Studio manifest 读取失败 | path=%s | %s", manifest_path, exc)
        return {}


def _find_product_manifests(product_id: str) -> list[Path]:
    """在 studio_assets/ppt_projects/ 下查找该产品的 manifest（兼容多版本目录）。"""
    settings = get_settings()
    base = Path(settings.OUTPUT_DIR).resolve() / "studio_assets" / "ppt_projects"
    if not base.is_dir():
        return []
    found: list[Path] = []
    # 目录名可能是 {product_id}_ts 或 {product_id[:8]}_ts（历史截断）
    prefixes = set()
    for form in _product_id_forms(product_id):
        prefixes.add(form)
        prefixes.add(form[:8])
    for d in base.iterdir():
        if not d.is_dir():
            continue
        if any(str(d.name).startswith(p) for p in prefixes):
            mp = d / "images" / "image_prompts.json"
            if mp.is_file():
                found.append(mp)
    return sorted(found)


_PIPELINE_STEM_RE = re.compile(r"^(hero|cover|architecture|design|scene|page_\d+)")


def _recover_disk_assets(product_id: str) -> list[dict]:
    """资产包无 ppt_design 图片记录时，从磁盘恢复图片清单。

    仅收集流水线产物命名（hero/page_* 等）或 manifest 中登记的图片；
    编辑器上传的 uuid 命名文件不导入。
    """
    settings = get_settings()
    asset_dirs = [
        Path(settings.OUTPUT_DIR).resolve() / "assets" / form
        for form in _product_id_forms(product_id)
    ]
    asset_dir = next((d for d in asset_dirs if d.is_dir()), None)
    if asset_dir is None:
        return []

    manifest_names: set[str] = set()
    for mp in _find_product_manifests(product_id):
        manifest_names.update(_load_manifest_items(mp.parent.parent).keys())

    entries: list[dict] = []
    for f in sorted(asset_dir.iterdir()):
        if not f.is_file() or f.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            continue
        if f.name in manifest_names or _PIPELINE_STEM_RE.match(f.stem):
            entries.append({
                "name": f.name,
                "url": f"/api/v1/files/assets/{product_id}/{f.name}",
                "size": f.stat().st_size,
            })
    return entries


def _read_api_text_sidecar(image_path: Path) -> str | None:
    """读取生图模型文本输出的 sidecar（{图片}.txt，见 backend_minimax 扩展）。"""
    for sidecar in (image_path.with_suffix(image_path.suffix + ".txt"),
                    image_path.with_name(image_path.stem + ".text.txt")):
        if sidecar.is_file():
            try:
                return sidecar.read_text(encoding="utf-8").strip()[:500] or None
            except OSError:
                return None
    return None


# ─────────────────────────────────────────────────────────────
# 组件智能拆解（LLM 建议，用户确认后创建）
# ─────────────────────────────────────────────────────────────

_DECOMPOSE_SYSTEM = (
    "你是产品工业设计拆解专家。根据产品想法与设计资料，判断该产品是否由多个"
    "可独立渲染的物理组件构成（如桌子=桌面+桌腿；智能音箱=机身+织物网罩+底座）。"
    "输出 JSON 数组，每项 {\"name\": 组件名, \"text\": 该组件单独渲染时的设计思路"
    "（30-80字，描述造型/材质/颜色/工艺）}。若产品是单一整体（无物理组件拆分），"
    "输出空数组 []。只输出 JSON，不要其他文字。"
)


def suggest_components(product_id: str, idea: str, context: dict | None = None) -> list[dict]:
    """LLM 拆解产品组件，返回 [{name, text}] 建议（未生成图片）。失败返回空列表。"""
    try:
        from app.llm.client import get_llm

        llm = get_llm()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Design Studio 组件拆解 LLM 不可用: %s", exc)
        return []

    brief: list[str] = [f"产品想法：{idea}"]
    if context:
        strategy = context.get("strategy") or {}
        if strategy.get("positioning"):
            brief.append(f"产品定位：{strategy['positioning']}")
        features = strategy.get("features") or []
        if features:
            brief.append("核心功能：" + "、".join(str(f.get("name", "")) for f in features[:6]))
        design = context.get("design") or {}
        if design.get("components"):
            brief.append("UX 组件：" + "、".join(str(c.get("name", "")) for c in design["components"][:8]))
    user = "\n".join(brief)

    try:
        raw = llm.invoke([
            {"role": "system", "content": _DECOMPOSE_SYSTEM},
            {"role": "user", "content": user},
        ])
        content = str(getattr(raw, "content", raw) or "").strip()
        content = re.sub(r"^```(?:json)?|```$", "", content, flags=re.MULTILINE).strip()
        data = json.loads(content)
        if not isinstance(data, list):
            return []
        return [
            {"name": str(d.get("name", "")).strip()[:40],
             "text": str(d.get("text", "")).strip()[:200]}
            for d in data
            if str(d.get("name", "")).strip()
        ][:6]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Design Studio 组件拆解失败: %s", exc)
        return []


# ─────────────────────────────────────────────────────────────
# 条目 CRUD
# ─────────────────────────────────────────────────────────────

def create_item(product_id: str, *, kind: str, name: str, text: str = "",
                parent: str | None = None, children: list[str] | None = None) -> dict:
    """创建资产条目（component / composite / standalone）。"""
    library = load_library(product_id)
    item_id = uuid.uuid4().hex
    children = children or []

    if kind == "composite":
        for cid in children:
            child = _find_item(library, cid)
            if child is None or child["kind"] != "component":
                raise ValueError(f"组合包含的组件不存在: {cid}")
            child["parent"] = item_id

    item = {
        "id": item_id,
        "kind": kind,
        "name": (name or "未命名").strip()[:60],
        "text": (text or "").strip(),
        "prompt": "",
        "api_text": None,
        "image": None,
        "source": "user",
        "parent": parent,
        "children": children,
        "created_at": _now(),
        "updated_at": _now(),
        "versions": [],
    }
    library["items"].append(item)
    if kind == "component" and parent:
        group = _find_item(library, parent)
        if group is not None and group["kind"] == "composite":
            group["children"] = sorted(set(group["children"] + [item_id]))
    save_library(library)
    return item


def update_item(product_id: str, item_id: str, *, name: str | None = None,
                text: str | None = None) -> dict:
    """更新条目名称/设计思路（不触发重新生图）。"""
    library = load_library(product_id)
    item = _find_item(library, item_id)
    if item is None:
        raise KeyError(item_id)
    if name is not None:
        item["name"] = str(name).strip()[:60] or item["name"]
    if text is not None:
        item["text"] = str(text).strip()
    item["updated_at"] = _now()
    save_library(library)
    return item


def delete_item(product_id: str, item_id: str) -> None:
    """删除条目；组件删除时从所属组合的 children 摘除。"""
    library = load_library(product_id)
    item = _find_item(library, item_id)
    if item is None:
        raise KeyError(item_id)
    library["items"] = [it for it in library["items"] if it["id"] != item_id]
    if item["kind"] == "component" and item.get("parent"):
        group = _find_item(library, item["parent"])
        if group is not None:
            group["children"] = [c for c in group["children"] if c != item_id]
    if item["kind"] == "composite":
        for cid in item.get("children", []):
            child = _find_item(library, cid)
            if child is not None:
                child["parent"] = None
    save_library(library)


def restore_version(product_id: str, item_id: str, index: int) -> dict:
    """从版本历史恢复（当前版本入历史尾部，目标版本成为当前）。"""
    library = load_library(product_id)
    item = _find_item(library, item_id)
    if item is None:
        raise KeyError(item_id)
    versions = item.get("versions") or []
    if index < 0 or index >= len(versions):
        raise IndexError(index)
    version = versions[index]
    versions.pop(index)
    versions.append({
        "ts": _now(),
        "text": item.get("text", ""),
        "prompt": item.get("prompt", ""),
        "image": item.get("image"),
    })
    item["versions"] = versions[-MAX_VERSIONS:]
    item["text"] = version["text"]
    item["prompt"] = version.get("prompt", "")
    item["image"] = version.get("image")
    item["updated_at"] = _now()
    save_library(library)
    return item


# ─────────────────────────────────────────────────────────────
# 生图（重新生成 / 首次生成）
# ─────────────────────────────────────────────────────────────

def _build_prompt(library: dict, item: dict) -> str:
    """根据条目文字构建发送给生图模型的完整 prompt。

    - standalone：设计思路（带统一风格前缀）
    - component： 组件名 + 设计思路，强调单独渲染
    - composite： 整体设计思路 + 各组件文字，强调组合装配
    """
    idea = library.get("idea") or ""
    text = (item.get("text") or "").strip()

    if item["kind"] == "component":
        body = f"单独渲染产品组件「{item['name']}」：{text}" if text else f"单独渲染产品组件「{item['name']}」"
        if idea:
            body += f"（所属产品：{idea}）"
        return _STYLE_PREFIX + body + "，组件单体展示，16:9"
    if item["kind"] == "composite":
        parts = []
        for cid in item.get("children", []):
            child = _find_item(library, cid)
            if child is not None:
                parts.append(f"{child['name']}：{child.get('text') or ''}".strip(" ："))
        body = f"完整产品整体渲染图：{text}" if text else f"完整产品整体渲染图：{idea}"
        if parts:
            body += "。产品由以下组件组合装配而成：" + "；".join(f"{i + 1}) {p}" for i, p in enumerate(parts))
        return _STYLE_PREFIX + body + "，组件间正确装配、整体协调统一，16:9"
    # standalone
    body = text or f"产品概念视觉：{idea}"
    return _STYLE_PREFIX + body + "，16:9"


def _image_gen_env() -> dict:
    """构建 image_gen.py 子进程环境（IMAGE_BACKEND 优先读 .env，缺省 minimax）。"""
    settings = get_settings()
    env = os.environ.copy()
    env.setdefault("IMAGE_BACKEND", "minimax")
    if settings.MINIMAX_API_KEY:
        env["MINIMAX_API_KEY"] = settings.MINIMAX_API_KEY
    env.setdefault("MINIMAX_BASE_URL", settings.MINIMAX_BASE_URL or "https://api.minimax.chat/v1")
    env.setdefault("MINIMAX_MODEL", settings.MINIMAX_MODEL or "image-01")
    return env


def _image_gen_script() -> Path:
    """定位 vendor ppt-master image_gen.py（与 PptDesignAgent 同一脚本）。"""
    root = Path(__file__).resolve()
    # backend/app/services/design_studio.py → parents[3] = QX_product_agent
    project_root = root.parents[3]
    # 兼容两个布局：工作区 agents/ 包（默认）与 QX_product_agent 内嵌 agents/
    candidates = [
        project_root.parent / "agents" / "ppt-design-agent" / "vendor" / "ppt-master" / "scripts" / "image_gen.py",
        project_root / "agents" / "ppt-design-agent" / "vendor" / "ppt-master" / "scripts" / "image_gen.py",
        project_root / "vendor" / "ppt-master" / "scripts" / "image_gen.py",
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError("未找到 image_gen.py（ppt-master vendor 脚本）")


def generate_image_for_item(product_id: str, item_id: str, *, timeout: int = 360) -> dict:
    """为条目生成/重新生成图片（同步调用生图模型，保留版本快照）。

    生成成功后：
      - 新图片写入资产库目录（保留旧文件以便版本恢复）
      - 旧 image/text 快照进 versions（最多 5 条）
      - 生图模型返回的文本输出（如有 sidecar）记录到 api_text
    """
    library = load_library(product_id)
    item = _find_item(library, item_id)
    if item is None:
        raise KeyError(item_id)

    prompt = _build_prompt(library, item)
    item["prompt"] = prompt

    script = _image_gen_script()
    out_dir = library_dir(product_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname_stem = f"{item_id[:8]}_{ts}"

    cmd = [
        sys.executable, str(script), prompt,
        "--aspect_ratio", "16:9", "--image_size", "1K",
        "-o", str(out_dir), "--filename", fname_stem,
    ]
    logger.info("[Design Studio] 生图 | product=%s | item=%s | kind=%s | name=%s",
                product_id, item_id, item["kind"], item["name"])
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=str(script.parent), env=_image_gen_env(),
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"生图超时（>{timeout}s）")

    # 找到实际产出文件（image_gen 自动决定扩展名）
    produced = sorted(out_dir.glob(f"{fname_stem}.*"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
    generated = next((p for p in produced if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")), None)

    if proc.returncode != 0 or generated is None:
        detail = (proc.stderr or proc.stdout or "").strip()[-400:] or "生图失败（无输出）"
        logger.warning("[Design Studio] 生图失败 | product=%s | item=%s | %s", product_id, item_id, detail)
        raise RuntimeError(f"生图失败: {detail}")

    new_fname = generated.name
    # 模型文本输出 sidecar（backend_minimax 扩展：{图片}.txt）
    api_text = _read_api_text_sidecar(generated)

    # 版本快照
    versions = item.get("versions") or []
    if item.get("image"):
        versions.append({
            "ts": _now(),
            "text": item.get("text", ""),
            "prompt": item.get("prompt", ""),
            "image": item["image"],
        })
    item["versions"] = versions[-MAX_VERSIONS:]
    item["image"] = {
        "name": new_fname,
        "url": _image_url(product_id, new_fname),
        "size": generated.stat().st_size,
    }
    item["api_text"] = api_text
    item["updated_at"] = _now()
    save_library(library)
    logger.info("[Design Studio] 生图成功 | product=%s | item=%s | %s (%.1f KB)",
                product_id, item_id, new_fname, generated.stat().st_size / 1024)
    return item


# ─────────────────────────────────────────────────────────────
# 打包下载
# ─────────────────────────────────────────────────────────────

def build_zip_bytes(product_id: str) -> bytes | None:
    """打包资产库全部图片（当前版本）为 ZIP 字节；无图片返回 None。"""
    import io
    import zipfile

    library = load_library(product_id)
    items = [it for it in library["items"] if it.get("image")]
    if not items:
        return None

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for it in items:
            img = it["image"]
            src = library_dir(product_id) / img["name"]
            if not src.is_file():
                continue
            safe = re.sub(r"[^\w.\-]+", "_", f"{it['kind']}_{it['name']}")[:60] or img["name"]
            ext = Path(img["name"]).suffix or ".png"
            zf.writestr(f"{safe}{ext}", src.read_bytes())
    return buf.getvalue()
