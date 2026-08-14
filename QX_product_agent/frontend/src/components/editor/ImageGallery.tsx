/**
 * ============================================================
 * ImageGallery —— 图片搜索与预览库面板
 *
 * 位于 Canvas 编辑器下方，提供：
 * - 图片搜索（DuckDuckGo），带搜索强度控制
 * - 缩略图预览网格（支持拖拽到画布）
 * - 持久化存储（按项目隔离，刷新后保留）
 * ============================================================
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Search,
  ChevronDown,
  ChevronUp,
  X,
  Image as ImageIcon,
  Loader2,
  Trash2,
  RefreshCw,
} from 'lucide-react'
import { Button } from '@/components/common/button'
import { cn } from '@/lib/utils'
import { projectsApi } from '@/lib/api'
import type { ImageResult } from '@/types/api'

// ══════════════════════════════════════════════════════════════
// 搜索强度选项
// ══════════════════════════════════════════════════════════════

const SEARCH_DEPTH_OPTIONS = [
  { value: 5, label: '快速', desc: '~2 张' },
  { value: 10, label: '标准', desc: '~4 张' },
  { value: 15, label: '深度', desc: '~6 张' },
  { value: 20, label: '极致', desc: '~8 张' },
] as const

// ══════════════════════════════════════════════════════════════
// Props
// ══════════════════════════════════════════════════════════════

interface ImageGalleryProps {
  projectId: string
  className?: string
  /** 🆕 当前激活的幻灯片页码（0-based），用于自动滚动到对应图片 */
  activePage?: number
  /** 🆕 项目状态，用于空状态上下文提示 */
  projectStatus?: string
  /** 🆕 每页自动搜索图片数，用于空状态上下文提示 */
  imagesPerPage?: number
}

// ══════════════════════════════════════════════════════════════
// 空状态上下文提示 — 根据项目状态给出不同的说明
// ══════════════════════════════════════════════════════════════

const EARLY_STAGES = [
  'preparing_data',
  'waiting_for_sources',
  'preparing_outline',
  'waiting_for_outline',
]

function getEmptyStateMessage(
  projectStatus?: string,
  imagesPerPage?: number,
): { title: string; hint: string } {
  if (!projectStatus || EARLY_STAGES.includes(projectStatus)) {
    return {
      title: '暂无图片素材',
      hint: '项目尚未开始 AI 撰写，图片将在撰写阶段自动搜索添加。您也可以使用下方搜索栏手动搜索图片。',
    }
  }
  if (projectStatus === 'drafting') {
    return {
      title: '图片加载中…',
      hint: 'AI 正在撰写报告并自动搜索相关图片，新图片将陆续出现在此处。您也可以使用搜索栏手动搜索。',
    }
  }
  if (projectStatus === 'completed' && imagesPerPage === 0) {
    return {
      title: '自动图片搜索已关闭',
      hint: '该项目创建时关闭了"每页图片"自动搜索。您可以使用搜索栏手动搜索图片素材。',
    }
  }
  if (projectStatus === 'completed') {
    return {
      title: '未找到图片素材',
      hint: 'AI 自动搜索未找到相关图片。您可以使用搜索栏手动搜索、或尝试不同的关键词。',
    }
  }
  // failed / unknown states
  return {
    title: '暂无图片素材',
    hint: '搜索关键词以添加图片到素材库',
  }
}

// ══════════════════════════════════════════════════════════════
// 缩略图渲染辅助（提取复用）
// ══════════════════════════════════════════════════════════════

