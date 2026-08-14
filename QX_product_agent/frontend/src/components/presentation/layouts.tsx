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
      <h2 className="text-2xl font-bold tracking-tight text-slate-900">{page.title}</h2>
      {page.subtitle && <p className="mt-1 text-sm text-slate-500">{page.subtitle}</p>}
      {page.insight && (
        <p className="mt-2 inline-block rounded-lg bg-[var(--p-primary)]/10 px-3 py-1 text-sm font-medium text-[var(--p-primary)]">
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

  const shellClass = exportMode
    ? 'absolute inset-0 flex flex-col'
    : 'flex h-full w-full flex-col'

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
      body = (
        <div className="flex flex-1 flex-col">
          <FrameHeader page={page} />
          <div className="mt-4 flex-1">
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

  const pageNumber = (
    <div className="absolute bottom-3 right-4 text-[10px] text-slate-400">
      {index + 1} / {total}
    </div>
  )

  return (
    <div className="relative h-full w-full rounded-xl bg-gradient-to-br from-slate-50 to-indigo-50/60 px-8 py-6 shadow-inner">
      <div className={shellClass}>
        {!isCover && !isClosing && page.components.length === 0 && (
          <p className="text-xs text-slate-400">（空页）</p>
        )}
        {body}
      </div>
      {!exportMode && pageNumber}
    </div>
  )
}

// 供导出模式使用的主题变量样式辅助
export function themeVars(palette?: Record<string, string>): CSSProperties {
  const p = palette ?? {}
  return {
    '--p-primary': p.primary ?? '#4f46e5',
    '--p-accent': p.accent ?? '#6366f1',
    '--p-bg': p.bg ?? '#f8fafc',
    '--p-surface': p.surface ?? '#ffffff',
    '--p-text': p.text ?? '#0f172a',
    '--p-muted': p.muted ?? '#64748b',
  } as CSSProperties
}
