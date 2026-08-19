/**
 * graphOptions —— 记忆图数据 → ECharts option 工厂
 *
 * 视觉规范（docs/memory-graph-visual-design.md）：
 *  - 类型→色相+图标；度数→面积（√ 缩放，离散档位）；置信度→描边；新鲜度→透明度
 *  - 平行边按索引曲率错开；有向箭头；权重→边宽；过期→虚线
 *  - 搜索聚焦：命中节点 + 邻域高亮（focused 标记），其余 muted
 */

import type { EChartsOption, GraphSeriesOption } from 'echarts'
import type { MemoryGraphEdge, MemoryGraphNode, MemoryGraphResponse } from '@/types/api'
import type { GraphTheme } from './graphTheme'
import { entityIconDataUrl } from './graphIcons'

/** 节点尺寸离散档（∝ degree） */
const SIZE_STEPS = [24, 32, 40, 50, 62, 76, 92, 110]

function nodeSize(degree: number): number {
  const idx = Math.min(SIZE_STEPS.length - 1, Math.floor(Math.sqrt(degree)))
  return SIZE_STEPS[idx]
}

/** 平行边曲率错开：按 (source,target) 对的出现次数索引分配 curveness */
function buildEdgeCurveness(edges: MemoryGraphEdge[]): Map<string, number> {
  const counts = new Map<string, number>()
  const result = new Map<string, number>()
  for (const edge of edges) {
    const key = [edge.source, edge.target].sort().join('|')
    const idx = counts.get(key) ?? 0
    counts.set(key, idx + 1)
    // 平行边：±0.15 交替，控制 [-0.3, 0.3]
    const base = 0.15 + 0.15 * Math.floor(idx / 2)
    result.set(`${edge.source}->${edge.target}#${edge.relation}`, idx % 2 === 0 ? base : -base)
  }
  return result
}

export interface GraphCallbacks {
  onNodeClick?: (node: MemoryGraphNode) => void
}

