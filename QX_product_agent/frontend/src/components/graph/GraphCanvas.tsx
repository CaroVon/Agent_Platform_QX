/**
 * GraphCanvas —— 知识关系图画布（ECharts 封装）
 *
 * 职责：实例管理 / resize / 主题热切换 / zoom LOD / 点击回调 / PNG 导出
 * 视觉规范详见 docs/memory-graph-visual-design.md
 */

import { useEffect, useMemo, useRef } from 'react'
import * as echarts from 'echarts'
import type { ECharts, EChartsOption } from 'echarts'
import type { MemoryGraphNode, MemoryGraphResponse } from '@/types/api'
import { readGraphTheme, watchThemeChange, type GraphTheme } from './graphTheme'
import { buildGraphOption, applyLabelLod } from './graphOptions'

interface GraphCanvasProps {
  data: MemoryGraphResponse | null
  loading?: boolean
  error?: string
  onNodeClick?: (node: MemoryGraphNode) => void
  /** 点击空白处取消聚焦 */
  onBackgroundClick?: () => void
}

export function GraphCanvas({
  data,
  loading,
  error,
  onNodeClick,
  onBackgroundClick,
}: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<ECharts | null>(null)
  const themeRef = useRef<GraphTheme>(readGraphTheme())

  // 节点 id → 原始数据（点击回调用）
  const nodeMap = useMemo(() => {
    const map = new Map<string, MemoryGraphNode>()
    for (const n of data?.nodes ?? []) map.set(n.id, n)
    return map
  }, [data])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const chart = echarts.init(el, undefined, { renderer: 'canvas' })
    chartRef.current = chart

    // 点击节点 → 回调
    chart.on('click', (params: unknown) => {
      const p = params as { dataType?: string; data?: { id?: string } }
      if (p.dataType === 'node' && p.data?.id) {
        const node = nodeMap.get(p.data.id)
        if (node) onNodeClick?.(node)
      } else if (p.dataType === 'edge') {
        // 边点击：聚焦两端
        const link = p.data as { source?: string; target?: string }
        if (link.source) {
          const node = nodeMap.get(String(link.source))
          if (node) onNodeClick?.(node)
        }
      } else {
        onBackgroundClick?.()
      }
    })

    const handleResize = () => chart.resize()
    window.addEventListener('resize', handleResize)

    // 主题热切换：重建
    const unsubscribe = watchThemeChange(() => {
      themeRef.current = readGraphTheme()
      chart.dispose()
      const fresh = echarts.init(el, undefined, { renderer: 'canvas' })
      chartRef.current = fresh
    })

    return () => {
      window.removeEventListener('resize', handleResize)
      unsubscribe()
      chart.dispose()
      chartRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 数据更新 → setOption
  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !data) return
    const option: EChartsOption = buildGraphOption(data, themeRef.current, {})
    // 记录当前 zoom 以应用 LOD
    chart.setOption(option, { notMerge: true, lazyUpdate: true })

    const applyLod = () => {
      try {
        const zoom = ((chart.getOption() as { series?: Array<{ zoom?: number }> }).series?.[0]?.zoom) ?? 1
        applyLabelLod(option, zoom, themeRef.current)
        chart.setOption(option, { lazyUpdate: true })
      } catch {
        /* ignore */
      }
    }
    // 初始 + roam 时更新标签 LOD
    applyLod()
    chart.getZr().on('zoom', applyLod)
    return () => {
      chart.getZr().off('zoom', applyLod)
    }
  }, [data])

  if (loading) {
    return (
      <div className="flex h-full min-h-[420px] items-center justify-center text-sm text-muted-foreground">
        <div className="flex items-center gap-2">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          记忆图谱加载中…
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-full min-h-[420px] items-center justify-center text-sm text-destructive">
        {error}
      </div>
    )
  }

  if (!data || data.nodes.length === 0) {
    return (
      <div className="flex h-full min-h-[420px] flex-col items-center justify-center gap-3 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-secondary text-3xl">
          🕸️
        </div>
        <p className="text-sm font-medium">记忆图谱还是空的</p>
        <p className="max-w-sm text-xs text-muted-foreground">
          完成一个研究任务后，系统会自动从章节/经验/图片分析中提炼实体、关系与洞察，在此生成知识关系图。
        </p>
      </div>
    )
  }

  return <div ref={containerRef} className="h-full min-h-[420px] w-full" />
}

/** 导出当前画布为 PNG（供报告配图） */
export function exportGraphPng(chart: ECharts | null): void {
  if (!chart) return
  const url = chart.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: '#fff',
  })
  const a = document.createElement('a')
  a.href = url
  a.download = `memory-graph-${Date.now()}.png`
  a.click()
}
