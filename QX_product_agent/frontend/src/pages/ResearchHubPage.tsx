/**
 * ResearchHubPage —— 市场研究资产库
 * 市场研究 / 竞品矩阵 / 行业趋势（复用 MarketCard / CompetitorMatrix）
 */

import { WorkspaceHeader } from '@/components/WorkspaceHeader'
import { ProductAssetBrowser } from '@/components/ProductAssetBrowser'
import { MarketCard } from '@/components/MarketCard'
import { CompetitorMatrix } from '@/components/CompetitorMatrix'
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
        renderDetail={(product: StudioProduct) => (
          <>
            <div className="rounded-xl bg-secondary/50 px-5 py-3 text-sm text-muted-foreground">
              产品：<span className="font-medium text-foreground">{product.idea}</span>
              {product.critic_score != null && (
                <span className="ml-3 text-xs">Critic 评分 {product.critic_score}/100</span>
              )}
            </div>
            {product.research ? (
              <>
                <MarketCard research={product.research} />
                {product.competitor_analysis && (
                  <CompetitorMatrix analysis={product.competitor_analysis} />
                )}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">该产品暂无研究资产。</p>
            )}
          </>
        )}
      />
    </div>
  )
}