export function buildGraphOption(
  data: MemoryGraphResponse,
  theme: GraphTheme,
  callbacks: GraphCallbacks = {},
): EChartsOption {
  const { nodes, edges } = data
  const hasQuery = Boolean(data.query)
  const curvenessMap = buildEdgeCurveness(edges)

  const nodeIdSet = new Set(nodes.map((n) => n.id))

  // 邻接索引：聚焦高亮用（前端自算邻域）
  const adjacency = new Map<string, Set<string>>()
  for (const e of edges) {
    if (!adjacency.has(e.source)) adjacency.set(e.source, new Set())
    if (!adjacency.has(e.target)) adjacency.set(e.target, new Set())
    adjacency.get(e.source)!.add(e.target)
    adjacency.get(e.target)!.add(e.source)
  }

  const focusedIds = new Set(nodes.filter((n) => n.focused).map((n) => n.id))

  const graphNodes = nodes.map((n) => {
    const color = theme.nodeColors[n.type] ?? theme.nodeColors.other
    const isFocused = hasQuery && n.focused
    const neighborOfFocus =
      hasQuery && [...focusedIds].some((fid) => adjacency.get(fid)?.has(n.id))
    const isMuted = hasQuery && !isFocused && !neighborOfFocus

    // 置信度描边宽度
    const strokeWidth = 0.75 + 1.75 * n.confidence
    // 新鲜度透明度（30 天内 1.0，每 30 天 -0.15，下限 0.45）
    let opacity = 1
    if (n.last_seen_at) {
      const days = (Date.now() - new Date(n.last_seen_at).getTime()) / 86400000
      opacity = Math.max(0.45, 1 - Math.floor(days / 30) * 0.15)
    }

    return {
      id: n.id,
      name: n.name,
      symbol: `image://${entityIconDataUrl(n.type, isMuted ? theme.muted : color)}`,
      symbolSize: nodeSize(n.degree) * (isFocused ? 1.12 : 1),
      x: undefined as number | undefined,
      y: undefined as number | undefined,
      itemStyle: {
        color,
        opacity: isMuted ? 0.25 : opacity,
        borderColor: isFocused ? theme.focusRing : color,
        borderWidth: isFocused ? 2.5 : strokeWidth,
        shadowBlur: isFocused ? 18 : 0,
        shadowColor: theme.focusRing,
      },
      label: { show: false },
      tooltip: {
        formatter: () => {
          const lines = [
            `<b>${n.name}</b>`,
            `<span style="color:${theme.muted}">${n.type} · 置信度 ${Math.round(n.confidence * 100)}%</span>`,
          ]
          if (n.summary) lines.push(`<span style="color:${theme.muted}">${n.summary}</span>`)
          if (n.aliases.length) lines.push(`<span style="color:${theme.muted}">又名: ${n.aliases.join(' / ')}</span>`)
          if (n.scope === 'global') lines.push(`<span style="color:${theme.focus}">🌐 全局记忆（跨项目）</span>`)
          return lines.join('<br/>')
        },
      },
    }
  })

  const graphEdges = edges
    .filter((e) => nodeIdSet.has(e.source) && nodeIdSet.has(e.target))
    .map((e) => {
      const key = `${e.source}->${e.target}#${e.relation}`
      const isFocused = hasQuery && (focusedIds.has(e.source) || focusedIds.has(e.target))
      return {
        source: e.source,
        target: e.target,
        // 无向"相关"类关系不画箭头
        symbol: e.relation === '相关' || e.relation === '属于' ? 'none' : ['none', 'arrow'],
        symbolSize: [0, 7],
        lineStyle: {
          color: isFocused ? theme.edgeFocus : theme.edge,
          width: Math.min(3, 1 + 2 * e.weight),
          curveness: curvenessMap.get(key) ?? 0,
          opacity: e.expired ? 0.4 : isFocused ? 1 : 0.75,
          type: (e.expired ? 'dashed' : 'solid') as 'dashed' | 'solid',
        },
        label: {
          show: false,
          formatter: e.relation,
          fontSize: 10,
          color: theme.label,
          backgroundColor: theme.labelBg,
          borderRadius: 4,
          padding: [2, 5],
        },
        tooltip: {
          formatter: () =>
            `<b>${e.relation}</b><br/><span style="color:${theme.muted}">权重 ${e.weight.toFixed(1)}${e.expired ? ' · 已过期' : ''}</span>`,
        },
      }
    })

  const series: GraphSeriesOption = {
    type: 'graph',
    layout: 'force',
    roam: true,
    scaleLimit: { min: 0.2, max: 4 },
    draggable: true,
    data: graphNodes,
    links: graphEdges,
    force: {
      repulsion: 220,
      gravity: 0.08,
      friction: 0.6,
      edgeLength: [80, 180],
      layoutAnimation: false,
    },
    emphasis: {
      focus: 'adjacency',
      lineStyle: { width: 2.5, opacity: 1 },
      label: { show: true, fontSize: 12, color: theme.label },
      itemStyle: { borderWidth: 2.5, shadowBlur: 18, shadowColor: theme.focusRing },
    },
    edgeSymbolSize: 8,
    label: { show: false },
  }

  return {
    backgroundColor: 'transparent',
    animationDuration: 500,
    animationEasingUpdate: 'cubicOut',
    tooltip: { show: true, backgroundColor: theme.labelBg, borderColor: theme.edge, textStyle: { color: theme.label } },
    series: [series],
  }
}

/** 按 zoom 档位切换标签显示（LOD）：zoom > 0.7 显示标签 */
export function applyLabelLod(option: EChartsOption, zoom: number, theme: GraphTheme): void {
  const series = (option.series as GraphSeriesOption[] | undefined)?.[0]
  if (!series) return
  series.label = {
    show: zoom > 0.7,
    fontSize: 11,
    color: theme.label,
    backgroundColor: theme.labelBg,
    borderRadius: 4,
    padding: [2, 5],
  }
}
