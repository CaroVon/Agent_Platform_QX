/**
 * ============================================================
 * OutlineApproval —— 大纲确认横幅组件
 *
 * 🎯 交互核心节点：等待用户确认大纲时渲染
 *
 * 布局：
 * ┌─────────────────────────────────────────────────────────┐
 * │  📋 大纲已生成完毕，请审阅并确认                         │
 * │  ┌─────────────────────────────────────────────────┐    │
 * │  │ ## 1. 行业概述                                   │    │
 * │  │ ## 2. 市场分析                                   │    │
 * │  │ ## 3. 竞争格局                                   │    │
 * │  │ ...                                             │    │
 * │  └─────────────────────────────────────────────────┘    │
 * │  [✏️ 编辑大纲]  [✅ 确认并开始撰写]                      │
 * └─────────────────────────────────────────────────────────┘
 * ============================================================
 */

import { useState } from 'react'
import { CheckCircle2, Loader2, FileText, AlertCircle, Edit2, Eye } from 'lucide-react'
import { Button } from '@/components/common/button'
import type { OutlineSection } from '@/types/index'

interface OutlineApprovalProps {
  /** 项目 ID */
  projectId: string
  /** 大纲 Markdown 原始内容 */
  outlineContent: string | null
  /** 解析后的章节列表 */
  sections: OutlineSection[]
  /** 确认回调 */
  onConfirm: (outline: string) => Promise<void>
  /** 是否正在提交确认 */
  isConfirming: boolean
  /** 确认失败的错误信息 */
  confirmError: string | null
}

/**
 * 从 Markdown 中解析 ## 章节标题
 */
function parseSections(outline: string): OutlineSection[] {
  const lines = outline.split('\n')
  const sections: OutlineSection[] = []
  let index = 0

  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.startsWith('## ')) {
      const title = trimmed.replace(/^##\s*/, '')
      sections.push({ title, raw: trimmed, index })
      index++
    }
  }

  return sections
}

/**
 * 大纲确认横幅
 *
 * 显示从后端拉取的大纲 Markdown，允许用户：
 * 1. 视觉审阅章节列表
 * 2. 切换到编辑模式修改大纲
 * 3. 点击"确认并开始撰写"按钮提交（可携带用户修改后的大纲）
 */
export function OutlineApproval({
  projectId,
  outlineContent,
  sections: propSections,
  onConfirm,
  isConfirming,
  confirmError,
}: OutlineApprovalProps) {
  const [localError, setLocalError] = useState<string | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [editedOutline, setEditedOutline] = useState<string>(outlineContent ?? '')

  // 如果没有传入解析好的 sections，自行解析
  const sections = propSections.length > 0
    ? propSections
    : (isEditing ? editedOutline : outlineContent)
      ? parseSections(isEditing ? editedOutline : (outlineContent ?? ''))
      : []

  // 如果 outlineContent 为空，显示骨架屏
  if (!outlineContent) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50/40 p-6">
        <div className="flex items-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-amber-500" />
          <div className="space-y-1">
            <p className="text-sm font-medium text-amber-700">大纲正在生成中...</p>
            <p className="text-xs text-amber-600/70">资料准备完成后将自动展示大纲供您审阅</p>
          </div>
        </div>
      </div>
    )
  }

  const handleConfirm = async () => {
    const finalOutline = isEditing ? editedOutline : (outlineContent ?? '')
    if (!finalOutline.trim()) return
    setLocalError(null)
    try {
      await onConfirm(finalOutline)
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : '确认失败，请重试')
    }
  }

  const handleToggleEdit = () => {
    if (!isEditing) {
      setEditedOutline(outlineContent ?? '')
    }
    setIsEditing((v) => !v)
  }

  const displayedSections = parseSections(isEditing ? editedOutline : outlineContent)

  return (
    <div className="rounded-xl border border-amber-200 bg-gradient-to-br from-amber-50/60 to-white p-6 shadow-sm">
      {/* ─── 顶部标题 ─────────────────────────────────────────── */}
      <div className="mb-4 flex items-start justify-between">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-full bg-amber-100">
            <FileText className="h-4 w-4 text-amber-600" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-amber-900">
              大纲已生成完毕，请审阅
            </h3>
            <p className="mt-0.5 text-sm text-amber-700/70">
              确认后 AI 将根据此大纲逐章节撰写产品分析报告。你可以直接修改大纲再确认。
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={handleToggleEdit}
          className="ml-4 inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-amber-200 bg-white px-3 py-1.5 text-xs font-medium text-amber-700 hover:bg-amber-50 transition-colors"
        >
          {isEditing ? (
            <>
              <Eye className="h-3.5 w-3.5" />
              预览
            </>
          ) : (
            <>
              <Edit2 className="h-3.5 w-3.5" />
              编辑大纲
            </>
          )}
        </button>
      </div>

      {/* ─── 大纲预览 / 编辑 ─────────────────────────────────── */}
      <div className="mb-4 rounded-lg border border-amber-200/60 bg-white/80">
        {isEditing ? (
          <textarea
            value={editedOutline}
            onChange={(e) => setEditedOutline(e.target.value)}
            className="block h-64 w-full resize-none rounded-lg bg-transparent p-4 font-mono text-sm leading-relaxed text-foreground/90 focus:outline-none focus:ring-1 focus:ring-amber-400"
            placeholder="输入大纲内容（使用 ## 标题格式定义章节）..."
          />
        ) : (
          <div className="max-h-64 overflow-y-auto p-4">
            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-foreground/90">
              {outlineContent}
            </pre>
          </div>
        )}
      </div>

      {/* ─── 章节统计 ─────────────────────────────────────────── */}
      {displayedSections.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-1.5">
          {displayedSections.map((section) => (
            <span
              key={section.index}
              className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700"
            >
              {section.title}
            </span>
          ))}
        </div>
      )}

      {/* ─── 错误提示 ─────────────────────────────────────────── */}
      {(localError || confirmError) && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{localError || confirmError}</span>
        </div>
      )}

      {/* ─── 操作按钮 ─────────────────────────────────────────── */}
      <div className="flex items-center gap-3">
        <Button
          onClick={handleConfirm}
          disabled={isConfirming}
          className="gap-2 bg-amber-600 text-white hover:bg-amber-700"
        >
          {isConfirming ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              正在启动撰写...
            </>
          ) : (
            <>
              <CheckCircle2 className="h-4 w-4" />
              确认并开始撰写
            </>
          )}
        </Button>

        <p className="text-xs text-muted-foreground">
          共 {displayedSections.length} 个章节 · 确认后不可撤销
        </p>
      </div>
    </div>
  )
}
