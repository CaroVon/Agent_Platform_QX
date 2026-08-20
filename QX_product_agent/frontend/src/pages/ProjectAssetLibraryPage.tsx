/**
 * ProjectAssetLibraryPage —— 项目资产库
 * 每个任务（产品）的全部资产归档：
 *   - 文本资产自动转化为 PDF / MD（需求 / 研究 / 竞品 / 策略PRD / UX设计 / 演示文案）
 *   - PPT 按现有模式产出（ppt-master 原生 PPTX + SVG 预览）
 *   - 设计图 / 上传素材一并归档
 * 支持单文件下载 与 ZIP 打包下载。
 */

import { useCallback, useEffect, useState } from 'react'
import {
  Archive,
  ChevronDown,
  Download,
  ExternalLink,
  FileImage,
  FileText,
  FileType,
  Loader2,
  Presentation,
  RefreshCw,
  Tags,
} from 'lucide-react'
import { WorkspaceHeader } from '@/components/WorkspaceHeader'
import { projectAssetsApi } from '@/lib/api'
import type { ProjectAssetFile, ProjectAssetSummary } from '@/types/studio'

const STATUS_META: Record<string, { label: string; cls: string }> = {
  running: { label: '进行中', cls: 'bg-[#24415E]/10 text-[#24415E]' },
  queued: { label: '排队中', cls: 'bg-slate-500/10 text-slate-500' },
  paused: { label: '已暂停', cls: 'bg-amber-500/10 text-amber-700' },
  completed: { label: '已完成', cls: 'bg-emerald-500/10 text-emerald-600' },
  failed: { label: '失败', cls: 'bg-destructive/10 text-destructive' },
  waiting_approval: { label: '待批准', cls: 'bg-sky-500/10 text-sky-600' },
}

