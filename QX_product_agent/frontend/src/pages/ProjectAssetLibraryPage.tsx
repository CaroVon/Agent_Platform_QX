/**
 * ProjectAssetLibraryPage —— 项目资产库（v3）
 *
 * 布局：左侧 PPT 缩略图 / 中段项目简介 / 右侧下载 + 展开
 *   [缩略图] [项目信息] [操作]
 * 展开后展示全部资产卡片
 */

import { useCallback, useEffect, useState } from 'react'
import {
  Archive,
  ChevronDown,
  Database,
  Download,
  FileImage,
  FileText,
  FileType,
  Loader2,
  Presentation,
  RefreshCw,
  Tags,
  ArchiveRestore,
  CheckCircle2,
} from 'lucide-react'
import { WorkspaceHeader } from '@/components/WorkspaceHeader'
import {
  projectAssetsApi,
  type ProjectAssetFile,
  type ProjectAssetLibrary,
  type ProjectAssetSummary,
  API_BASE,
} from '@/lib/api'
import { cn } from '@/lib/utils'
import { Button } from '@/components/common/button'
import { Badge } from '@/components/common/badge'
import { FadeIn } from '@/components/motion/PageTransition'
import { EmptyStateIllustration } from '@/components/illustrations/PageBackgrounds'

/* ─── 文件类型配置 ─── */
const FILE_ICONS: Record<string, typeof FileText> = {
  doc: FileText,
  ppt: Presentation,
  presentation: FileType,
  keywords: Tags,
  image: FileImage,
  data: Database,
}

const KIND_LABELS: Record<string, string> = {
  doc: '文档',
  ppt: '演示 PPT',
  presentation: '幻灯片',
  keywords: '关键词',
  image: '图片',
  data: '数据',
}

