/**
 * ============================================================
 * useEditorSync —— 前后端 Block 数据同步 Hook
 *
 * 职责：
 * 1. 在 drafting 阶段连接 SSE /stream-draft 端点
 * 2. 将流式推送的 section_chunk 事件实时注入编辑器
 * 3. 维护一个完整的 EditorBlock[] 列表供 Tiptap 渲染
 * 4. 当 draft_complete 事件到达时关闭 SSE 连接
 * ============================================================
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { connectDraftStream } from '@/lib/api'
import type { DocumentBlockResponse } from '@/types/api'
import type { EditorBlock } from '@/types/index'

interface UseEditorSyncOptions {
  projectId: string | undefined
  /** 是否启用 SSE 流式接收（drafting 阶段为 true） */
  enabled: boolean
  /** 初始 blocks（从 REST API 拉取的存量数据） */
  initialBlocks?: DocumentBlockResponse[]
}

interface UseEditorSyncReturn {
  /** 当前完整块列表（按 order_index 排序） */
  blocks: EditorBlock[]
  /** 是否正在接收流式数据 */
  isStreaming: boolean
  /** 已接收的流式块数 */
  streamedCount: number
  /** 总块数（draft_complete 时更新） */
  totalBlocks: number
  /** 手动重置流式状态 */
  reset: () => void
}

/**
 * Block 数据同步 Hook
 *
 * 在 drafting 阶段：
 * 1. 先通过 REST API 拉取存量 blocks
 * 2. 同时连接 SSE，接收实时推送的 section_chunk
 * 3. 新块到达时合并到 blocks 列表
 *
 * SSE 消息格式：
 * - event: section_chunk
 *   data: { section_title, order_index, content, citations }
 * - event: draft_complete
 *   data: { project_id, total_blocks }
 */
export function useEditorSync({
  projectId,
  enabled,
  initialBlocks = [],
}: UseEditorSyncOptions): UseEditorSyncReturn {
  const [blocks, setBlocks] = useState<EditorBlock[]>(() =>
    initialBlocks.map((b) => ({ ...b, isStreaming: false })),
  )
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamedCount, setStreamedCount] = useState(0)
  const [totalBlocks, setTotalBlocks] = useState(initialBlocks.length)
  const eventSourceRef = useRef<EventSource | null>(null)
  const blocksRef = useRef<EditorBlock[]>(blocks)

  // 保持 ref 同步
  useEffect(() => {
    blocksRef.current = blocks
  }, [blocks])

  // 重置函数
  const reset = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setBlocks([])
    setIsStreaming(false)
    setStreamedCount(0)
    setTotalBlocks(0)
  }, [])

  // SSE 连接管理
  useEffect(() => {
    if (!projectId || !enabled) return

    // 关闭之前的连接
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    setIsStreaming(true)
    const es = connectDraftStream(projectId)
    eventSourceRef.current = es

    // 监听 section_chunk 事件
    es.addEventListener('section_chunk', (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data) as {
          section_title: string
          order_index: number
          content: string
          citations: Record<string, string> | null
        }

        const newBlock: EditorBlock = {
          id: `streaming-${payload.order_index}-${Date.now()}`,
          section_title: payload.section_title,
          order_index: payload.order_index,
          content: payload.content,
          citations: payload.citations ? JSON.stringify(payload.citations) : null,
          created_at: new Date().toISOString(),
          updated_at: null,
          isStreaming: true,
        }

        setBlocks((prev) => {
          // 去重：检查是否已存在同 order_index 的 block
          const exists = prev.some((b) => b.order_index === payload.order_index)
          if (exists) {
            // 更新已有块（覆盖内容）
            return prev.map((b) =>
              b.order_index === payload.order_index
                ? { ...b, content: payload.content, isStreaming: false }
                : b,
            )
          }
          // 新增块
          const updated = [...prev, newBlock].sort(
            (a, b) => a.order_index - b.order_index,
          )
          return updated
        })

        setStreamedCount((prev) => prev + 1)
      } catch (err) {
        console.error('[SSE] 解析 section_chunk 失败:', err)
      }
    })

    // 监听 draft_complete 事件
    es.addEventListener('draft_complete', (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data) as {
          project_id: string
          total_blocks: number
        }
        setTotalBlocks(payload.total_blocks)
        setIsStreaming(false)

        // 所有块标记为非流式
        setBlocks((prev) =>
          prev.map((b) => ({ ...b, isStreaming: false })),
        )

        // 关闭 SSE 连接
        es.close()
        eventSourceRef.current = null
      } catch (err) {
        console.error('[SSE] 解析 draft_complete 失败:', err)
      }
    })

    // 错误处理
    es.onerror = (err) => {
      console.error('[SSE] 连接错误:', err)
      // EventSource 会自动重连，但超过一定次数后关闭
      setIsStreaming(false)
    }

    return () => {
      es.close()
      eventSourceRef.current = null
    }
  }, [projectId, enabled])

  return {
    blocks,
    isStreaming,
    streamedCount,
    totalBlocks: totalBlocks || blocks.length,
    reset,
  }
}
