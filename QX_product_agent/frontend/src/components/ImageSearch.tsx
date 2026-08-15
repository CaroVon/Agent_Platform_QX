/**
 * ImageSearch —— 图片搜索与项目素材库（恢复缺失功能）
 *
 * 复用既有 API：
 *   POST /projects/{id}/search-images（DuckDuckGo，持久化到项目图片库）
 *   GET  /projects/{id}/images（项目图片库）
 *   DELETE /projects/{id}/images/{imageId}
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { ImagePlus, Loader2, RefreshCw, Search, Trash2, Upload } from 'lucide-react'
import { Button } from '@/components/common/button'
import { productApi, projectsApi } from '@/lib/api'
import type { ImageResult } from '@/types/api'

export function ImageSearch({
  projectId,
  selectable,
}: {
  projectId: string
  /** 编辑器模式：提供插入按钮与拖拽到画布；productId 时走产品级无状态搜索/上传 */
  selectable?: { onInsert: (url: string) => void; productId?: string }
}) {
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [library, setLibrary] = useState<ImageResult[]>([])
  const [loadingLib, setLoadingLib] = useState(false)
  const [error, setError] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 产品级模式（编辑器）：无持久化，素材库为本地状态
  const productMode = Boolean(selectable?.productId)

  const loadLibrary = useCallback(async () => {
    if (productMode) return
    setLoadingLib(true)
    try {
      const data = await projectsApi.getProjectImages(projectId)
      setLibrary(data.images ?? [])
    } catch {
      /* 图片库加载失败静默 */
    } finally {
      setLoadingLib(false)
    }
  }, [projectId, productMode])

  useEffect(() => {
    loadLibrary()
  }, [loadLibrary])

  const search = async () => {
    if (!query.trim() || searching) return
    setSearching(true)
    setError('')
    try {
      if (productMode && selectable?.productId) {
        const data = await productApi.searchImages(selectable.productId, {
          query: query.trim(),
          max_results: 12,
          search_depth: 5,
        })
        setLibrary(
          data.images.map((img) => ({
            id: img.id,
            query: img.query,
            title: img.title,
            image_url: img.image_url,
            source_url: img.source_url,
            search_depth: 5,
            page_number: null,
            created_at: '',
          })),
        )
      } else {
        await projectsApi.searchImages(projectId, {
          query: query.trim(),
          max_results: 12,
          search_depth: 5,
        })
        await loadLibrary()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '搜索失败')
    } finally {
      setSearching(false)
    }
  }

  const remove = async (imageId: string) => {
    if (productMode) {
      setLibrary((prev) => prev.filter((i) => i.id !== imageId))
      return
    }
    try {
      await projectsApi.deleteProjectImage(projectId, imageId)
      setLibrary((prev) => prev.filter((i) => i.id !== imageId))
    } catch {
      /* 删除失败静默 */
    }
  }

  /** 本地上传（编辑器模式）：文件 → 产品级静态资源 URL → 入素材库 */
  const upload = async (file: File) => {
    if (!selectable?.productId || uploading) return
    setUploading(true)
    setError('')
    try {
      const { url } = await productApi.uploadAsset(selectable.productId, file)
      setLibrary((prev) => [
        {
          id: `upload-${Date.now()}`,
          query: file.name,
          title: file.name,
          image_url: url,
          source_url: null,
          search_depth: 0,
          page_number: null,
          created_at: '',
        },
        ...prev,
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传失败')
    } finally {
      setUploading(false)
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
        {productMode ? (
          <>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) upload(file)
                e.target.value = ''
              }}
            />
            <Button
              variant="outline"
              size="icon"
              title="本地上传图片"
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
            >
              {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            </Button>
          </>
        ) : (
          <Button variant="outline" size="icon" title="刷新素材库" onClick={loadLibrary}>
            <RefreshCw className={loadingLib ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />
          </Button>
        )}
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
              {productMode
                ? '暂无图片 · 输入关键词搜索，或点击上传按钮添加本地图片'
                : '暂无图片 · 输入关键词搜索，结果会自动收录到这里'}
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
