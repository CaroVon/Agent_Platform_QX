/** Product Studio 一级 Keywords 资产管理页。 */

import { useCallback, useEffect, useState } from 'react'
import { Loader2, PenLine, RefreshCw, Tags } from 'lucide-react'
import { KeywordsEditor } from '@/components/KeywordsEditor'
import { WorkspaceHeader } from '@/components/WorkspaceHeader'
import { productApi } from '@/lib/api'
import { KEYWORD_GROUP_LABELS, type StudioProduct } from '@/types/studio'

const GROUP_COLORS: Record<string, string> = {
  design: 'bg-sky-500/10 text-sky-700 border-sky-500/20',
  function: 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20',
  appearance: 'bg-violet-500/10 text-violet-700 border-violet-500/20',
  audience: 'bg-amber-500/10 text-amber-700 border-amber-500/20',
  scenario: 'bg-rose-500/10 text-rose-700 border-rose-500/20',
}

const countKeywords = (product: StudioProduct) =>
  Object.values(product.keywords ?? {}).reduce((sum, words) => sum + words.length, 0)

export function KeywordsPage() {
  const [products, setProducts] = useState<StudioProduct[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setRefreshing(true)
    try {
      setError('')
      const list = await productApi.list(0, 100)
      const details = await Promise.all(
        list.filter((item) => item.status === 'completed')
          .map((item) => productApi.get(item.product_id).catch(() => null)),
      )
      const merged = details.filter((item): item is StudioProduct => item !== null)
      setProducts(merged)
      setSelectedId((current) => {
        const requested = new URLSearchParams(window.location.search).get('product_id')
        if (requested && merged.some((item) => item.product_id === requested)) return requested
        if (current && merged.some((item) => item.product_id === current)) return current
        return merged[0]?.product_id ?? ''
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载 Keywords 失败')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const selected = products.find((item) => item.product_id === selectedId) ?? null

  return (
    <div>
      <WorkspaceHeader
        crumb="创作 · Keywords"
        title="Keywords"
        description="按 Product Studio 任务管理设计、功能、外观、人群与场景关键词，并作为项目资产归档。"
      />
      <div className="mb-6 flex items-center justify-between">
        <div className="text-sm text-muted-foreground">共 <span className="font-semibold text-foreground">{products.length}</span> 个任务</div>
        <button type="button" onClick={() => load()} disabled={refreshing}
          className="flex items-center gap-2 rounded-lg border bg-card px-4 py-2 text-xs font-medium text-muted-foreground hover:text-foreground disabled:opacity-50">
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} /> 刷新
        </button>
      </div>
      {loading ? (
        <div className="flex items-center justify-center py-24 text-muted-foreground"><Loader2 className="mr-2 h-5 w-5 animate-spin" /> 加载 Keywords…</div>
      ) : error ? (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-5 py-3 text-sm text-destructive">{error}</div>
      ) : products.length === 0 ? (
        <div className="flex min-h-[360px] flex-col items-center justify-center rounded-2xl border border-dashed bg-card/40 text-center">
          <Tags className="h-8 w-8 text-muted-foreground/40" /><p className="mt-4 text-sm font-medium">暂无已完成任务</p>
          <p className="mt-1 text-xs text-muted-foreground">Product Studio 任务完成后，AI 关键词会自动出现在这里。</p>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
          <aside className="space-y-1.5">
            {products.map((product) => (
              <button key={product.product_id} type="button" onClick={() => setSelectedId(product.product_id)}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left transition-colors ${product.product_id === selectedId ? 'bg-secondary text-foreground' : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'}`}>
                <Tags className="h-4 w-4 shrink-0" /><span className="min-w-0 flex-1 truncate text-sm">{product.idea}</span>
                <span className="shrink-0 rounded-full bg-background px-2 py-0.5 text-[10px]">{countKeywords(product)}</span>
              </button>
            ))}
          </aside>
          {selected && (
            <section className="rounded-2xl border bg-card p-6 shadow-sm">
              <div className="flex items-start justify-between gap-4 border-b pb-5">
                <div className="min-w-0"><div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">Key Words · 项目资产</div>
                  <h2 className="mt-2 text-lg font-semibold">{selected.idea}</h2>
                  <p className="mt-1 text-xs text-muted-foreground">{countKeywords(selected)} 个关键词，保存后同步进入该任务项目资产库。</p>
                </div>
                <button type="button" onClick={() => setEditing(true)} className="flex shrink-0 items-center gap-1.5 rounded-lg bg-[#24415E] px-4 py-2 text-xs font-medium text-white hover:opacity-90"><PenLine className="h-3.5 w-3.5" /> 编辑关键词</button>
              </div>
              <div className="mt-6 grid gap-5 sm:grid-cols-2">
                {Object.entries(KEYWORD_GROUP_LABELS).map(([key, label]) => {
                  const words = selected.keywords?.[key] ?? []
                  return <div key={key} className="rounded-xl border bg-background/50 p-4"><div className="mb-3 flex items-center justify-between"><span className="text-sm font-medium">{label}</span><span className="text-[10px] text-muted-foreground">{words.length} 个</span></div>{words.length ? <div className="flex flex-wrap gap-1.5">{words.map((word) => <span key={word} className={`rounded-full border px-2.5 py-1 text-[11px] ${GROUP_COLORS[key]}`}>{word}</span>)}</div> : <p className="text-xs text-muted-foreground/60">暂无关键词</p>}</div>
                })}
              </div>
            </section>
          )}
        </div>
      )}
      {editing && selected && <KeywordsEditor product={selected} onClose={() => setEditing(false)} onSaved={() => { setEditing(false); load() }} />}
    </div>
  )
}
