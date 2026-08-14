/**
 * research/ResearchCard —— 市场研究卡（vintage 编辑风）
 */

import { BarChart3, TrendingUp } from 'lucide-react'
import type { MarketResearch } from '@/types/studio'

export function ResearchCard({ research }: { research: MarketResearch }) {
  const ms = research.market_size
  return (
    <div className="rounded-2xl border bg-card px-8 py-7">
      <div className="mb-5 flex items-center gap-2.5">
        <BarChart3 className="h-4 w-4 text-[#24415E]" />
        <h3 className="font-editorial text-base font-semibold tracking-tight">市场研究</h3>
      </div>

      <p className="text-sm leading-relaxed text-foreground/85">{ms.summary}</p>

      {(ms.tam || ms.sam || ms.som || ms.cagr) && (
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            ['TAM', ms.tam],
            ['SAM', ms.sam],
            ['SOM', ms.som],
            ['CAGR', ms.cagr],
          ].map(([label, value]) =>
            value ? (
              <div key={label} className="rounded-xl border bg-background/60 px-4 py-3.5">
                <div className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                  {label}
                </div>
                <div className="font-editorial mt-1 text-lg font-semibold text-[#24415E]">
                  {value}
                </div>
              </div>
            ) : null,
          )}
        </div>
      )}

      {research.industry_trends.length > 0 && (
        <div className="mt-6">
          <div className="mb-2.5 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <TrendingUp className="h-3.5 w-3.5 text-[#3F6B4F]" /> 行业趋势
          </div>
          <div className="flex flex-wrap gap-2">
            {research.industry_trends.map((trend) => (
              <span key={trend} className="rounded-full border bg-background/70 px-3 py-1.5 text-xs">
                {trend}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
