/**
 * PptAssetLibraryPage —— PPT 资产库
 * P7：扫描磁盘 outputs/studio_assets/ppt_projects 的全部 PPT 资产
 * （含早期 ppt_design 节点失败、但磁盘已成功导出 PPTX 的滞留资产），
 * 提供浏览 / 预览 / 下载，让后端资产与前端呈现完全一致。
 */

import { useCallback, useEffect, useState } from 'react'
import { Download, FileDown, FolderOpen, Loader2, RefreshCw } from 'lucide-react'
import { WorkspaceHeader } from '@/components/WorkspaceHeader'
import { productApi } from '@/lib/api'
import type { PptAssetIndexEntry } from '@/types/studio'

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${bytes} B`
}

export function PptAssetLibraryPage() {
  const [assets, setAssets] = useState<PptAssetIndexEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      setError('')
      setRefreshing(true)
      const data = await productApi.pptAssets()
      setAssets(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载 PPT 资产失败')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div>
      <WorkspaceHeader
        crumb="管理 · 资产"
        title="PPT 资产库"
        description="磁盘导出资产总览：含早期丢失记录但已成功产出 PPTX 的恢复资产，与后端 outputs/studio_assets/ppt_projects 实时对账。"
      />
      <div className="mb-6 flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          共 <span className="font-semibold text-foreground">{assets.length}</span> 个可下载 PPT
          资产
        </div>
        <button
          type="button"
          onClick={() => load(true)}
          disabled={refreshing}
          className="flex items-center gap-2 rounded-lg border bg-card px-4 py-2 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          刷新对账
        </button>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-24 text-muted-foreground">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" /> 扫描磁盘 PPT 资产…
        </div>
      )}
      {error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-5 py-3.5 text-sm text-destructive">
          {error}
        </div>
      )}
      {!loading && !error && assets.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed bg-card/40 py-24 text-center">
          <FileDown className="mb-3 h-8 w-8 text-muted-foreground/40" />
          <p className="text-sm font-medium">暂无 PPT 资产</p>
          <p className="mt-1 max-w-md text-xs text-muted-foreground">
            运行 Product Workspace 流水线后，ppt-master 导出的 .pptx 会自动归档到
            outputs/studio_assets/ppt_projects。
          </p>
        </div>
      )}

      {!loading && !error && assets.length > 0 && (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {assets.map((asset) => (
            <div
              key={asset.folder_name}
              className="flex flex-col overflow-hidden rounded-2xl border bg-card shadow-sm transition-shadow hover:shadow-md"
            >
              {/* SVG 预览墙 */}
              <div className="relative flex h-36 items-center justify-center overflow-hidden bg-slate-50">
                {asset.svg_previews.length > 0 ? (
                  <img
                    src={asset.svg_previews[0]}
                    alt={asset.title || asset.folder_name}
                    className="h-full w-full object-cover transition-transform duration-300 hover:scale-105"
                    loading="lazy"
                  />
                ) : (
                  <FileDown className="h-8 w-8 text-muted-foreground/30" />
                )}
                <span className="absolute right-2 top-2 rounded-full bg-black/50 px-2 py-0.5 text-[10px] font-medium text-white backdrop-blur">
                  {asset.svg_count} 页
                </span>
              </div>

              <div className="flex flex-1 flex-col gap-3 p-5">
                <div>
                  <h3 className="line-clamp-2 text-sm font-semibold leading-snug">
                    {asset.title || '（未命名演示）'}
                  </h3>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
                    <span className="inline-flex items-center gap-1">
                      <FolderOpen className="h-3 w-3" />
                      {asset.folder_name}
                    </span>
                    <span>{formatSize(asset.size)}</span>
                    {asset.created_at && (
                      <span>{new Date(asset.created_at).toLocaleString()}</span>
                    )}
                  </div>
                </div>

                <div className="flex gap-2 border-t pt-3">
                  <a
                    href={asset.pptx_url}
                    download
                    className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-[#24415E] px-4 py-2 text-xs font-medium text-white transition-opacity hover:opacity-90"
                  >
                    <Download className="h-3.5 w-3.5" /> 下载 PPTX
                  </a>
                  {asset.svg_previews.length > 1 && (
                    <a
                      href={asset.pptx_url}
                      className="flex items-center justify-center rounded-lg border bg-card px-4 py-2 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
                      title="在浏览器中打开"
                    >
                      预览
                    </a>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}