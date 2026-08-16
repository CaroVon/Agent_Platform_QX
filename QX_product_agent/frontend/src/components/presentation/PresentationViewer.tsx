/**
 * PresentationViewer —— Presentation DSL 的单一 React 渲染源（P4）
 *
 * Web 预览、编辑器视图与 PDF 导出共用本渲染器（WYSIWYG）：
 *   - 普通模式：16:9 画布 + 翻页导航 + 导出按钮
 *   - exportMode：无 UI 外壳，每页一个固定 16:9 section（打印分页）
 */

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import {
  ChevronLeft,
  ChevronRight,
  MonitorPlay,
  Palette,
} from 'lucide-react'
import { Button } from '@/components/common/button'
import { cn } from '@/lib/utils'
import { ExportMenu } from '@/components/presentation/ExportMenu'
import type { PresentationDSL, QualityGateReport } from '@/types/presentation'
import { PageFrame, THEMES, themeVars } from '@/components/presentation/layouts'

// ─── 固定 1280×720 舞台（预览与导出 HTML/PDF 同坐标系） ────────
const STAGE_W = 1280
const STAGE_H = 720

function useStageScale() {
  const ref = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const update = () => {
      const width = el.clientWidth
      if (width > 0) setScale(width / STAGE_W)
    }
    update()
    const observer = new ResizeObserver(update)
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return { ref, scale }
}

// ─── 预览溢出自适应（与导出 autoFit 同逻辑，逐级 10% 缩放） ───
function usePreviewAutoFit(pageEl: HTMLElement | null, scale: number, pageKey: string) {
  useLayoutEffect(() => {
    if (!pageEl) return
    // 先重置再测量（避免累计）；坐标系为 stage 内 CSS 像素（720 上限）
    pageEl.style.fontSize = '100%'
    for (let i = 0; i < 4; i++) {
      const scrollH = pageEl.scrollHeight
      if (scrollH <= STAGE_H + 2) break
      const current = parseFloat(pageEl.style.fontSize || '100')
      const next = Math.max(current - 10, 60)
      pageEl.style.fontSize = `${next}%`
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageEl, pageKey]) // pageKey 变化（翻页）时重新测量
}

export function PresentationViewer({
  presentation,
  productId,
  exportMode = false,
  qualityGate,
  currentIndex,
  onIndexChange,
}: {
  presentation: PresentationDSL
  productId?: string
  exportMode?: boolean
  qualityGate?: QualityGateReport | null
  currentIndex?: number
  onIndexChange?: (index: number) => void
}) {
  const [internalIndex, setInternalIndex] = useState(0)
  // 初始主题取自 DSL（生成的咨询风主题直接生效）；切换器仍可覆盖
  const [themeId, setThemeId] = useState<string>(() =>
    presentation.theme?.id && THEMES[presentation.theme.id] ? presentation.theme.id : 'default',
  )
  const [themeOpen, setThemeOpen] = useState(false)
  const pages = presentation.pages ?? []
  const index = currentIndex ?? internalIndex
  const page = pages[index]

  const setIndex = useCallback(
    (next: number) => {
      const clamped = pages.length ? ((next % pages.length) + pages.length) % pages.length : 0
      if (currentIndex !== undefined && onIndexChange) {
        onIndexChange(clamped)
      } else {
        setInternalIndex(clamped)
      }
    },
    [pages.length, currentIndex, onIndexChange],
  )
  const fontScale = presentation.theme?.font_scale ?? 1

  const go = useCallback(
    (next: number) => {
      if (!pages.length) return
      setIndex(next)
    },
    [pages.length, setIndex],
  )

  useEffect(() => {
    if (exportMode) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') go(index + 1)
      if (e.key === 'ArrowLeft') go(index - 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [go, index, exportMode])

  // 主题切换（仅显示层覆盖，不改数据；导出时通过 ?theme= 传参）
  const activePalette = THEMES[themeId]?.palette ?? presentation.theme?.palette
  const vars = themeVars(activePalette)

  // 预览固定舞台（与导出同坐标系）
  const { ref: stageWrapRef, scale } = useStageScale()
  const stageRef = useRef<HTMLDivElement>(null)
  const currentPageEl = stageRef.current?.querySelector<HTMLElement>('.stage-page') ?? null
  usePreviewAutoFit(currentPageEl, scale, page?.id ?? '')

  // ─── 导出模式：全量渲染，打印分页 ─────────────────────────
  if (exportMode) {
    return (
      <div style={{ ...vars, fontSize: `${fontScale * 100}%` }}>
        {pages.map((p, i) => (
          <section
            key={p.id}
            data-page={p.id}
            className="export-page"
          >
            <PageFrame page={p} index={i} total={pages.length} exportMode />
          </section>
        ))}
      </div>
    )
  }

  if (!page) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border bg-card text-sm text-muted-foreground">
        演示内容为空
      </div>
    )
  }

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm" style={vars}>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MonitorPlay className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold">演示（Web Presentation）</h3>
          <span className="text-xs text-muted-foreground">
            {index + 1} / {pages.length}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {qualityGate && qualityGate.warnings.length > 0 && (
            <span className="text-[10px] text-amber-600">
              质量门警告 ×{qualityGate.warnings.length}
            </span>
          )}
          {/* 主题切换器（预置品牌主题） */}
          <div className="relative">
            <Button
              variant="ghost"
              size="sm"
              title="切换主题"
              onClick={() => setThemeOpen((v) => !v)}
            >
              <Palette className="mr-2 h-3.5 w-3.5" />
              {THEMES[themeId]?.name ?? '主题'}
            </Button>
            {themeOpen && (
              <div className="absolute right-0 top-full z-20 mt-1 w-36 rounded-lg border bg-popover p-1 shadow-lg">
                {Object.entries(THEMES).map(([id, theme]) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => {
                      setThemeId(id)
                      setThemeOpen(false)
                    }}
                    className={cn(
                      'flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-xs transition-colors hover:bg-accent',
                      id === themeId && 'bg-accent',
                    )}
                  >
                    <span
                      className="h-3.5 w-3.5 shrink-0 rounded-full border"
                      style={{ backgroundColor: theme.palette.primary }}
                    />
                    {theme.name}
                  </button>
                ))}
              </div>
            )}
          </div>
          {productId && <ExportMenu productId={productId} />}
        </div>
      </div>

      {/* 16:9 画布：固定 1280×720 舞台 + scale 适配（与导出 HTML/PDF 完全一致） */}
      <div ref={stageWrapRef} className="relative w-full overflow-hidden rounded-xl" style={{ aspectRatio: '16 / 9' }}>
        <div
          ref={stageRef}
          className="absolute left-1/2 top-1/2"
          style={{
            width: STAGE_W,
            height: STAGE_H,
            transform: `translate(-50%, -50%) scale(${scale})`,
            transformOrigin: 'center center',
          }}
        >
          <div className="stage-page h-full w-full" style={{ fontSize: '100%' }}>
            <PageFrame page={page} index={index} total={pages.length} />
          </div>
        </div>
      </div>

      {/* 导航 */}
      <div className="mt-4 flex items-center justify-between">
        <Button variant="ghost" size="sm" onClick={() => go(index - 1)}>
          <ChevronLeft className="mr-1 h-4 w-4" /> 上一页
        </Button>
        <div className="flex items-center gap-1.5">
          {pages.map((p, i) => (
            <button
              key={p.id}
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