function renderThumb(
  img: ImageResult,
  key: string,
  onDragStart: (e: React.DragEvent, img: ImageResult) => void,
  onDelete: (imageId: string) => void,
) {
  return (
    <div
      key={key}
      className="group relative flex-shrink-0 cursor-grab active:cursor-grabbing"
      draggable
      onDragStart={(e) => onDragStart(e, img)}
      title={img.title || img.query}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={img.image_url}
        alt={img.title || img.query}
        className="h-[68px] w-[120px] object-cover rounded border border-border
                   group-hover:ring-1 group-hover:ring-primary/50 transition-shadow"
        loading="lazy"
        onError={(e) => {
          ;(e.target as HTMLImageElement).style.display = 'none'
          const placeholder = (e.target as HTMLImageElement).nextElementSibling
          if (placeholder) {
            ;(placeholder as HTMLElement).style.display = 'flex'
          }
        }}
      />
      <div
        className="hidden h-[68px] w-[120px] items-center justify-center
                    rounded border border-border bg-muted"
      >
        <ImageIcon className="h-5 w-5 text-muted-foreground opacity-50" />
      </div>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          onDelete(img.id)
        }}
        className="absolute -top-1.5 -right-1.5 h-5 w-5 rounded-full bg-destructive
                   text-destructive-foreground opacity-0 group-hover:opacity-100
                   transition-opacity flex items-center justify-center shadow-sm"
        title="删除"
      >
        <Trash2 className="h-3 w-3" />
      </button>
      <div
        className="absolute bottom-1 left-1 text-[10px] px-1 py-0.5 rounded
                    bg-black/50 text-white truncate max-w-[110px] opacity-0
                    group-hover:opacity-100 transition-opacity"
      >
        {img.query}
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════
// 组件
// ══════════════════════════════════════════════════════════════

