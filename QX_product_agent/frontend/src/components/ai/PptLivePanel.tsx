/**
 * ai/PptLivePanel —— PPT 制作过程可视化（详细状态版，P6）
 *
 * 数据源：GET /product/{id}/ppt-progress（progress.json + svg_output 实时页清单）
 * 形态：
 *   - 顶部：当前阶段活动条（规范→生图→逐页创作→转换→MOD 导出→完成）
 *     + 审校分数 / 返工轮次 + 已完成/总页数计数
 *   - 缩略图网格流式填充（SVG 生成一页显示一页），每页状态徽标
 *     （生成中 llm / 兜底 fallback / 返工 rework 后完成）
 *   - 点击缩略图 → Lightbox 放大预览 SVG
 * 仅在 ppt_design 运行中或已有页面产物时激活。
 */

import { useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  Presentation,
  Loader2,
  Maximize2,
  RefreshCw,
  ShieldCheck,
  ThumbsDown,
  X,
} from 'lucide-react'
import { productApi, type PptProgress } from '@/lib/api'
import { cn } from '@/lib/utils'

const STAGE_LABELS: Record<string, string> = {
  spec: '设计规范生成',
  images: '配图生成（hero / 架构 / 场景）',
  authoring: '逐页 SVG 创作 + 质量门禁',
  finalizing: 'finalize + 转换 PPTX',
  mod_export: 'MOD 独立 PPTX 导出',
  done: '制作完成',
}

const STAGE_ORDER = ['spec', 'images', 'authoring', 'finalizing', 'mod_export', 'done']

function pageStatusOf(
  index: number,
  perPage: Record<string, string> | undefined,
  total: number | null | undefined,
): 'pending' | 'llm' | 'fallback' | 'done' {
  const s = perPage?.[String(index)]
  if (s === 'llm') return 'llm'
  if (s === 'fallback') return 'fallback'
  // 无 per_page 记录但文件已出现（早期版本/回放）→ 视为完成
  if (s === undefined && total && index <= total) return 'done'
  return 'pending'
}

