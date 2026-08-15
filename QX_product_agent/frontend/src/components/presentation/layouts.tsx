/**
 * Layout Library —— 10 个固定布局的页面框架（P4）
 *
 * 布局是人为定义的栅格（模型只选不造）：
 *   cover / summary / market / matrix / persona / journey /
 *   features / architecture / roadmap / closing
 */

import type { CSSProperties } from 'react'
import type { PresentationPage } from '@/types/presentation'
import { ComponentRenderer } from '@/components/presentation/components'

function FrameHeader({ page }: { page: PresentationPage }) {
  return (
    <div>
      <h2 className="text-[26px] font-bold leading-snug tracking-tight text-slate-900">{page.title}</h2>
      {page.subtitle && <p className="mt-2 text-sm leading-relaxed text-slate-500">{page.subtitle}</p>}
      {page.insight && (
        <p className="mt-3.5 inline-block rounded-lg bg-[var(--p-primary)]/10 px-3.5 py-1.5 text-sm font-medium leading-relaxed text-[var(--p-primary)]">
          {page.insight}
        </p>
      )}
    </div>
  )
}

function GridBody({
  page,
  columns,
  className = '',
}: {
  page: PresentationPage
  columns: number
  className?: string
}) {
  const gridStyle = { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }
  return (
    <div className={`grid gap-3 ${className}`} style={gridStyle}>
      {page.components.map((c) => (
        <ComponentRenderer key={c.id} component={c} />
      ))}
    </div>
  )
}

export function PageFrame({
  page,
  index,
  total,
  exportMode = false,
}: {
  page: PresentationPage
  index: number
  total: number
  exportMode?: boolean
}) {
  const isCover = page.layout === 'cover'
  const isClosing = page.layout === 'closing'

  // B1 修复：不再使用 absolute inset-0（会无视父级 padding 导致标题贴边），
  // 屏幕与导出模式统一为流式布局（WYSIWYG）。
  const shellClass = 'flex h-full w-full flex-col'

  // ── 布局分发 ──────────────────────────────────────────────
  let body: React.ReactNode = null
  switch (page.layout) {
    case 'cover':
    case 'closing':
      body = (
        <div className="flex flex-1 flex-col items-center justify-center text-center">
          <h2 className={`font-bold tracking-tight text-slate-900 ${isCover ? 'text-5xl' : 'text-4xl'}`}>
            {page.title}
          </h2>
          {page.subtitle && <p className="mt-3 text-lg text-slate-500">{page.subtitle}</p>}
          {page.insight && (
            <p className="mt-4 max-w-xl text-base font-medium text-slate-600">{page.insight}</p>
          )}
          {page.components.length > 0 && (
            <div className="mt-6 w-full max-w-2xl space-y-3">
              {page.components.map((c) => (
                <ComponentRenderer key={c.id} component={c} />
              ))}
            </div>
          )}
        </div>
      )
      break
    case 'summary':
      body = (
        <div className="flex flex-1 flex-col">
          <FrameHeader page={page} />
          <div className="mt-4 flex-1">
            <GridBody page={page} columns={Math.min(page.components.length, 3)} className="h-full content-start" />
          </div>
        </div>
      )
      break
    case 'market':
      body = (
        <div className="flex flex-1 flex-col">
          <FrameHeader page={page} />
          <div className="mt-4 grid flex-1 grid-cols-2 gap-4">
            {page.components.map((c) => (
              <ComponentRenderer key={c.id} component={c} />
            ))}
          </div>
        </div>
      )
      break
    case 'matrix':
      // 双栏：左侧象限图、右侧洞察卡片 —— 根治矩阵页高度溢出
      body = (
        <div className="flex flex-1 flex-col">
          <FrameHeader page={page} />
          <div className="mt-4 grid flex-1 grid-cols-2 gap-4">
            {page.components.map((c) => (
              <ComponentRenderer key={c.id} component={c} />
            ))}
          </div>
        </div>
      )
      break
    case 'persona':
      body = (
        <div className="flex flex-1 flex-col">
          <FrameHeader page={page} />
          <div className="mt-4 flex-1">
            <GridBody page={page} columns={Math.min(Math.max(page.components.length, 2), 3)} className="h-full content-start" />
          </div>
        </div>
      )
      break
    case 'journey':
    case 'roadmap':
      body = (
        <div className="flex flex-1 flex-col">
          <FrameHeader page={page} />
          <div className="mt-4 flex-1">
            <GridBody page={page} columns={page.components.length > 1 ? 1 : 1} />
          </div>
        </div>
      )
      break
    case 'features':
      body = (
        <div className="flex flex-1 flex-col">
          <FrameHeader page={page} />
          <div className="mt-4 flex-1">
            <GridBody page={page} columns={1} />
          </div>
        </div>
      )
      break
    case 'architecture':
      body = (
        <div className="flex flex-1 flex-col">
          <FrameHeader page={page} />
          <div className="mt-4 flex flex-1 flex-col gap-2">
            {page.components.map((c) => (
              <ComponentRenderer key={c.id} component={c} />
            ))}
          </div>
        </div>
      )
      break
    default:
      body = (
        <div className="flex flex-1 flex-col">
          <FrameHeader page={page} />
          <div className="mt-4 flex-1">
            <GridBody page={page} columns={1} />
          </div>
        </div>
      )
  }

  // B2: 导出模式也显示页码（放在安全区内）
  const pageNumber = (
    <div className="pointer-events-none absolute bottom-5 right-7 text-[10px] font-medium text-slate-400">
      {index + 1} / {total}
    </div>
  )

  return (
    // B2: 统一安全边距（56px 侧边 / 48px 上下），屏幕与导出一致
    <div className="relative h-full w-full rounded-xl bg-gradient-to-br from-slate-50 to-indigo-50/60 px-14 py-12 shadow-inner">
      <div className={shellClass}>
        {!isCover && !isClosing && page.components.length === 0 && (
          <p className="text-xs text-slate-400">（空页）</p>
        )}
        {body}
      </div>
      {pageNumber}
    </div>
  )
}

