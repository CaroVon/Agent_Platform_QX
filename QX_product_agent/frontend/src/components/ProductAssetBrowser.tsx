/**
 * ProductAssetBrowser —— 资产聚合页通用骨架
 *
 * 左侧：全部产品列表（含状态徽标：运行中/排队中/已完成/失败）
 * 右侧：选中产品的资产详情（由各模块页提供 renderDetail）
 * 运行中/排队中的产品展示占位提示，并自动轮询刷新直至完成。
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useLocation } from 'react-router-dom'
import { Boxes, ChevronRight, Loader2 } from 'lucide-react'
import { productApi } from '@/lib/api'
import type { StudioProduct } from '@/types/studio'
import { cn } from '@/lib/utils'

const STATUS_META: Record<string, { label: string; cls: string }> = {
  running: { label: '进行中', cls: 'bg-[#24415E]/10 text-[#24415E] animate-soft-pulse' },
  queued: { label: '排队中', cls: 'bg-slate-500/10 text-slate-500' },
  completed: { label: '已完成', cls: 'bg-emerald-500/10 text-emerald-600' },
  failed: { label: '失败', cls: 'bg-destructive/10 text-destructive' },
}

export function ProductAssetBrowser({
  renderDetail,
  emptyTitle,
  emptyDescription,
}: {
  renderDetail: (product: StudioProduct) => React.ReactNode
  emptyTitle: string
  emptyDescription: string
}) {
  const location = useLocation()
  const [products, setProducts] = useState<StudioProduct[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const timerRef = useRef<number | null>(null)

  const load = useCallback(async () => {
    try {
      // F3 体验优化：列表页只用轻量摘要（不再对全部产品 N+1 拉全量详情包）；
      // 详情由上方 detailQuery 按选中项拉取并经 TanStack Query 缓存
      const list = await productApi.list(0, 100)
      const merged = list as StudioProduct[]
      setProducts(merged)
      const requested = (location.state as { productId?: string } | null)?.productId
      setSelectedId((prev) => {
        if (prev && merged.some((p) => p.product_id === prev)) return prev
        if (requested && merged.some((p) => p.product_id === requested)) return requested
        // 优先默认选中「PPT 最新产出」的已完成产品（用户最关心的新资产），
        // 其次最新已完成产品；运行中任务在列表可见
        const completed = merged.filter((p) => p.status === 'completed')
        const withPpt = completed
          .filter((p) => p.ppt_design?.pptx_relative)
          .sort((a, b) => {
            const ta = a.ppt_design?.created_at ? Date.parse(a.ppt_design.created_at) : 0
            const tb = b.ppt_design?.created_at ? Date.parse(b.ppt_design.created_at) : 0
            return tb - ta
          })
        return (
          withPpt[0]?.product_id ??
          completed[0]?.product_id ??
          merged[0]?.product_id ??
          null
        )
      })
      return merged.some((p) => p.status === 'running' || p.status === 'queued')
    } finally {
      setLoading(false)
    }
  }, [location.state])

  // 选中项详情（按需 + 缓存；列表摘要缺 ppt_design 等字段时由此补齐）
  const detailQuery = useQuery({
    queryKey: ['product-detail', selectedId],
    queryFn: () => productApi.get(selectedId as string),
    enabled: !!selectedId,
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    // 列表显示 completed 但详情尚未加载完成时仍展示摘要卡
    placeholderData: (prev) => prev,
  })
  const selectedDetail = detailQuery.data ?? null

  useEffect(() => {
    let cancelled = false
    const start = async () => {
      if (cancelled) return
      const stillActive = await load()
      // 有运行/排队任务 → 每 15s 自动刷新直至全部落地
      if (stillActive && !cancelled) {
        timerRef.current = window.setInterval(async () => {
          const active = await load()
          if (!active && timerRef.current) {
            window.clearInterval(timerRef.current)
            timerRef.current = null
          }
        }, 15000)
      }
    }
    start()
    return () => {
      cancelled = true
      if (timerRef.current) window.clearInterval(timerRef.current)
    }
  }, [load])

  const selected = (selectedDetail && selectedDetail.product_id === selectedId
    ? selectedDetail
    : products.find((p) => p.product_id === selectedId)) ?? null
  const runningCount = products.filter((p) => p.status === 'running' || p.status === 'queued').length

  /** 展示名称：优先 idea；空 idea 时退回 presentation 标题（或恢复资产生成标题） */
  const displayName = (p: StudioProduct) => {
    if (p.idea) return p.idea
    const pres = p.presentation as { title?: string } | null | undefined
    if (pres?.title) return pres.title
    if (p.ppt_design?.design_brief && p.ppt_design.pptx_relative) return p.ppt_design.design_brief
    return '（未命名）'
  }

  const hasPpt = (p: StudioProduct) => Boolean(p.ppt_design?.pptx_relative)
  const isRecoveredPpt = (p: StudioProduct) => Boolean(p.ppt_design?.pptx_relative && p.ppt_design?.recovered)

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> 加载资产中…
      </div>
    )
  }

  if (products.length === 0) {
    return (
      <div className="flex min-h-[380px] flex-col items-center justify-center rounded-2xl border border-dashed bg-card/40 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-secondary">
          <Boxes className="h-6 w-6 text-muted-foreground" />
        </div>
        <h3 className="mt-5 text-base font-medium">{emptyTitle}</h3>
        <p className="mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
          {emptyDescription}
        </p>
      </div>
    )
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
      {/* ─── 产品列表（全部状态） ─────────────────────────────── */}
      <aside className="space-y-1.5">
        <div className="px-2 pb-2 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
          产品资产
          {runningCount > 0 && (
            <span className="ml-1.5 rounded-full bg-[#24415E]/10 px-1.5 py-0.5 text-[#24415E]">
              {runningCount} 个任务进行中
            </span>
          )}
        </div>
        {products.map((p) => {
          const active = p.product_id === selectedId
          const meta = STATUS_META[p.status] ?? STATUS_META.failed
          return (
            <button
              key={p.product_id}
              type="button"
              onClick={() => setSelectedId(p.product_id)}
              className={cn(
                'flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-left text-sm transition-colors',
                active
                  ? 'bg-secondary font-medium text-foreground'
                  : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground',
              )}
            >
              <span className="min-w-0 flex-1 truncate">{displayName(p)}</span>
              {hasPpt(p) && (
                <span
                  title={isRecoveredPpt(p) ? '已从磁盘资产对账恢复（可下载）' : '已生成可编辑 PPT（ppt-master）'}
                  className="flex shrink-0 items-center gap-1 rounded-full bg-emerald-600/10 px-1.5 py-0.5 text-[10px] font-medium text-emerald-600"
                >
                  PPT
                  {isRecoveredPpt(p) && <span className="text-[9px] opacity-70">·恢复</span>}
                </span>
              )}
              <span className={cn('shrink-0 rounded-full px-1.5 py-0.5 text-[10px]', meta.cls)}>
                {meta.label}
              </span>
              {p.critic_score != null && p.status === 'completed' && (
                <span
                  className={cn(
                    'shrink-0 rounded-full px-1.5 py-0.5 text-[10px]',
                    p.critic_score >= 80 ? 'bg-emerald-500/10 text-emerald-600' : 'bg-amber-500/10 text-amber-600',
                  )}
                >
                  {p.critic_score}
                </span>
              )}
              <ChevronRight className="h-3.5 w-3.5 shrink-0 opacity-40" />
            </button>
          )
        })}
      </aside>

      {/* ─── 资产详情 ─────────────────────────────────────────── */}
      <div className="min-w-0 space-y-5">
        {!selected ? null : selected.status === 'completed' ? (
          renderDetail(selected)
        ) : (
          <div className="flex min-h-[300px] flex-col items-center justify-center rounded-2xl border border-dashed bg-card/40 text-center animate-step-in">
            <Loader2 className="h-7 w-7 animate-spin text-[#24415E]" />
            <p className="mt-4 text-sm font-medium text-foreground">
              {selected.status === 'queued' ? '任务排队中，等待调度…' : '任务执行中，资产生成后将自动出现'}
            </p>
            <p className="mt-1.5 text-xs text-muted-foreground">
              「{displayName(selected)}」· 实时进度请前往 Product Workspace 查看
            </p>
            <p className="mt-0.5 text-[11px] text-muted-foreground/70">
              页面每 15 秒自动刷新，完成后无需手动重载
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
