/**
 * MemoryPage —— 记忆图谱（P4）
 *
 * 知识关系图可视化：全局/项目记忆切换、实体搜索聚焦、类型筛选、
 * 实体详情侧栏、洞察面板、手动重建。
 * 视觉规范详见 docs/memory-graph-visual-design.md
 */

import { useEffect, useMemo, useState } from 'react'
import {
  Download,
  Filter,
  Loader2,
  Network,
  RefreshCw,
  Search,
} from 'lucide-react'
import { WorkspaceHeader } from '@/components/WorkspaceHeader'
import { GraphCanvas } from '@/components/graph/GraphCanvas'
import { GraphSidebar } from '@/components/graph/GraphSidebar'
import { useGraphData } from '@/components/graph/useGraphData'
import { productApi, projectsApi, memoryApi } from '@/lib/api'
import type { MemoryEntityType, ProjectResponse } from '@/types/api'

const TYP_PTINS: { key: MemoryEntityType; label: string }[] = [
  { key: 'company', label: '公司' },
  { key: 'product', label: '产品' },
  { key: 'technology', label: '技术' },
  { key: 'person', label: '人物' },
  { key: 'market', label: '市场' },
  { key: 'metric', label: '指标' },
  { key: 'other', label: '其他' },
]

export function MemoryPage() {
  const { filter, patchFilter, data, loading, error, refresh, rebuild, rebuilding } = useGraphData()
  const [projects, setProjects] = useState<ProjectResponse[]>([])
  const [studioProducts, setStudioProducts] = useState<Array<{ product_id: string; idea: string; status: string }>>([])
  const [selectedntityId, setSelectedntityId] = useState<string | null>(null)
  const [insights, setInsights] = useState<{ id: string; content: string; source: string }[]>([])
  const [insightsLoading, setInsightsLoading] = useState(false)

  useEffect(() => {
    Promise.all([
      projectsApi.list(0, 100).catch(() => []),
      productApi.list(0, 100).catch(() => []),
    ]).then(([legacyProjects, products]) => {
      setProjects(legacyProjects)
      setStudioProducts(products)
    })
  }, [])

  // 项目选择：默认第一个
  useEffect(() => {
    if (filter.scope === 'project' && !filter.projectId) {
      if (projects.length > 0) patchFilter({ projectId: projects[0].id })
      else if (studioProducts.length > 0) patchFilter({ projectId: `studio:${studioProducts[0].product_id}` })
    }
  }, [filter.scope, filter.projectId, projects, studioProducts, patchFilter])

  // 洞察面板
  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setInsightsLoading(true)
      try {
        const isStudio = filter.projectId.startsWith('studio:')
        const resp = await memoryApi.insights({
          scope: filter.scope,
          projectId: filter.scope === 'project' && !isStudio ? filter.projectId || undefined : undefined,
          studioProductId: filter.scope === 'project' && isStudio ? filter.projectId.slice('studio:'.length) : undefined,
        })
        if (!cancelled) setInsights(resp.insights)
      } catch {
        if (!cancelled) setInsights([])
      } finally {
        if (!cancelled) setInsightsLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [filter.scope, filter.projectId])

  const toggleType = (key: MemoryEntityType) => {
    const next = filter.entityTypes.includes(key)
      ? filter.entityTypes.filter((t) => t !== key)
      : [...filter.entityTypes, key]
    patchFilter({ entityTypes: next })
  }

  const handlexportPng = () => {
    // GraphCanvas 暴露导出需持有实例；此处通过 DM 触发（简化：提示使用浏览器截图）
    const canvas = document.querySelector('#memory-graph-canvas canvas')
    if (canvas instanceof HTMLCanvasElement) {
      const a = document.createElement('a')
      a.href = canvas.toDataURL('image/png')
      a.download = `memory-graph-${filter.scope}-${Date.now()}.png`
      a.click()
    }
  }

  const stats = useMemo(() => {
    if (!data) return null
    const globalCount = data.nodes.filter((n) => n.scope === 'global').length
    return {
      entities: data.meta.entity_count,
      relations: data.meta.relation_count,
      globalCount,
      projects: data.meta.projects_covered + (data.meta.studio_products_covered ?? 0),
    }
  }, [data])

  return (
    <div>
      <WorkspaceHeader
        crumb="管理 · 记忆"
        title="Memory Graph"
        description="每次任务自动沉淀实体·关系·洞察 —— 全局记忆跨项目复用，项目记忆专属本任务。"
      />

      {/* ─── 工具栏 ─────────────────────────────────────────── */}
      <div className="mb-5 flex flex-wrap items-center gap-3 rounded-md border bg-card px-5 py-3.5 shadow-sm">
        {/* scope 切换 */}
        <div className="flex items-center gap-1 rounded-md bg-secondary/60 p-1">
          {(['global', 'project'] as const).map((scope) => (
            <button
              key={scope}
              type="button"
              onClick={() => patchFilter({ scope })}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                filter.scope === scope
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {scope === 'global' ? '🌐 全局记忆' : '📁 项目记忆'}
            </button>
          ))}
        </div>

        {/* 项目选择（项目模式） */}
        {filter.scope === 'project' && (
          <select
            value={filter.projectId}
            onChange={(e) => patchFilter({ projectId: e.target.value })}
            className="h-9 rounded-md border border-input bg-background px-3 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {projects.length === 0 && studioProducts.length === 0 && <option value="">（暂无任务）</option>}
            {projects.length > 0 && (
              <optgroup label="研究项目">
                {projects.map((p) => <option key={p.id} value={p.id}>{p.topic}</option>)}
              </optgroup>
            )}
            {studioProducts.length > 0 && (
              <optgroup label="Product Studio 任务">
                {studioProducts.map((p) => (
                  <option key={p.product_id} value={`studio:${p.product_id}`}>
                    {p.idea}
                  </option>
                ))}
              </optgroup>
            )}
          </select>
        )}

        {/* 搜索 */}
        <div className="relative min-w-52 flex-1">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            value={filter.q}
            onChange={(e) => patchFilter({ q: e.target.value })}
            onKeyDown={(e) => e.key === 'Enter' && refresh()}
            placeholder="搜索实体（回车聚焦其邻域）…"
            className="h-9 w-full rounded-md border border-input bg-background pl-9 pr-3 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>

        {/* 类型筛选 */}
        <div className="flex items-center gap-1.5">
          <Filter className="h-3.5 w-3.5 text-muted-foreground" />
          {TYP_PTINS.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => toggleType(t.key)}
              title={t.label}
              className={`rounded-md px-2 py-1 text-sm transition-colors ${
                filter.entityTypes.includes(t.key)
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-muted-foreground hover:text-foreground'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* 操作 */}
        <div className="flex items-center gap-1.5">
          {filter.scope === 'project' && filter.projectId && (
            <button
              type="button"
              onClick={() => rebuild(filter.projectId)}
              disabled={rebuilding}
              className="flex items-center gap-1.5 rounded-md bg-secondary px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
              title="重新抽取该项目的记忆（异步）"
            >
              {rebuilding ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
              重建
            </button>
          )}
          <button
            type="button"
            onClick={refresh}
            className="rounded-md bg-secondary px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
            title="刷新图谱"
          >
            刷新
          </button>
          <button
            type="button"
            onClick={handlexportPng}
            className="flex items-center gap-1.5 rounded-md bg-secondary px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
            title="导出 PNG（可放入报告）"
          >
            <Download className="h-3.5 w-3.5" />
            导出
          </button>
        </div>
      </div>

      {/* ─── 统计条 ─────────────────────────────────────────── */}
      {stats && (
        <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            { label: '实体', value: stats.entities, icon: '🔵' },
            { label: '关系', value: stats.relations, icon: '🔗' },
            {
              label: filter.scope === 'global' ? '全局实体' : '本项目记忆',
              value: filter.scope === 'global' ? stats.globalCount : stats.entities,
              icon: '🌐',
            },
            { label: '覆盖项目', value: stats.projects, icon: '📁' },
          ].map((s) => (
            <div key={s.label} className="rounded-md border bg-card px-4 py-3 shadow-sm">
              <div className="text-lg font-semibold">
                {s.icon} {s.value}
              </div>
              <div className="text-sm text-muted-foreground">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* ─── 画布 + 侧栏 ────────────────────────────────────── */}
      <div className="flex gap-5">
        <div
          id="memory-graph-canvas"
          className="relative flex-1 overflow-hidden rounded-md border bg-[hsl(var(--graph-bg))] shadow-sm"
          style={{ minHeight: 560 }}
        >
          {error && <div className="absolute inset-0 z-10 flex items-center justify-center text-sm text-destructive">{error}</div>}

          {/* 空状态引导条：全局空 → 去项目视图；项目空 → 提示抽取 */}
          {!loading && !error && data && data.nodes.length === 0 && (
            <div className="absolute right-3 top-3 z-20 flex items-center gap-2 rounded-md border bg-card/95 px-3 py-2 shadow-sm backdrop-blur">
              {filter.scope === 'global' ? (
                <>
                  <span className="text-xs text-muted-foreground">全局记忆为空 —— 先查看项目记忆？</span>
                  <button
                    type="button"
                    onClick={() => patchFilter({ scope: 'project' })}
                    className="rounded bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground transition-opacity hover:opacity-90"
                  >
                    查看项目记忆
                  </button>
                </>
              ) : (
                <>
                  <span className="text-xs text-muted-foreground">该任务还没有记忆 —— 从成果自动抽取？</span>
                  {filter.projectId && (
                    <button
                      type="button"
                      onClick={() => rebuild(filter.projectId)}
                      disabled={rebuilding}
                      className="flex items-center gap-1 rounded bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
                    >
                      {rebuilding && <Loader2 className="h-3 w-3 animate-spin" />}
                      立即抽取
                    </button>
                  )}
                </>
              )}
            </div>
          )}

          <GraphCanvas
            data={data}
            loading={loading}
            error={error}
            onNodeClick={(node) => setSelectedntityId(node.id)}
            onBackgroundClick={() => setSelectedntityId(null)}
          />
          {/* 底部图例 */}
          <div className="absolute bottom-3 left-3 flex flex-wrap items-center gap-2 rounded-md border bg-card/90 px-3 py-2 backdrop-blur">
            <Network className="h-3.5 w-3.5 text-muted-foreground" />
            {TYP_PTINS.map((t) => (
              <span key={t.key} className="flex items-center gap-1 text-sm text-muted-foreground">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ background: `hsl(var(--graph-type-${t.key}))` }}
                />
                {t.label}
              </span>
            ))}
            {data?.meta.truncated && (
              <span className="text-sm text-secondary">
                已截断显示（共 {data.meta.entity_count} 实体）
              </span>
            )}
          </div>
        </div>

        <GraphSidebar
          entityId={selectedntityId}
          onClose={() => setSelectedntityId(null)}
          onDeleted={() => refresh()}
        />
      </div>

      {/* ─── 洞察面板 ───────────────────────────────────────── */}
      <section className="mt-5 rounded-md border bg-card p-6 shadow-sm">
        <div className="mb-3 flex items-center gap-2">
          <span className="text-sm font-semibold">💡 记忆洞察</span>
          <span className="text-xs text-muted-foreground">
            {filter.scope === 'global' ? '全局结论（跨项目复用）' : '本项目沉淀的结论'}
          </span>
          {insightsLoading && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
        </div>
        {insights.length === 0 && !insightsLoading ? (
          <p className="rounded-md border border-dashed py-6 text-center text-sm text-muted-foreground">
            暂无洞察 —— 完成任务后自动从章节/经验/图片分析中提炼
          </p>
        ) : (
          <div className="grid gap-2 md:grid-cols-2">
            {insights.slice(0, 8).map((ins) => (
              <div key={ins.id} className="rounded-md border border-primary/10 bg-primary/[0.03] px-4 py-3">
                <p className="text-xs leading-relaxed">{ins.content}</p>
                <p className="mt-1 text-sm text-muted-foreground">来源：{ins.source}</p>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
