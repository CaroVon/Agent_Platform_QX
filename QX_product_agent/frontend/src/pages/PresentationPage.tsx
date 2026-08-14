/**
 * PresentationPage —— 演示资产管理
 * Slide JSON 演示（PresentationViewer，Web 预览 = PDF 导出）+ 导出操作
 */

import { PresentationViewer } from '@/components/presentation/PresentationViewer'
import { SlideRenderer } from '@/components/SlideRenderer'
import { WorkspaceHeader } from '@/components/WorkspaceHeader'
import { ProductAssetBrowser } from '@/components/ProductAssetBrowser'
import type { PresentationDSL } from '@/types/presentation'
import type { SlideDeck, StudioProduct } from '@/types/studio'

export function PresentationPage() {
  return (
    <div>
      <WorkspaceHeader
        crumb="创作 · 演示"
        title="Presentation"
        description="专业演示资产：Web 演示与 PDF/PPTX 导出共用同一渲染源（所见即所得）。"
      />
      <ProductAssetBrowser
        emptyTitle="暂无演示资产"
        emptyDescription="运行 Product Workspace 流水线后，Slide JSON 演示会自动归档到这里。"
        renderDetail={(product: StudioProduct) => {
          const presentation = product.presentation
          if (!presentation) {
            return <p className="text-sm text-muted-foreground">该产品暂无演示资产。</p>
          }
          return Array.isArray((presentation as PresentationDSL).pages) ? (
            <PresentationViewer
              presentation={presentation as PresentationDSL}
              productId={product.product_id}
              qualityGate={product.gate_report ?? null}
            />
          ) : (
            <SlideRenderer deck={presentation as SlideDeck} productId={product.product_id} />
          )
        }}
      />
    </div>
  )
}
