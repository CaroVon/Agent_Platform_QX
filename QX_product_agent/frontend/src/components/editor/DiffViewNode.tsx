/**
 * ============================================================
 * DiffViewNode —— 改写内容差异视图
 *
 * 当 InlineAIBubble 获取到 AI 改写结果后，
 * 在编辑器上方/下方渲染 Diff 面板：
 * - 原始文本（灰色背景）
 * - 新文本（绿色背景）
 * - Approve ✓ / Discard ✗ 按钮
 *
 * 这是临时浮层面板，不修改 Tiptap 文档结构，
 * 仅在用户点击 "Approve" 后才执行
 * `editor.commands.insertContentAt({from, to}, newContent)`
 * ============================================================
 */

import { useMemo } from 'react'

// ─── 接口 ──────────────────────────────────────────────────────

interface DiffViewNodeProps {
  /** 原始选中的文本 */
  originalText: string
  /** AI 改写后的文本 */
  revisedText: string
  /** 批准回调：用修订文本替换原始文本 */
  onApprove: () => void
  /** 丢弃回调：关闭 Diff 面板，不修改内容 */
  onDiscard: () => void
}

// ─── Diff 行类型 ──────────────────────────────────────────────

type DiffType = 'same' | 'removed' | 'added'

interface DiffLine {
  type: DiffType
  text: string
}

/**
 * 简单的行级 Diff 算法
 * 按行对比，标记 added / removed / same
 */
function computeLineDiff(original: string, revised: string): DiffLine[] {
  const origLines = original.split('\n')
  const revLines = revised.split('\n')
  const result: DiffLine[] = []

  const maxLen = Math.max(origLines.length, revLines.length)

  for (let i = 0; i < maxLen; i++) {
    const origLine = origLines[i]
    const revLine = revLines[i]

    if (origLine === undefined && revLine !== undefined) {
      // 新增行
      result.push({ type: 'added', text: revLine })
    } else if (origLine !== undefined && revLine === undefined) {
      // 删除行
      result.push({ type: 'removed', text: origLine })
    } else if (origLine !== revLine) {
      // 修改行：先显示原始（删除），再显示新（新增）
      result.push({ type: 'removed', text: origLine! })
      result.push({ type: 'added', text: revLine! })
    } else {
      // 相同行
      result.push({ type: 'same', text: origLine! })
    }
  }

  return result
}

// ─── 组件 ──────────────────────────────────────────────────────

export function DiffViewNode({
  originalText,
  revisedText,
  onApprove,
  onDiscard,
}: DiffViewNodeProps) {
  const diffLines = useMemo(
    () => computeLineDiff(originalText, revisedText),
    [originalText, revisedText],
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20">
      <div className="mx-auto w-full max-w-2xl rounded-xl border bg-white p-4 shadow-2xl">
        {/* ─── 标题 ──────────────────────────────────────────── */}
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">
            AI 改写预览
          </h3>
          <button
            type="button"
            onClick={onDiscard}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            ✕
          </button>
        </div>

        {/* ─── Diff 内容 ─────────────────────────────────────── */}
        <div className="max-h-64 overflow-y-auto rounded-lg border bg-muted/30 p-3 font-mono text-sm leading-relaxed">
          {diffLines.map((line, idx) => {
            if (line.type === 'same') {
              return (
                <div key={idx} className="py-0.5 text-muted-foreground">
                  {line.text || '\u00A0'}
                </div>
              )
            }

            if (line.type === 'removed') {
              return (
                <div
                  key={idx}
                  className="rounded bg-red-50 px-1 py-0.5 text-red-700 line-through"
                >
                  {line.text || '\u00A0'}
                </div>
              )
            }

            // added
            return (
              <div
                key={idx}
                className="rounded bg-emerald-50 px-1 py-0.5 text-emerald-800"
              >
                {line.text || '\u00A0'}
              </div>
            )
          })}
        </div>

        {/* ─── 操作按钮 ──────────────────────────────────────── */}
        <div className="mt-4 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onDiscard}
            className="rounded-lg border border-border px-4 py-1.5 text-sm font-medium text-muted-foreground hover:bg-muted transition-colors"
          >
            丢弃
          </button>
          <button
            type="button"
            onClick={onApprove}
            className="rounded-lg bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 transition-colors"
          >
            确认修改
          </button>
        </div>
      </div>
    </div>
  )
}
