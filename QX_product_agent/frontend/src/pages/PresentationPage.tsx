/**
 * PresentationPage —— 演示资产管理
 * Slide JSON 演示（PresentationViewer，Web 预览 = PDF 导出）+ 导出操作
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileDown, PenLine } from 'lucide-react'
import { PresentationViewer } from '@/components/presentation/PresentationViewer'
import { SlidePreview } from '@/components/presentation/SlidePreview'
import { SlideRenderer } from '@/components/SlideRenderer'
import { WorkspaceHeader } from '@/components/WorkspaceHeader'
import { ProductAssetBrowser } from '@/components/ProductAssetBrowser'
import type { PresentationDSL } from '@/types/presentation'
import type { SlideDeck, StudioProduct } from '@/types/studio'

export function PresentationPage() {
  const navigate = useNavigate()
  const [pageIndex, setPageIndex] = useState(0)

  return (
    <div>
      <WorkspaceHeader
        crumb="创作 · 演示"
        title="Presentation"
        description="专业演示资产：Web 演示与 PDF/PPTX/HTML 导出共用同一渲染源（所见即所得）。"
      />
      <ProductAssetBrowser
        emptyTitle="暂无演示资产"
        emptyDescription="运行 Product Workspace 流水线后，Slide JSON 演示会自动归档到这里。"
        renderDetail={(product: StudioProduct) => {
          const presentation = product.presentation
          if (!presentation) {
            return <p className="text-sm text-muted-foreground">该产品暂无演示资产。</p>
          }
          if (!Array.isArray((presentation as PresentationDSL).pages)) {
            return (
              <SlideRenderer deck={presentation as SlideDeck} productId={product.product_id} />
            )
          }
          const dsl = presentation as PresentationDSL
          const pptDesign = product.ppt_design
          return (
            <div className="space-y-6">
              {/* ── PPT 资产（ppt-master 原生产出） ── */}
              {pptDesign?.pptx_relative && (
                <div className="flex items-center justify-between rounded-xl border border-emerald-600/20 bg-emerald-50/70 px-6 py-3.5">
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-600 text-white">
                      <FileDown className="h-4 w-4" />
                    </span>
                    <div>
                      <div className="text-sm font-medium text-foreground">
                        PPT 已生成（ppt-master 原生 · 可编辑 .pptx）
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        模型 {pptDesign.model ?? '—'} · {pptDesign.pages ?? '—'} 页 · 图片资产 {pptDesign.images?.length ?? 0} 张
                      </div>
                    </div>
                  </div>
                  <a
                    href={`/api/v1/files/${pptDesign.pptx_relative}`}
                    download
                    className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-medium text-white transition-opacity hover:opacity-90"
                  >
                    <FileDown className="h-3.5 w-3.5" /> 下载 PPT
                  </a>
                </div>
              )}
              <div className="flex items-center justify-between rounded-xl border bg-background/60 px-6 py-3.5">
                <span className="text-sm text-muted-foreground">
                  编辑演示内容（文本 / 图片 / 基础元素 / 素材插入）
                </span>
                <button
                  type="button"
                  onClick={() => navigate(`/presentation/editor/${product.product_id}`)}
                  className="flex items-center gap-2 rounded-lg bg-[#24415E] px-4 py-2 text-xs font-medium text-white transition-opacity hover:opacity-90"
                >
                  <PenLine className="h-3.5 w-3.5" /> 在编辑器中打开
                </button>
              </div>
              <SlidePreview
                presentation={dsl}
                currentIndex={pageIndex}
                onSelect={setPageIndex}
              />
              <PresentationViewer
                presentation={dsl}
                productId={product.product_id}
                qualityGate={product.gate_report ?? null}
                currentIndex={pageIndex}
                onIndexChange={setPageIndex}
              />
            </div>
          )
        }}
      />
    </div>
  )
}
