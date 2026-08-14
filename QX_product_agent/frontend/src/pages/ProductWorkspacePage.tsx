/**
 * ProductWorkspacePage —— AI Product Creation Canvas（frontedUI.md Phase 2）
 *
 * 不是 dashboard，是创作画布：
 *   Hero 想法输入 → AI 团队进度（时间线+工具）→ 生成资产 → 知识上下文
 */

import { useEffect, useRef, useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { ProjectHeader } from '@/components/workspace/ProjectHeader'
import { IdeaInput } from '@/components/workspace/IdeaInput'
import { AssetPanel } from '@/components/workspace/AssetPanel'
import { KnowledgePanel } from '@/components/workspace/KnowledgePanel'
import { AgentTimeline } from '@/components/ai/AgentTimeline'
import { ToolExecution } from '@/components/ai/ToolExecution'
import { StreamingMessage } from '@/components/ai/StreamingMessage'
import { productApi } from '@/lib/api'
import type { StudioProduct } from '@/types/studio'
import { cn } from '@/lib/utils'

function Section({
  step,
  title,
  children,
  className,
}: {
  step: string
  title: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <section className={cn('rounded-2xl border bg-card px-8 py-8', className)}>
      <div className="mb-6 flex items-baseline gap-4">
        <span className="font-editorial text-sm italic text-[#C87E4F]">{step}</span>
        <h2 className="text-base font-semibold tracking-tight">{title}</h2>
      </div>
      {children}
    </section>
  )
}

export function ProductWorkspacePage() {
  const [idea, setIdea] = useState('')
  const [creating, setCreating] = useState(false)
  const [product, setProduct] = useState<StudioProduct | null>(null)
  const [recent, setRecent] = useState<Array<{ product_id: string; idea: string; status: string }>>([])
  const [loadError, setLoadError] = useState('')
  const pollTimer = useRef<number | null>(null)

  const isActive = product !== null && (product.status === 'queued' || product.status === 'running')

  const loadRecent = async () => {
    try {
      setRecent(await productApi.list(0, 10))
    } catch {
      /* 非关键路径 */
    }
  }

  const loadProduct = async (id: string) => {
    try {
      setLoadError('')
      const p = await productApi.get(id)
      setProduct(p)
      try {
        localStorage.setItem('qx-current-project', p.idea)
      } catch {
        /* 忽略 */
      }
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : '加载失败')
    }
  }

  useEffect(() => {
    loadRecent()
  }, [])

  useEffect(() => {
    if (!product || !isActive) return
    pollTimer.current = window.setInterval(async () => {
      try {
        const fresh = await productApi.get(product.product_id)
        setProduct(fresh)
        if (fresh.status === 'completed' || fresh.status === 'failed') {
          if (pollTimer.current) window.clearInterval(pollTimer.current)
          loadRecent()
        }
      } catch {
        /* 单次失败继续轮询 */
      }
    }, 3000)
    return () => {
      if (pollTimer.current) window.clearInterval(pollTimer.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product?.product_id, isActive])

  const handleGenerate = async () => {
    const trimmed = idea.trim()
    if (!trimmed || creating) return
    setCreating(true)
    setLoadError('')
    try {
      const created = await productApi.create(trimmed)
      await loadProduct(created.product_id)
      loadRecent()
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : '创建失败')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="space-y-12">
      {/* ─── Hero / 项目头部 ─────────────────────────────────── */}
      {product ? (
        <ProjectHeader product={product} />
      ) : (
        <IdeaInput
          value={idea}
          onChange={setIdea}
          onSubmit={handleGenerate}
          creating={creating}
        />
      )}

      {loadError && (
        <div className="flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/5 px-5 py-3.5 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" /> {loadError}
        </div>
      )}

      {/* ─── 最近产品（无当前产品时引导） ────────────────────── */}
      {!product && recent.length > 0 && (
        <div className="flex flex-wrap items-center justify-center gap-2">
          <span className="text-xs text-muted-foreground">最近产品：</span>
          {recent.map((item) => (
            <button
              key={item.product_id}
              type="button"
              onClick={() => loadProduct(item.product_id)}
              className="rounded-full border bg-card px-3.5 py-1.5 text-xs text-muted-foreground transition-colors hover:border-[#24415E]/30 hover:text-foreground"
            >
              {item.idea} · {item.status}
            </button>
          ))}
        </div>
      )}

      {/* ─── AI Team Progress ──────────────────────────────── */}
      {product && (
        <>
          <Section step="01" title="AI Team Progress">
            <div className="grid gap-8 lg:grid-cols-[1fr_260px]">
              <AgentTimeline nodeStatus={product.node_status ?? {}} />
              <div className="border-l border-border/60 pl-6">
                <div className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60">
                  工具与检查
                </div>
                <ToolExecution nodeStatus={product.node_status ?? {}} />
              </div>
            </div>
          </Section>

          <StreamingMessage active={isActive} />

          {product.status === 'failed' && (
            <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-6 py-4 text-sm text-destructive">
              <p className="font-medium">流水线失败：{product.error_message ?? '未知错误'}</p>
              {Object.keys(product.errors ?? {}).length > 0 && (
                <ul className="mt-2 space-y-1 text-xs">
                  {Object.entries(product.errors).map(([node, err]) => (
                    <li key={node}>
                      <span className="font-medium">{node}</span>: {err}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* ─── Generated Assets ──────────────────────────── */}
          <Section step="02" title="Generated Product Assets">
            <AssetPanel product={product} />
          </Section>

          {/* ─── 新想法输入（紧凑模式） ──────────────────────── */}
          <Section step="03" title="New Idea">
            <div className="flex gap-3">
              <input
                type="text"
                value={idea}
                onChange={(e) => setIdea(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
                placeholder="输入下一个产品想法…"
                className="h-11 flex-1 rounded-lg border bg-background px-4 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <button
                type="button"
                onClick={handleGenerate}
                disabled={creating || !idea.trim()}
                className="h-11 rounded-lg bg-[#24415E] px-6 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
              >
                {creating ? '启动中…' : 'Generate'}
              </button>
            </div>
          </Section>
        </>
      )}

      {/* ─── Knowledge Context ──────────────────────────────── */}
      <Section step={product ? '04' : '02'} title="Knowledge Context">
        <KnowledgePanel />
      </Section>
    </div>
  )
}
