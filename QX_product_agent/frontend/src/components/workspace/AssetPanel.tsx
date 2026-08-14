/**
 * AssetPanel —— Generated Product Assets（四大资产面板）
 */

import { useNavigate } from 'react-router-dom'
import { FileText, FlaskConical, MonitorPlay, PenTool } from 'lucide-react'
import { AssetCard } from '@/components/AssetCard'
import type { StudioProduct } from '@/types/studio'

export function AssetPanel({ product }: { product: StudioProduct }) {
  const navigate = useNavigate()
  const completed = product.status === 'completed'
  const running = product.status === 'queued' || product.status === 'running'
  const nav = (path: string) =>
    navigate(path, { state: { productId: product.product_id } })

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <AssetCard
        icon={FlaskConical}
        title="Research"
        description="市场研究、竞品矩阵与行业洞察"
        status={completed && product.research ? 'ready' : running ? 'running' : 'empty'}
        onClick={completed ? () => nav('/research') : undefined}
      />
      <AssetCard
        icon={FileText}
        title="PRD"
        description="产品定位、画像、功能与路线图"
        status={completed && product.strategy ? 'ready' : running ? 'running' : 'empty'}
        onClick={completed ? () => nav('/prd') : undefined}
      />
      <AssetCard
        icon={PenTool}
        title="Design"
        description="用户旅程、信息架构与组件规格"
        status={completed && product.design ? 'ready' : running ? 'running' : 'empty'}
        onClick={completed ? () => nav('/design') : undefined}
      />
      <AssetCard
        icon={MonitorPlay}
        title="Presentation"
        description="Slide JSON 演示（Web / PDF / PPTX / HTML）"
        status={completed && product.presentation ? 'ready' : running ? 'running' : 'empty'}
        onClick={completed ? () => nav('/presentation') : undefined}
      />
    </div>
  )
}
