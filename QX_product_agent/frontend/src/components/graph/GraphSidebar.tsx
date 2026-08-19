/**
 * GraphSidebar —— 实体详情侧栏 + 洞察面板
 *
 * 点击关系图节点后展示：基本信息 / 邻域关系 / 关联洞察 / 证据溯源。
 */

import { useCallback, useEffect, useState } from 'react'
import { Loader2, ShieldAlert, Trash2, X } from 'lucide-react'
import { memoryApi } from '@/lib/api'
import type { MemoryEntityDetail } from '@/types/api'

const TYPE_LABELS: Record<string, string> = {
  company: '公司',
  product: '产品',
  technology: '技术',
  person: '人物',
  market: '市场',
  metric: '指标',
  other: '其他',
}

interface GraphSidebarProps {
  entityId: string | null
  onClose: () => void
  onDeleted?: (entityId: string) => void
}

export function GraphSidebar({ entityId, onClose, onDeleted }: GraphSidebarProps) {
  const [detail, setDetail] = useState<MemoryEntityDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)

  const load = useCallback(async (id: string) => {
    setLoading(true)
    setError('')
    try {
      setDetail(await memoryApi.entity(id))
    } catch (e) {
      setError(e instanceof Error ? e.message : '实体详情加载失败')
      setDetail(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (entityId) void load(entityId)
    else setDetail(null)
  }, [entityId, load])

  const handleDelete = async () => {
    if (!detail || !confirmDelete) {
      setConfirmDelete(true)
      return
    }
    try {
      await memoryApi.deleteEntity(detail.id)
      onDeleted?.(detail.id)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败')
    }
  }

  return (
    <aside className="flex w-80 shrink-0 flex-col overflow-hidden rounded-2xl border bg-card shadow-sm">
      {/* ── 头部 ── */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h3 className="text-sm font-semibold">实体详情</h3>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-secondary"
          aria-label="关闭详情"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* ── 内容 ── */}
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {loading && (
          <div className="flex items-center justify-center py-10 text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 加载中…
          </div>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}

        {detail && !loading && (
          <>
            {/* 基本信息 */}
            <div>
              <div className="flex items-center gap-2">
                <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                  {TYPE_LABELS[detail.type] ?? detail.type}
                </span>
                {detail.scope === 'global' && (
                  <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-medium text-emerald-600">
                    🌐 全局记忆
                  </span>
                )}
              </div>
              <h4 className="mt-1.5 text-base font-semibold">{detail.name}</h4>
              {detail.aliases.length > 0 && (
                <p className="mt-0.5 text-[11px] text-muted-foreground">
                  又名：{detail.aliases.join(' / ')}
                </p>
              )}
              {detail.summary && (
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{detail.summary}</p>
              )}
              <div className="mt-2 flex items-center gap-3 text-[10px] text-muted-foreground">
                <span>置信度 {Math.round(detail.confidence * 100)}%</span>
                {detail.first_seen_at && (
                  <span>首次 {new Date(detail.first_seen_at).toLocaleDateString()}</span>
                )}
                {detail.last_seen_at && (
                  <span>最近 {new Date(detail.last_seen_at).toLocaleDateString()}</span>
                )}
              </div>
            </div>

            {/* 邻域关系 */}
            <div>
              <h5 className="mb-2 text-xs font-semibold text-muted-foreground">
                关联关系（{detail.relations.length}）
              </h5>
              {detail.relations.length === 0 ? (
                <p className="text-[11px] text-muted-foreground">暂无关联关系</p>
              ) : (
                <ul className="space-y-1.5">
                  {detail.relations.map((rel) => (
                    <li key={rel.relation_id} className="rounded-lg border px-3 py-2">
                      <div className="flex items-center gap-1.5 text-xs">
                        <span className="font-medium">{rel.other.name}</span>
                        <span className="text-[10px] text-muted-foreground">
                          {rel.direction === 'out' ? '←' : '→'}
                        </span>
                        <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px]">
                          {rel.relation}
                        </span>
                        {rel.expired && <span className="text-[10px] text-muted-foreground">（已过期）</span>}
                      </div>
                      {rel.evidence.length > 0 && (
                        <div className="mt-1 text-[10px] text-muted-foreground">
                          证据：{rel.evidence.length} 个项目
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* 关联洞察 */}
            <div>
              <h5 className="mb-2 text-xs font-semibold text-muted-foreground">
                关联洞察（{detail.insights.length}）
              </h5>
              {detail.insights.length === 0 ? (
                <p className="text-[11px] text-muted-foreground">暂无关联洞察</p>
              ) : (
                <ul className="space-y-1.5">
                  {detail.insights.map((ins) => (
                    <li key={ins.id} className="rounded-lg border border-primary/15 bg-primary/5 px-3 py-2 text-xs">
                      💡 {ins.content}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* 纠错 */}
            <div className="border-t pt-3">
              {confirmDelete ? (
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-destructive">确认删除该实体及其关系？</span>
                  <button
                    type="button"
                    onClick={handleDelete}
                    className="rounded-md bg-destructive px-2 py-1 text-[11px] font-medium text-destructive-foreground"
                  >
                    确认删除
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(false)}
                    className="rounded-md px-2 py-1 text-[11px] text-muted-foreground hover:bg-secondary"
                  >
                    取消
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={handleDelete}
                  className="flex items-center gap-1.5 text-[11px] text-muted-foreground transition-colors hover:text-destructive"
                >
                  <Trash2 className="h-3 w-3" />
                  删除该实体（纠错）
                </button>
              )}
              <p className="mt-1.5 flex items-center gap-1 text-[10px] text-muted-foreground/70">
                <ShieldAlert className="h-3 w-3" />
                删除仅影响记忆图，不影响项目原始文档
              </p>
            </div>
          </>
        )}
      </div>
    </aside>
  )
}
