/**
 * GraphCanvas —— 知识关系图画布（ECharts 封装）
 *
 * 职责：实例管理 / resize / 主题热切换 / zoom LOD / 点击回调 / 空载错状态
 *
 * 修复记录（2026-08）：
 *  - 容器 div 常驻：loading/error/empty 用覆盖层叠放，图表实例在挂载时必然初始化
 *    （此前 loading 分支不渲染容器，ref 为 null，effect 只跑一次 → 图表永不初始化）
 *  - 主题切换：dispose 后重建实例并重放当前 option
 *  - 点击回调：经 ref 读取最新 nodeMap，避免闭包捕获过期数据
 *  - StrictMode 双跑兼容：cleanup 完整 dispose
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

  // 最新数据/回调经 ref 暴露给 chart 事件（避免闭包过期）
  const dataRef = useRef(data)
  dataRef.current = data
  const nodeMapRef = useRef(new Map<string, MemoryGraphNode>())
  nodeMapRef.current = useMemo(() => {
    const map = new Map<string, MemoryGraphNode>()
    for (const n of data?.nodes ?? []) map.set(n.id, n)
    return map
  }, [data])
  const onNodeClickRef = useRef(onNodeClick)
  onNodeClickRef.current = onNodeClick
  const onBackgroundClickRef = useRef(onBackgroundClick)
  onBackgroundClickRef.current = onBackgroundClick

  /** 用当前数据（ref）重放 option 到实例。

  空数据必须 chart.clear()——否则切换到空项目时 ECharts 保留上一项目的
  option，视觉上"卡在上一项目静态图"（实测根因）。
  */
  const renderData = (chart: ECharts, theme: GraphTheme) => {
    const current = dataRef.current
    if (!current || current.nodes.length === 0) {
      chart.clear()
      return
    }
    const option = buildGraphOption(current, theme)
    chart.setOption(option, { notMerge: true, lazyUpdate: true })

    const applyLod = () => {
      try {
        const series = (chart.getOption() as { series?: Array<{ zoom?: number }> }).series?.[0]
        const zoom = series?.zoom ?? 1
        applyLabelLod(option, zoom, theme)
        chart.setOption(option, { lazyUpdate: true })
      } catch {
        /* ignore */
      }
    }
    applyLod()
    chart.getZr().on('zoom', applyLod)
  }

  // ── 初始化（容器常驻，挂载即成功；StrictMode 双跑安全） ──
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const initChart = () => {
      const theme = readGraphTheme()
      themeRef.current = theme
      const chart = echarts.init(el, undefined, { renderer: 'canvas' })
      chartRef.current = chart

      chart.on('click', (params: unknown) => {
        const p = params as { dataType?: string; data?: { id?: string; source?: string } }
        const map = nodeMapRef.current
        if (p.dataType === 'node' && p.data?.id) {
          const node = map.get(p.data.id)
          if (node) onNodeClickRef.current?.(node)
          else onBackgroundClickRef.current?.()
        } else if (p.dataType === 'edge' && p.data?.source) {
          const node = map.get(String(p.data.source))
          if (node) onNodeClickRef.current?.(node)
        } else {
          onBackgroundClickRef.current?.()
        }
      })

      renderData(chart, theme)
      return chart
    }

    let chart = initChart()
    const handleResize = () => chart.resize()
    window.addEventListener('resize', handleResize)

    // 主题切换：重建实例并重放数据
    const unsubscribe = watchThemeChange(() => {
      chart.dispose()
      chartRef.current = null
      window.removeEventListener('resize', handleResize)
      chart = initChart()
      window.addEventListener('resize', handleResize)
    })

    return () => {
      window.removeEventListener('resize', handleResize)
      unsubscribe()
      chart.dispose()
      chartRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 数据变化 → 重放（实例已存在）
  useEffect(() => {
    const chart = chartRef.current
    if (chart) renderData(chart, themeRef.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data])

  const isEmpty = !loading && !error && (!data || data.nodes.length === 0)

  return (
    <div className="relative h-full min-h-[420px] w-full">
      {/* 画布容器常驻：图表实例从挂载起就有宿主 */}
      <div ref={containerRef} className="absolute inset-0" />

      {/* ── 覆盖层：加载 / 错误 / 空状态 ── */}
      {loading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center rounded-2xl bg-[hsl(var(--graph-bg))/0.6] text-sm text-muted-foreground backdrop-blur-[2px]">
          <div className="flex items-center gap-2">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            记忆图谱加载中…
          </div>
        </div>
      )}

      {error && !loading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center rounded-2xl text-sm text-destructive">
          <div className="max-w-sm rounded-xl border border-destructive/20 bg-card px-6 py-5 text-center">
            {error}
          </div>
        </div>
      )}

      {isEmpty && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 rounded-2xl bg-[hsl(var(--graph-bg))] text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-secondary text-2xl">
            🕸️
          </div>
          <p className="text-sm font-medium">该范围暂无记忆实体</p>
          <p className="max-w-sm text-xs leading-relaxed text-muted-foreground">
            完成一个研究/产品任务后，系统会自动从章节、经验包与图片分析中
            提炼实体、关系与洞察；也可在下方点击「重建记忆图谱」立即抽取。
          </p>
        </div>
      )}
    </div>
  )
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
