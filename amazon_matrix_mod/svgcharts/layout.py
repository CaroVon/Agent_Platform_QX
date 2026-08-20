"""布局引擎 —— 缩略图/标签防重叠（需求 2 核心）。

算法：贪心锚点螺旋放置（构造性无重叠）。
  1. 节点按权重降序处理（高销量竞品优先占据真实坐标位）
  2. 逐个放置：从自身锚点出发，若与已放置节点（AABB + pad 间隙）冲突，
     沿极坐标环向外搜索最近的无冲突位置（角度网格确定性枚举）
  3. 活动边界内无解时取冲突最小的位置（极端密度下的优雅降级）

相比力松弛法：无振荡、无收敛问题，构造上保证两两不重叠（密度可行时）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Node:
    x: float                 # 中心 x（像素）
    y: float                 # 中心 y（像素，含标签的联合包围盒中心）
    w: float                 # 包围盒宽
    h: float                 # 包围盒高（缩略图 + 标签）
    anchor_x: float = 0.0    # 真实数据点 x
    anchor_y: float = 0.0    # 真实数据点 y
    weight: float = 1.0      # 权重越大越不容易被推开
    displaced: bool = field(init=False, default=False)

    def __post_init__(self):
        self.anchor_x = self.anchor_x or self.x
        self.anchor_y = self.anchor_y or self.y

    @property
    def half_w(self) -> float:
        return self.w / 2

    @property
    def half_h(self) -> float:
        return self.h / 2


def _overlap(a: Node, b: Node, pad: float = 0.0) -> tuple[float, float]:
    """返回 (x 向重叠量, y 向重叠量)（扣除 pad 间隙）；任一 ≤0 表示不相交。"""
    ox = min(a.x + a.half_w, b.x + b.half_w) - max(a.x - a.half_w, b.x - b.half_w) - pad
    oy = min(a.y + a.half_h, b.y + b.half_h) - max(a.y - a.half_h, b.y - b.half_h) - pad
    return ox, oy


def _clamp(nd: Node, x: float, y: float, bounds) -> tuple[float, float]:
    x0, y0, x1, y1 = bounds
    return (min(max(x, x0 + nd.half_w), x1 - nd.half_w),
            min(max(y, y0 + nd.half_h), y1 - nd.half_h))


def resolve_collisions(nodes: list[Node], bounds: tuple[float, float, float, float],
                       max_iter: int = 260, pad: float = 3.0,
                       displace_threshold: float = 26.0,
                       spring: float = 0.05, push: float = 0.66) -> list[Node]:
    """贪心锚点螺旋放置。bounds=(x0, y0, x1, y1) 为允许的活动区域。

    修改并返回 nodes（displaced 标记哪些节点被挤离真实坐标点）。
    （max_iter/spring/push 参数保留以兼容旧签名，当前算法不使用。）
    """
    x0, y0, x1, y1 = bounds
    if len(nodes) < 2:
        for nd in nodes:
            nd.displaced = False
        return nodes
    span_x, span_y = x1 - x0, y1 - y0
    diagonal = math.hypot(span_x, span_y)
    step = max(12.0, min(span_x, span_y) / 24)

    placed: list[Node] = []
    order = sorted(range(len(nodes)), key=lambda i: -nodes[i].weight)
    for idx in order:
        nd = nodes[idx]
        nd.x, nd.y = _clamp(nd, nd.anchor_x, nd.anchor_y, bounds)
        if not any(min(_overlap(nd, p, pad)) > 0 for p in placed):
            placed.append(nd)
            continue
        # 螺旋搜索：距锚点由近及远的确定性候选位
        best: tuple[float, tuple[float, float]] | None = None  # (冲突深度和, 位置)
        r = step
        while r <= diagonal:
            n_angle = max(8, int(8 * r / step))
            for k in range(n_angle):
                ang = 2 * math.pi * k / n_angle
                cx, cy = _clamp(nd, nd.anchor_x + r * math.cos(ang),
                                nd.anchor_y + r * math.sin(ang), bounds)
                conflict = 0.0
                for p in placed:
                    ox, oy = _overlap_set(nd, cx, cy, p, pad)
                    if ox > 0 and oy > 0:
                        conflict += min(ox, oy)
                if conflict <= 0:
                    nd.x, nd.y = cx, cy
                    best = None
                    break
                if best is None or conflict < best[0]:
                    best = (conflict, (cx, cy))
            if best is None:
                break
            r += step
        if best is not None:  # 边界内无完全无冲突位：取冲突最小者（降级）
            nd.x, nd.y = best[1]
        placed.append(nd)

    for nd in nodes:
        nd.displaced = ((nd.x - nd.anchor_x) ** 2 + (nd.y - nd.anchor_y) ** 2) \
            > displace_threshold ** 2
    return nodes


def _overlap_set(nd: Node, cx: float, cy: float, other: Node,
                 pad: float) -> tuple[float, float]:
    """候选位 (cx, cy) 处 nd 与 other 的 AABB 重叠量。"""
    ox = min(cx + nd.half_w, other.x + other.half_w) \
        - max(cx - nd.half_w, other.x - other.half_w) - pad
    oy = min(cy + nd.half_h, other.y + other.half_h) \
        - max(cy - nd.half_h, other.y - other.half_h) - pad
    return ox, oy


def assert_no_overlap(nodes: list[Node], pad: float = 1.0) -> bool:
    """校验工具（单测用）：所有节点两两不重叠（允许 pad 残余）。"""
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            ox, oy = _overlap(nodes[i], nodes[j])
            if ox > pad and oy > pad:
                return False
    return True
