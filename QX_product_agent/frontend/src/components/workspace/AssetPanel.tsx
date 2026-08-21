/**
 * AssetPanel —— Generated Product Assets（渐进式交付面板，P6）
 *
 * - 运行中：轮询项目资产库，节点资产一落盘（md/json/图表）即以「就绪」态出现，
 *   可直接预览/下载（不必等全部跑完）；新出现的区块带「新增」徽标
 * - 完成态：四/五大资产卡 + 局部重新生成 + 版本历史（原能力保留）
 */

import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { RefreshCw, History, LayoutGrid } from 'lucide-react'
import { FileText, FlaskConical, MonitorPlay, PenTool } from 'lucide-react'
import { AssetCard } from '@/components/AssetCard'
import { productApi, projectAssetsApi, type ProjectAssetLibrary } from '@/lib/api'
import type { StudioProduct } from '@/types/studio'

const ASSET_META: Array<{
  asset: string
  title: string
  description: string
  icon: typeof FileText
  /** 渐进交付：资产库中代表该节点就绪的文件名（前缀匹配） */
  readyFile?: string
  navPath?: string
}> = [
  { asset: 'research', title: 'Research', description: '市场研究、竞品矩阵与行业洞察', icon: FlaskConical, readyFile: 'research.md', navPath: '/research' },
  { asset: 'competitor_matrix', title: '竞品矩阵 MOD', description: '真实亚马逊数据：四分区/图表/14 章/SKU', icon: LayoutGrid, readyFile: 'competitor_matrix.md' },
  { asset: 'strategy', title: 'PRD', description: '产品定位、画像、功能与路线图', icon: FileText, readyFile: 'strategy.md', navPath: '/prd' },
  { asset: 'design', title: 'Design', description: '用户旅程、信息架构与组件规格', icon: PenTool, readyFile: 'design.md', navPath: '/design' },
  { asset: 'presentation', title: 'Presentation', description: 'Slide JSON 演示（Web / PDF / PPTX / HTML）', icon: MonitorPlay, readyFile: 'presentation.json', navPath: '/presentation' },
]

export function AssetPanel({
  product,
  onRefresh,
}: {
  product: StudioProduct
  /** 重生成成功后刷新产品数据 */
  onRefresh?: () => void
}) {
  const navigate = useNavigate()
  const completed = product.status === 'completed'
  const running = product.status === 'queued' || product.status === 'running'
  const [library, setLibrary] = useState<ProjectAssetLibrary | null>(null)
  const [freshKeys, setFreshKeys] = useState<Set<string>>(new Set())
  const knownFiles = useRef<Set<string>>(new Set())

  // ── 渐进交付：运行中轮询资产库，节点资产即时可见 ──
  useEffect(() => {
    if (!product.product_id) return
    let cancelled = false
    const load = async () => {
      try {
        const lib = await projectAssetsApi.get(product.product_id)
        if (cancelled) return
        setLibrary(lib)
        const fresh = new Set<string>()
        for (const f of lib.files ?? []) {
          if (!knownFiles.current.has(f.name)) {
            fresh.add(f.name)
            knownFiles.current.add(f.name)
          }
        }
        if (fresh.size) setFreshKeys((prev) => new Set([...prev, ...fresh]))
      } catch {
        /* 资产库尚未初始化（采集阶段）静默 */
      }
    }
    load()
    if (!running) return
    const t = window.setInterval(load, 4000)
    return () => {
      cancelled = true
      window.clearInterval(t)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product.product_id, running])

  const handleRegenerate = async (asset: string) => {
    const instruction = window.prompt(
      `重新生成「${asset}」资产（可选：输入修改要求，例如"补充东南亚市场数据"）\n留空则按原需求重跑。`,
      '',
    )
    if (instruction === null) return
    try {
      await productApi.regenerate(product.product_id, asset, instruction.trim())
      alert('重新生成完成，已保存为新版本')
      onRefresh?.()
    } catch (err) {
      alert(`重新生成失败: ${err instanceof Error ? err.message : String(err)}`)
    }
  }

  const handleVersions = async (asset: string) => {
    try {
      const data = await productApi.versions(product.product_id)
      const list = data.versions[asset] ?? []
      if (list.length === 0) {
        alert('暂无历史版本')
        return
      }
      const labels = list
        .map((v, i) => `${i + 1}. ${new Date(v.ts).toLocaleString('zh-CN')}`)
        .join('\n')
      const pick = window.prompt(
        `「${asset}」历史版本（最新在前，输入编号回滚）：\n${labels}`,
        '1',
      )
      if (pick === null) return
      const index = Number(pick) - 1
      if (Number.isNaN(index) || index < 0 || index >= list.length) {
        alert('无效编号')
        return
      }
      await productApi.restore(product.product_id, asset, index)
      alert('已回滚到所选版本')
      onRefresh?.()
    } catch (err) {
      alert(`版本操作失败: ${err instanceof Error ? err.message : String(err)}`)
    }
  }

  /** 该节点是否已有落盘资产（渐进就绪） */
  const incrementalFile = (asset: string, readyFile?: string) => {
    if (!readyFile || !library) return null
    return (
      (library.files ?? []).find(
        (f) => f.name === readyFile || f.name.startsWith(readyFile.replace(/\.(md|json)$/, '')),
      ) ?? null
    )
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {ASSET_META.map(({ asset, title, description, icon, readyFile, navPath }) => {
        const pkgData = (product as unknown as Record<string, unknown>)[asset]
        const incFile = incrementalFile(asset, readyFile)
        const ready = completed ? Boolean(pkgData) : Boolean(incFile)
        const isFresh = incFile ? freshKeys.has(incFile.name) : false
        return (
          <AssetCard
            key={asset}
            icon={icon}
            title={title}
            description={
              ready && !completed && incFile
                ? `${description} · 已先行交付，可预览`
                : description
            }
            status={ready ? 'ready' : running ? 'running' : 'empty'}
            badge={
              isFresh && running
                ? { text: '新增', tone: 'new' as const }
                : incFile && running
                  ? { text: '已交付', tone: 'soft' as const }
                  : undefined
            }
            onClick={completed && navPath ? () => navigate(navPath) : undefined}
            action={
              completed && ready ? (
                <span className="flex shrink-0 items-center gap-1">
                  {incFile && (
                    <a
                      href={incFile.url}
                      target="_blank"
                      rel="noreferrer"
                      title="预览/下载该资产文件"
                      onClick={(e) => e.stopPropagation()}
                      className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-secondary hover:text-[#24415E]"
                    >
                      <FileText className="h-3.5 w-3.5" />
                    </a>
                  )}
                  <button
                    type="button"
                    title="重新生成（可附修改要求）"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleRegenerate(asset)
                    }}
                    className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-secondary hover:text-[#24415E]"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    title="版本历史（回滚）"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleVersions(asset)
                    }}
                    className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-secondary hover:text-[#24415E]"
                  >
                    <History className="h-3.5 w-3.5" />
                  </button>
                </span>
              ) : running && incFile ? (
                <a
                  href={incFile.url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="shrink-0 rounded-md border border-[#24415E]/30 px-2 py-1 text-[11px] text-[#24415E] transition-colors hover:bg-[#24415E]/10"
                >
                  预览
                </a>
              ) : undefined
            }
          />
        )
      })}
    </div>
  )
}
