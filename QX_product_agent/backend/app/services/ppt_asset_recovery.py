"""
============================================================
PPT 资产恢复服务 —— 磁盘 ppt_projects 与 DB 产品资产包对账
============================================================

背景：
  P4 集成早期因 `agent._run` 未定义变量 `brief` 的 NameError，
  导致 ppt_design 节点在**成功导出 PPTX 之后**的 return 阶段报错，
  `pptx_relative` 从未写入 asset_package。但 PPTX/SVG 已落在
  outputs/studio_assets/ppt_projects/ 磁盘上，属高价值滞留资产。

职责：
  1. 扫描 outputs/studio_assets/ppt_projects/，抽取每个项目的
     core_message（spec_lock.md）、有效 .pptx、SVG 页数、创建时间
  2. 与 DB 产品匹配（product_id 前缀 > core_message==presentation.title
     > idea 前缀 > 时间窗口），返回结构化 ppt_design（只读，不写库）
  3. 提供全局索引（供前端「PPT 资产库」/审计展示）

匹配信号权重（基于存量 31 个有效资产的验证）：
  - 目录名前缀 == 产品 UUID（下单横线兼容）          +6（最强）
  - core_message == asset_package.presentation.title  +4
  - 目录名前缀 == idea[:40]                          +2
  - 目录时间戳 ∈ [created_at-30min, updated_at+30min] +3
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_TZ = timezone(timedelta(hours=8))  # 目录名时间戳为本地时间（UTC+8）
_TS_RE = re.compile(r"_(\d{8}_\d{6})$")

# 模块级缓存：扫描结果（目录 mtime 聚合 → 失效）
_scan_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


def _folder_timestamp(name: str) -> datetime | None:
    """从目录名尾部的 _YYYYMMDD_HHMMSS 提取本地时间 → UTC。"""
    m = _TS_RE.search(name)
    if not m:
        return None
    try:
        local_dt = datetime.strptime(m.group(1), "%Y%m%d_%H%M%S").replace(tzinfo=_TZ)
        return local_dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _read_core_message(project_dir: Path) -> str:
    lock = project_dir / "spec_lock.md"
    if not lock.is_file():
        return ""
    m = re.search(r"core_message:\s*(.+)", lock.read_text(encoding="utf-8", errors="ignore"))
    return m.group(1).strip() if m else ""


def _svg_files(project_dir: Path) -> tuple[tuple[Path, ...], str]:
    """返回后端最终 SVG；旧项目没有 svg_final 时兼容 svg_output。"""
    final_dir = project_dir / "svg_final"
    if final_dir.is_dir():
        return tuple(sorted(final_dir.glob("*.svg"))), "svg_final"
    output_dir = project_dir / "svg_output"
    if output_dir.is_dir():
        return tuple(sorted(output_dir.glob("*.svg"))), "svg_output"
    return (), "svg_final"


def build_svg_preview_urls(project_dir: Path) -> list[str]:
    """把后端真实 SVG 产物转换为前端可访问的缩略图 URL。"""
    files, directory = _svg_files(project_dir)
    if not files:
        return []
    folder = quote(project_dir.name, safe="")
    return [
        f"/api/v1/files/studio_assets/ppt_projects/{folder}/{directory}/{quote(path.name, safe='')}"
        for path in files
    ]


def scan_ppt_projects(ttl: int = 30) -> list[dict[str, Any]]:
    """扫描 ppt_projects 目录并返回资产索引（带 TTL 缓存）。

    每个条目：{folder, folder_name, core_message, pptx_relative,
              pptx_absolute, svg_count, created_at_utc, size}
    """
    settings = get_settings()
    base = Path(settings.OUTPUT_DIR).resolve() / "studio_assets" / "ppt_projects"
    if not base.is_dir():
        return []

    # TTL 缓存：以目录内容 mtime 快照作为失效依据
    try:
        newest = max((p.stat().st_mtime for p in base.rglob("*")), default=0.0)
    except OSError:
        newest = 0.0
    key = str(base)
    cached = _scan_cache.get(key)
    if cached and time.time() - cached[0] < ttl and cached[1] and cached[1][0].get("_sig") == newest:
        return [a for a in cached[1] if "_sig" not in a]

    items: list[dict[str, Any]] = []
    for d in sorted(base.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        spec = _read_core_message(d)
        exports = sorted((d / "exports").glob("*.pptx")) if (d / "exports").is_dir() else []
        if not exports:
            continue
        svg_files, _ = _svg_files(d)
        svg_count = len(svg_files)
        pptx = exports[0]
        try:
            stat = pptx.stat()
        except OSError:
            continue
        direction = "studio_assets/ppt_projects"
        relative = f"{direction}/{d.name}/exports/{pptx.name}"
        items.append({
            "folder_name": d.name,
            "folder": str(d),
            "core_message": spec,
            "pptx_relative": relative,
            "pptx_absolute": str(pptx),
            "svg_count": svg_count,
            "svg_previews": build_svg_preview_urls(d),
            "size": stat.st_size,
"created_at_utc": _folder_timestamp(d.name).replace(tzinfo=None).isoformat()
        if _folder_timestamp(d.name)
        else None,
    })
    _scan_cache[key] = (time.time(), [*items, {"_sig": newest}])
    return items


def _score(product: dict[str, Any], asset: dict[str, Any]) -> int:
    """返回资产与该产品的匹配得分（0 = 不匹配）。

    归属信号：
      - 目录名前缀 == 产品 UUID                        +6（最强，可独立成立）
      - core_message == presentation.title              +4（次强，可独立成立）
      - 目录名前缀 == idea[:40]                         +2（弱信号，需时间窗命中）
    时间窗命中（目录时间 ∈ [created, updated] 严格区间）本身不独立计分，
    但弱信号（idea 前缀）必须在时间窗命中时才被采信 —— 防止同名产品的跨天误配。
    """
    name = asset["folder_name"]
    pid = str(product["id"])
    pid_nodash = pid.replace("-", "")
    score = 0

    # ── 时间窗判定 ─────────────────────────────────────────
    time_hit = False
    ts = asset.get("created_at_utc")
    created = product.get("created_at_utc")
    updated = product.get("updated_at_utc")
    if ts and created and updated:
        try:
            ts_dt = datetime.fromisoformat(ts)
            c_dt = datetime.fromisoformat(created)
            u_dt = datetime.fromisoformat(updated)

            def _naive(dt: datetime) -> datetime:
                return dt.replace(tzinfo=None) - dt.utcoffset() if dt.tzinfo else dt

            ts_dt = _naive(ts_dt)
            c_dt = _naive(c_dt)
            u_dt = _naive(u_dt)
            time_hit = c_dt - timedelta(minutes=30) <= ts_dt <= u_dt + timedelta(minutes=30)
        except ValueError:
            pass

    # ── 强信号（UUID 前缀 / title 精确匹配） ──────────────
    if name.startswith(pid) or name.startswith(pid_nodash):
        score += 6
    title = product.get("title") or ""
    if title and asset["core_message"] == title:
        score += 4

    # ── 弱信号（idea 前缀）仅在时间窗命中时采信 ──────────
    idea = product.get("idea") or ""
    if idea and name.startswith(idea[:40]):
        if time_hit:
            score += 2
        else:
            score -= 100  # 同名但时间完全不吻合 → 视为不匹配（防跨天误配）

    # ── 时间窗本身作为稳定性的加分项（需已有强/弱信号） ──
    if score > 0 and time_hit and not (name.startswith(pid) or name.startswith(pid_nodash)):
        score += 3

    return score if score > 0 else 0


def match_asset_for_product(
    product_id: str,
    *,
    idea: str = "",
    presentation_title: str = "",
    created_at_utc: str | None = None,
    updated_at_utc: str | None = None,
) -> dict[str, Any] | None:
    """为单个产品找到最佳匹配的磁盘 PPT 资产（只读，不改库）。

    返回可直接并入 asset_package.ppt_design 的 dict（含 recovered 标记）。
    """
    assets = scan_ppt_projects()
    if not assets:
        return None
    product = {
        "id": product_id,
        "idea": idea,
        "title": presentation_title,
        "created_at_utc": created_at_utc,
        "updated_at_utc": updated_at_utc,
    }
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for a in assets:
        s = _score(product, a)
        if s > 0:
            scored.append((s, a.get("created_at_utc") or "", a))
    if not scored:
        return None
    # presentation_title 缺失（DSL 尚未落库）时，仅当候选唯一才恢复：
    # 同名产品的多个磁盘 PPTX 无法可靠归属，避免「别人家的 PPT」误配。
    if not presentation_title and len(scored) > 1:
        logger.info(
            "PPT 恢复跳过（presentation 缺失且候选不唯一，避免误配）: product=%s 候选=%d",
            product_id, len(scored),
        )
        return None
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    _, _, asset = scored[0]
    project_dir = Path(asset["pptx_absolute"]).parent.parent  # .../ppt_projects/{folder}
    return {
        "project_dir": str(project_dir),
        "pptx_path": asset["pptx_absolute"],
        "pptx_relative": asset["pptx_relative"],
        "pages": asset["svg_count"],
        "svg_files": _list_svg_files(project_dir),
        "svg_previews": build_svg_preview_urls(project_dir),
        "created_at": asset["created_at_utc"],
        "model": "ppt-master (recovered)",
        "design_brief": asset["core_message"][:200],
        "images": [],
        "recovered": True,
    }


def _list_svg_files(project_dir: Path) -> list[str]:
    files, _ = _svg_files(project_dir)
    return [path.name for path in files]


def build_ppt_asset_index() -> list[dict[str, Any]]:
    """全部磁盘 PPT 资产（含 svg 预览 URL，供前端资产库/审计）。"""
    assets = scan_ppt_projects()
    out: list[dict[str, Any]] = []
    for a in assets:
        project_dir = Path(a["folder"])
        out.append({
            "folder_name": a["folder_name"],
            "title": a["core_message"],
            "pptx_url": f"/api/v1/files/{a['pptx_relative']}",
            "size": a["size"],
            "svg_count": a["svg_count"],
            "created_at": a["created_at_utc"],
            "svg_previews": a.get("svg_previews", [])[:6],
        })
    return out
