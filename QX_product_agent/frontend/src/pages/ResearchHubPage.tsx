/**
 * ResearchHubPage —— 市场研究资产库
 * 市场研究 / 竞品矩阵 / 行业趋势（复用 MarketCard / CompetitorMatrix）
 */

import { WorkspaceHeader } from '@/components/WorkspaceHeader'
import { ProductAssetBrowser } from '@/components/ProductAssetBrowser'
import { SourceIndex } from '@/components/product/SourceIndex'
import { ResearchCard } from '@/components/research/ResearchCard'
import { CompetitorCard } from '@/components/research/CompetitorCard'
import { InsightCard } from '@/components/research/InsightCard'
import type { StudioProduct } from '@/types/studio'

export function ResearchHubPage() {
  return (
    <div>
      <WorkspaceHeader
        crumb="创作 · 研究"
        title="Research Hub"
        description="集中管理市场研究、竞品分析与行业洞察 —— 资产来自多 Agent 流水线的结构化产出。"
      />
      <ProductAssetBrowser
        emptyTitle="暂无研究资产"
        emptyDescription="在 Product Workspace 输入产品想法并运行流水线后，市场研究与竞品分析会自动归档到这里。"
        renderDetail={(product: StudioProduct) => {
          const research = product.research
          const competitors = product.competitor_analysis
          return (
            <>
              <div className="rounded-xl border bg-background/60 px-6 py-3.5 text-sm text-muted-foreground">
                产品：<span className="font-medium text-foreground">{product.idea}</span>
                {product.critic_score != null && (
                  <span className="ml-3 text-xs">Critic 评分 {product.critic_score}/100</span>
                )}
              </div>

              {research && <ResearchCard research={research} />}

              <SourceIndex
                sources={research?.sources}
                marketSource={research?.market_size?.source}
                fallbackUrls={(competitors?.competitors ?? []).map((c: { url?: string; name?: string }) => ({ url: c.url ?? '', title: c.url ? c.name : '' })).filter((c: { url: string }) => c.url)}
              />

              {competitors && competitors.competitors.length > 0 && (
                <div className="space-y-5">
                  <div className="grid gap-4 lg:grid-cols-2">
                    {competitors.competitors.map((profile) => (
                      <CompetitorCard key={profile.name} profile={profile} />
                    ))}
                  </div>
                  <div className="grid gap-4 lg:grid-cols-2">
                    {research && (
                      <InsightCard title="用户痛点" items={research.customer_pain_points} />
                    )}
                    {competitors.differentiation_opportunities.length > 0 && (
                      <InsightCard
                        title="差异化机会"
                        items={competitors.differentiation_opportunities}
                      />
                    )}
                  </div>
                  {competitors.competitive_landscape && (
                    <div className="rounded-2xl border bg-card px-7 py-5">
                      <h4 className="font-serif mb-2 text-sm font-semibold tracking-tight">
                        竞争格局
                      </h4>
                      <p className="text-sm leading-relaxed text-muted-foreground">
                        {competitors.competitive_landscape}
                      </p>
                    </div>
                  )}
                </div>
              )}

              {!research && !competitors && (
                <p className="text-sm text-muted-foreground">该产品暂无研究资产。</p>
              )}
            </>
          )
        }}
      />
    </div>
  )
}
