/**
 * ProductWorkspacePage —— AI Product Creation Canvas（frontedUI.md Phase 2）
 *
 * 不是 dashboard，是创作画布：
 *   Hero 想法输入 → AI 团队进度（时间线+工具）→ 生成资产 → 知识上下文
 */

import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { AlertCircle, Globe, Loader2, Upload } from 'lucide-react'
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
  const location = useLocation()
  const templateIdea = (location.state as { templateIdea?: string } | null)?.templateIdea
  const [idea, setIdea] = useState(templateIdea ?? '')
  const [creating, setCreating] = useState(false)
  const [product, setProduct] = useState<StudioProduct | null>(null)
  const [recent, setRecent] = useState<Array<{ product_id: string; idea: string; status: string }>>([])
  const [loadError, setLoadError] = useState('')
  const [eventLogs, setEventLogs] = useState<Array<{ ts: string; node: string; status: string; detail?: string }>>([])
  // ── 资料审核（source_gathering 门） ──
  const [sources, setSources] = useState<Array<{
    title: string
    url: string
    content?: string
    weight?: number
    weight_label?: string
    weight_detail?: string
    selected?: boolean
    local?: boolean
  }>>([])
  const [sourcesLoading, setSourcesLoading] = useState(false)
  const [uploadingSource, setUploadingSource] = useState(false)
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

  // 资料审核：进入 waiting_approval 且暂停于 source_gathering 时拉取资料列表
  const pausedNode = product?.status === 'waiting_approval'
    ? product.error_message?.replace('等待人工确认节点: ', '') ?? ''
    : ''
  useEffect(() => {
    if (product?.status !== 'waiting_approval' || pausedNode !== 'source_gathering') return
    let cancelled = false
    setSourcesLoading(true)
    productApi
      .getSources(product.product_id)
      .then((d) => {
        if (!cancelled) setSources(d.sources ?? [])
      })
      .catch(() => { /* 拉取失败保持空 */ })
      .finally(() => {
        if (!cancelled) setSourcesLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product?.product_id, product?.status, pausedNode])

  useEffect(() => {
    if (!product || !isActive) return
    pollTimer.current = window.setInterval(async () => {
      try {
        const fresh = await productApi.get(product.product_id)
        const prevStatus = product.status
        setProduct(fresh)
        productApi.logs(product.product_id).then((r) => setEventLogs(r.logs)).catch(() => {})
        if (fresh.status === 'completed' || fresh.status === 'failed') {
          if (pollTimer.current) window.clearInterval(pollTimer.current)
          loadRecent()
          // ── 完成通知（浏览器 Notification，需用户授权） ──
          if (prevStatus !== fresh.status && 'Notification' in window) {
            try {
              if (Notification.permission === 'granted') {
                new Notification(
                  fresh.status === 'completed' ? '✅ 产品资产已生成' : '❌ 产品生成失败',
                  {
                    body:
                      fresh.status === 'completed'
                        ? `「${fresh.idea}」的研究/PRD/设计/演示资产已就绪`
                        : `「${fresh.idea}」：${fresh.error_message || '请查看详情'}`,
                  },
                )
              } else if (Notification.permission === 'default') {
                Notification.requestPermission()
              }
            } catch {
              /* 通知不可用时静默 */
            }
          }
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

      {/* ─── 资料审核（source_gathering 门：搜索完成，用户勾选资料后继续） ── */}
      {product?.status === 'waiting_approval' && pausedNode === 'source_gathering' && (
        <div className="rounded-2xl border border-[#24415E]/15 bg-card p-6 shadow-sm">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <Globe className="h-4 w-4 text-[#24415E]" />
                资料审核
                <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                  {sources.length} 条资料
                </span>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                AI 已检索 {sources.length} 条资料并标注权重（研究报告类权重最高）。
                勾选需要保留的资料（默认全选），或上传本地资料补充；后续研究/PRD/设计将仅基于保留的资料，并强制标注来源。
              </p>
            </div>
            <div className="flex gap-2">
              <label
                className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-[#24415E]/25 px-3.5 py-2 text-xs font-medium text-[#24415E] transition-colors hover:bg-[#24415E]/5"
              >
                <Upload className="h-3.5 w-3.5" />
                {uploadingSource ? '上传中…' : '上传本地资料'}
                <input
                  type="file"
                  accept=".pdf,.txt,.md"
                  className="hidden"
                  disabled={uploadingSource}
                  onChange={async (e) => {
                    const file = e.target.files?.[0]
                    e.target.value = ''
                    if (!file || !product) return
                    setUploadingSource(true)
                    try {
                      const r = await productApi.uploadSource(product.product_id, file)
                      setSources((prev) => [...prev, r.source as typeof prev[number]])
                    } catch (err) {
                      setLoadError(err instanceof Error ? err.message : '上传失败')
                    } finally {
                      setUploadingSource(false)
                    }
                  }}
                />
              </label>
            </div>
          </div>

          {sourcesLoading ? (
            <div className="flex items-center justify-center py-10 text-xs text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 加载资料…
            </div>
          ) : (
            <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
              {sources.map((src, i) => {
                const checked = src.selected !== false
                return (
                  <label
                    key={`${src.url}-${i}`}
                    className="flex cursor-pointer items-start gap-3 rounded-xl border border-border/70 bg-background/60 px-4 py-3 transition-colors hover:border-[#24415E]/25"
                  >
                    <input
                      type="checkbox"
                      className="mt-0.5 h-4 w-4 shrink-0 accent-[#24415E]"
                      checked={checked}
                      onChange={(e) => {
                        setSources((prev) =>
                          prev.map((p, idx) => (idx === i ? { ...p, selected: e.target.checked } : p)),
                        )
                      }}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="truncate text-[13px] font-medium text-foreground">
                          [{i + 1}] {src.title}
                        </span>
                        {src.local && (
                          <span className="rounded-full bg-[#24415E]/10 px-2 py-px text-[10px] font-medium text-[#24415E]">
                            本地资料
                          </span>
                        )}
                      </div>
                      <div className="mt-0.5 truncate text-[11px] text-muted-foreground/80">{src.url}</div>
                      {src.content && (
                        <div className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground/70">
                          {src.content}
                        </div>
                      )}
                    </div>
                    <span
                      className={cn(
                        'shrink-0 rounded-full px-2.5 py-1 text-[10px] font-medium',
                        (src.weight ?? 0.5) >= 0.8 && 'bg-emerald-500/10 text-emerald-700',
                        (src.weight ?? 0.5) >= 0.6 && (src.weight ?? 0.5) < 0.8 && 'bg-sky-500/10 text-sky-700',
                        (src.weight ?? 0.5) >= 0.45 && (src.weight ?? 0.5) < 0.6 && 'bg-amber-500/10 text-amber-700',
                        (src.weight ?? 0.5) < 0.45 && 'bg-gray-400/10 text-gray-500',
                      )}
                      title={src.weight_detail ?? ''}
                    >
                      权重 {src.weight_label ?? '中'}
                    </span>
                  </label>
                )
              })}
              {sources.length === 0 && !sourcesLoading && (
                <div className="rounded-xl border border-dashed py-8 text-center text-xs text-muted-foreground">
                  暂无资料 —— 可上传本地资料后继续
                </div>
              )}
            </div>
          )}

          <div className="mt-4 flex items-center justify-between gap-3 border-t border-border/60 pt-4">
            <p className="text-[11px] text-muted-foreground">
              已选 {sources.filter((s) => s.selected !== false).length}/{sources.length} 条
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={async () => {
                  try {
                    await productApi.rejectNode(product.product_id, 'source_gathering')
                    await loadProduct(product.product_id)
                  } catch (err) {
                    setLoadError(err instanceof Error ? err.message : '操作失败')
                  }
                }}
                className="rounded-lg border border-red-400/50 px-4 py-2 text-xs font-medium text-red-600 transition-colors hover:bg-red-50"
              >
                放弃并终止
              </button>
              <button
                type="button"
                disabled={sources.filter((s) => s.selected !== false).length === 0}
                onClick={async () => {
                  try {
                    const selected = sources
                      .filter((s) => s.selected !== false)
                      .map((s) => s.url)
                    await productApi.approveNode(product.product_id, 'source_gathering', selected)
                    await loadProduct(product.product_id)
                  } catch (err) {
                    setLoadError(err instanceof Error ? err.message : '提交失败')
                  }
                }}
                className="rounded-lg bg-[#24415E] px-5 py-2 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
              >
                确认资料，继续生成 →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── 节点级 Plan/Act 门（其他节点等待人工批准） ────────── */}
      {product?.status === 'waiting_approval' && pausedNode !== 'source_gathering' && (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-50/60 p-6 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold text-amber-800">
                <AlertCircle className="h-4 w-4" />
                人工确认节点
              </div>
              <p className="mt-1 text-xs text-amber-700/80">
                流水线已暂停：请审阅「{pausedNode}」节点的产出后决定继续或终止。
              </p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={async () => {
                  try {
                    await productApi.approveNode(product.product_id, pausedNode)
                    await loadProduct(product.product_id)
                  } catch (err) {
                    setLoadError(err instanceof Error ? err.message : '批准失败')
                  }
                }}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-medium text-white transition-opacity hover:opacity-90"
              >
                批准并继续
              </button>
              <button
                type="button"
                onClick={async () => {
                  try {
                    await productApi.rejectNode(product.product_id, pausedNode)
                    await loadProduct(product.product_id)
                  } catch (err) {
                    setLoadError(err instanceof Error ? err.message : '拒绝失败')
                  }
                }}
                className="rounded-lg border border-red-400/50 px-4 py-2 text-xs font-medium text-red-600 transition-colors hover:bg-red-50"
              >
                拒绝并终止
              </button>
            </div>
          </div>
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
              <AgentTimeline
                nodeStatus={product.node_status ?? {}}
                nodeModels={product.node_models ?? {}}
                productStatus={product.status}
                logs={eventLogs}
              />
              <div className="border-l border-border/60 pl-6">
                <div className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60">
                  工具与检查
                </div>
                <ToolExecution nodeStatus={product.node_status ?? {}} />
              </div>
            </div>
          </Section>

          <StreamingMessage
            active={isActive}
            latestEvent={eventLogs.length > 0 ? eventLogs[eventLogs.length - 1] : undefined}
          />

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
            <AssetPanel
              product={product}
              onRefresh={() => product && loadProduct(product.product_id)}
            />
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
