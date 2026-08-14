/**
 * ============================================================
 * InlineAIBubble —— 基于 BubbleMenu 的 Inline AI 改写面板
 *
 * 核心功能：
 * 1. 选中文本后弹出 BubbleMenu
 * 2. 提供输入框 + 快速按钮（扩写/精简/润色）
 * 3. 调用 `/api/v1/editor/revise` 获取改写结果
 * 4. 将改写结果以 DiffView 形式展示（等待确认）
 *
 * 状态流：
 *   idle → loading（AI 改写中）→ diff（展示 DiffView）
 *   → approved（应用修改）/ discarded（丢弃修改）→ idle
 *
 * 数据流：
 *   editor.state.selection.from/to
 *     → selected_text + instruction
 *       → POST /api/v1/editor/revise
 *         → revised_text
 *           → DiffViewNode（绿色高亮 + 确认/丢弃）
 *             → editor.commands.insertContentAt({from,to}, newContent)
 * ============================================================
 */

import { useState, useCallback, useRef } from 'react'
import { BubbleMenu } from '@tiptap/react/menus'
import type { Editor } from '@tiptap/react'
import { editorApi } from '@/lib/api'
import { DiffViewNode } from './DiffViewNode'

// ─── 常量 ──────────────────────────────────────────────────────

/** 快速操作按钮列表 */
const QUICK_ACTIONS = [
  { label: '扩写', instruction: '扩写' },
  { label: '精简', instruction: '精简' },
  { label: '润色', instruction: '润色' },
] as const

// ─── 类型 ──────────────────────────────────────────────────────

type AiBubbleState =
  | { phase: 'idle' }
  | { phase: 'loading' }
  | { phase: 'diff'; revisedText: string; from: number; to: number }

interface InlineAIBubbleProps {
  editor: Editor
}

// ─── 组件 ──────────────────────────────────────────────────────

export function InlineAIBubble({ editor }: InlineAIBubbleProps) {
  const [state, setState] = useState<AiBubbleState>({ phase: 'idle' })
  const [inputValue, setInputValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  // ─── 获取选中文本及位置 ──────────────────────────────────
  const getSelectionInfo = useCallback(() => {
    const { from, to } = editor.state.selection
    const selectedText = editor.state.doc.textBetween(from, to)
    return { from, to, selectedText }
  }, [editor])

  // ─── 调用 AI 改写 ──────────────────────────────────────
  const handleRevise = useCallback(
    async (instruction: string) => {
      const { from, to, selectedText } = getSelectionInfo()
      if (!selectedText.trim()) return

      setState({ phase: 'loading' })
      setInputValue('')

      try {
        const res = await editorApi.revise({
          selected_text: selectedText,
          instruction,
        })

        setState({
          phase: 'diff',
          revisedText: res.revised_text,
          from,
          to,
        })
      } catch (err) {
        console.error('[InlineAIBubble] 改写失败:', err)
        setState({ phase: 'idle' })
      }
    },
    [editor, getSelectionInfo],
  )

  // ─── 自定义输入提交 ──────────────────────────────────────
  const handleCustomSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()
      const trimmed = inputValue.trim()
      if (trimmed) {
        handleRevise(trimmed)
      }
    },
    [handleRevise, inputValue],
  )

  // ─── 批准修改 ──────────────────────────────────────────
  const handleApprove = useCallback(() => {
    if (state.phase !== 'diff') return

    editor
      .chain()
      .focus()
      .deleteRange({ from: state.from, to: state.to })
      .insertContentAt(state.from, state.revisedText)
      .run()

    setState({ phase: 'idle' })
  }, [editor, state])

  // ─── 丢弃修改 ──────────────────────────────────────────
  const handleDiscard = useCallback(() => {
    setState({ phase: 'idle' })
  }, [])

  // ─── 显示 DiffView ─────────────────────────────────────
  if (state.phase === 'diff') {
    return (
      <DiffViewNode
        originalText={editor.state.doc.textBetween(state.from, state.to)}
        revisedText={state.revisedText}
        onApprove={handleApprove}
        onDiscard={handleDiscard}
      />
    )
  }

  return (
    <BubbleMenu
      editor={editor}
      shouldShow={({ state: editorState }) => {
        // 仅当选中非空文本时显示
        if (editorState.selection.empty) return false
        // 如果处于 diff 或 loading 阶段，由上层控制
        if (state.phase !== 'idle') return false
        return true
      }}
    >
      <div className="flex items-center gap-1.5 rounded-lg border bg-popover p-1.5 shadow-md min-w-[240px]">
        {/* ─── 快速操作按钮 ─────────────────────────────────── */}
        <div className="flex items-center gap-0.5 border-r border-border pr-1.5">
          {QUICK_ACTIONS.map((action) => (
            <button
              key={action.instruction}
              type="button"
              disabled={state.phase === 'loading'}
              onClick={() => handleRevise(action.instruction)}
              className="rounded px-2 py-1 text-xs font-medium text-violet-600 hover:bg-violet-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {action.label}
            </button>
          ))}
        </div>

        {/* ─── 自定义输入框 ─────────────────────────────────── */}
        <form onSubmit={handleCustomSubmit} className="flex flex-1 items-center gap-1">
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="请输入修改指令..."
            disabled={state.phase === 'loading'}
            className="flex-1 rounded border-0 bg-transparent px-1.5 py-1 text-xs text-foreground placeholder:text-muted-foreground outline-none focus:ring-0"
          />
          <button
            type="submit"
            disabled={state.phase === 'loading' || !inputValue.trim()}
            className="rounded bg-primary px-2 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {state.phase === 'loading' ? (
              <span className="inline-flex items-center gap-1">
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
                改写中
              </span>
            ) : (
              '发送'
            )}
          </button>
        </form>
      </div>
    </BubbleMenu>
  )
}
