/**
 * graphTheme —— 知识关系图主题桥接
 *
 * 读取 CSS 变量（--graph-* 与 --primary 等）生成 ECharts 可用的主题对象，
 * 亮/暗主题由 .dark class 自动适配；主题切换通过重建图表生效。
 */

import type { MemoryEntityType } from '@/types/api'

export interface GraphTheme {
  isDark: boolean
  bg: string
  /** 实体类型 → 主色 */
  nodeColors: Record<MemoryEntityType, string>
  focus: string
  focusRing: string
  muted: string
  edge: string
  edgeFocus: string
  label: string
  labelBg: string
}

function hslVar(name: string): string {
  if (typeof document === 'undefined') return '#888'
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  if (!raw) return '#888'
  return `hsl(${raw})`
}

export function readGraphTheme(): GraphTheme {
  const isDark =
    typeof document !== 'undefined' && document.documentElement.classList.contains('dark')

  return {
    isDark,
    bg: hslVar('--graph-bg'),
    nodeColors: {
      company: hslVar('--graph-type-company'),
      product: hslVar('--graph-type-product'),
      technology: hslVar('--graph-type-technology'),
      person: hslVar('--graph-type-person'),
      market: hslVar('--graph-type-market'),
      metric: hslVar('--graph-type-metric'),
      other: hslVar('--graph-type-other'),
    },
    focus: hslVar('--graph-focus'),
    focusRing: hslVar('--graph-focus-ring'),
    muted: hslVar('--graph-muted'),
    edge: hslVar('--graph-edge'),
    edgeFocus: hslVar('--graph-edge-focus'),
    label: hslVar('--graph-label'),
    labelBg: hslVar('--graph-label-bg'),
  }
}

export function watchThemeChange(onChange: () => void): () => void {
  if (typeof document === 'undefined') return () => {}
  const target = document.documentElement
  const observer = new MutationObserver(() => onChange())
  observer.observe(target, { attributes: true, attributeFilter: ['class'] })
  return () => observer.disconnect()
}