const FILE_ICONS: Record<string, typeof FileText> = {
  doc: FileText,
  ppt: Presentation,
  presentation: FileType,
  keywords: Tags,
  image: FileImage,
}

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${bytes} B`
}

function AssetThumbnail({ file }: { file: ProjectAssetFile }) {
  const preview = file.preview_url || file.preview_urls?.[0]
  if (preview && (file.kind === 'image' || file.kind === 'ppt')) {
    return (
      <div className="h-14 w-24 shrink-0 overflow-hidden rounded-md border bg-white">
        <img src={preview} alt="" className="h-full w-full object-cover" loading="lazy" />
      </div>
    )
  }
  const Icon = FILE_ICONS[file.kind] ?? FileText
  return (
    <div className="flex h-14 w-24 shrink-0 flex-col items-center justify-center gap-1 rounded-md border bg-secondary/40 text-muted-foreground">
      <Icon className="h-5 w-5" />
      <span className="max-w-[5rem] truncate text-[9px]">
        {file.kind === 'doc' ? (file.name.endsWith('.pdf') ? 'PDF 文档' : 'Markdown 文档') : file.category}
      </span>
    </div>
  )
}

/** 触发 Blob 下载（带鉴权） */
function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function ProjectAssetLibraryPage() {
  const [libraries, setLibraries] = useState<ProjectAssetSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [detail, setDetail] = useState<Record<string, { files: ProjectAssetFile[]; total_size: number; loading: boolean }>>({})
  const [zipBusy, setZipBusy] = useState('')

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      setError('')
      setRefreshing(true)
      setLibraries(await projectAssetsApi.list())
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载项目资产库失败')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const toggleExpand = useCallback(async (productId: string) => {
    const willExpand = !expanded[productId]
    setExpanded((prev) => ({ ...prev, [productId]: willExpand }))
    if (!willExpand) return
    if (detail[productId]) return
    setDetail((prev) => ({ ...prev, [productId]: { files: [], total_size: 0, loading: true } }))
    try {
      const data = await projectAssetsApi.get(productId)
      setDetail((prev) => ({
        ...prev,
        [productId]: { files: data.files, total_size: data.total_size, loading: false },
      }))
    } catch (err) {
      setDetail((prev) => ({
        ...prev,
        [productId]: { files: [], total_size: 0, loading: false },
      }))
      setError(err instanceof Error ? err.message : '加载任务资产失败')
    }
  }, [expanded, detail])

  const handleZip = async (lib: ProjectAssetSummary) => {
    setZipBusy(lib.product_id)
    try {
      const blob = await projectAssetsApi.downloadZip(lib.product_id)
      const safe = (lib.idea || lib.product_id).slice(0, 20).replace(/[\\/:*?"<>|]/g, '_')
      triggerBlobDownload(blob, `项目资产_${safe}.zip`)
    } catch (err) {
      setError(err instanceof Error ? err.message : '打包下载失败')
    } finally {
      setZipBusy('')
    }
  }

  const grouped = (files: ProjectAssetFile[]): Array<[string, ProjectAssetFile[]]> => {
    const order = ['文档', '演示文稿', '关键词', '设计图片', '素材']
    const map = new Map<string, ProjectAssetFile[]>()
    for (const f of files) {
      const list = map.get(f.category) ?? []
      list.push(f)
      map.set(f.category, list)
    }
    return [...map.entries()].sort(
      (a, b) => order.indexOf(a[0]) - order.indexOf(b[0]),
    )
  }

  return (
    <div>
      <WorkspaceHeader
        crumb="管理 · 资产"
        title="项目资产库"
        description="每个任务的完整资产归档：文本资产自动产出 PDF / MD，演示文稿按现有模式产出 PPTX，支持单文件下载与打包下载。"
      />
      <div className="mb-6 flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          共 <span className="font-semibold text-foreground">{libraries.length}</span>{' '}
          个任务的资产库
        </div>
        <button
          type="button"
          onClick={() => load(true)}
          disabled={refreshing}
          className="flex items-center gap-2 rounded-lg border bg-card px-4 py-2 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          刷新
        </button>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-24 text-muted-foreground">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" /> 加载项目资产库…
        </div>
      )}
      {error && (
        <div className="mb-5 rounded-xl border border-destructive/30 bg-destructive/5 px-5 py-3.5 text-sm text-destructive">
          {error}
        </div>
      )}
      {!loading && !error && libraries.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed bg-card/40 py-24 text-center">
          <Archive className="mb-3 h-8 w-8 text-muted-foreground/40" />
          <p className="text-sm font-medium">暂无项目资产</p>
          <p className="mt-1 max-w-md text-xs text-muted-foreground">
            在 Product Workspace 输入产品想法并运行流水线后，该任务的文本资产
            （PDF/MD）、PPTX 与设计图会自动归档到这里。
          </p>
        </div>
      )}

      {!loading && !error && libraries.length > 0 && (
        <div className="space-y-4">
          {libraries.map((lib) => {
            const meta = STATUS_META[lib.status] ?? STATUS_META.failed
            const isOpen = Boolean(expanded[lib.product_id])
            const det = detail[lib.product_id]
            const files = det?.files ?? []
            return (
              <div
                key={lib.product_id}
                className="overflow-hidden rounded-2xl border bg-card shadow-sm transition-shadow hover:shadow-md"
              >
                {/* ── 任务概要 ── */}
                <div className="flex flex-wrap items-center gap-4 p-5">
                  {lib.svg_previews.length > 0 && (
                    <div className="hidden h-20 w-32 shrink-0 gap-1 overflow-hidden rounded-lg sm:flex">
                      {lib.svg_previews.slice(0, 3).map((src) => (
                        <img
                          key={src}
                          src={src}
                          alt=""
                          className="h-full w-full object-cover"
                          loading="lazy"
                        />
                      ))}
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="line-clamp-1 text-sm font-semibold leading-snug">
                        {lib.idea || '（未命名任务）'}
                      </h3>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${meta.cls}`}>
                        {meta.label}
                      </span>
                    </div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
                      <span>{lib.doc_count} 份文档（MD/PDF）</span>
                      {lib.has_pptx && <span>{lib.ppt_count} 份演示文稿（PPTX）</span>}
                      {lib.presentation_count > 0 && (
                        <span>{lib.presentation_count} 份 Web 演示</span>
                      )}
                      {(lib.keywords_count ?? 0) > 0 && <span>{lib.keywords_count} 份 Keywords</span>}
                      <span>{lib.image_count} 张图片</span>
                      <span>共 {formatSize(lib.total_size)}</span>
                      {lib.updated_at && (
                        <span>{new Date(lib.updated_at).toLocaleString()}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleZip(lib)}
                      disabled={zipBusy === lib.product_id || lib.file_count === 0}
                      className="flex items-center gap-1.5 rounded-lg bg-[#24415E] px-4 py-2 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
                      title={lib.file_count === 0 ? '任务暂无资产' : '打包下载全部资产'}
                    >
                      {zipBusy === lib.product_id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Archive className="h-3.5 w-3.5" />
                      )}
                      打包下载
                    </button>
                    <button
                      type="button"
                      onClick={() => toggleExpand(lib.product_id)}
                      className="flex items-center gap-1 rounded-lg border bg-card px-3 py-2 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
                    >
                      资产清单
                      <ChevronDown className={`h-3.5 w-3.5 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                    </button>
                  </div>
                </div>

                {/* ── 资产清单（按类别分组，单文件下载） ── */}
                {isOpen && (
                  <div className="border-t bg-background/40 px-5 py-4">
                    {det?.loading ? (
                      <div className="flex items-center justify-center py-8 text-xs text-muted-foreground">
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> 生成文本资产并扫描磁盘…
                      </div>
                    ) : files.length === 0 ? (
                      <p className="py-4 text-center text-xs text-muted-foreground">
                        该任务暂无资产。
                      </p>
                    ) : (
                      <div className="space-y-4">
                        {grouped(files).map(([category, items]) => (
                          <div key={category}>
                            <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">
                              {category}
                              <span className="ml-2 font-normal normal-case tracking-normal text-muted-foreground/50">
                                {items.length} 个文件
                              </span>
                            </div>
                            <div className="overflow-hidden rounded-xl border">
                              {items.map((file, idx) => {
                                return (
                                  <div
                                    key={`${file.path}-${idx}`}
                                    className="flex items-center gap-3 border-b bg-card px-4 py-2.5 text-xs last:border-b-0"
                                  >
                                    <AssetThumbnail file={file} />
                                    <div className="min-w-0 flex-1">
                                      <div className="truncate font-medium" title={file.name}>
                                        {file.name}
                                      </div>
                                      <div className="text-[10px] text-muted-foreground/60">
                                        {file.generated ? '自动产出 · ' : ''}
                                        {formatSize(file.size)}
                                        {file.kind === 'ppt' && file.pages ? ` · ${file.pages} 页` : ''}
                                      </div>
                                    </div>
                                    <a
                                      href={file.url}
                                      download={file.name}
                                      className="flex shrink-0 items-center gap-1 rounded-md border bg-card px-2.5 py-1.5 font-medium text-muted-foreground transition-colors hover:text-foreground"
                                    >
                                      <Download className="h-3 w-3" /> 下载
                                    </a>
                                    {file.viewer_url && (
                                      <a
                                        href={file.viewer_url}
                                        className="flex shrink-0 items-center gap-1 rounded-md border border-[#24415E]/20 bg-card px-2.5 py-1.5 font-medium text-[#24415E] transition-colors hover:bg-[#24415E]/5"
                                      >
                                        <ExternalLink className="h-3 w-3" /> 打开演示
                                      </a>
                                    )}
                                  </div>
                                )
                              })}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
