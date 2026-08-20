#!/usr/bin/env python3
"""e2e_driver.py —— 前端输入 → 全管线 → 资产库 E2E 驱动脚本。

流程：bootstrap 登录 → 创建产品（可选主题/风格）→ 处理 source_gathering
审批门 → 轮询至完成 → 验证交付物（合并 PPTX / MOD 资产 / keywords /
记忆图谱 / 资产包 ZIP）→ 输出结构化结果。

用法:
    python e2e_driver.py --idea "蓝牙耳机" [--theme cyber-black-gold] \
        [--style product-launch] [--timeout 3600] [--quiet-poll]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request

BASE = "http://localhost:8000/api/v1"


def _req(method: str, path: str, token: str, body: dict | None = None,
         timeout: int = 120) -> dict:
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    })
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--idea", required=True)
    ap.add_argument("--theme", default=None)
    ap.add_argument("--style", default=None)
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args()

    t0 = time.time()
    tok = _req("POST", "/auth/bootstrap", "")["access_token"]
    print("[auth] bootstrap OK")

    body = {"idea": args.idea}
    if args.theme:
        body["theme_id"] = args.theme
    if args.style:
        body["style_id"] = args.style
    created = _req("POST", "/product/create", tok, body,
                   ) if False else _req("POST", "/product/create", tok, body)
    pid = created["product_id"]
    print(f"[create] product={pid}（theme={args.theme} style={args.style}）")

    gate_handled = False
    last_nodes = ""
    result: dict = {}
    while time.time() - t0 < args.timeout:
        time.sleep(10)
        try:
            result = _req("GET", f"/product/{pid}", tok)
        except Exception as exc:  # noqa: BLE001
            print(f"[poll] 临时错误: {exc}")
            continue
        status = result.get("status")
        nodes = json.dumps(result.get("node_status") or {}, ensure_ascii=False)
        if nodes != last_nodes:
            print(f"[{int(time.time()-t0):>4}s] status={status} nodes={nodes[:400]}")
            last_nodes = nodes
        if str(status).upper() == "WAITING_APPROVAL" and not gate_handled:
            # 默认门为 source_gathering（SOURCE_REVIEW）；重组响应无
            # asset_package/_paused_node，从 gate_report 兜底取节点名
            paused = ((result.get("gate_report") or {}).get("node")
                      or "source_gathering")
            review = (result.get("gate_report") or {}).get("sources") \
                or (result.get("_sources_review") or [])
            urls = [s.get("url") for s in review if isinstance(s, dict) and s.get("url")]
            sel = urls if urls else None
            try:
                _req("POST", f"/product/{pid}/approve-node", tok,
                     {"node": paused, "selected_urls": sel})
                gate_handled = True
                print(f"[gate] 已批准 {paused}（{len(urls)} 条资料）")
            except Exception as exc:  # noqa: BLE001
                print(f"[gate] 批准失败（将重试）: {exc}")
            continue
        if status in ("COMPLETED", "FAILED", "CANCELLED",
                      "completed", "failed", "cancelled"):
            break

    status = result.get("status")
    print(f"\n===== 终态: {status}（{int(time.time()-t0)}s） =====")
    if str(status).upper() != "COMPLETED":
        print("error:", (result.get("error_message") or "")[:500])
        pkg = json.loads(result.get("asset_package") or "{}")
        for n, e in (pkg.get("meta", {}).get("errors") or {}).items():
            print(f"  node {n}: {str(e)[:200]}")
        return 1

    # ── 交付物验证 ──
    checks: dict = {}
    pkg = json.loads(result.get("asset_package") or "{}")
    ppt = pkg.get("ppt_design") or {}
    checks["merged_pptx"] = {
        "path": ppt.get("pptx_relative"),
        "main_pages": ppt.get("pages"),
        "mod_appendix": ppt.get("mod_appendix"),
    }
    cm = pkg.get("competitor_matrix") or {}
    checks["mod_artifacts"] = cm.get("artifacts_paths")
    checks["keywords"] = pkg.get("keywords")
    checks["theme_used"] = (pkg.get("presentation") or {}).get("theme", {}).get("id")

    # 资产包
    try:
        lib = _req("GET", f"/project-assets/{pid}", tok)
        mod_group = [f for f in lib.get("files", [])
                     if f.get("category") == "竞品矩阵"]
        checks["asset_library"] = {
            "total_files": len(lib.get("files") or []),
            "mod_files": len(mod_group),
            "mod_pptx_previews": len(
                next((f.get("preview_urls") for f in mod_group
                      if f["name"].endswith(".pptx")), []) or 0),
        }
    except Exception as exc:  # noqa: BLE001
        checks["asset_library"] = {"error": str(exc)[:150]}

    # 记忆图谱（studio 任务实体）
    try:
        g = _req("GET", f"/memory/graph?scope=project&studio_product_id={pid}", tok)
        checks["memory_graph"] = {
            "entities": g.get("meta", {}).get("entity_count"),
            "relations": g.get("meta", {}).get("relation_count"),
        }
    except Exception as exc:  # noqa: BLE001
        checks["memory_graph"] = {"error": str(exc)[:150]}

    print(json.dumps(checks, ensure_ascii=False, indent=1))
    with open("/tmp/e2e_last_result.json", "w", encoding="utf-8") as f:
        json.dump({"product_id": pid, "status": status, "checks": checks},
                  f, ensure_ascii=False, indent=1)
    print(f"\nproduct_id: {pid}（详情已写 /tmp/e2e_last_result.json）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
