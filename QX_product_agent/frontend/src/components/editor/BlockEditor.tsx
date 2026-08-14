/**
 * ============================================================
 * BlockEditor —— 16:9 幻灯片多实例编辑器 (Phase 3 重构)
 *
 * 核心能力（重构后）：
 * 1. 接收 DocumentBlock[] 数组，为每个 block 渲染独立的 SlidePage 画布
 * 2. 每页独立的 Tiptap 编辑器实例，支持文本编辑与图片自由插入
 * 3. 16:9 视觉约束 (800×450px)，通过 CSS 严格锁定幻灯片比例
 * 4. 图片自由插入：通过 @tiptap/extension-image + POST /assets API
 * 5. 前端手动导出：遍历所有 slide 内容 → POST /export-pdf → WeasyPrint 渲染
 *
 * 技术选型：
 * - @tiptap/react + StarterKit（每页独立实例）
 * - @tiptap/extension-underline
 * - @tiptap/extension-placeholder
 * - @tiptap/extension-image（官方图片扩展，inline: false）
 * - CitationMark（自定义 Mark，渲染 <sup> 角标）
 *
 * 数据流：
 *   GET /blocks → EditorBlock[]
 *     → SlidePage × N（独立 Tiptap 实例）
 *       → onBlockChange → onSync（父组件）
 *         → POST /export-pdf（手动导出）
 *           → WeasyPrint render_custom_html_to_pdf
 * ============================================================
 */

import { useMemo, useCallback, useEffect } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import Placeholder from '@tiptap/extension-placeholder'
import Image from '@tiptap/extension-image'
import { CitationMark } from './extensions/CitationMark'
import { useCitationStore } from '@/hooks/useCitationStore'
import type { EditorBlock } from '@/types/index'

// ─── SlidePage 16:9 画布组件 ────────────────────────────────────

interface SlidePageProps {
  /** 文档块唯一 ID */
  blockId: string
  /** 当前页的 HTML/Markdown 初始内容 */
  initialContent: string
  /** 章节标题（显示在幻灯片上方） */
  sectionTitle: string
  /** 内容变更回调，向上层同步当前页的最新 HTML */
  onBlockChange: (id: string, html: string) => void
  /** 是否只读 */
  readOnly?: boolean
}

/**
 * SlidePage —— 单页 16:9 幻灯片画布
 *
 * 每页拥有独立的 Tiptap 编辑器实例，
 * 支持图片自由插入（通过 @tiptap/extension-image），
 * 并通过 CSS 严格锁定 16:9 比例模拟真实视觉边界。
 */
function SlidePage({
  blockId,
  initialContent,
  sectionTitle,
  onBlockChange,
  readOnly = false,
}: SlidePageProps) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        codeBlock: false,
        heading: { levels: [1, 2, 3] },
      }),
      Underline,
      Placeholder.configure({ placeholder: '在此输入内容...' }),
      Image.configure({
        inline: false,
        HTMLAttributes: { class: 'manual-slide-img' },
      }),
      CitationMark.configure({ citationMap: {} }),
    ],
    content: initialContent,
    editable: !readOnly,
    onUpdate: ({ editor: ed }) => {
      // 实时向父组件同步当前页的内容
      onBlockChange(blockId, ed.getHTML())
    },
  })

  return (
    <div className="my-8 flex flex-col items-center">
      {/* 页码与章节标题提示 */}
      <div className="w-[800px] mb-2 text-sm text-gray-500 font-medium flex justify-between">
        <span>章节: {sectionTitle}</span>
      </div>

      {/* 🌟 核心：16:9 幻灯片画布 */}
      <div className="w-[800px] h-[450px] bg-white shadow-2xl border border-gray-200 p-12 overflow-y-auto relative prose prose-slate">
        <EditorContent editor={editor} />
      </div>
    </div>
  )
}

// ─── BlockEditor 多实例幻灯片容器 ────────────────────────────────

interface BlockEditorProps {
  /** 文档块列表（从后端 /blocks 获取） */
  blocks: EditorBlock[]
  /** 是否正在流式接收中 */
  isStreaming?: boolean
  /** 已流式接收的块数 */
  streamedCount?: number
  /** 编辑器是否只读（completed 阶段只读） */
  readOnly?: boolean
  /** 内容同步回调：当任意 SlidePage 内容变更时触发 */
  onSync?: (id: string, html: string) => void
  /** 引用 map 更新回调（供父组件接收完整引用映射） */
  onCitationMapUpdate?: (map: Record<string, string>) => void
  /** 引用角标点击回调（供父组件切换引用面板） */
  onCitationClick?: (citationId: string) => void
}

/**
 * BlockEditor 组件（重构后）
 *
 * 将原本的单实例编辑器替换为多实例 16:9 幻灯片编辑器。
 * 每个 DocumentBlock 渲染为一个独立的 SlidePage 画布，
 * 用户可在各页面中自由编辑文本与插入图片。
 *
 * 使用方式：
 * ```tsx
 * <BlockEditor
 *   blocks={editorBlocks}
 *   isStreaming={isStreaming}
 *   readOnly={false}
 *   onSync={(id, html) => console.log('block updated', id)}
 * />
 * ```
 */
export function BlockEditor({
  blocks,
  isStreaming = false,
  streamedCount = 0,
  readOnly = false,
  onSync,
  onCitationMapUpdate,
  onCitationClick,
}: BlockEditorProps) {
  const { setActiveCitationId } = useCitationStore()

  // ─── 合并所有 citation map（保持父组件通知能力） ──────────
  const globalCitationMap = useMemo(() => {
    const map: Record<string, string> = {}
    for (const block of blocks) {
      if (block.citations) {
        try {
          const parsed = JSON.parse(block.citations) as Record<string, string>
          Object.assign(map, parsed)
        } catch {
          // ignore parse errors
        }
      }
    }
    return map
  }, [blocks])

  // ─── 引用 map 更新通知父组件 ─────────────────────────────
  useEffect(() => {
    if (onCitationMapUpdate) {
      onCitationMapUpdate(globalCitationMap)
    }
  }, [globalCitationMap, onCitationMapUpdate])

  // ─── 内容变更处理 ────────────────────────────────────────
  const handleBlockChange = useCallback(
    (blockId: string, html: string) => {
      onSync?.(blockId, html)
    },
    [onSync],
  )

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* ─── 流式接收指示器 ─────────────────────────────────── */}
      {isStreaming && (
        <div className="flex items-center gap-2 border-b border-blue-100 bg-blue-50/50 px-4 py-1.5">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500" />
          </span>
          <span className="text-xs text-blue-600">
            正在接收 AI 生成内容... 已接收 {streamedCount} 个块
          </span>
        </div>
      )}

      {/* ─── 多实例幻灯片编辑器区域 ─────────────────────────── */}
      <div className="w-full bg-gray-50 overflow-y-auto h-full py-4">
        {blocks.length === 0 && (
          <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
            等待内容生成...
          </div>
        )}

        {blocks
          .sort((a, b) => a.order_index - b.order_index)
          .map((block) => (
            <SlidePage
              key={block.id}
              blockId={block.id}
              sectionTitle={block.section_title}
              initialContent={block.content}
              onBlockChange={handleBlockChange}
              readOnly={readOnly}
            />
          ))}
      </div>
    </div>
  )
}
