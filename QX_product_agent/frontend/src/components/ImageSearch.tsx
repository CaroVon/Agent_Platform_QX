/**
 * ImageSearch —— 图片搜索与项目素材库（恢复缺失功能）
 *
 * 复用既有 API：
 *   POST /projects/{id}/search-images（DuckDuckGo，持久化到项目图片库）
 *   GET  /projects/{id}/images（项目图片库）
 *   DELETE /projects/{id}/images/{imageId}
 */

import { useCallback, useEffect, useState } from 'react'
import { ImagePlus, Loader2, RefreshCw, Search, Trash2 } from 'lucide-react'
import { Button } from '@/components/common/button'
import { projectsApi } from '@/lib/api'
import type { ImageResult } from '@/types/api'

export function ImageSearch({
  projectId,
  selectable,
}: {
  projectId: string
  /** 编辑器模式：提供插入按钮与拖拽到画布 */
  selectable?: { onInsert: (url: string) => void }
}) {
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [library, setLibrary] = useState<ImageResult[]>([])
  const [loadingLib, setLoadingLib] = useState(false)
  const [error, setError] = useState('')

  const loadLibrary = useCallback(async () => {
    setLoadingLib(true)
    try {
      const data = await projectsApi.getProjectImages(projectId)
      setLibrary(data.images ?? [])
    } catch {
      /* 图片库加载失败静默 */
    } finally {
      setLoadingLib(false)
    }
  }, [projectId])

  useEffect(() => {
    loadLibrary()
  }, [loadLibrary])

  const search = async () => {
    if (!query.trim() || searching) return
    setSearching(true)
    setError('')
    try {
      await projectsApi.searchImages(projectId, {
        query: query.trim(),
        max_results: 12,
        search_depth: 5,
      })
      await loadLibrary()
    } catch (err) {
      setError(err instanceof Error ? err.message : '搜索失败')
    } finally {
      setSearching(false)
    }
  }

  const remove = async (imageId: string) => {
    try {
      await projectsApi.deleteProjectImage(projectId, imageId)
      setLibrary((prev) => prev.filter((i) => i.id !== imageId))
    } catch {
      /* 删除失败静默 */
    }
  }

  return (
    <div>
      {/* ─── 搜索栏 ─────────────────────────────────────────── */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && search()}
            placeholder="搜索产品参考图 / 竞品截图 / 行业灵感…"
            className="h-10 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>
        <Button onClick={search} disabled={searching || !query.trim()}>
          {searching ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Search className="mr-2 h-4 w-4" />}
          搜索
        </Button>
        <Button variant="outline" size="icon" title="刷新素材库" onClick={loadLibrary}>
          <RefreshCw className={loadingLib ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />
        </Button>
      </div>
      {error && <p className="mt-2 text-xs text-destructive">{error}</p>}

      {/* ─── 项目图片库 ─────────────────────────────────────── */}
      <div className="mt-4">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-medium text-muted-foreground">
            项目图片库（{library.length}）
          </span>
          <span className="text-[10px] text-muted-foreground">
            搜索结果自动存入，供画布与演示使用
          </span>
        </div>
        {library.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-10 text-center">
            <ImagePlus className="h-6 w-6 text-muted-foreground/60" />
            <p className="mt-2 text-xs text-muted-foreground">
              暂无图片 · 输入关键词搜索，结果会自动收录到这里
            </p>
          </div>
        ) : (
          <div className={selectable ? "grid grid-cols-3 gap-2" : "grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-6"}>
            {library.map((img) => (
              <div key={img.id} className="group relative overflow-hidden rounded-lg border">
                <img
                  src={img.image_url}
                  alt={img.query ?? '素材图'}
                  loading="lazy"
                  draggable={Boolean(selectable)}
                  onDragStart={(e) => {
                    e.dataTransfer.setData('text/plain', img.image_url)
                    e.dataTransfer.effectAllowed = 'copy'
                  }}
                  className="aspect-square w-full cursor-grab object-cover"
                />
                {selectable && (
                  <button
                    type="button"
                    title="插入到画布"
                    onClick={() => selectable.onInsert(img.image_url)}
                    className="absolute inset-x-0 bottom-0 bg-[#24415E]/85 py-1 text-[10px] font-medium text-white opacity-0 transition-opacity hover:bg-[#24415E] group-hover:opacity-100"
                  >
                    插入
                  </button>
                )}
                {!selectable && (
                  <button
                    type="button"
                    title="从素材库删除"
                    onClick={() => remove(img.id)}
                    className="absolute right-1.5 top-1.5 rounded-md bg-black/50 p-1 text-white opacity-0 transition-opacity hover:bg-destructive group-hover:opacity-100"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
