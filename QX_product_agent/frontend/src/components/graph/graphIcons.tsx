/**
 * graphIcons —— 实体类型 → 内联 SVG data-URL 注册表
 *
 * 关键修复（v2）：
 *  - 颜色直接烤进 SVG 的 stroke 属性，不再依赖 currentColor
 *  - 输出完整 viewBox + 显式 stroke，确保 ECharts 的 Image 能正确渲染
 *  - 提高图标比例（默认 0.55）让图标在小节点上也清晰可见
 */

const cache = new Map<string, string>()

// 实体类型 → 颜色 hex
const TYPE_COLORS: Record<string, string> = {
  company: '#3B82F6',
  product: '#06B6D4',
  technology: '#A855F7',
  person: '#F59E0B',
  market: '#EC4899',
  metric: '#14B8A6',
  other: '#6B7280',
}

// 实体类型 → SVG path d (24x24 viewBox)
const TYPE_PATHS: Record<string, string> = {
  company:
    'M3 21V7l9-4 9 4v14M9 21V11h6v10M3 21h18',
  product:
    'M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16zM3.27 6.96L12 12.01l8.73-5.05M12 22.08V12',
  technology:
    'M9 2v6h6V2M9 22v-6h6v6M2 9h6v6H2M22 9h-6v6h6M6 6h12v12H6z',
  person:
    'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
  market:
    'M3 17l6-6 4 4 8-8M14 7h7v7',
  metric:
    'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM12 6v6l4 2',
  other:
    'M12 12m-9 0a9 9 0 1 0 18 0 9 9 0 1 0-18 0M12 8v4M12 16h.01',
}

const DEFAULT_PATH =
  'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM12 8v4M12 16h.01'

function encodeSvg(svg: string): string {
  const cleaned = svg.replace(/\s+/g, ' ').trim()
  if (typeof btoa === 'function') {
    try {
      return `data:image/svg+xml;base64,${btoa(cleaned)}`
    } catch {
      /* fallthrough */
    }
  }
  return `data:image/svg+xml,${encodeURIComponent(cleaned)}`
}

export function entityIconDataUrl(type: string, color?: string): string {
  const c = color ?? TYPE_COLORS[type] ?? TYPE_COLORS.other
  const key = `${type}:${c}`
  const cached = cache.get(key)
  if (cached) return cached

  const path = TYPE_PATHS[type] ?? DEFAULT_PATH
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="${c}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="${path}"/></svg>`

  const url = encodeSvg(svg)
  cache.set(key, url)
  return url
}
