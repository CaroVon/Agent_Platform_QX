/**
 * useClarifyChat —— 需求澄清对话状态管理
 *
 * - 消息数组 + SS 流式接收（复用 editor/chat 同款 event: content 解析）
 * - 解析 event: meta 维度覆盖信号 → 决定「生成产品」是否可用
 * - localStorage 持久化（P1：刷新可续聊）
 * - brief 拼装：对话摘要 → productApi.create 的 idea
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { productApi } from '@/lib/api'

export interface ClarifyMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface DimensionSignal {
  dimensions: Record<string, boolean>
  enough: boolean
  rounds_used: number
  max_rounds: number
}

const STORAGE_KEY = 'qx-recommend-session'

interface PersistedSession {
  idea: string
  messages: ClarifyMessage[]
  updatedAt: string
}

function loadSession(): PersistedSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const s = JSON.parse(raw) as PersistedSession
    if (!Array.isArray(s.messages)) return null
    return s
  } catch {
    return null
  }
}

export function useClarifyChat() {
  const saved = useRef<PersistedSession | null>(null)
  if (saved.current === null) saved.current = loadSession()

  const [idea, setIdea] = useState(saved.current?.idea ?? '')
  const [messages, setMessages] = useState<ClarifyMessage[]>(
    saved.current?.messages ?? [],
  )
  const [streaming, setStreaming] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [signal, setSignal] = useState<DimensionSignal | null>(null)
  const [error, setError] = useState('')
  const abortRef = useRef<AbortController | null>(null)

  // ── 持久化（P1：刷新可续聊） ─────────────────────────────
  useEffect(() => {
    try {
      const payload: PersistedSession = {
        idea,
        messages,
        updatedAt: new Date().toISOString(),
      }
      if (messages.length === 0 && !idea) {
        localStorage.removeItem(STORAGE_KEY)
      } else {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
      }
    } catch {
      /* 存储不可用时静默 */
    }
  }, [idea, messages])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    setIdea('')
    setMessages([])
    setStreaming('')
    setSignal(null)
    setError('')
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      /* ignore */
    }
  }, [])

  /** 发送一条用户消息，流式接收 AI 澄清回复 */
  const send = useCallback(
    async (content: string) => {
      const text = content.trim()
      if (!text || isLoading) return
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      const nextMessages: ClarifyMessage[] = [
        ...messages,
        { role: 'user', content: text },
      ]
      setMessages(nextMessages)
      setStreaming('')
      setError('')
      setIsLoading(true)
      setSignal(null)

try {
        const resp = await fetch(`/api/v1/product/clarify`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            idea,
            messages: nextMessages,
            max_rounds: 4,
          }),
          signal: controller.signal,
        })
        if (!resp.ok) {
          let detail = `HTTP ${resp.status}`
          try {
            const body = await resp.json()
            detail = body.detail ?? detail
          } catch {
            /* ignore */
          }
          throw new Error(detail)
        }
        const reader = resp.body?.getReader()
        if (!reader) throw new Error('无响应流')
        const dec = new TextDecoder()
        let buf = ''
        let full = ''
        let evType = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buf += dec.decode(value, { stream: true })
          while (buf.includes('\n')) {
            const idx = buf.indexOf('\n')
            const line = buf.slice(0, idx).trimEnd()
            buf = buf.slice(idx + 1)
            if (line.startsWith('event: ')) evType = line.slice(7).trim()
            else if (line.startsWith('data: ')) {
              try {
                const p = JSON.parse(line.slice(6))
                if (evType === 'content' && p.text) {
                  full += p.text
                  setStreaming(full)
                } else if (evType === 'meta') {
                  setSignal(p as DimensionSignal)
                } else if (evType === 'error') {
                  setError(p.error || '澄清失败')
                }
              } catch {
                /* skip */
              }
            }
            if (line === '') evType = ''
          }
        }
        if (full.trim()) {
          setMessages((prev) => [...prev, { role: 'assistant', content: full }])
        }
      } catch (err) {
        if ((err as Error).name !== 'Abortrror') {
          setError(err instanceof Error ? err.message : '发送失败')
        }
      } finally {
        setStreaming('')
        setIsLoading(false)
      }
    },
    [idea, messages, isLoading],
  )

  const stop = useCallback(() => {
    abortRef.current?.abort()
    setIsLoading(false)
  }, [])

  /** 拼装产品 brief：对话摘要 → create 的 idea */
  const buildBrief = useCallback((): string => {
    const userMsgs = messages.filter((m) => m.role === 'user').map((m) => m.content)
    const dims = signal?.dimensions ?? {
      target_users: false,
      scenario: false,
      features: false,
      constraints: false,
    }
    const parts: string[] = []
    if (idea.trim()) parts.push(`产品方向：${idea.trim()}`)
    if (userMsgs.length > 0) {
      parts.push(
        '【需求澄清】' +
          userMsgs
            .map((c, i) => `\n${i + 1}. ${c}`)
            .join(''),
      )
    }
    parts.push(
      `【覆盖维度】${Object.entries(dims)
        .filter(([, v]) => v)
        .map(([k]) => k)
        .join('、') || '待补充'}`,
    )
    return parts.join('\n\n')
  }, [idea, messages, signal])

  const canGenerate = signal?.enough === true || messages.filter((m) => m.role === 'user').length >= 2

  return {
    idea,
    setIdea,
    messages,
    streaming,
    isLoading,
    signal,
    error,
    send,
    stop,
    reset,
    buildBrief,
    canGenerate,
    hasSession: messages.length > 0,
  }
}
