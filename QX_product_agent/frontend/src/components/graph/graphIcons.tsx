/**
 * graphIcons —— 实体类型 → lucide SVG data-URL 注册表
 *
 * 用 react-dom/server 将 lucide-react 图标渲染为内联 SVG，
 * 编码为 ECharts 可直接使用的 image://data:image/svg+xml;base64,... symbol。
 * 结果按 (icon,color) 缓存，避免重复渲染。
 */

import { renderToStaticMarkup } from 'react-dom/server'
import {
  Building2,
  Package,
  Cpu,
  User,
  TrendingUp,
  Gauge,
  CircleDot,
  type LucideIcon,
} from 'lucide-react'
import type { MemoryEntityType } from '@/types/api'

const ICON_MAP: Record<MemoryEntityType, LucideIcon> = {
  company: Building2,
  product: Package,
  technology: Cpu,
  person: User,
  market: TrendingUp,
  metric: Gauge,
  other: CircleDot,
}

const cache = new Map<string, string>()

function encodeSvg(svg: string): string {
  // 先尝试 base64（体积更小），失败回退 encodeURIComponent
  try {
    if (typeof btoa === 'function') {
      return `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(svg)))}`
    }
  } catch {
    /* fallthrough */
  }
  return `data:image/svg+xml,${encodeURIComponent(svg)}`
}

export function entityIconDataUrl(type: MemoryEntityType, color: string): string {
  const key = `${type}:${color}`
  const cached = cache.get(key)
  if (cached) return cached

  const Icon = ICON_MAP[type] ?? CircleDot
  const svg = renderToStaticMarkup(
    <Icon size={18} color={color} strokeWidth={2.2} aria-hidden />,
  )
  const url = encodeSvg(svg)
  cache.set(key, url)
  return url
}
