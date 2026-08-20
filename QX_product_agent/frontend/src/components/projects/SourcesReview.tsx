/**
 * ============================================================
 * SourcesReview —— 资料审核面板组件
 *
 * 🎯 交互节点1：等待用户审核资料时渲染
 *
 * 布局：
 * ┌─────────────────────────────────────────────────────────┐
 * │  🔍 资料搜集完毕，请审核                                 │
 * │  AI 为您搜索了 N 条参考资料，您可以取消勾选低质量信息。  │
 * │  ┌─────────────────────────────────────────────────┐    │
 * │  │ ☑ [1] 资料标题                      来源域名     │    │
 * │  │     摘要前 200 字...                            │    │
 * │  │     🔗 https://...                              │    │
 * │  ├─────────────────────────────────────────────────┤    │
 * │  │ ☑ [2] ...                                      │    │
 * │  └─────────────────────────────────────────────────┘    │
 * │  [✅ 确认资料，开始生成大纲]  共 N 条 · 已选 M 条       │
 * └─────────────────────────────────────────────────────────┘
 * ============================================================
 */

import { useState, useMemo } from 'react'
import { CheckCircle2, Loader2, Search, ExternalLink, AlertCircle, Globe } from 'lucide-react'
import { Button } from '@/components/common/button'
import type { SourceItem } from '@/types/api'
import { cn } from '@/lib/utils'

interface SourcesReviewProps {
  /** 项目 ID */
  projectId: string
  /** 资料来源列表 */
  sources: SourceItem[]
  /** 项目主题 */
  topic: string
  /** 确认回调 */
  onConfirm: (selectedUrls: string[]) => Promise<void>
  /** 是否正在提交 */
  isConfirming: boolean
  /** 错误信息 */
  confirmError: string | null
}

/**
 * 从 URL 中提取域名（用于展示来源）
 */
function extractDomain(url: string): string {
  try {
    const parsed = new URL(url)
    return parsed.hostname.replace('www.', '')
  } catch {
    return url
  }
}

/**
 * 资料审核面板
 *
 * 核心交互：
 * 1. 查看每条资料的标题、摘要、来源
 * 2. 点击 checkbox 切换选中/取消
 * 3. 点击"确认资料"提交筛选结果
 * 4. 支持全选/取消全选
 */
export function SourcesReview({
  projectId,
  sources,
  topic: _topic,
  onConfirm,
  isConfirming,
  confirmError,
}: SourcesReviewProps) {
  const [selectedSet, setSelectedSet] = useState<Set<string>>(
    () => new Set(sources.map((s) => s.url)),
  )
  const [localError, setLocalError] = useState<string | null>(null)

  // ─── 统计数据 ──────────────────────────────────────────
  const totalCount = sources.length
  const selectedCount = selectedSet.size
  const allSelected = selectedCount === totalCount
  const noneSelected = selectedCount === 0

  // ─── 切换选中 ──────────────────────────────────────────
  const toggleSource = (url: string) => {
    setSelectedSet((prev) => {
      const next = new Set(prev)
      if (next.has(url)) {
        next.delete(url)
      } else {
        next.add(url)
      }
      return next
    })
    setLocalError(null)
  }

  // ─── 全选/取消全选 ─────────────────────────────────────
  const toggleAll = () => {
    if (allSelected) {
      setSelectedSet(new Set())
    } else {
      setSelectedSet(new Set(sources.map((s) => s.url)))
    }
  }

  // ─── 提交确认 ──────────────────────────────────────────
  const handleConfirm = async () => {
    if (noneSelected) {
      setLocalError('请至少选择一条参考资料')
      return
    }
    setLocalError(null)
    try {
      const urls = Array.from(selectedSet)
      await onConfirm(urls)
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : '提交失败，请重试')
    }
  }

  return (
    <div className="rounded-xl border border-blue-200 bg-gradient-to-br from-blue-50/60 to-white p-6 shadow-sm">
      {/* ─── 头部 ─────────────────────────────────────────── */}
      <div className="mb-4 flex items-start justify-between">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-full bg-blue-100">
            <Search className="h-4 w-4 text-blue-600" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-blue-900">
              资料搜集完毕，请审核
            </h3>
            <p className="mt-0.5 text-sm text-blue-700/70">
              AI 为您搜索了 {totalCount} 条参考资料。
              您可以取消勾选低质量或不相关的信息，确认后 AI 将基于选定资料生成分析大纲。
            </p>
          </div>
        </div>
      </div>

      {/* ─── 全选操作栏 ────────────────────────────────────── */}
      <div className="mb-3 flex items-center justify-between">
        <button
          type="button"
          onClick={toggleAll}
          className="text-xs font-medium text-blue-600 hover:text-blue-800 transition-colors"
        >
          {allSelected ? '取消全选' : '全选'}
        </button>
        <span className="text-xs text-muted-foreground">
          共 {totalCount} 条 · 已选 {selectedCount} 条
        </span>
      </div>

      {/* ─── 资料列表 ──────────────────────────────────────── */}
      <div className="mb-4 max-h-80 space-y-1.5 overflow-y-auto rounded-lg border border-blue-200/60 bg-white/80">
        {sources.map((source) => {
          const isSelected = selectedSet.has(source.url)
          const domain = extractDomain(source.url)

          return (
            <button
              key={source.index}
              type="button"
              onClick={() => toggleSource(source.url)}
              className={cn(
                'flex w-full items-start gap-3 px-4 py-3 text-left transition-colors',
                'border-b border-blue-100/50 last:border-b-0',
                isSelected
                  ? 'bg-white hover:bg-blue-50/30'
                  : 'bg-muted/30 opacity-60 hover:opacity-80',
              )}
            >
              {/* ─── Checkbox ────────────────────────────── */}
              <div
                className={cn(
                  'mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border-2 transition-colors',
                  isSelected
                    ? 'border-blue-500 bg-blue-500 text-white'
                    : 'border-muted-foreground/30 bg-transparent',
                )}
              >
                {isSelected && <CheckCircle2 className="h-3.5 w-3.5" />}
              </div>

              {/* ─── 内容 ──────────────────────────────────── */}
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-medium text-foreground line-clamp-1">
                    <span className="mr-1.5 text-xs text-muted-foreground">
                      [{source.index}]
                    </span>
                    {source.title}
                  </span>
                  <span className="mt-0.5 inline-flex shrink-0 items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-600">
                    <Globe className="h-2.5 w-2.5" />
                    {domain}
                  </span>
                </div>

                {source.snippet && (
                  <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                    {source.snippet}
                  </p>
                )}

                <div className="mt-1 flex items-center gap-1 text-[10px] text-blue-500 hover:text-blue-700">
                  <ExternalLink className="h-2.5 w-2.5" />
                  <span className="truncate">{source.url}</span>
                </div>
              </div>
            </button>
          )
        })}
      </div>

      {/* ─── 错误提示 ──────────────────────────────────────── */}
      {(localError || confirmError) && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{localError || confirmError}</span>
        </div>
      )}

      {/* ─── 操作按钮 ──────────────────────────────────────── */}
      <div className="flex items-center gap-3">
        <Button
          onClick={handleConfirm}
          disabled={isConfirming || noneSelected}
          className="gap-2 bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {isConfirming ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              正在提交...
            </>
          ) : (
            <>
              <CheckCircle2 className="h-4 w-4" />
              确认资料，开始生成大纲
            </>
          )}
        </Button>

        <p className="text-xs text-muted-foreground">
          将基于 {selectedCount} 条资料生成分析大纲 · 确认后不可撤销
        </p>
      </div>
    </div>
  )
}