export function PptLivePanel({
  productId,
  active,
}: {
  productId: string
  /** ppt_design 节点运行中（外层根据 node_status 判定） */
  active: boolean
}) {
  const [progress, setProgress] = useState<PptProgress | null>(null)
  const [lightbox, setLightbox] = useState<PptProgress['pages'][number] | null>(null)
  const [error, setError] = useState('')
  const [reworkMsg, setReworkMsg] = useState('')
  const [reworkBusy, setReworkBusy] = useState<number | null>(null)
  const timer = useRef<number | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const p = await productApi.pptProgress(productId)
        if (!cancelled) {
          setProgress(p)
          setError('')
        }
      } catch {
        if (!cancelled) setError('进度暂不可用')
      }
    }
    load()
    // 运行中 3s 轮询；完成后 8s 低频兜底（PPTX URL 延迟落库）
    const interval = active ? 3000 : 8000
    timer.current = window.setInterval(load, interval)
    return () => {
      cancelled = true
      if (timer.current) window.clearInterval(timer.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId, active])

  const hasPages = (progress?.pages?.length ?? 0) > 0
  if (!progress || (!progress.active && !hasPages && progress.stage !== 'done')) {
    return null
  }

  /** P0.5：页级👎返工（运行中入队 / 完成态外科重做） */
  const handleRework = async (pageIndex: number) => {
    const feedback =
      window.prompt(
        `对第 ${pageIndex + 1} 页的改进意见（会带反馈重做该页并重新导出）：`,
        '',
      ) ?? ''
    if (feedback === null) return
    setReworkBusy(pageIndex)
    try {
      const r = await productApi.pptRework(productId, pageIndex, feedback.trim())
      setReworkMsg(r.queued ? `P${pageIndex + 1} 已入返工队列` : (r.detail || `P${pageIndex + 1} 已重做`))
    } catch (e) {
      setReworkMsg(`返工失败: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setReworkBusy(null)
      setTimeout(() => setReworkMsg(''), 6000)
    }
  }

  const stage = progress.stage ?? ''
  const stageLabel = STAGE_LABELS[stage] ?? 'PPT 制作'
  const stageIdx = STAGE_ORDER.indexOf(stage)
  const done = stage === 'done'
  const totalPages = progress.total ?? 0
  const donePages = progress.done_pages ?? progress.pages.length

  return (
    <div className="rounded-lg border border-border bg-card shadow-elev-sm">
      {/* ── 头部：阶段活动条 + 计数 ── */}
      <div className="border-b border-border px-4 py-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                'flex h-6 w-6 items-center justify-center rounded-md',
                done ? 'bg-emerald-500/10 text-emerald-600' : 'bg-[#24415E]/10 text-[#24415E]',
              )}
            >
              {done ? (
                <ShieldCheck className="h-3.5 w-3.5" />
              ) : (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              )}
            </span>
            <div>
              <div className="text-[12px] font-semibold leading-tight">
                PPT 制作可视化
              </div>
              <div className="text-[11px] text-muted-foreground">
                {done ? '全部页面完成' : stageLabel}
                {active && !done && <span className="ml-1 animate-pulse-dot">·</span>}
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className="font-mono text-[13px] font-semibold text-[#24415E]">
              {donePages}/{totalPages || '—'}
            </div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
              pages
            </div>
          </div>
        </div>

        {/* 阶段进度条 */}
        <div className="flex gap-1">
          {STAGE_ORDER.map((s, i) => (
            <div
              key={s}
              className={cn(
                'h-1 flex-1 rounded-full transition-all duration-500',
                i < stageIdx || done
                  ? 'bg-emerald-500/70'
                  : i === stageIdx
                    ? 'bg-[#24415E] animate-soft-pulse'
                    : 'bg-secondary',
              )}
            />
          ))}
        </div>

        {/* 审校分数 / 返工轮次 */}
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
          {progress.critic_score != null && (
            <span>
              审校分数{' '}
              <span
                className={cn(
                  'font-mono font-semibold',
                  (progress.critic_score ?? 0) >= 80 ? 'text-emerald-600' : 'text-amber-600',
                )}
              >
                {progress.critic_score}
              </span>
            </span>
          )}
          {progress.revision_round != null && progress.revision_round > 1 && (
            <span className="flex items-center gap-1 text-amber-600">
              <RefreshCw className="h-3 w-3" />
              第 {progress.revision_round} 轮制作
            </span>
          )}
          {progress.pptx_url && (
            <a
              href={progress.pptx_url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 text-[#24415E] underline-offset-2 hover:underline"
            >
              <Presentation className="h-3 w-3" />
              下载 PPTX
            </a>
          )}
        </div>
      </div>

      {/* ── 缩略图网格（流式填充） ── */}
      <div className="px-4 py-3">
        {error && <div className="mb-2 text-[11px] text-muted-foreground">{error}</div>}
        {reworkMsg && (
          <div className="mb-2 rounded border border-[#24415E]/30 bg-[#24415E]/5 px-2 py-1 text-[11px] text-[#24415E]">
            {reworkMsg}
          </div>
        )}
        {hasPages ? (
          <div className="grid grid-cols-3 gap-2">
            {progress.pages.map((pg) => {
              const st = pageStatusOf(pg.index, progress.per_page, progress.total)
              return (
                <div key={pg.file} className="group relative">
                <button
                  type="button"
                  onClick={() => setLightbox(pg)}
                  className="relative block w-full overflow-hidden rounded-md border border-border bg-background/60 transition-all hover:border-[#24415E]/50 hover:shadow-elev-xs"
                >
                  <img
                    src={pg.url}
                    alt={pg.file}
                    loading="lazy"
                    className="aspect-video w-full object-cover"
                  />
                  <div className="absolute left-1 top-1 rounded bg-black/55 px-1 py-px font-mono text-[9px] text-white">
                    P{String(pg.index).padStart(2, '0')}
                  </div>
                  {st === 'fallback' && (
                    <div className="absolute right-1 top-1 flex items-center gap-0.5 rounded bg-amber-500/85 px-1 py-px text-[9px] font-medium text-white">
                      <AlertTriangle className="h-2.5 w-2.5" />
                      兜底
                    </div>
                  )}
                  {st === 'llm' && !done && (
                    <div className="absolute right-1 top-1 rounded bg-emerald-500/85 px-1 py-px text-[9px] font-medium text-white">
                      新
                    </div>
                  )}
                  <div className="pointer-events-none absolute inset-0 hidden items-center justify-center bg-black/40 group-hover:flex">
                    <Maximize2 className="h-4 w-4 text-white" />
                  </div>
                  {/* MOD 章节页标记 */}
                  {pg.file.includes('_mod_') && (
                    <div className="absolute bottom-1 right-1 rounded bg-[#24415E]/85 px-1 py-px font-mono text-[9px] text-white">
                      MOD
                    </div>
                  )}
                </button>
                  {/* P0.5：页级返工按钮（hover 出现，运行中入队 / 完成态重做） */}
                  <button
                    type="button"
                    title="对此页返工（附改进意见）"
                    disabled={reworkBusy === pg.index}
                    onClick={(e) => {
                      e.stopPropagation()
                      handleRework(pg.index)
                    }}
                    className="absolute bottom-1 left-1 hidden items-center gap-1 rounded bg-white/90 px-1.5 py-0.5 text-[10px] font-medium text-red-600 shadow group-hover:flex disabled:opacity-50"
                  >
                    {reworkBusy === pg.index ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <ThumbsDown className="h-3 w-3" />
                    )}
                    返工
                  </button>
                </div>
              )
            })}
            {/* 待生成占位 */}
            {active &&
              !done &&
              totalPages > progress.pages.length &&
              Array.from({ length: Math.min(totalPages - progress.pages.length, 6) }).map((_, i) => (
                <div
                  key={`ph-${i}`}
                  className="flex aspect-video items-center justify-center rounded-md border border-dashed border-border/80 bg-background/30"
                >
                  <Loader2 className="h-3 w-3 animate-spin text-muted-foreground/50" />
                </div>
              ))}
          </div>
        ) : (
          <div className="flex items-center justify-center gap-2 py-6 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-[#24415E]" />
            <span>{stageLabel}</span>
          </div>
        )}
      </div>

      {/* ── Lightbox 放大预览 ── */}
      {lightbox && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-8 backdrop-blur-sm"
          onClick={() => setLightbox(null)}
        >
          <div className="relative max-h-full w-full max-w-5xl">
            <button
              type="button"
              onClick={() => setLightbox(null)}
              className="absolute -top-9 right-0 flex items-center gap-1.5 rounded-md border border-white/20 bg-white/10 px-2.5 py-1 text-[12px] text-white hover:bg-white/20"
            >
              <X className="h-3.5 w-3.5" />
              关闭
            </button>
            <img
              src={lightbox.url}
              alt={lightbox.file}
              className="max-h-full w-full rounded-lg bg-white object-contain shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            />
            <div className="mt-2 text-center font-mono text-[11px] text-white/70">
              {lightbox.file}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
