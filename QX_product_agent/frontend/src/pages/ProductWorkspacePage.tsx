/**
 * ProductWorkspacePage —— Product Workspace（四段式主工作区）
 *
 * 结构（productize 要求）:
 *   1. Project Information  产品想法输入 + 生成入口 + 最近产品
 *   2. Agent Workflow       八节点流水线进度（含 Critic 评审）
 *   3. Generated Assets     四大资产卡（研究/PRD/设计/演示）
 *   4. Related Knowledge    文件上传 + 图片搜索（绑定既有研究项目）
 */

import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertCircle,
  Check,
  FileText,
  FlaskConical,
  Loader2,
  MonitorPlay,
  PenTool,
  Rocket,
} from 'lucide-react'
import { Button } from '@/components/common/button'
import { WorkspaceHeader } from '@/components/WorkspaceHeader'
import { AssetCard } from '@/components/AssetCard'
import { FileUploader } from '@/components/FileUploader'
import { ImageSearch } from '@/components/ImageSearch'
import { productApi, projectsApi } from '@/lib/api'
import type { StudioProduct } from '@/types/studio'
import type { ProjectResponse } from '@/types/api'
import { cn } from '@/lib/utils'

const PIPELINE_STEPS = [
  { key: 'requirement_parser', label: '需求解析' },
  { key: 'research', label: '市场研究' },
  { key: 'competitor_analysis', label: '竞品分析' },
  { key: 'strategy', label: '产品策略' },
  { key: 'design', label: 'UX 设计' },
  { key: 'presentation', label: '演示生成' },
  { key: 'critic', label: '质量评审' },
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

function Section({
  step,
  title,
  description,
  children,
}: {
  step: string
  title: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <section className="rounded-2xl border bg-card p-7 shadow-sm">
      <div className="mb-5 flex items-baseline gap-3">
        <span className="text-xs font-semibold uppercase tracking-widest text-primary/70">
          {step}
        </span>
        <h2 className="text-base font-semibold">{title}</h2>
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
      </div>
      {children}
    </section>
  )
}

export function ProductWorkspacePage() {
  const navigate = useNavigate()
  const [idea, setIdea] = useState('')
  const [creating, setCreating] = useState(false)
  const [product, setProduct] = useState<StudioProduct | null>(null)
  const [recent, setRecent] = useState<Array<{ product_id: string; idea: string; status: string }>>([])
  const [projects, setProjects] = useState<ProjectResponse[]>([])
  const [projectId, setProjectId] = useState('')
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

  const loadProjects = async () => {
    try {
      const list = await projectsApi.list(0, 50)
      setProjects(list)
      if (!projectId && list.length > 0) setProjectId(list[0].id)
    } catch {
      /* 非关键路径 */
    }
  }

  const loadProduct = async (id: string) => {
    try {
      setLoadError('')
      setProduct(await productApi.get(id))
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : '加载失败')
    }
  }

  useEffect(() => {
    loadRecent()
    loadProjects()
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
      setProduct(await productApi.get(created.product_id))
      loadRecent()
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : '创建失败')
    } finally {
      setCreating(false)
    }
  }

  const completed = product?.status === 'completed'
  const assetNav = (path: string) => navigate(path, { state: { productId: product?.product_id } })

  return (
    <div className="space-y-8">
      <WorkspaceHeader
        crumb="工作台"
        title="Product Workspace"
        description="输入产品想法，多 Agent 流水线自动产出市场研究、PRD、设计方案与演示资产。"
        actions={
          product ? (
            <span
              className={cn(
                'rounded-full px-3 py-1 text-xs font-medium',
                product.status === 'completed' && 'bg-emerald-500/10 text-emerald-600',
                product.status === 'failed' && 'bg-destructive/10 text-destructive',
                (product.status === 'running' || product.status === 'queued') &&
                  'bg-primary/10 text-primary',
              )}
            >
              {product.idea} · {product.status}
            </span>
          ) : undefined
        }
      />

      {/* ─── 1. Project Information ─────────────────────────── */}
      <Section
        step="01"
        title="Project Information"
        description="产品想法 → 多 Agent 流水线"
      >
        <div className="flex gap-3">
          <input
            type="text"
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
            placeholder='输入产品想法，例如: "Build an AI fitness application"'
            className="h-11 flex-1 rounded-lg border border-input bg-background px-4 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <Button size="lg" onClick={handleGenerate} disabled={creating || !idea.trim()}>
            {creating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Rocket className="mr-2 h-4 w-4" />}
            Generate
          </Button>
        </div>
        {loadError && (
          <p className="mt-3 flex items-center gap-1.5 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" /> {loadError}
          </p>
        )}
        {recent.length > 0 && (
          <div className="mt-5 flex flex-wrap items-center gap-2 border-t pt-4">
            <span className="text-xs text-muted-foreground">最近产品：</span>
            {recent.map((item) => (
              <button
                key={item.product_id}
                type="button"
                onClick={() => loadProduct(item.product_id)}
                className={cn(
                  'rounded-full border bg-background px-3 py-1.5 text-xs transition-colors hover:bg-accent',
                  product?.product_id === item.product_id && 'border-primary/50 bg-primary/5',
                )}
              >
                {item.idea} · {item.status}
              </button>
            ))}
          </div>
        )}
      </Section>

      {/* ─── 2. Agent Workflow ──────────────────────────────── */}
      {product && (
        <Section
          step="02"
          title="Agent Workflow"
          description={
            product.critic_score != null
              ? `Critic 评分 ${product.critic_score}/100`
              : '八节点流水线'
          }
        >
          <ol className="flex flex-wrap gap-x-7 gap-y-3">
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
        </Section>
      )}

      {/* ─── 3. Generated Assets ────────────────────────────── */}
      <Section
        step="03"
        title="Generated Assets"
        description="结构化资产包：研究与策略 → PRD → 设计 → 演示"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <AssetCard
            icon={FlaskConical}
            title="Research Report"
            description="市场研究、竞品矩阵与行业洞察"
            status={completed && product.research ? 'ready' : isActive ? 'running' : 'empty'}
            onClick={completed ? () => assetNav('/research') : undefined}
          />
          <AssetCard
            icon={FileText}
            title="PRD"
            description="产品定位、功能清单、路线图与 PRD 章节"
            status={completed && product.strategy ? 'ready' : isActive ? 'running' : 'empty'}
            onClick={completed ? () => assetNav('/prd') : undefined}
          />
          <AssetCard
            icon={PenTool}
            title="Design Proposal"
            description="用户旅程、信息架构与 UI 组件规格"
            status={completed && product.design ? 'ready' : isActive ? 'running' : 'empty'}
            onClick={completed ? () => assetNav('/design') : undefined}
          />
          <AssetCard
            icon={MonitorPlay}
            title="Presentation"
            description="Slide JSON 演示（Web / PDF / PPTX）"
            status={completed && product.presentation ? 'ready' : isActive ? 'running' : 'empty'}
            onClick={completed ? () => assetNav('/presentation') : undefined}
          />
        </div>
      </Section>

      {/* ─── 4. Related Knowledge ───────────────────────────── */}
      <Section
        step="04"
        title="Related Knowledge"
        description="上传参考资料与视觉素材，绑定到研究项目（RAG 检索上下文）"
      >
        <div className="mb-4 flex items-center gap-3">
          <label htmlFor="knowledge-project" className="shrink-0 text-xs font-medium text-muted-foreground">
            研究项目
          </label>
          <select
            id="knowledge-project"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            className="h-10 w-full max-w-md rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {projects.length === 0 && <option value="">（暂无研究项目）</option>}
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.topic}
              </option>
            ))}
          </select>
        </div>
        {projectId ? (
          <div className="grid gap-6 lg:grid-cols-2">
            <div>
              <h3 className="mb-3 text-sm font-medium">文件上传</h3>
              <FileUploader projectId={projectId} />
            </div>
            <div>
              <h3 className="mb-3 text-sm font-medium">图片搜索</h3>
              <ImageSearch projectId={projectId} />
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            暂无研究项目。可在 <span className="font-medium">控制台</span>（/）先创建一个研究项目，
            或直接在上方输入产品想法启动 Product Studio 流水线。
          </p>
        )}
      </Section>
    </div>
  )
}
