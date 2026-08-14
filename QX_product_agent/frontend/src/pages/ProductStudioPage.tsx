/**
 * ProductStudioPage —— AI Product Studio（多 Agent 产品工作台）
 *
 * 体验流:
 *   输入产品想法 → Generate → 七节点流水线进度 → 结构化输出工作区
 *
 * 输出工作区由可复用渲染组件（MarketCard / CompetitorMatrix /
 * PersonaCard / FeatureMatrix / RoadmapTimeline / PRDViewer /
 * SlideRenderer）渲染结构化 JSON —— 无 LLM 生成的 HTML/CSS。
 */

import { useEffect, useRef, useState } from 'react'
import {
  AlertCircle,
  Check,
  ChevronRight,
  Loader2,
  Rocket,
  Sparkles,
} from 'lucide-react'
import { Button } from '@/components/common/button'
import { productApi } from '@/lib/api'
import type { StudioProduct } from '@/types/studio'
import { MarketCard } from '@/components/MarketCard'
import { CompetitorMatrix } from '@/components/CompetitorMatrix'
import { PersonaCard } from '@/components/PersonaCard'
import { FeatureMatrix } from '@/components/FeatureMatrix'
import { RoadmapTimeline } from '@/components/RoadmapTimeline'
import { PRDViewer } from '@/components/PRDViewer'
import { SlideRenderer } from '@/components/SlideRenderer'
import { PresentationViewer } from '@/components/presentation/PresentationViewer'
import type { PresentationDSL } from '@/types/presentation'
import type { SlideDeck } from '@/types/studio'
import { cn } from '@/lib/utils'

const PIPELINE_STEPS = [
  { key: 'requirement_parser', label: '需求解析' },
  { key: 'research', label: '市场研究' },
  { key: 'competitor_analysis', label: '竞品分析' },
  { key: 'strategy', label: '用户画像与产品策略' },
  { key: 'design', label: 'UX 设计' },
  { key: 'presentation', label: '演示生成' },
  { key: 'critic', label: '质量评审（Critic）' },
  { key: 'assemble', label: '资产打包' },
] as const

function StepIcon({ status }: { status?: string }) {
  if (status === 'completed') {
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 text-white">
        <Check className="h-3 w-3" />
      </span>
    )
  }
  if (status === 'running') {
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
      </span>
    )
  }
  if (status === 'failed') {
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-destructive text-white">
        <AlertCircle className="h-3 w-3" />
      </span>
    )
  }
  return <span className="h-5 w-5 rounded-full border-2 border-border" />
}

export function ProductStudioPage() {
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
      /* 列表加载失败静默（非关键路径） */
    }
  }

  const loadProduct = async (productId: string) => {
    try {
      setLoadError('')
      setProduct(await productApi.get(productId))
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : '加载失败')
    }
  }

  // ─── 轮询流水线进度（queued/running 时 3 秒间隔） ──────────
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
        /* 单次轮询失败保持原有状态，下轮继续 */
      }
    }, 3000)
    return () => {
      if (pollTimer.current) window.clearInterval(pollTimer.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product?.product_id, isActive])

  useEffect(() => {
    loadRecent()
  }, [])

  const handleGenerate = async () => {
    const trimmed = idea.trim()
    if (!trimmed || creating) return
    setCreating(true)
    setLoadError('')
    try {
      const created = await productApi.create(trimmed)
      setProduct(await productApi.get(created.product_id))
      loadRecent()
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : '创建失败')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* ─── 页面头部 ─────────────────────────────────────── */}
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
          <Sparkles className="h-5 w-5 text-primary" />
          AI Product Studio
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          多 Agent 产品工作台：研究 → 竞品 → 策略 → 设计 → 演示，全结构化输出。
        </p>
      </div>

      {/* ─── 创建产品 ─────────────────────────────────────── */}
      <div className="rounded-xl border bg-card p-5 shadow-sm">
        <label htmlFor="studio-idea" className="text-sm font-semibold">
          创建产品
        </label>
        <div className="mt-3 flex gap-3">
          <input
            id="studio-idea"
            type="text"
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
            placeholder='例如: "Build an AI fitness application"'
            className="h-10 flex-1 rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <Button onClick={handleGenerate} disabled={creating || !idea.trim()}>
            {creating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Rocket className="mr-2 h-4 w-4" />}
            Generate
          </Button>
        </div>
        {loadError && (
          <p className="mt-3 flex items-center gap-1.5 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" /> {loadError}
          </p>
        )}

        {/* 历史产品（可重新打开已完成资产包） */}
        {recent.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2 border-t pt-4">
            {recent.map((item) => (
              <button
                key={item.product_id}
                type="button"
                onClick={() => loadProduct(item.product_id)}
                className={cn(
                  'flex items-center gap-1.5 rounded-full border bg-background px-3 py-1.5 text-xs transition-colors hover:bg-accent',
                  product?.product_id === item.product_id && 'border-primary/50 bg-primary/5',
                )}
              >
                {item.idea}
                <span className="text-muted-foreground">· {item.status}</span>
                <ChevronRight className="h-3 w-3 text-muted-foreground" />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ─── 进度：流水线七节点 ───────────────────────────── */}
      {product && (
        <div className="rounded-xl border bg-card p-5 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold">Progress</h2>
          <ol className="flex flex-wrap gap-x-6 gap-y-3">
            {PIPELINE_STEPS.map((step) => {
              const status = product.node_status?.[step.key]
              return (
                <li key={step.key} className="flex items-center gap-2 text-sm">
                  <StepIcon status={status} />
                  <span
                    className={cn(
                      status === 'failed' && 'text-destructive',
                      status === 'completed' && 'text-foreground',
                      status !== 'completed' && status !== 'failed' && 'text-muted-foreground',
                    )}
                  >
                    {step.label}
                  </span>
                </li>
              )
            })}
          </ol>

          {product.status === 'failed' && (
            <div className="mt-4 rounded-lg bg-destructive/10 p-4 text-sm text-destructive">
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
        </div>
      )}

      {/* ─── 输出工作区：结构化资产包 ─────────────────────── */}
      {product?.status === 'completed' && (
        <div className="space-y-5">
          <h2 className="text-sm font-semibold text-muted-foreground">Output Workspace</h2>

          {product.research && <MarketCard research={product.research} />}

          {product.competitor_analysis && (
            <CompetitorMatrix analysis={product.competitor_analysis} />
          )}

          {product.strategy && product.strategy.personas.length > 0 && (
            <div className="rounded-xl border bg-card p-5 shadow-sm">
              <h3 className="mb-4 text-sm font-semibold">用户画像</h3>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {product.strategy.personas.map((persona) => (
                  <PersonaCard key={persona.name} persona={persona} />
                ))}
              </div>
            </div>
          )}

          {product.strategy && product.strategy.features.length > 0 && (
            <FeatureMatrix features={product.strategy.features} />
          )}

          {product.strategy && product.strategy.roadmap.length > 0 && (
            <RoadmapTimeline roadmap={product.strategy.roadmap} />
          )}

          {product.strategy && product.strategy.prd_sections.length > 0 && (
            <PRDViewer sections={product.strategy.prd_sections} />
          )}

          {product.presentation && (
            Array.isArray((product.presentation as PresentationDSL).pages) ? (
              <PresentationViewer
                presentation={product.presentation as PresentationDSL}
                productId={product.product_id}
                qualityGate={product.gate_report ?? null}
              />
            ) : (
              // 旧版资产包（P2 前）兼容
              <SlideRenderer
                deck={product.presentation as SlideDeck}
                productId={product.product_id}
              />
            )
          )}
        </div>
      )}
    </div>
  )
}
