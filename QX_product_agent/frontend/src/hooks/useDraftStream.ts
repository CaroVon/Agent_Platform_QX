/**
 * ============================================================
 * useDraftStream —— SSE 流式渲染 Hook
 *
 * 核心功能：
 * 1. 监听后端 /stream-draft SSE 端点
 * 2. 将涌入的 Markdown 字符片段通过 editor.commands.insertContent()
 *    实时插入 Tiptap 编辑器
 * 3. 处理流中断重连（指数退避）
 * 4. 识别 [DONE] 终止标识
 *
 * 使用方式：
 * ```tsx
 * useDraftStream({
 *   editor,
 *   projectId: 'xxx',
 *   enabled: isStreaming,
 *   onSectionStart: (title) => console.log('新章节开始:', title),
 *   onDraftComplete: () => console.log('草稿完成'),
 * })
 * ```
 * ============================================================
 */

import { useEffect, useRef, useCallback } from 'react'
import type { Editor } from '@tiptap/react'
import { connectDraftStream } from '@/lib/api'

// ─── 常量 ──────────────────────────────────────────────────────

/** 最大重连次数（超过后停止重连） */
const MAX_RETRIES = 5

/** 初始重连延迟（ms） */
const INITIAL_RETRY_DELAY = 1000

/** 最大重连延迟（ms） */
const MAX_RETRY_DELAY = 30_000

/** 指数退避系数 */
const BACKOFF_FACTOR = 2

// ─── 接口定义 ──────────────────────────────────────────────────

export interface UseDraftStreamOptions {
  /** Tiptap 编辑器实例 */
  editor: Editor | null
  /** 项目 ID */
  projectId: string | undefined
  /** 是否启用流式接收 */
  enabled: boolean
  /** 每个新章节开始的回调（可用来更新左侧大纲高亮） */
  onSectionStart?: (sectionTitle: string) => void
  /** 草稿流完全结束的回调 */
  onDraftComplete?: () => void
  /** 发生不可恢复错误的回调 */
  onError?: (error: Error) => void
}

// ─── Hook ──────────────────────────────────────────────────────

export function useDraftStream({
  editor,
  projectId,
  enabled,
  onSectionStart,
  onDraftComplete,
  onError,
}: UseDraftStreamOptions) {
  // ─── 计数器 ref（不触发渲染） ────────────────────────────
  const retryCountRef = useRef(0)
  const esRef = useRef<EventSource | null>(null)
  const currentSectionRef = useRef<string | null>(null)
  const enabledRef = useRef(enabled)

  // 保持 enabled 引用最新
  useEffect(() => {
    enabledRef.current = enabled
  }, [enabled])

  // ─── 清理函数 ────────────────────────────────────────────
  const cleanup = useCallback(() => {
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }
  }, [])

  // ─── 创建 SSE 连接 ──────────────────────────────────────
  const connect = useCallback(() => {
    if (!projectId) return

    // 关闭旧连接
    cleanup()

    const es = connectDraftStream(projectId)
    esRef.current = es

    // ─── section_chunk 事件 ──────────────────────────────
    es.addEventListener('section_chunk', (event: MessageEvent) => {
      if (!enabledRef.current) return

      try {
        const data = JSON.parse(event.data) as {
          section_title: string
          order_index: number
          content: string
          citations: Record<string, string> | null
        }

        const { section_title, content, citations } = data

        // 新章节开始 → 触发回调
        if (section_title !== currentSectionRef.current) {
          currentSectionRef.current = section_title
          onSectionStart?.(section_title)
        }

        // ─── 核心：将 Markdown 插入 Tiptap 编辑器 ─────
        if (editor && content) {
          const insertContent = content

          // 将 Markdown 块转换为 HTML 片段（匹配 BlockEditor 的 convertToHtml 逻辑）
          let html = insertContent
            .replace(/&/g, '&')
            .replace(/</g, '<')
            .replace(/>/g, '>')
            .replace(/^##\s+(.+)$/gm, '<h2>$1</h2>')
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            .replace(/\[(\d+)\]/g, '<span data-citation-id="$1" class="citation-sup">[$1]</span>')

          // 将非标题行包裹为 <p>
          html = html
            .split('\n')
            .map((line) => {
              if (line.startsWith('<h') || line.trim() === '') return line
              return `<p>${line}</p>`
            })
            .join('\n')

          // 插入到编辑器末尾
          editor.commands.insertContent(html)
        }

        // 重置重连计数器 —— 成功收到数据则网络正常
        retryCountRef.current = 0
      } catch (err) {
        console.error('[useDraftStream] 解析 section_chunk 失败:', err)
      }
    })

    // ─── draft_complete 事件 ─────────────────────────────
    es.addEventListener('draft_complete', () => {
      if (!enabledRef.current) return

      // 插入 [DONE] 分隔标识（可选）
      if (editor) {
        editor.commands.insertContent(
          '<hr class="draft-divider" data-done="true" />',
        )
      }

      currentSectionRef.current = null
      onDraftComplete?.()
      cleanup()
    })

    // ─── 错误处理 & 重连 ─────────────────────────────────
    es.onerror = () => {
      // 如果已经是 closed 状态（draft_complete 主动关闭），不重连
      if (es.readyState === EventSource.CLOSED) return
      if (!enabledRef.current) return

      cleanup()

      if (retryCountRef.current < MAX_RETRIES) {
        const delay = Math.min(
          INITIAL_RETRY_DELAY * Math.pow(BACKOFF_FACTOR, retryCountRef.current),
          MAX_RETRY_DELAY,
        )
        retryCountRef.current += 1
        console.warn(
          `[useDraftStream] SSE 连接断开，${delay}ms 后第 ${retryCountRef.current} 次重连...`,
        )
        setTimeout(connect, delay)
      } else {
        const err = new Error(
          `SSE 连接在重连 ${MAX_RETRIES} 次后仍然失败，停止重连`,
        )
        console.error('[useDraftStream]', err.message)
        onError?.(err)
      }
    }
  }, [projectId, editor, onSectionStart, onDraftComplete, onError, cleanup])

  // ─── 启用/禁用 流式接收 ────────────────────────────────
  useEffect(() => {
    if (enabled && projectId) {
      retryCountRef.current = 0
      currentSectionRef.current = null
      connect()
    } else {
      cleanup()
    }

    return cleanup
  }, [enabled, projectId, connect, cleanup])
}
