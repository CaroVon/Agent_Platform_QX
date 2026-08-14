/**
 * ProductAssetBrowser —— 资产聚合页通用骨架
 *
 * 左侧：已完成产品列表（含资产概览徽标）
 * 右侧：选中产品的资产详情（由各模块页提供 renderDetail）
 */

import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { Boxes, ChevronRight, Loader2 } from 'lucide-react'
import { productApi } from '@/lib/api'
import type { StudioProduct } from '@/types/studio'
import { cn } from '@/lib/utils'

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

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const list = await productApi.list(0, 100)
        const completed = (await Promise.all(
          list
            .filter((i) => i.status === 'completed')
            .map((i) => productApi.get(i.product_id).catch(() => null)),
        )).filter((p): p is StudioProduct => p !== null)
        if (cancelled) return
        setProducts(completed)
        const requested = (location.state as { productId?: string } | null)?.productId
        setSelectedId(
          requested && completed.some((p) => p.product_id === requested)
            ? requested
            : completed[0]?.product_id ?? null,
        )
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [location.state])

  const selected = products.find((p) => p.product_id === selectedId) ?? null

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
    <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
      {/* ─── 产品列表 ─────────────────────────────────────────── */}
      <aside className="space-y-1.5">
        <div className="px-2 pb-2 text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
          已完成产品（{products.length}）
        </div>
        {products.map((p) => {
          const active = p.product_id === selectedId
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
              <span className="min-w-0 flex-1 truncate">{p.idea}</span>
              {p.critic_score != null && (
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
      <div className="min-w-0 space-y-5">{selected ? renderDetail(selected) : null}</div>
    </div>
  )
}
