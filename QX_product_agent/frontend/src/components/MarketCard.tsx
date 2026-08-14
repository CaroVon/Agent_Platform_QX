/**
 * MarketCard —— 市场分析卡片
 * 渲染 MarketResearch（结构化 JSON），不渲染 LLM 生成的 HTML。
 */

import { TrendingUp, Users, BarChart3 } from 'lucide-react'
import type { MarketResearch } from '@/types/studio'

export function MarketCard({ research }: { research: MarketResearch }) {
  const { market_size: ms } = research

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-2">
        <BarChart3 className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold">市场分析</h3>
      </div>

      <p className="text-sm leading-relaxed text-foreground">{ms.summary}</p>

      {(ms.tam || ms.sam || ms.som || ms.cagr) && (
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            ['TAM', ms.tam],
            ['SAM', ms.sam],
            ['SOM', ms.som],
            ['CAGR', ms.cagr],
          ].map(([label, value]) =>
            value ? (
              <div key={label} className="rounded-lg bg-secondary p-3">
                <div className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                  {label}
                </div>
                <div className="mt-1 text-sm font-semibold">{value}</div>
              </div>
            ) : null,
          )}
        </div>
      )}

      {research.industry_trends.length > 0 && (
        <div className="mt-4">
          <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <TrendingUp className="h-3.5 w-3.5" /> 行业趋势
          </div>
          <div className="flex flex-wrap gap-2">
            {research.industry_trends.map((trend) => (
              <span
                key={trend}
                className="rounded-full border bg-background px-3 py-1 text-xs"
              >
                {trend}
              </span>
            ))}
          </div>
        </div>
      )}

      {research.customer_pain_points.length > 0 && (
        <div className="mt-4">
          <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <Users className="h-3.5 w-3.5" /> 用户痛点
          </div>
          <ul className="space-y-1.5">
            {research.customer_pain_points.map((pain) => (
              <li key={pain} className="flex gap-2 text-sm text-foreground/90">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary/60" />
                {pain}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
