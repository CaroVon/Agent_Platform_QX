/**
 * KeywordsPage —— 关键词资产管理
 *
 * 后端：PUT /api/v1/product/{product_id}/keywords
 * Groups（固定 5 个）：design / function / appearance / audience / scenario
 */

import { useCallback, useEffect, useState } from 'react'
import { Loader2, PenLine, RefreshCw, Tags } from 'lucide-react'
import { WorkspaceHeader } from '@/components/WorkspaceHeader'
import { productApi } from '@/lib/api'
import type { StudioProduct } from '@/types/studio'
import { cn } from '@/lib/utils'
import { Button } from '@/components/common/button'
import { KeywordsEditor, KEYWORD_GROUPS } from '@/components/KeywordsEditor'

const COLOR_MAP: Record<string, string> = {
  design: 'border-primary/40 bg-primary/10 text-primary',
  function: 'border-accent/40 bg-accent/10 text-accent',
  appearance: 'border-warning/40 bg-warning/10 text-warning',
  audience: 'border-success/40 bg-success/10 text-success',
  scenario: 'border-muted-foreground/30 bg-muted text-muted-foreground',
}

function keywordCount(product: StudioProduct): number {
  return Object.values(product.keywords ?? {}).reduce(
    (sum, words) => sum + (words?.length ?? 0),
    0,
  )
}

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
      // 只保留已完成的任务（关键词在该状态下生成）
      const candidates = list.filter(
        (item) =>
          item.status === 'completed' || item.status === 'running' || item.status === 'queued',
      )
      // 拉取每个的详情（含 keywords）
      const details = await Promise.all(
        candidates.map((item) =>
          productApi.get(item.product_id).catch(() => null),
        ),
      )
      const merged = details.filter((item): item is StudioProduct => item !== null)
      setProducts(merged)
      setSelectedId((current) => {
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

  useEffect(() => {
    load()
  }, [load])

  const selected = products.find((item) => item.product_id === selectedId) ?? null

  return (
    <div>
      <WorkspaceHeader
        crumb="创作 · Keywords"
        title="关键词资产"
        description="按 Product Studio 任务管理设计、功能、外观、人群与场景关键词。修改后同步到任务资产库。"
      />

      <div className="mb-6 flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          共{' '}
          <span className="font-mono font-semibold text-foreground">
            {products.length}
          </span>{' '}
          个任务
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => load()}
          disabled={refreshing}
        >
          <RefreshCw
            className={cn('h-3.5 w-3.5', refreshing && 'animate-spin')}
          />
          刷新
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-24 font-mono text-[12px] uppercase tracking-[0.18em] text-muted-foreground">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          加载关键词
          <span className="typing-dot" />
          <span className="typing-dot" />
          <span className="typing-dot" />
        </div>
      ) : error ? (
        <div className="border border-destructive/40 bg-destructive/10 px-5 py-3 font-mono text-[12px] text-destructive">
          <span className="font-semibold">[ERROR]</span> {error}
        </div>
      ) : products.length === 0 ? (
        <div className="flex min-h-[360px] flex-col items-center justify-center rounded-lg border border-dashed border-border bg-card/40 text-center">
          <Tags className="h-8 w-8 text-muted-foreground/40" />
          <p className="mt-4 text-sm font-medium">暂无关键词资产</p>
          <p className="mt-1 max-w-md text-xs text-muted-foreground">
            Product Studio 任务完成后，AI 提取的关键词会自动出现在这里。
          </p>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
          {/* 左：任务列表 */}
          <aside className="space-y-1.5">
            {products.map((product) => {
              const count = keywordCount(product)
              const isActive = product.product_id === selectedId
              return (
                <button
                  key={product.product_id}
                  type="button"
                  onClick={() => setSelectedId(product.product_id)}
                  className={cn(
                    'flex w-full items-center gap-3 rounded-md px-3 py-3 text-left transition-colors',
                    isActive
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:bg-secondary hover:text-foreground',
                  )}
                >
                  <Tags className="h-4 w-4 shrink-0" />
                  <span className="min-w-0 flex-1 truncate text-sm">
                    {product.idea}
                  </span>
                  {count > 0 && (
                    <span className="font-mono text-[10px] text-primary">
                      {count}
                    </span>
                  )}
                </button>
              )
            })}
          </aside>

          {/* 右：选中任务的关键词 */}
          {selected && (
            <section className="rounded-lg border border-border bg-card p-6 shadow-elev-sm">
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-5">
                <div className="min-w-0">
                  <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                    Key Words · 项目资产
                  </div>
                  <h2 className="mt-1.5 font-display text-lg font-semibold tracking-tight text-foreground">
                    {selected.idea}
                  </h2>
                  <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                    共{' '}
                    <span className="font-semibold text-primary">
                      {keywordCount(selected)}
                    </span>{' '}
                    个关键词 · 保存后同步到项目资产库
                  </p>
                </div>
                <Button onClick={() => setEditing(true)}>
                  <PenLine className="h-3.5 w-3.5" />
                  编辑关键词
                </Button>
              </div>

              <div className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                {KEYWORD_GROUPS.map((g) => {
                  const words =
                    (selected.keywords?.[g.key] as string[] | undefined) ?? []
                  return (
                    <div
                      key={g.key}
                      className="rounded-md border border-border bg-background/40 p-4"
                    >
                      <div className="mb-3 flex items-center justify-between">
                        <span
                          className={cn(
                            'rounded-sm border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.14em]',
                            COLOR_MAP[g.key],
                          )}
                        >
                          {g.label}
                        </span>
                        <span className="font-mono text-[10px] uppercase text-muted-foreground">
                          {words.length}
                        </span>
                      </div>
                      {words.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {words.map((word, i) => (
                            <span
                              key={`${g.key}-${i}-${word}`}
                              className="rounded-full border border-white/15 bg-white/10 px-2.5 py-1 font-mono text-[12px] text-white"
                            >
                              {word}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-muted-foreground/60">
                          暂无关键词
                        </p>
                      )}
                    </div>
                  )
                })}
              </div>
            </section>
          )}
        </div>
      )}

      {editing && selected && (
        <KeywordsEditor
          product={selected}
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false)
            load()
          }}
        />
      )}
    </div>
  )
}