/**
 * PRDStudioPage —— 结构化 PRD 资产
 * PRD 章节阅读（复用 PRDViewer）+ 画像 / 功能 / 路线图
 */

import { WorkspaceHeader } from '@/components/WorkspaceHeader'
import { ProductAssetBrowser } from '@/components/ProductAssetBrowser'
import { SourceIndex } from '@/components/product/SourceIndex'
import { PRDViewer } from '@/components/product/PRDViewer'
import { PersonaCard } from '@/components/PersonaCard'
import { FeatureMatrix } from '@/components/product/FeatureMatrix'
import { Roadmap } from '@/components/product/Roadmap'
import type { StudioProduct } from '@/types/studio'

export function PRDStudioPage() {
  return (
    <div>
      <WorkspaceHeader
        crumb="创作 · PRD"
        title="PRD Studio"
        description="结构化产品需求：定位、画像、功能与路线图 —— AI 生成、章节化呈现。"
      />
      <ProductAssetBrowser
        emptyTitle="暂无 PRD 资产"
        emptyDescription="运行 Product Workspace 流水线后，产品策略与 PRD 章节会自动归档到这里。"
        renderDetail={(product: StudioProduct) => {
          const strategy = product.strategy
          if (!strategy) {
            return <p className="text-sm text-muted-foreground">该产品暂无 PRD 资产。</p>
          }
          return (
            <>
              <div className="rounded-xl bg-secondary/50 px-5 py-3 text-sm text-muted-foreground">
                定位：<span className="font-medium text-foreground">{strategy.positioning}</span>
              </div>
              <SourceIndex sources={strategy.sources} />
              {strategy.personas.length > 0 && (
                <div className="rounded-xl border bg-card p-5 shadow-sm">
                  <h3 className="mb-4 text-sm font-semibold">用户画像</h3>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {strategy.personas.map((p) => (
                      <PersonaCard key={p.name} persona={p} />
                    ))}
                  </div>
                </div>
              )}
              {strategy.features.length > 0 && <FeatureMatrix features={strategy.features} />}
              {strategy.roadmap.length > 0 && <Roadmap roadmap={strategy.roadmap} />}
              {strategy.prd_sections.length > 0 && <PRDViewer sections={strategy.prd_sections} />}
            </>
          )
        }}
      />
    </div>
  )
}
