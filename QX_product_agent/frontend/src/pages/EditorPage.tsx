/**
 * ============================================================
 * EditorPage —— 沉浸式 Canvas 编辑器页面 (Phase 5)
 *
 * 布局（全屏，无 ThreePaneLayout 干扰）：
 * ┌──────────────────────────────────────────────────────────┐
 * │ ← 返回工作台 │ 主题名称 │ [导出 PDF] │ 页码指示器       │  ← 顶部栏
 * ├──────────┬───────────────────────────────┬───────────────┤
 * │ 缩略图   │                              │  AI 助手      │
 * │ 列表     │   React-Konva Canvas          │  (可折叠)     │
 * │          │   1280×720 (16:9)            │               │
 * │          │                              │  对话 +       │
 * │ [+添加]  │   拖拽编辑                    │  应用到画布   │
 * └──────────┴───────────────────────────────┴───────────────┘
 *
 * 职责：
 * - 从 REST API 拉取 blocks → convertBlocksToKonvaSlides → 初始化 slides
 * - 嵌入 CanvasSlideEditor
 * - 管理 jsPDF 导出（使用 Konva stage.toDataURL 极速离屏渲染）
 * - 右侧 AI 助手面板（直接写入 Zustand store）
 * ============================================================
 */

import { useState, useCallback, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft,
  Download,
  Loader2,
  AlertCircle,
  Bot,
  Send,
  PanelRightClose,
  PanelRight,
} from 'lucide-react'
import { Button } from '@/components/common/button'
import { CanvasSlideEditor } from '@/components/editor/CanvasSlideEditor'
import type { KonvaCanvasInstance } from '@/components/editor/CanvasSlideEditor'
import { ImageGallery } from '@/components/editor/ImageGallery'
import { cn } from '@/lib/utils'
import {
  convertBlocksToKonvaSlides,
  type KonvaSlide,
} from '@/lib/dataTransform'
import {
  useProjectStatus,
  useProjectBlocks,
  getStatusFlags,
} from '@/hooks/useProjectStatus'
import { editorApi, projectsApi } from '@/lib/api'
import { useCanvasStore } from '@/store/useCanvasStore'
import type { CanvasElement } from '@/store/useCanvasStore'
import type { EditorChatMessage } from '@/types/api'

// ══════════════════════════════════════════════════════════════
// AI 助手面板（内嵌版 —— Phase 5 更新：直接写入 Zustand）
// ══════════════════════════════════════════════════════════════

interface AiPanelProps {
  projectId: string
  canvasRef: React.MutableRefObject<KonvaCanvasInstance | null>
}

