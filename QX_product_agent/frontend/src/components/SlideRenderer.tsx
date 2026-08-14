/**
 * SlideRenderer —— 演示渲染器（React-based renderer）
 *
 * 渲染 Slide JSON Schema（SlideDeck）为 16:9 Web 演示：
 *   - AI 生成: 内容结构 + layout_type + visual_metadata
 *   - 本组件控制: 排版、间距、组件样式（typography / spacing / style）
 *   - 支持键盘翻页（←/→）与 PPT 风格 PDF 导出
 */

import { useCallback, useEffect, useState } from 'react'
import {
  ChevronLeft,
  ChevronRight,
  FileDown,
  Loader2,
  MonitorPlay,
} from 'lucide-react'
import { Button } from '@/components/common/button'
import { cn } from '@/lib/utils'
import { productApi } from '@/lib/api'
import type { SlideBlock, SlideDeck } from '@/types/studio'

function renderBlock(block: SlideBlock) {
  const meta = (block.meta ?? {}) as Record<string, unknown>
  const emphasis = block.emphasis === 'high' ? 'text-primary' : ''

  switch (block.block_type) {
    case 'title':
      return <h2 className={`text-4xl font-bold tracking-tight ${emphasis}`}>{block.content}</h2>
    case 'subtitle':
      return <p className="text-xl text-muted-foreground">{block.content}</p>
    case 'bullets': {
      const items = block.content
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean)
      return (
        <ul className="space-y-2.5 pl-2">
          {(items.length ? items : [block.content]).map((item, i) => (
            <li key={`${block.id}-${i}`} className="flex gap-2.5 text-lg leading-relaxed">
              <span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary/70" />
              {item}
            </li>
          ))}
        </ul>
      )
    }
    case 'metric': {
      const value = String(meta.value ?? block.content)
      const label = String(meta.label ?? '')
      return (
        <div className="text-center">
          <div className="text-5xl font-bold text-primary">{value}</div>
          {label && <div className="mt-2 text-sm text-muted-foreground">{label}</div>}
        </div>
      )
    }
    case 'quote':
      return (
        <blockquote className="border-l-4 border-primary bg-secondary/40 px-6 py-4 text-xl leading-relaxed">
          {block.content}
        </blockquote>
      )
    case 'table': {
      const columns = (meta.columns as string[]) ?? []
      const rows = (meta.rows as string[][]) ?? []
      return (
        <table className="w-full border-collapse text-sm">
          {columns.length > 0 && (
            <thead>
              <tr>
                {columns.map((c) => (
                  <th
                    key={c}
                    className="bg-primary px-3 py-2 text-left text-primary-foreground"
                  >
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
          )}
          <tbody>
            {rows.map((row, i) => (
              <tr key={`${block.id}-${i}`} className="border-b last:border-0">
                {row.map((cell, j) => (
                  <td key={j} className="px-3 py-2">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )
    }
    case 'image':
      return (
        <div className="flex h-48 items-center justify-center rounded-xl border-2 border-dashed bg-secondary/40 text-sm text-muted-foreground">
          {String(meta.alt ?? block.content ?? '概念图')}
        </div>
      )
    default:
      return <p className="text-lg leading-relaxed">{block.content}</p>
  }
}

const LAYOUT_BODY_CLASS: Record<string, string> = {
  cover: 'items-center justify-center text-center',
  closing: 'items-center justify-center text-center',
  section_header: 'justify-center',
  two_column: 'grid grid-cols-2 gap-10 items-center',
}

export function SlideRenderer({
  deck,
  productId,
}: {
  deck: SlideDeck
  productId?: string
}) {
  const [index, setIndex] = useState(0)
  const [exporting, setExporting] = useState(false)
  const slides = deck.slides ?? []
  const slide = slides[index]

  const go = useCallback(
    (next: number) => {
      if (!slides.length) return
      setIndex((next + slides.length) % slides.length)
    },
    [slides.length],
  )

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') go(index + 1)
      if (e.key === 'ArrowLeft') go(index - 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [go, index])

  const exportPdf = async () => {
    if (!productId || exporting) return
    setExporting(true)
    try {
      const result = await productApi.exportPdf(productId)
      window.open(result.pdf_url, '_blank')
    } finally {
      setExporting(false)
    }
  }

  if (!slide) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border bg-card text-sm text-muted-foreground">
        演示内容为空
      </div>
    )
  }

  const layout = slide.layout_type ?? 'default'
  const bodyClass = LAYOUT_BODY_CLASS[layout] ?? ''

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MonitorPlay className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold">演示（Web Presentation）</h3>
          <span className="text-xs text-muted-foreground">
            {index + 1} / {slides.length}
          </span>
        </div>
        {productId && (
          <Button variant="outline" size="sm" onClick={exportPdf} disabled={exporting}>
            {exporting ? (
              <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
            ) : (
              <FileDown className="mr-2 h-3.5 w-3.5" />
            )}
            导出 PDF
          </Button>
        )}
      </div>

      {/* 16:9 幻灯片画布 */}
      <div className="relative aspect-video w-full overflow-hidden rounded-lg bg-gradient-to-br from-slate-50 to-indigo-50 shadow-inner">
        <div
          className={cn(
            'flex h-full w-full flex-col px-12 py-9',
            layout === 'cover' && bodyClass,
            layout === 'closing' && bodyClass,
          )}
        >
          {(layout === 'cover' || layout === 'closing' || layout === 'section_header') && (
            <div className={cn(layout === 'cover' || layout === 'closing' ? 'text-center' : '')}>
              <h2
                className={cn(
                  'font-bold tracking-tight text-slate-900',
                  layout === 'cover' ? 'text-5xl' : 'text-4xl',
                )}
              >
                {slide.title}
              </h2>
              {slide.subtitle && (
                <p className="mt-3 text-lg text-slate-500">{slide.subtitle}</p>
              )}
            </div>
          )}

          {layout !== 'cover' &&
            layout !== 'closing' &&
            layout !== 'section_header' && (
              <h2 className="mb-5 text-2xl font-semibold text-slate-900">{slide.title}</h2>
            )}

          <div className={cn('flex flex-1 flex-col justify-center gap-5', bodyClass)}>
            {slide.blocks.map((block) => (
              <div key={block.id}>{renderBlock(block)}</div>
            ))}
          </div>

          {/* 底部页码 */}
          <div className="absolute bottom-4 right-6 text-xs text-slate-400">
            {slide.id ?? index + 1}
          </div>
        </div>
      </div>

      {/* 导航 */}
      <div className="mt-4 flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={() => go(index - 1)}>
          <ChevronLeft className="mr-1 h-4 w-4" /> 上一页
        </Button>
        <div className="flex items-center gap-1.5">
          {slides.map((s, i) => (
            <button
              key={s.id}
              type="button"
              aria-label={`跳转到第 ${i + 1} 页`}
              onClick={() => setIndex(i)}
              className={cn(
                'h-1.5 rounded-full transition-all',
                i === index ? 'w-5 bg-primary' : 'w-1.5 bg-border hover:bg-muted-foreground/40',
              )}
            />
          ))}
        </div>
        <Button variant="ghost" size="sm" onClick={() => go(index + 1)}>
          下一页 <ChevronRight className="ml-1 h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
