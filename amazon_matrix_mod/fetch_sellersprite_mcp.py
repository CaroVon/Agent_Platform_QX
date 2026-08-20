#!/usr/bin/env python3
"""P1: 卖家精灵 MCP 客户端 — 通过官方 MCP 服务拉取 ASIN 详情 / 竞品数据。

MCP 端点: https://mcp.sellersprite.com/mcp（官方，见 open.sellersprite.com/mcp）
认证:     Authorization: Bearer <SELLERSPRITE_API_KEY>（开放平台注册后获取）

用法:
    export SELLERSPRITE_API_KEY=...
    python fetch_sellersprite_mcp.py --tool asin_detail --asins B0XXXXXXXX,B0YYYYYYYY
    python fetch_sellersprite_mcp.py --list-tools          # 查看可用工具与参数 schema

说明:
    - 实现 MCP streamable HTTP 最小客户端（initialize → tools/call），兼容 JSON 与 SSE 响应；
    - 工具参数名以 tools/list 返回的 schema 为准，脚本会对常见变体自动尝试；
    - 卖家精灵 MCP 无需自己解析原始 JSON，AI 可直接消费，本脚本用于自动化管道。
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

MCP_URL = os.environ.get("SELLERSPRITE_MCP_URL", "https://mcp.sellersprite.com/mcp")
DEFAULT_SITE = "US"
OUT_DIR = "outputs"


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_key() -> str:
    key = os.environ.get("SELLERSPRITE_API_KEY", "")
    if not key:
        sys.exit("缺少 SELLERSPRITE_API_KEY 环境变量（卖家精灵开放平台注册后获取，见 README）")
    return key


def _extract_data(resp: requests.Response) -> dict:
    """兼容两种响应：纯 JSON 与 SSE（event: message / data: {...}）。"""
    ctype = resp.headers.get("content-type", "")
    if "text/event-stream" in ctype:
        for line in resp.text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                payload = line[5:].strip()
                try:
                    return json.loads(payload)
                except json.JSONDecodeError:
                    continue
        raise RuntimeError(f"SSE 响应无有效 data 行: {resp.text[:300]}")
    return resp.json()


def _headers(extra: dict = None) -> dict:
    """卖家精灵 MCP 认证：请求头 secret-key（官方配置文档口径，非 Bearer）。"""
    h = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "secret-key": get_key(),
    }
    if extra:
        h.update(extra)
    return h


def rpc(method: str, params: dict = None, _id: int = 1) -> dict:
    body = {"jsonrpc": "2.0", "id": _id, "method": method}
    if params is not None:
        body["params"] = params
    r = requests.post(MCP_URL, json=body, headers=_headers(), timeout=60)
    r.raise_for_status()
    return _extract_data(r)


def init_session() -> None:
    resp = rpc("initialize", {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "qx-amazon-p1", "version": "0.1.0"},
    }, _id=1)
    if "error" in resp:
        sys.exit(f"MCP initialize 失败: {resp['error']}")
    # 通知 initialized（无 id 的通知）
    try:
        requests.post(MCP_URL, json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                      headers=_headers(), timeout=30)
    except requests.RequestException:
        pass  # 通知失败不阻断


def list_tools() -> list:
    init_session()
    resp = rpc("tools/list", _id=2)
    tools = (resp.get("result") or {}).get("tools") or []
    print(f"可用 MCP 工具 {len(tools)} 个：")
    for t in tools:
        args = (t.get("inputSchema") or {}).get("properties") or {}
        print(f"  - {t['name']}: {t.get('description', '')[:70]}")
        print(f"      参数: {', '.join(args.keys())}")
    return tools


def call_tool(name: str, asin: str, site: str) -> dict:
    """调用工具；参数名按常见变体自动尝试。"""
    variants = [
        {"asin": asin, "site": site},
        {"asin": asin, "marketplace": site},
        {"asin": asin},
        {"asins": [asin], "site": site},
        {"ASIN": asin, "site": site},
    ]
    last_err = None
    for params in variants:
        try:
            resp = rpc("tools/call", {"name": name, "arguments": params}, _id=3)
            if "error" in resp:
                last_err = resp["error"]
                continue
            result = resp.get("result") or {}
            if result.get("isError"):
                last_err = result.get("content")
                continue
            return result
        except requests.RequestException as e:
            last_err = str(e)
    raise RuntimeError(f"工具 {name} 调用失败（尝试了参数变体）: {last_err}")


def extract_text(result: dict) -> str:
    parts = []
    for c in result.get("content") or []:
        if c.get("type") == "text":
            parts.append(c.get("text", ""))
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser(description="P1: 卖家精灵 MCP 拉数")
    ap.add_argument("--list-tools", action="store_true", help="列出可用工具与参数")
    ap.add_argument("--tool", default="asin_detail",
                    help="MCP 工具名（默认 asin_detail；竞品数据可用 competitor_lookup）")
    ap.add_argument("--asins", help="逗号分隔 ASIN 列表")
    ap.add_argument("--site", default=DEFAULT_SITE, help="站点代码（US/UK/DE/JP...）")
    ap.add_argument("--out", default=OUT_DIR)
    args = ap.parse_args()

    if args.list_tools:
        list_tools()
        return
    if not args.asins:
        ap.error("需要 --asins（或先用 --list-tools 查看工具）")

    init_session()
    asins = [a.strip() for a in args.asins.split(",")]
    rows = []
    for i, asin in enumerate(asins, 1):
        print(f"  [{i}/{len(asins)}] {asin} -> {args.tool} ...")
        try:
            result = call_tool(args.tool, asin, args.site)
            text = extract_text(result)
            rows.append({"asin": asin, "tool": args.tool, "result": text})
            # 结果常为 JSON 字符串，尝试解析存档
            try:
                rows[-1]["parsed"] = json.loads(text)
            except json.JSONDecodeError:
                pass
        except RuntimeError as e:
            print(f"  [失败] {e}")
            rows.append({"asin": asin, "tool": args.tool, "error": str(e)})
        time.sleep(0.5)

    os.makedirs(os.path.join(args.out, "raw"), exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    raw_path = os.path.join(args.out, "raw", f"sellersprite_{ts}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump({"fetched_at": utcnow(), "source": "sellersprite_mcp",
                   "site": args.site, "rows": rows}, f, ensure_ascii=False, indent=1)

    print(f"\n[完成] {len(rows)} 个 ASIN，存档: {raw_path}")
    for r in rows:
        head = (r.get("result") or r.get("error") or "")[:120].replace("\n", " ")
        print(f"  {r['asin']}: {head}")


if __name__ == "__main__":
    main()