export function ImageGallery({ projectId, className, activePage, projectStatus, imagesPerPage }: ImageGalleryProps) {
  const [collapsed, setCollapsed] = useState(() => {
    // 持久化折叠状态
    try {
      return localStorage.getItem('imageGalleryCollapsed') === 'true'
    } catch {
      return false
    }
  })
  const [query, setQuery] = useState('')
  const [searchDepth, setSearchDepth] = useState(10)
  const [images, setImages] = useState<ImageResult[]>([])
  const [searching, setSearching] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchHint, setSearchHint] = useState<string | null>(null)
  const searchHintTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  // 🆕 按页码索引的图片 DOM 引用
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map())

  // ── 搜索提示自动消失 ──────────────────────────────────────
  const showSearchHint = useCallback((msg: string) => {
    if (searchHintTimerRef.current) clearTimeout(searchHintTimerRef.current)
    setSearchHint(msg)
    searchHintTimerRef.current = setTimeout(() => setSearchHint(null), 5000)
  }, [])

  // ── 加载已有图片库 ──────────────────────────────────────────
  const loadImages = useCallback(async () => {
    if (!projectId) return
    try {
      setLoading(true)
      setError(null)
      const data = await projectsApi.getProjectImages(projectId)
      setImages(data.images || [])
    } catch (err: any) {
      setError(err?.message || '加载图片库失败')
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    loadImages()
  }, [loadImages])

  // cleanup searchHint timer
  useEffect(() => {
    return () => {
      if (searchHintTimerRef.current) clearTimeout(searchHintTimerRef.current)
    }
  }, [])

  // 🆕 切换幻灯片时自动滚动到对应页码的图片
  useEffect(() => {
    if (activePage === undefined || !scrollContainerRef.current) return
    // 先尝试精确匹配页码
    let targetEl = pageRefs.current.get(activePage)
    if (!targetEl) {
      // 查找最近的前一个页码组
      const sortedPages = [...pageRefs.current.keys()].sort((a, b) => a - b)
      let nearestPage: number | null = null
      for (const p of sortedPages) {
        if (p <= activePage) nearestPage = p
        else break
      }
      if (nearestPage !== null) targetEl = pageRefs.current.get(nearestPage)
    }
    if (targetEl) {
      targetEl.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
    }
  }, [activePage, images.length])

  // ── 撰写中自动轮询（每 15 秒刷新一次图片列表）────────────────
  useEffect(() => {
    if (projectStatus !== 'drafting') return
    const interval = setInterval(() => {
      loadImages()
    }, 15_000)
    return () => clearInterval(interval)
  }, [projectStatus, loadImages])

  // ── 执行搜索 ────────────────────────────────────────────────
  const handleSearch = useCallback(async () => {
    const trimmed = query.trim()
    if (!trimmed || !projectId) return

    try {
      setSearching(true)
      setError(null)
      setSearchHint(null)
      const data = await projectsApi.searchImages(projectId, {
        query: trimmed,
        search_depth: searchDepth,
      })
      if (data.images.length === 0) {
        // 搜索成功但无结果 — 用提示而不是报错
        showSearchHint(`未找到与「${trimmed}」相关的图片，试试其他关键词`)
      } else {
        // 将新结果前置
        setImages((prev) => {
          const existingIds = new Set(prev.map((img) => img.id))
          const newOnes = data.images.filter((img) => !existingIds.has(img.id))
          return [...newOnes, ...prev]
        })
      }
    } catch (err: any) {
      // 区分不同类型的失败
      if (err?.status) {
        if (err.status >= 500) {
          setError('搜索服务异常，请稍后重试')
        } else if (err.status === 404) {
          setError('项目不存在或已被删除')
        } else {
          setError(err.message || '图片搜索失败')
        }
      } else {
        setError('网络连接失败，请检查网络和服务状态')
      }
    } finally {
      setSearching(false)
    }
  }, [query, searchDepth, projectId, showSearchHint])

  // ── 删除图片 ────────────────────────────────────────────────
  const handleDelete = useCallback(
    async (imageId: string) => {
      try {
        await projectsApi.deleteProjectImage(projectId, imageId)
        setImages((prev) => prev.filter((img) => img.id !== imageId))
      } catch (err: any) {
        setError(err?.message || '删除失败')
      }
    },
    [projectId],
  )

  // ── Enter 键搜索 ────────────────────────────────────────────
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSearch()
    }
  }

  // ── 拖拽开始 ────────────────────────────────────────────────
  const handleDragStart = (e: React.DragEvent, img: ImageResult) => {
    e.dataTransfer.setData(
      'application/json',
      JSON.stringify({
        imageUrl: img.image_url,
        title: img.title,
        query: img.query,
      }),
    )
    e.dataTransfer.effectAllowed = 'copy'
  }

  // ── 切换折叠 ────────────────────────────────────────────────
  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev
      try {
        localStorage.setItem('imageGalleryCollapsed', String(next))
      } catch { /* ignore */ }
      return next
    })
  }

  return (
    <div className={cn('border-t border-border bg-card', className)}>
      {/* ── 标题栏 ─────────────────────────────────────────── */}
      <div
        role="button"
        tabIndex={0}
        onClick={toggleCollapsed}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            toggleCollapsed()
          }
        }}
        className="flex w-full items-center gap-2 px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted/50 transition-colors cursor-pointer"
      >
        <ImageIcon className="h-4 w-4" />
        <span>图片素材库</span>
        {images.length > 0 && (
          <span className="text-xs rounded-full bg-primary/10 text-primary px-1.5 py-0.5">
            {images.length}
          </span>
        )}
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            loadImages()
          }}
          className="p-1 rounded hover:bg-muted transition-colors"
          title="刷新图片库"
        >
          <RefreshCw className="h-3.5 w-3.5 text-muted-foreground" />
        </button>
        <span className="ml-auto">
          {collapsed ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </span>
      </div>

      {!collapsed && (
        <div className="px-4 pb-3 space-y-3">
          {/* ── 搜索栏 ─────────────────────────────────────── */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                ref={searchInputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="搜索图片素材…"
                className="w-full rounded-md border border-input bg-background pl-8 pr-3 py-1.5 text-sm
                           placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <Button
              size="sm"
              onClick={handleSearch}
              disabled={searching || !query.trim()}
            >
              {searching ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                '搜索'
              )}
            </Button>
          </div>

          {/* ── 搜索强度选择器 ─────────────────────────────── */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted-foreground whitespace-nowrap">
              强度:
            </span>
            <div className="flex gap-1">
              {SEARCH_DEPTH_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setSearchDepth(opt.value)}
                  className={cn(
                    'px-2 py-0.5 rounded text-xs transition-colors',
                    searchDepth === opt.value
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground hover:bg-muted/70',
                  )}
                  title={opt.desc}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* ── 错误提示 ───────────────────────────────────── */}
          {error && (
            <div className="text-xs text-destructive flex items-center gap-1">
              <span>{error}</span>
              <button
                type="button"
                onClick={() => setError(null)}
                className="ml-auto hover:underline"
              >
                关闭
              </button>
            </div>
          )}

          {/* ── 搜索提示（非错误） ──────────────────────────── */}
          {searchHint && !error && (
            <div className="text-xs text-amber-600 flex items-center gap-1 bg-amber-50 rounded px-2 py-1">
              <span>{searchHint}</span>
              <button
                type="button"
                onClick={() => setSearchHint(null)}
                className="ml-auto hover:underline"
              >
                关闭
              </button>
            </div>
          )}

          {/* ── 图片网格 ───────────────────────────────────── */}
          {loading ? (
            <div className="flex items-center justify-center py-6 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              加载中…
            </div>
          ) : images.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-6 text-sm text-muted-foreground gap-1">
              <ImageIcon className="h-8 w-8 opacity-30" />
              <span>{getEmptyStateMessage(projectStatus, imagesPerPage).title}</span>
              <span className="text-xs text-center max-w-xs">
                {getEmptyStateMessage(projectStatus, imagesPerPage).hint}
              </span>
              <button
                type="button"
                onClick={() => loadImages()}
                className="mt-2 inline-flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <RefreshCw className="h-3 w-3" />
                刷新
              </button>
            </div>
          ) : (
            <div ref={scrollContainerRef} className="flex gap-2 overflow-x-auto pb-1 scrollbar-thin">
              {(() => {
                // 🆕 按页码分组：手动搜索（null）→ 按 page_number 升序
                const grouped = new Map<number | string, ImageResult[]>()
                const manual: ImageResult[] = []
                for (const img of images) {
                  if (img.page_number != null) {
                    const key = img.page_number
                    if (!grouped.has(key)) grouped.set(key, [])
                    grouped.get(key)!.push(img)
                  } else {
                    manual.push(img)
                  }
                }
                const sortedPages = [...grouped.keys()].sort((a, b) => Number(a) - Number(b))
                const thumbEls: React.ReactNode[] = []

                // 手动搜索的图片（无页码关联）
                manual.forEach((img) => {
                  thumbEls.push(renderThumb(img, img.id, handleDragStart, handleDelete))
                })

                // 按页码分组的图片
                sortedPages.forEach((pageNum) => {
                  const pageImgs = grouped.get(pageNum)!
                  thumbEls.push(
                    <div
                      key={`page-label-${pageNum}`}
                      ref={(el) => {
                        if (el) pageRefs.current.set(Number(pageNum), el)
                        else pageRefs.current.delete(Number(pageNum))
                      }}
                      className="flex-shrink-0 flex items-center justify-center w-6 text-[10px] font-medium text-muted-foreground bg-muted/50 rounded border border-border/50 px-1"
                      title={`第 ${Number(pageNum) + 1} 页的图片`}
                    >
                      P{Number(pageNum) + 1}
                    </div>,
                  )
                  pageImgs.forEach((img) => {
                    thumbEls.push(renderThumb(img, img.id, handleDragStart, handleDelete))
                  })
                })

                return thumbEls
              })()}
            </div>
          )}

          {/* ── 提示文字 ───────────────────────────────────── */}
          {images.length > 0 && (
            <p className="text-[11px] text-muted-foreground">
              拖拽图片到画布以添加到当前幻灯片
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export default ImageGallery