function AiPanel({ projectId, canvasRef }: AiPanelProps) {
  const [msgs, setMsgs] = useState<
    Array<{ role: 'user' | 'assistant'; text: string }>
  >([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [streaming, setStreaming] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [msgs, streaming])

  const send = useCallback(async () => {
    const t = input.trim()
    if (!t || loading) return
    const userMsg = { role: 'user' as const, text: t }
    setMsgs((p) => [...p, userMsg])
    setInput('')
    setLoading(true)
    setStreaming('')

    const history: EditorChatMessage[] = msgs.map((m) => ({
      role: m.role,
      content: m.text,
    }))
    abortRef.current = new AbortController()

    try {
      const resp = await editorApi.chat({
        project_id: projectId,
        chat_mode: 'work',
        message: t,
        selected_text: null,
        history,
      })
      const reader = resp.body?.getReader()
      if (!reader) throw new Error('No body')
      const dec = new TextDecoder()
      let buf = '',
        full = '',
        evType = ''

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
              } else if (evType === 'error') {
                full += `\n⚠️ ${p.error || ''}`
                setStreaming(full)
              }
            } catch {
              /* skip */
            }
          }
          if (line === '') evType = ''
        }
      }
      setMsgs((p) => [...p, { role: 'assistant', text: full }])
      setStreaming('')
    } catch (err: any) {
      if (err?.name !== 'AbortError')
        setMsgs((p) => [...p, { role: 'assistant', text: '⚠️ 请求失败' }])
      setStreaming('')
    } finally {
      setLoading(false)
      abortRef.current = null
    }
  }, [input, loading, msgs, projectId])

  // ─── Phase 5 更新：直接写入 Zustand store ──────────────────
  const applyText = useCallback(
    async (text: string) => {
      const activePage = useCanvasStore.getState().activePage
      useCanvasStore.getState().addElement(activePage, {
        type: 'text',
        x: 200,
        y: 300,
        width: 880,
        height: 60,
        text,
        fill: '#334155',
      })
    },
    [],
  )

  const applyImage = useCallback(async (url: string) => {
    const activePage = useCanvasStore.getState().activePage
    useCanvasStore.getState().addElement(activePage, {
      type: 'image',
      x: 1280 * 0.15,
      y: 720 * 0.1,
      width: 1280 * 0.7,
      height: 720 * 0.7,
      src: url,
    })
  }, [])

  const extractUrls = (text: string) =>
    text.match(
      /https?:\/\/[^\s]+\.(?:png|jpg|jpeg|gif|webp|svg)(?:\?[^\s]*)?/gi,
    ) || []

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-3 py-2.5">
        <span className="text-xs font-medium flex items-center gap-1.5">
          <Bot className="h-3.5 w-3.5" /> AI 助手
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        {msgs.length === 0 && !streaming && (
          <div className="flex h-full items-center justify-center text-center">
            <p className="text-[11px] text-muted-foreground">
              基于知识库的 AI 对话，可生成内容直接应用到画布
            </p>
          </div>
        )}
        {msgs.map((m, i) => {
          const urls = m.role === 'assistant' ? extractUrls(m.text) : []
          return (
            <div
              key={i}
              className={cn(
                'rounded-lg px-3 py-2 text-xs',
                m.role === 'user'
                  ? 'ml-4 bg-primary/10'
                  : 'mr-4 bg-muted',
              )}
            >
              <p className="mb-1 text-[10px] font-medium text-muted-foreground">
                {m.role === 'user' ? '你' : 'AI'}
              </p>
              <p className="whitespace-pre-wrap">{m.text}</p>
              {m.role === 'assistant' && (
                <div className="mt-2 flex flex-wrap gap-1.5 border-t border-border/50 pt-2">
                  <button
                    onClick={() => applyText(m.text)}
                    className="inline-flex items-center gap-1 rounded bg-primary/10 px-2 py-0.5 text-[10px] text-primary hover:bg-primary/20"
                  >
                    应用到画布
                  </button>
                  {urls.map((u, j) => (
                    <button
                      key={j}
                      onClick={() => applyImage(u)}
                      className="inline-flex items-center gap-1 rounded bg-violet-100 px-2 py-0.5 text-[10px] text-violet-700 hover:bg-violet-200"
                    >
                      插入图片{j + 1}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )
        })}
        {streaming && (
          <div className="mr-4 rounded-lg bg-muted px-3 py-2">
            <p className="mb-1 text-[10px] font-medium text-muted-foreground">
              AI
            </p>
            <p className="whitespace-pre-wrap text-xs">
              {streaming}
              <span className="ml-0.5 inline-block h-3.5 w-0.5 animate-pulse bg-primary align-middle" />
            </p>
          </div>
        )}
        {loading && !streaming && (
          <div className="mr-4 rounded-lg bg-muted px-3 py-2">
            <div className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/50 [animation-delay:0ms]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/50 [animation-delay:150ms]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/50 [animation-delay:300ms]" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-border p-3">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
            placeholder="输入问题（Enter 发送）"
            disabled={loading}
            rows={2}
            className="flex-1 resize-none rounded-lg border border-border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
          />
          <button
            onClick={send}
            disabled={!input.trim() || loading}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════
// EditorPage 主组件
// ══════════════════════════════════════════════════════════════

export function EditorPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const canvasRef = useRef<KonvaCanvasInstance | null>(null)

  // ─── 状态 ──────────────────────────────────────────────
  const [slides, setSlides] = useState<KonvaSlide[]>([])
  const [activeIndex, setActiveIndex] = useState(0)
  const [exportingPdf, setExportingPdf] = useState(false)
  const [rightPanelOpen, setRightPanelOpen] = useState(true)
  // ── Canvas 自动保存（修复「编辑永不保存、刷新即丢」） ──
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [lastSavedAt, setLastSavedAt] = useState<string>('')
  const saveTimer = useRef<number | null>(null)
  const loadedCanvas = useRef(false)

  // ─── 数据获取 ──────────────────────────────────────────
  const { data: statusData, isLoading: statusLoading } = useProjectStatus({
    projectId,
    enabled: true,
  })
  const flags = getStatusFlags(statusData?.project_status)
  const blocksEnabled = flags.isDrafting || flags.isCompleted
  const { data: blocksData, isLoading: blocksLoading } = useProjectBlocks(
    projectId,
    blocksEnabled,
  )

  const topic = statusData?.topic ?? ''
  const logoUrl = statusData?.logo_url || undefined

  // blocks → slides（存在已保存 canvas 时优先恢复用户布局）
  useEffect(() => {
    const blocks = blocksData?.blocks ?? []
    if (blocks.length > 0 && slides.length === 0) {
      const newSlides = convertBlocksToKonvaSlides(topic, blocks, logoUrl)
      setSlides(newSlides)

      // 同时初始化 Zustand store
      const storeSlides: { [page: number]: typeof newSlides[0]['elements'] } =
        {}
      for (const slide of newSlides) {
        storeSlides[slide.pageNumber] = slide.elements
      }
      useCanvasStore.getState().setSlides(storeSlides)

      // 恢复已保存的 canvas 数据（用户编辑过的布局优先于 blocks 派生布局）
      if (!loadedCanvas.current && projectId) {
        loadedCanvas.current = true
        projectsApi
          .getCanvas(projectId)
          .then((saved) => {
            const savedSlides = saved.slides as { [page: number]: CanvasElement[] } | undefined
            if (savedSlides && Object.keys(savedSlides).length > 0) {
              useCanvasStore.getState().setSlides(savedSlides)
              if (saved.saved_at) {
                setLastSavedAt(new Date(saved.saved_at).toLocaleTimeString('zh-CN', { hour12: false }))
              }
            }
          })
          .catch(() => { /* 无历史保存或后端不支持 */ })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blocksData, topic])

  // ─── Canvas 自动保存（store 变更 → 防抖 1.5s → 后端持久化） ──
  useEffect(() => {
    if (!projectId || !statusData) return
    const unsub = useCanvasStore.subscribe((state, prev) => {
      if (state.slides === prev.slides) return
      setSaveState('saving')
      if (saveTimer.current) window.clearTimeout(saveTimer.current)
      saveTimer.current = window.setTimeout(async () => {
        try {
          await projectsApi.saveCanvas(projectId, state.slides)
          setSaveState('saved')
          setLastSavedAt(new Date().toLocaleTimeString('zh-CN', { hour12: false }))
        } catch {
          setSaveState('error')
        }
      }, 1500)
    })
    return () => {
      unsub()
      if (saveTimer.current) window.clearTimeout(saveTimer.current)
    }
  }, [projectId, statusData])

  // ─── 导出 PDF（使用原生 Konva 离屏渲染，无 React 时序依赖） ──
  const handleExport = useCallback(async () => {
    if (!canvasRef.current || slides.length === 0) return
    setExportingPdf(true)

    try {
      const { jsPDF } = await import('jspdf')
      const pdf = new jsPDF({
        orientation: 'landscape',
        unit: 'px',
        format: [1280, 720],
      })

      // 以 Zustand store 为准（AiPanel 等可能直接写入 store），回退到本地 slides
      const storeSlides = useCanvasStore.getState().slides
      for (let i = 0; i < slides.length; i++) {
        const elements = storeSlides[i] ?? slides[i].elements
        // 使用离屏原生 Konva Stage 渲染并抓取（Promise 保证完成）
        const dataUrl = await canvasRef.current.capturePage(
          elements,
          1280,
          720,
          2,
        )

        if (i > 0) pdf.addPage()
        pdf.addImage(dataUrl, 'JPEG', 0, 0, 1280, 720)
      }

      pdf.save(topic ? `${topic}_专业报告.pdf` : '产品分析报告.pdf')
    } catch (err: any) {
      console.error('[Export]', err)
      alert(`导出失败: ${err.message}`)
    } finally {
      setExportingPdf(false)
    }
  }, [slides, topic])

  // ─── 加载状态 ──────────────────────────────────────────
  if (statusLoading || blocksLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">加载编辑器...</p>
        </div>
      </div>
    )
  }

  if (!statusData) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-destructive">
          <AlertCircle className="h-10 w-10" />
          <p className="font-medium">项目不存在</p>
          <Link to="/">
            <Button variant="outline" size="sm">
              返回控制台
            </Button>
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      {/* ─── 顶部导航栏 ─────────────────────────────────── */}
      <header className="flex items-center gap-3 border-b border-border px-4 py-2 shrink-0">
        <Link
          to={`/projects/${projectId}/workspace`}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          返回工作台
        </Link>
        <span
          className="ml-2 flex items-center gap-1.5 text-[11px] text-muted-foreground"
          title={saveState === 'error' ? '保存失败，请检查网络后重试' : '画布编辑自动保存'}
        >
          {saveState === 'saving' && <Loader2 className="h-3 w-3 animate-spin" />}
          {saveState === 'saved' && <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />}
          {saveState === 'error' && <span className="h-1.5 w-1.5 rounded-full bg-red-500" />}
          {saveState === 'saving' && '保存中…'}
          {saveState === 'saved' && `已保存 ${lastSavedAt}`}
          {saveState === 'idle' && '自动保存'}
        </span>

        <span className="h-3 w-px bg-border" />

        <h1 className="truncate text-sm font-medium min-w-0 flex-1">
          {topic}
        </h1>

        {/* 状态标签 */}
        <span
          className={cn(
            'inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium',
            flags.isCompleted && 'bg-emerald-50 text-emerald-600',
            flags.isDrafting && 'bg-violet-50 text-violet-600',
            flags.isFailed && 'bg-red-50 text-red-600',
          )}
        >
          {flags.isCompleted
            ? '已完成'
            : flags.isDrafting
              ? '撰写中'
              : statusData.project_status}
        </span>

        {/* 导出按钮 */}
        <Button
          size="sm"
          onClick={handleExport}
          disabled={exportingPdf || slides.length === 0}
          loading={exportingPdf}
          className="gap-1.5"
        >
          <Download className="h-3.5 w-3.5" />
          {exportingPdf ? '导出中...' : '导出 PDF'}
        </Button>

        {/* 切换右面板 */}
        <button
          onClick={() => setRightPanelOpen((v) => !v)}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          title={rightPanelOpen ? '收起 AI 面板' : '展开 AI 面板'}
        >
          {rightPanelOpen ? (
            <PanelRightClose className="h-4 w-4" />
          ) : (
            <PanelRight className="h-4 w-4" />
          )}
        </button>
      </header>

      {/* ─── 主体：编辑器 + AI 面板 ────────────────────────── */}
      <div className="flex flex-1 min-h-0">
        {/* 左侧：Canvas 编辑器 + 图片素材库（垂直布局） */}
        <div className="flex flex-col flex-1 min-w-0 min-h-0">
          {/* Canvas 编辑器 */}
          <div className="flex-1 min-h-0">
            {slides.length === 0 ? (
              <div className="flex h-full items-center justify-center">
                <div className="flex flex-col items-center gap-3 text-muted-foreground">
                  <Loader2 className="h-8 w-8 animate-spin" />
                  <p className="text-sm">正在准备幻灯片内容...</p>
                </div>
              </div>
            ) : (
              <CanvasSlideEditor
                slides={slides}
                activeIndex={activeIndex}
                onActiveIndexChange={setActiveIndex}
                onSlidesChange={setSlides}
                canvasRef={canvasRef}
                readOnly={false}
                showToolbar={true}
                projectId={projectId}
              />
            )}
          </div>
          {/* 图片素材库（编辑器下方） */}
          <ImageGallery
            projectId={projectId!}
            activePage={activeIndex}
            projectStatus={statusData?.project_status}
            imagesPerPage={statusData?.images_per_page}
          />
        </div>

        {/* AI 助手面板（可折叠） */}
        {rightPanelOpen && (
          <aside className="w-72 shrink-0 border-l border-border bg-card">
            <AiPanel projectId={projectId!} canvasRef={canvasRef} />
          </aside>
        )}
      </div>
    </div>
  )
}
