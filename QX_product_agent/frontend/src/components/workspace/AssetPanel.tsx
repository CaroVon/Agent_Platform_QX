/**
 * AssetPanel —— Generated Product Assets（四大资产面板）
 * 支持局部重新生成（带可选指令）+ 版本历史查看
 */

import { useNavigate } from 'react-router-dom'
import { RefreshCw, History } from 'lucide-react'
import { FileText, FlaskConical, MonitorPlay, PenTool } from 'lucide-react'
import { AssetCard } from '@/components/AssetCard'
import { productApi } from '@/lib/api'
import type { StudioProduct } from '@/types/studio'

const ASSET_META: Array<{
  asset: string
  title: string
  description: string
  icon: typeof FileText
}> = [
  { asset: 'research', title: 'Research', description: '市场研究、竞品矩阵与行业洞察', icon: FlaskConical },
  { asset: 'strategy', title: 'PRD', description: '产品定位、画像、功能与路线图', icon: FileText },
  { asset: 'design', title: 'Design', description: '用户旅程、信息架构与组件规格', icon: PenTool },
  { asset: 'presentation', title: 'Presentation', description: 'Slide JSON 演示（Web / PDF / PPTX / HTML）', icon: MonitorPlay },
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
  const nav = (path: string) =>
    navigate(path, { state: { productId: product.product_id } })

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

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {ASSET_META.map(({ asset, title, description, icon }) => {
        const ready = completed && (product as unknown as Record<string, unknown>)[asset]
        const assetKey = asset === 'strategy' ? 'strategy' : asset
        const readyData = completed && (product as unknown as Record<string, unknown>)[assetKey]
        return (
          <AssetCard
            key={asset}
            icon={icon}
            title={title}
            description={description}
            status={readyData ? 'ready' : running ? 'running' : 'empty'}
            onClick={completed ? () => nav(`/${asset === 'strategy' ? 'prd' : asset === 'presentation' ? 'presentation' : asset}`) : undefined}
            action={
              completed && ready ? (
                <span className="flex shrink-0 items-center gap-1">
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
              ) : undefined
            }
          />
        )
      })}
    </div>
  )
}
