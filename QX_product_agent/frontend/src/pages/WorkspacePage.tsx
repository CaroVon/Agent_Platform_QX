/**
 * ============================================================
 * WorkspacePage —— 项目管理工作台
 *
 * 页面组成：
 * ┌─────────────────────────────────────────────────────────────┐
 * │  WorkspacePage                                             │
 * │  ┌──────────┬───────────────────────────┬───────────────┐   │
 * │  │ 大纲目录 │  状态面板                  │  日志/引用    │   │
 * │  │ (左栏)   │  - ProgressTracker        │              │   │
 * │  │          │  - SourcesReview          │              │   │
 * │  │          │  - OutlineApproval        │              │   │
 * │  │          │  - 完成状态 + 进入编辑器   │              │   │
 * │  └──────────┴───────────────────────────┴───────────────┘   │
 * └─────────────────────────────────────────────────────────────┘
 *
 * Canvas 编辑 → 跳转到专用 EditorPage (/projects/:id/editor)
 * ============================================================
 */

import { useState, useCallback, useMemo, useEffect, useRef } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Loader2, AlertCircle, Search, FileText, Download,
  Quote, Terminal, ExternalLink, Upload, ChevronDown,
  Check, FileUp, X, Paperclip, Edit3, Eye,
} from 'lucide-react'
import { Button } from '@/components/common/button'
import { ProgressTracker } from '@/components/projects/ProgressTracker'
import { SourcesReview } from '@/components/projects/SourcesReview'
import { OutlineApproval } from '@/components/projects/OutlineApproval'
import { ThreePaneLayout } from '@/components/layout/ThreePaneLayout'
import { cn } from '@/lib/utils'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter,
} from '@/components/common/dialog'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/common/popover'
import {
  useProjectStatus,
  useProjectBlocks,
  useSources,
  useReviewSources,
  useApproveOutline,
  getStatusFlags,
} from '@/hooks/useProjectStatus'
import { useCitationStore } from '@/hooks/useCitationStore'
import { useProjectLogs } from '@/hooks/useProjectLogs'
import { TerminalTimeline } from '@/components/projects/TerminalTimeline'
import { projectsApi } from '@/lib/api'
import type { RightPanelView, OutlineSection } from '@/types/index'

// ================================================================
// 左栏：大纲目录树
// ================================================================

interface OutlineTreeProps {
  sections: OutlineSection[]
  activeSectionTitle: string | null
  onSectionClick: (title: string) => void
}

function OutlineTree({ sections, activeSectionTitle, onSectionClick }: OutlineTreeProps) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <FileText className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">大纲目录</span>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {sections.length === 0 ? (
          <div className="px-3 py-8 text-center">
            <p className="text-xs text-muted-foreground">暂无章节</p>
            <p className="mt-1 text-[10px] text-muted-foreground/60">等待 AI 生成大纲...</p>
          </div>
        ) : (
          <nav className="space-y-0.5">
            {sections.map((section) => (
              <button
                key={section.index}
                type="button"
                onClick={() => onSectionClick(section.title)}
                className={cn(
                  'w-full rounded-md px-3 py-2 text-left text-xs transition-colors',
                  activeSectionTitle === section.title
                    ? 'bg-primary/10 font-medium text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                <span className="line-clamp-2">{section.title}</span>
              </button>
            ))}
          </nav>
        )}
      </div>
      <div className="border-t border-border px-4 py-2">
        <p className="text-[10px] text-muted-foreground/60">{sections.length} 个章节</p>
      </div>
    </div>
  )
}

// ================================================================
// 右栏：日志 / 引用
// ================================================================

interface CitationsPanelProps {
  citationMap: Record<string, string>
}