// ─── 预置品牌主题（免费方案：品牌主题系统） ───────────────────
export const THEMES: Record<string, { name: string; palette: Record<string, string> }> = {
  default: {
    name: '咨询蓝',
    palette: {
      bg: '#f8fafc', surface: '#ffffff', primary: '#4f46e5',
      accent: '#6366f1', text: '#0f172a', muted: '#64748b',
    },
  },
  vintage: {
    name: '复古编辑',
    palette: {
      bg: '#FAF9F5', surface: '#F4F1EA', primary: '#24415E',
      accent: '#C87E4F', text: '#1C2430', muted: '#716E66',
    },
  },
  forest: {
    name: '森林绿',
    palette: {
      bg: '#F4F6F3', surface: '#FFFFFF', primary: '#2F5D43',
      accent: '#4E8A66', text: '#16211B', muted: '#5B6B62',
    },
  },
  ink: {
    name: '墨黑金',
    palette: {
      bg: '#F5F4F2', surface: '#FFFFFF', primary: '#2B2A26',
      accent: '#B08A3C', text: '#1B1A17', muted: '#6B675E',
    },
  },
}

// 供导出模式使用的主题变量样式辅助
export function themeVars(palette?: Record<string, string>): CSSProperties {
  const p = palette ?? THEMES.default.palette
  return {
    '--p-primary': p.primary ?? '#4f46e5',
    '--p-accent': p.accent ?? '#6366f1',
    '--p-bg': p.bg ?? '#f8fafc',
    '--p-surface': p.surface ?? '#ffffff',
    '--p-text': p.text ?? '#0f172a',
    '--p-muted': p.muted ?? '#64748b',
  } as CSSProperties
}