function formatSize(bytes?: number): string {
  if (!bytes) return '—'
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${bytes} B`
}

async function downloadFile(url: string, filename: string) {
  const { ensureAuthToken } = await import('@/lib/api')
  const token = await ensureAuthToken()
  const headers: Record<string, string> = {}
  if (token) headers.Authorization = `Bearer ${token}`

  // 后端资产 URL 已含 /api/v1 前缀（/api/v1/files/...），仅对裸路径补 API_BASE
  const full = url.startsWith('http') || url.startsWith('/api/')
    ? url
    : `${API_BASE}${url}`
  const res = await fetch(full, { headers })
  if (!res.ok) throw new Error(`下载失败: HTTP ${res.status}`)
  const blob = await res.blob()
  const blobUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = filename
  a.click()
  URL.revokeObjectURL(blobUrl)
}

/* ─── PPT 缩略图（实际 SVG 渲染） ─── */
function PptThumbnail({ summary }: { summary: ProjectAssetSummary }) {
  // 用 svg_previews 第一张（如有），否则用 MockSlides
  const preview = summary.svg_previews?.[0]
  if (preview) {
    return (
      <div className="relative h-28 w-44 shrink-0 overflow-hidden rounded-lg border border-border bg-card shadow-elev-sm">
        <img
          src={preview}
          alt=""
          className="h-full w-full object-cover"
          loading="lazy"
        />
        {summary.has_pptx && (
          <span className="absolute right-1.5 top-1.5 border border-primary/40 bg-primary/15 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em] text-primary backdrop-blur">
            PPTX
          </span>
        )}
      </div>
    )
  }
  // MockSlides：抽象幻灯片
  return (
    <div className="relative h-28 w-44 shrink-0 overflow-hidden rounded-lg border border-border bg-card shadow-elev-sm">
      <div className="absolute inset-0 grid grid-cols-12 gap-0.5 p-1.5">
        {/* 模拟 4 张幻灯片 */}
        {Array.from({ length: 12 }).map((_, i) => (
          <div
            key={i}
            className="bg-gradient-to-br from-primary/15 to-accent/10"
            style={{
              borderRadius: '2px',
            }}
          />
        ))}
      </div>
      <div className="absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-background/90 via-background/30 to-transparent p-2">
        <div className="space-y-0.5">
          <div className="h-1.5 w-3/4 rounded-full bg-foreground/80" />
          <div className="h-1 w-1/2 rounded-full bg-foreground/50" />
        </div>
      </div>
      {summary.has_pptx && (
        <span className="absolute right-1.5 top-1.5 border border-primary/40 bg-primary/15 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.14em] text-primary backdrop-blur">
          PPTX
        </span>
      )}
    </div>
  )
}

/* ─── 摘要列表项 ─── */
function LibraryCard({
  summary,
  onOpen,
  isOpen,
}: {
  summary: ProjectAssetSummary
  onOpen: () => void
  isOpen: boolean
}) {
  const updated = summary.updated_at ? new Date(summary.updated_at) : null
  return (
    <div
      className={cn(
        'group relative grid grid-cols-[auto_1fr_auto] items-center gap-5 rounded-xl border bg-card p-4 shadow-elev-sm transition-all duration-200 lift-on-hover',
        isOpen
          ? 'border-primary/50 ring-1 ring-primary/30 shadow-elev-md'
          : 'border-border hover:border-primary/40',
      )}
    >
      {/* 左侧：PPT 缩略图 */}
      <div className="shrink-0">
        <PptThumbnail summary={summary} />
      </div>

      {/* 中段：项目信息 */}
      <div className="min-w-0">
        <div className="mb-1.5 flex flex-wrap items-center gap-2">
          <Badge
            variant={
              summary.status === 'completed'
                ? 'success'
                : summary.status === 'failed'
                  ? 'destructive'
                  : summary.status === 'paused'
                    ? 'warning'
                    : 'processing'
            }
          >
            {summary.status === 'completed'
              ? '已完成'
              : summary.status === 'failed'
                ? '失败'
                : summary.status === 'paused'
                  ? '已暂停'
                  : '运行中'}
          </Badge>
          {summary.has_keywords && (
            <Badge variant="info">关键词</Badge>
          )}
          {summary.has_presentation && (
            <Badge variant="default">演示</Badge>
          )}
        </div>
        <h3 className="truncate font-serif text-[16px] font-semibold tracking-tight text-foreground">
          {summary.idea}
        </h3>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px] text-muted-foreground">
          <span>
            <span className="text-primary">{summary.file_count}</span> 个文件
          </span>
          <span className="text-border">·</span>
          <span>
            <span className="text-secondary">{formatSize(summary.total_size)}</span>
          </span>
          {updated && (
            <>
              <span className="text-border">·</span>
              <span>
                更新于{' '}
                {updated.toLocaleDateString('zh-CN', {
                  month: '2-digit',
                  day: '2-digit',
                })}{' '}
                {updated.toLocaleTimeString('zh-CN', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            </>
          )}
        </div>
        <div className="mt-2 flex flex-wrap gap-2 text-[10px]">
          {summary.doc_count > 0 && (
            <span className="font-mono uppercase tracking-[0.14em] text-muted-foreground">
              文档 ·{' '}
              <span className="text-primary">{summary.doc_count}</span>
            </span>
          )}
          {summary.ppt_count > 0 && (
            <span className="font-mono uppercase tracking-[0.14em] text-muted-foreground">
              PPT · <span className="text-primary">{summary.ppt_count}</span>
            </span>
          )}
          {summary.presentation_count > 0 && (
            <span className="font-mono uppercase tracking-[0.14em] text-muted-foreground">
              幻灯 ·{' '}
              <span className="text-primary">{summary.presentation_count}</span>
            </span>
          )}
          {summary.keywords_count > 0 && (
            <span className="font-mono uppercase tracking-[0.14em] text-muted-foreground">
              关键词 ·{' '}
              <span className="text-primary">{summary.keywords_count}</span>
            </span>
          )}
          {summary.image_count > 0 && (
            <span className="font-mono uppercase tracking-[0.14em] text-muted-foreground">
              图片 ·{' '}
              <span className="text-primary">{summary.image_count}</span>
            </span>
          )}
        </div>
      </div>

      {/* 右侧：操作 */}
      <div className="flex shrink-0 items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() =>
            projectAssetsApi
              .downloadUrl(summary.product_id)
              .then((url) =>
                downloadFile(
                  url,
                  `project_assets_${summary.product_id.slice(0, 8)}.zip`,
                ),
              )
              .catch(() => {})
          }
          disabled={summary.file_count === 0}
        >
          <ArchiveRestore className="h-3.5 w-3.5" />
          ZIP
        </Button>
        <Button
          variant={isOpen ? 'secondary' : 'default'}
          size="sm"
          onClick={onOpen}
        >
          {isOpen ? (
            <>
              <ChevronDown className="h-3.5 w-3.5" />
              收起
            </>
          ) : (
            <>
              <ChevronDown className="h-3.5 w-3.5 -rotate-90" />
              展开
            </>
          )}
        </Button>
      </div>
    </div>
  )
}

/* ─── 资产明细 ─── */
function LibraryDetail({
  detail,
  onDownloadZip,
  downloading,
}: {
  detail: ProjectAssetLibrary
  onDownloadZip: () => void
  downloading: boolean
}) {
  return (
    <div className="mt-3 rounded-xl border border-primary/30 bg-card/60 p-5 shadow-elev-md animate-fade-in-up">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
        <div>
          <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
            资产库明细
          </div>
          <div className="mt-0.5 flex items-baseline gap-3">
            <span className="font-serif text-base font-semibold text-foreground">
              {detail.idea}
            </span>
            <span className="font-mono text-[11px] text-muted-foreground">
              {detail.files.length} 个文件 · {formatSize(detail.total_size)}
            </span>
          </div>
        </div>
        <Button onClick={onDownloadZip} disabled={downloading || detail.files.length === 0}>
          {downloading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <ArchiveRestore className="h-3.5 w-3.5" />
          )}
          打包下载 ZIP
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {detail.files.map((file, i) => (
          <div
            key={`${file.url}-${i}`}
            className="group overflow-hidden rounded-lg border border-border bg-background/50 transition-all hover:border-primary/40 hover:shadow-elev-xs"
          >
            {/* 预览缩略图（矩阵图/章节图/设计图等，有 preview_url 即渲染） */}
            {file.preview_url && (
              <button
                type="button"
                onClick={() =>
                  downloadFile(file.url, file.name).catch(() => {})
                }
                className="block w-full"
                title={`预览/下载 ${file.name}`}
              >
                <div className="aspect-video w-full overflow-hidden border-b border-border bg-secondary/30">
                  <img
                    src={file.preview_url}
                    alt={file.name}
                    loading="lazy"
                    className="h-full w-full object-contain"
                    onError={(e) => {
                      ;(e.target as HTMLImageElement).parentElement!.style.display =
                        'none'
                    }}
                  />
                </div>
              </button>
            )}
            <div className="flex items-center gap-3 p-3">
              <div className="flex h-10 w-12 shrink-0 items-center justify-center rounded-md border border-border bg-secondary/40 text-muted-foreground">
                {(() => {
                  const Icon = FILE_ICONS[file.kind] ?? FileText
                  return <Icon className="h-4 w-4" />
                })()}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13px] font-medium text-foreground">
                  {file.name}
                </div>
                <div className="font-mono text-[10px] uppercase text-muted-foreground">
                  {KIND_LABELS[file.kind] ?? file.kind} · {formatSize(file.size)}
                  {file.preview_urls && file.preview_urls.length > 0
                    ? ` · ${file.preview_urls.length} 页预览`
                    : ''}
                </div>
              </div>
              <button
                type="button"
                onClick={() => downloadFile(file.url, file.name).catch(() => {})}
                className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                aria-label={`下载 ${file.name}`}
                title="下载"
              >
                <Download className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export function ProjectAssetLibraryPage() {
  const [libraries, setLibraries] = useState<ProjectAssetSummary[]>([])
  const [details, setDetails] = useState<Record<string, ProjectAssetLibrary>>({})
  const [openId, setOpenId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    setRefreshing(true)
    try {
      setError('')
      const list = await projectAssetsApi.list()
      setLibraries(list)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载资产库失败')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // 加载展开项的明细
  useEffect(() => {
    if (!openId || details[openId]) return
    let cancelled = false
    projectAssetsApi
      .get(openId)
      .then((d) => {
        if (!cancelled) setDetails((prev) => ({ ...prev, [openId]: d }))
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : '加载资产明细失败')
      })
    return () => {
      cancelled = true
    }
  }, [openId, details])

  const handleDownloadZip = async () => {
    if (!openId) return
    setDownloading(true)
    try {
      const url = await projectAssetsApi.downloadUrl(openId)
      await downloadFile(url, `project_assets_${openId.slice(0, 8)}.zip`)
    } catch (err) {
      setError(err instanceof Error ? err.message : '打包下载失败')
    } finally {
      setDownloading(false)
    }
  }

  const totalFiles = libraries.reduce((s, l) => s + l.file_count, 0)
  const totalSize = libraries.reduce((s, l) => s + l.total_size, 0)

  return (
    <FadeIn>
      <WorkspaceHeader
        crumb="LIBRARY · 项目资产库"
        title="项目资产库"
        description="每个 Product Studio 任务的全部资产归档：研究报告 / 竞品矩阵 / PRD / 路线图 / 演示 PPT / 关键词 / 设计图。每条资产左侧展示 PPT 缩略图，中段展示项目简介，右侧打包下载或展开明细。"
      />

      {/* 顶部统计 */}
      {!loading && libraries.length > 0 && (
        <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
          <div className="rounded-lg border border-border bg-card p-4 shadow-elev-sm">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">任务</div>
            <div className="mt-1 font-display text-2xl font-semibold text-primary">{libraries.length}</div>
          </div>
          <div className="rounded-lg border border-border bg-card p-4 shadow-elev-sm">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">文件</div>
            <div className="mt-1 font-display text-2xl font-semibold text-primary">{totalFiles}</div>
          </div>
          <div className="rounded-lg border border-border bg-card p-4 shadow-elev-sm">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">总大小</div>
            <div className="mt-1 font-display text-2xl font-semibold text-primary">{formatSize(totalSize)}</div>
          </div>
          <div className="rounded-lg border border-border bg-card p-4 shadow-elev-sm">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">已打包</div>
            <div className="mt-1 flex items-baseline gap-1">
              <CheckCircle2 className="h-5 w-5 text-success" />
              <span className="font-display text-2xl font-semibold text-success">
                {libraries.filter((l) => l.has_pptx).length}
              </span>
              <span className="text-xs text-muted-foreground">PPTX</span>
            </div>
          </div>
        </div>
      )}

      <div className="mb-6 flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          共 <span className="font-mono font-semibold text-foreground">{libraries.length}</span> 个任务
        </div>
        <Button variant="outline" size="sm" onClick={() => load()} disabled={loading}>
          <RefreshCw className={cn('h-3.5 w-3.5', refreshing && 'animate-spin')} />
          刷新
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-24 font-mono text-[12px] uppercase tracking-[0.18em] text-muted-foreground">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          加载项目资产库
          <span className="typing-dot" />
          <span className="typing-dot" />
          <span className="typing-dot" />
        </div>
      ) : error ? (
        <div className="border border-destructive/40 bg-destructive/10 px-5 py-3 font-mono text-[12px] text-destructive">
          <span className="font-semibold">[ERROR]</span> {error}
        </div>
      ) : libraries.length === 0 ? (
        <div className="flex min-h-[360px] flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card/40 text-center">
          <EmptyStateIllustration className="text-muted-foreground/40" />
          <p className="mt-4 text-sm font-medium">暂无项目资产</p>
          <p className="mt-1 max-w-md text-xs text-muted-foreground">
            完成 Product Studio 任务后，所有产出（研究 / 竞品 / PRD / 设计 / 演示）都会按任务归档到此处。
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {libraries.map((summary) => (
            <div key={summary.product_id}>
              <LibraryCard
                summary={summary}
                isOpen={openId === summary.product_id}
                onOpen={() =>
                  setOpenId((curr) =>
                    curr === summary.product_id ? null : summary.product_id,
                  )
                }
              />
              {openId === summary.product_id && (
                <>
                  {details[summary.product_id] ? (
                    <LibraryDetail
                      detail={details[summary.product_id]}
                      onDownloadZip={handleDownloadZip}
                      downloading={downloading}
                    />
                  ) : (
                    <div className="mt-3 flex items-center justify-center rounded-xl border border-border bg-card/60 p-8 font-mono text-[12px] uppercase tracking-[0.18em] text-muted-foreground">
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      加载资产明细
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </FadeIn>
  )
}