function CitationsPanel({ citationMap }: CitationsPanelProps) {
  const activeCitationId = useCitationStore((s) => s.activeCitationId)
  const url = activeCitationId ? citationMap[activeCitationId] : null

  return (
    <div className="p-4">
      <h3 className="mb-3 text-sm font-semibold">引用溯源</h3>
      {activeCitationId ? (
        <div className="rounded-lg border border-violet-100 bg-violet-50/50 p-3">
          <p className="text-xs font-semibold text-violet-700">引用 [^{activeCitationId}]</p>
          {url ? (
            <>
              <p className="mt-1.5 break-all text-[11px] text-violet-600/80">{url}</p>
              <a href={url} target="_blank" rel="noopener noreferrer"
                className="mt-2 inline-flex items-center gap-1 rounded bg-violet-100 px-2 py-0.5 text-[11px] font-medium text-violet-700 hover:bg-violet-200">
                <ExternalLink className="h-3 w-3" />打开原文
              </a>
            </>
          ) : (
            <p className="mt-1 text-[11px] text-violet-600/60">（未找到该引用的来源链接）</p>
          )}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-border bg-muted/20 p-4 text-center">
          <Quote className="mx-auto mb-2 h-5 w-5 text-muted-foreground/50" />
          <p className="text-xs text-muted-foreground">点击报告引用角标查看来源</p>
        </div>
      )}
      {Object.keys(citationMap).length > 0 && (
        <div className="mt-4 space-y-1.5">
          {Object.entries(citationMap).map(([id, href]) => (
            <div key={id} className="flex items-start gap-2 rounded p-1.5 hover:bg-muted/50">
              <span className="mt-0.5 shrink-0 rounded bg-muted px-1 py-0.5 text-[10px] font-mono">[{id}]</span>
              <a href={href} target="_blank" rel="noopener noreferrer" className="line-clamp-2 text-[11px] text-blue-600 hover:underline">{href}</a>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function RightPanel({
  view, onViewChange, logs = [], logsLoading = false, citationMap = {},
}: {
  view: RightPanelView
  onViewChange: (v: RightPanelView) => void
  logs?: import('@/types/api').ProjectLogResponse[]
  logsLoading?: boolean
  citationMap?: Record<string, string>
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center border-b border-border">
        <button
          onClick={() => onViewChange('logs')}
          className={cn('flex flex-1 items-center justify-center gap-1.5 px-3 py-2.5 text-xs font-medium',
            view === 'logs' ? 'border-b-2 border-emerald-500 text-emerald-600' : 'text-muted-foreground hover:text-foreground')}
        >
          <Terminal className="h-3.5 w-3.5" />日志
        </button>
        <button
          onClick={() => onViewChange('citations')}
          className={cn('flex flex-1 items-center justify-center gap-1.5 px-3 py-2.5 text-xs font-medium',
            view === 'citations' ? 'border-b-2 border-violet-500 text-violet-600' : 'text-muted-foreground hover:text-foreground')}
        >
          <Quote className="h-3.5 w-3.5" />引用
        </button>
      </div>
      <div className="flex-1 overflow-hidden">
        {view === 'logs' && <div className="h-full bg-slate-900"><TerminalTimeline logs={logs} isLoading={logsLoading} /></div>}
        {view === 'citations' && <div className="h-full overflow-y-auto"><CitationsPanel citationMap={citationMap} /></div>}
      </div>
    </div>
  )
}

// ================================================================
// 上传文档弹窗
// ================================================================

function UploadDocsDialog({ open, onOpenChange, projectId }: { open: boolean; onOpenChange: (v: boolean) => void; projectId: string }) {
  const [files, setFiles] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<{ chunk_count: number; message: string } | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { if (!open) { const t = setTimeout(() => { setFiles([]); setResult(null) }, 200); return () => clearTimeout(t) } }, [open])

  const doUpload = async () => {
    if (!files.length || uploading) return
    setUploading(true); setResult(null)
    try {
      let total = 0
      for (let i = 0; i < files.length; i++) {
        if (files.length > 1) setResult({ chunk_count: -1, message: `上传中 (${i + 1}/${files.length})...` })
        const r = await projectsApi.uploadDocs(projectId, [files[i]])
        total += r.chunk_count
        if (i === files.length - 1) setResult({ chunk_count: total, message: files.length > 1 ? `${files.length} 个文件上传完成，共 ${total} 个切片` : r.message })
      }
      setFiles([])
    } catch (e: any) { setResult({ chunk_count: 0, message: `❌ ${e.message}` }) }
    finally { setUploading(false) }
  }

  const totalSize = files.reduce((s, f) => s + f.size, 0)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><FileUp className="h-5 w-5" />上传参考文件</DialogTitle>
          <DialogDescription>支持 PDF、DOCX、TXT。上传后自动加入知识库。</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <button onClick={() => inputRef.current?.click()} disabled={uploading}
            className="flex w-full flex-col items-center gap-2 rounded-lg border-2 border-dashed border-border bg-muted/30 px-4 py-6 hover:border-primary/50 disabled:opacity-50">
            <Upload className="h-6 w-6 text-muted-foreground" />
            <p className="text-xs text-muted-foreground">点击选择文件</p>
            <input ref={inputRef} type="file" multiple accept=".pdf,.docx,.txt"
              onChange={(e) => { if (e.target.files) setFiles((p) => [...p, ...Array.from(e.target.files!)]); e.target.value = '' }}
              className="hidden" />
          </button>
          {files.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium">已选 {files.length} 个 ({totalSize < 1024*1024 ? `${(totalSize/1024).toFixed(1)} KB` : `${(totalSize/(1024*1024)).toFixed(1)} MB`})</p>
                <button onClick={() => setFiles([])} className="text-[10px] text-muted-foreground hover:text-foreground">清空</button>
              </div>
              {files.map((f, i) => (
                <div key={`${f.name}-${i}`} className="flex items-center gap-2 rounded-md bg-muted/50 px-3 py-1.5">
                  <Paperclip className="h-3 w-3 text-muted-foreground" />
                  <span className="flex-1 truncate text-xs">{f.name}</span>
                  <button onClick={() => setFiles((p) => p.filter((_, j) => j !== i))} className="text-muted-foreground hover:text-destructive"><X className="h-3 w-3" /></button>
                </div>
              ))}
            </div>
          )}
          {result && (
            <div className={cn('rounded-lg px-3 py-2.5 text-xs', result.chunk_count < 0 ? 'bg-blue-50 text-blue-700' : result.chunk_count > 0 ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700')}>
              {result.chunk_count < 0 && <Loader2 className="mr-1.5 inline h-3 w-3 animate-spin" />}{result.message}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)} disabled={uploading}>关闭</Button>
          <Button size="sm" onClick={doUpload} disabled={!files.length || uploading} loading={uploading}>{uploading ? '上传中...' : '开始上传'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ================================================================
// 模板选择
// ================================================================

const TEMPLATE_OPTIONS = [
  { key: 'product', label: '📊 产品预研报告', desc: '产品定位、功能、CMF、竞品与定价' },
  { key: 'design', label: '🎨 工业设计推演', desc: '设计语言、人机工程、CMF与结构堆叠' },
] as const
type TemplateKey = (typeof TEMPLATE_OPTIONS)[number]['key']

function TemplatePopover({ value, onChange }: { value: TemplateKey; onChange: (k: TemplateKey) => void }) {
  const [open, setOpen] = useState(false)
  const sel = TEMPLATE_OPTIONS.find((t) => t.key === value) ?? TEMPLATE_OPTIONS[0]
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          <FileText className="h-3.5 w-3.5" /><span className="max-w-[120px] truncate text-[11px]">{sel.label}</span><ChevronDown className="h-3 w-3" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64 p-1">
        {TEMPLATE_OPTIONS.map((o) => {
          const active = value === o.key
          return (
            <button key={o.key} onClick={() => { onChange(o.key); setOpen(false) }}
              className={cn('flex w-full items-start gap-2 rounded-sm px-3 py-2 text-left', active ? 'bg-primary/10 text-primary' : 'hover:bg-muted')}>
              <div className="flex-1 min-w-0"><p className="text-xs font-medium">{o.label}</p><p className="text-[10px] text-muted-foreground">{o.desc}</p></div>
              {active && <Check className="mt-0.5 h-3.5 w-3.5 shrink-0" />}
            </button>
          )
        })}
      </PopoverContent>
    </Popover>
  )
}

// ================================================================
// 主组件
// ================================================================

export function WorkspacePage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [activeSectionTitle, setActiveSectionTitle] = useState<string | null>(null)
  const [rightPanelView, setRightPanelView] = useState<RightPanelView>('logs')
  const [citationMap, setCitationMap] = useState<Record<string, string>>({})
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateKey>('product')

  // ─── 数据获取 ──────────────────────────────────────
  const { data: st, isLoading: stLoading, isError: stError, error: stErr } = useProjectStatus({ projectId, enabled: true })

  useEffect(() => {
    if (st?.template_type && (st.template_type === 'product' || st.template_type === 'design'))
      setSelectedTemplate(st.template_type as TemplateKey)
  }, [st?.template_type])

  const flags = getStatusFlags(st?.project_status)
  const { logs, isLoading: logsLoading } = useProjectLogs({ projectId, status: st?.project_status, enabled: true })

  const { data: sourcesData, isLoading: srcLoading, isError: srcError } = useSources(projectId, flags.isWaitingSources)
  const reviewMutation = useReviewSources()
  const approveMutation = useApproveOutline()

  const { data: blocksData } = useProjectBlocks(projectId, flags.isDrafting || flags.isCompleted)

  // ─── 引用 map ──────────────────────────────────────
  useEffect(() => {
    const blocks = blocksData?.blocks ?? []
    if (!blocks.length) return
    const map: Record<string, string> = {}
    for (const b of blocks) {
      if (b.citations) {
        try { Object.assign(map, JSON.parse(b.citations)) } catch { /* ignore */ }
      }
    }
    setCitationMap(map)
  }, [blocksData])

  // ─── 大纲解析 ─────────────────────────────────────
  const outlineSections = useMemo<OutlineSection[]>(() => {
    if (!st?.outline_content) return []
    const lines = st.outline_content.split('\n')
    const secs: OutlineSection[] = []
    let idx = 0
    for (const line of lines) {
      const t = line.trim()
      if (t.startsWith('## ')) { secs.push({ title: t.replace(/^##\s*/, ''), raw: t, index: idx }); idx++ }
    }
    return secs
  }, [st?.outline_content])

  // ─── 回调 ─────────────────────────────────────────
  const handleReview = useCallback(async (urls: string[]) => {
    if (!projectId) return
    await reviewMutation.mutateAsync({ projectId, data: { selected_urls: urls } })
  }, [projectId, reviewMutation])

  const handleApprove = useCallback(async (outline: string) => {
    if (!projectId) return
    await approveMutation.mutateAsync({ projectId, data: { outline } })
  }, [projectId, approveMutation])

  const handleSectionClick = useCallback((title: string) => setActiveSectionTitle(title), [])

  const { setActiveCitationId } = useCitationStore()
  const handleCitationClick = useCallback((id: string) => { setActiveCitationId(id); setRightPanelView('citations') }, [setActiveCitationId])

  // ─── 加载/错误状态 ────────────────────────────────
  if (stLoading) return <div className="flex h-screen items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>
  if (stError || !st) return (
    <div className="flex h-screen items-center justify-center">
      <div className="flex flex-col items-center gap-4 text-destructive">
        <AlertCircle className="h-10 w-10" />
        <p className="font-medium">加载失败</p>
        <p className="text-sm text-muted-foreground">{(stErr as Error)?.message ?? '项目不存在'}</p>
        <Link to="/"><Button variant="outline" size="sm">返回控制台</Button></Link>
      </div>
    </div>
  )

  const topic = st.topic
  const tasks = st.tasks
  const percentage = st.progress?.percentage ?? 0
  const blocksCount = blocksData?.blocks?.length ?? 0

  return (
    <>
    <ThreePaneLayout
      leftPane={
        <OutlineTree sections={outlineSections} activeSectionTitle={activeSectionTitle} onSectionClick={handleSectionClick} />
      }
      centerPane={
        <div className="flex h-full flex-col">
          {/* ─── 顶部导航 ──────────────────────────────── */}
          <div className="flex items-center gap-2 border-b border-border px-4 py-2.5">
            <Link to="/" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground shrink-0">
              <ArrowLeft className="h-3.5 w-3.5" />返回
            </Link>
            <span className="h-3 w-px bg-border shrink-0" />
            <h1 className="truncate text-sm font-medium min-w-0">{topic}</h1>
            <TemplatePopover value={selectedTemplate} onChange={setSelectedTemplate} />
            <Button size="sm" variant="outline" onClick={() => setUploadDialogOpen(true)} className="gap-1.5 shrink-0">
              <Upload className="h-3.5 w-3.5" /><span className="hidden sm:inline text-[11px]">上传参考文件</span>
            </Button>

            <div className="ml-auto flex items-center gap-2 shrink-0">
              <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium',
                flags.isCompleted && 'bg-emerald-50 text-emerald-600',
                flags.isFailed && 'bg-red-50 text-red-600',
                flags.isPreparing && 'bg-blue-50 text-blue-600',
                flags.isWaitingSources && 'bg-blue-50 text-blue-600',
                flags.isPreparingOutline && 'bg-blue-50 text-blue-600',
                flags.isWaitingApproval && 'bg-amber-50 text-amber-600',
                flags.isDrafting && 'bg-violet-50 text-violet-600')}
              >
                {flags.isCompleted && '已完成'}
                {flags.isFailed && '失败'}
                {flags.isPreparing && '资料搜索中'}
                {flags.isWaitingSources && '待审核资料'}
                {flags.isPreparingOutline && '大纲生成中'}
                {flags.isWaitingApproval && '待确认大纲'}
                {flags.isDrafting && 'AI 撰写中'}
              </span>
            </div>
          </div>

          {/* ─── ProgressTracker ──────────────────────────── */}
          {tasks.length > 0 && (flags.isPreparing || flags.isPreparingOutline || flags.isDrafting) && (
            <div className="border-b border-border px-4 py-3">
              <ProgressTracker tasks={tasks} percentage={percentage} projectStatus={st.project_status} currentStep={st.current_step} />
            </div>
          )}

          {/* ─── 资料审核 ─────────────────────────────────── */}
          {flags.isWaitingSources && (
            <div className="p-4">
              {srcLoading ? (
                <div className="flex items-center justify-center rounded-xl border border-blue-200 bg-blue-50/40 p-8"><Loader2 className="h-6 w-6 animate-spin text-blue-500" /></div>
              ) : srcError || !sourcesData ? (
                <div className="rounded-xl border border-red-200 bg-red-50/40 p-8 text-center"><p className="text-sm text-red-600">加载资料失败</p></div>
              ) : sourcesData.sources.length === 0 ? (
                <div className="rounded-xl border border-dashed border-blue-200 bg-blue-50/20 p-8 text-center"><Search className="mx-auto h-6 w-6 text-blue-400" /><p className="mt-2 text-sm text-blue-600">暂无搜索到的资料</p></div>
              ) : (
                <SourcesReview projectId={projectId!} sources={sourcesData.sources} topic={topic}
                  onConfirm={handleReview} isConfirming={reviewMutation.isPending} confirmError={reviewMutation.error?.message ?? null} />
              )}
            </div>
          )}

          {/* ─── 大纲确认 ─────────────────────────────────── */}
          {flags.isWaitingApproval && (
            <div className="p-4">
              <OutlineApproval projectId={projectId!} outlineContent={st.outline_content} sections={outlineSections}
                onConfirm={handleApprove} isConfirming={approveMutation.isPending} confirmError={approveMutation.error?.message ?? null} />
            </div>
          )}

          {/* ─── 完成 / 草稿就绪 → 进入编辑器入口 ─────────────── */}
          {(flags.isDrafting || flags.isCompleted) && (
            <div className="flex flex-1 flex-col items-center justify-center p-8">
              <div className="max-w-md w-full rounded-2xl border border-border bg-card p-8 text-center shadow-sm">
                {/* 图标 */}
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                  <Edit3 className="h-8 w-8 text-primary" />
                </div>

                {/* 标题 */}
                <h2 className="text-lg font-semibold">
                  {flags.isCompleted ? '报告已生成完毕' : 'AI 正在撰写中'}
                </h2>

                {/* 描述 */}
                <p className="mt-2 text-sm text-muted-foreground">
                  {flags.isCompleted
                    ? `已为「${topic}」生成 ${blocksCount} 个内容块，${outlineSections.length} 个章节。进入 Canvas 编辑器进行排版、拖拽编辑和导出 PDF。`
                    : `AI 正在逐章节撰写内容，已生成 ${blocksCount} 个块。可提前进入编辑器查看已生成的内容。`}
                </p>

                {/* 信息卡片 */}
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div className="rounded-lg bg-muted/50 px-4 py-3 text-center">
                    <p className="text-2xl font-bold text-primary">{outlineSections.length}</p>
                    <p className="text-[10px] text-muted-foreground">章节</p>
                  </div>
                  <div className="rounded-lg bg-muted/50 px-4 py-3 text-center">
                    <p className="text-2xl font-bold text-primary">{blocksCount}</p>
                    <p className="text-[10px] text-muted-foreground">内容块</p>
                  </div>
                </div>

                {/* 进入编辑器按钮 */}
                <Button
                  size="lg"
                  onClick={() => navigate(`/projects/${projectId}/editor`)}
                  className="mt-6 w-full gap-2"
                >
                  <Edit3 className="h-4 w-4" />
                  进入 Canvas 编辑器
                </Button>

                <p className="mt-3 text-[10px] text-muted-foreground">
                  在编辑器中可自由拖拽排版、插入图片、应用 AI 生成内容、导出高清 PDF
                </p>
              </div>
            </div>
          )}

          {/* ─── 等待中 ────────────────────────────────────── */}
          {(flags.isPreparing || flags.isPreparingOutline) && (
            <div className="flex flex-1 items-center justify-center">
              <div className="flex flex-col items-center gap-3 text-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                <p className="text-sm font-medium text-muted-foreground">AI 正在搜集资料并生成大纲</p>
                <p className="text-xs text-muted-foreground/60">完成后将展示大纲供您审阅确认</p>
              </div>
            </div>
          )}
        </div>
      }
      rightPane={
        <RightPanel view={rightPanelView} onViewChange={setRightPanelView} logs={logs} logsLoading={logsLoading} citationMap={citationMap} />
      }
    />
    <UploadDocsDialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen} projectId={projectId ?? ''} />
    </>
  )
}
