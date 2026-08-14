/**
 * CompetitorMatrix —— 竞品对比矩阵
 * 渲染 CompetitorAnalysis（结构化 JSON 表格）。
 */

import { Swords } from 'lucide-react'
import type { CompetitorAnalysis } from '@/types/studio'

const THREAT_STYLE: Record<string, string> = {
  high: 'bg-destructive/10 text-destructive',
  medium: 'bg-yellow-500/10 text-yellow-600',
  low: 'bg-emerald-500/10 text-emerald-600',
}

const THREAT_LABEL: Record<string, string> = {
  high: '高威胁',
  medium: '中威胁',
  low: '低威胁',
}

export function CompetitorMatrix({ analysis }: { analysis: CompetitorAnalysis }) {
  const { matrix } = analysis

  if (!matrix.profiles.length) {
    return (
      <div className="rounded-xl border bg-card p-5 shadow-sm">
        <div className="mb-2 flex items-center gap-2">
          <Swords className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold">竞品矩阵</h3>
        </div>
        <p className="text-sm text-muted-foreground">{analysis.competitive_landscape}</p>
      </div>
    )
  }

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-2">
        <Swords className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold">竞品矩阵</h3>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr className="border-b">
              {matrix.dimensions.map((dim) => (
                <th
                  key={dim}
                  className="px-3 py-2 text-left text-xs font-medium text-muted-foreground"
                >
                  {dim}
                </th>
              ))}
              <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">
                威胁等级
              </th>
            </tr>
          </thead>
          <tbody>
            {matrix.profiles.map((p) => (
              <tr key={p.name} className="border-b last:border-0">
                <td className="px-3 py-3 font-medium">{p.name}</td>
                <td className="px-3 py-3">{p.positioning}</td>
                <td className="px-3 py-3">{p.target_segment ?? '—'}</td>
                <td className="px-3 py-3">{p.pricing ?? '—'}</td>
                <td className="px-3 py-3">
                  <ul className="space-y-0.5">
                    {p.strengths.slice(0, 3).map((s) => (
                      <li key={s} className="text-xs text-emerald-700">
                        + {s}
                      </li>
                    ))}
                  </ul>
                </td>
                <td className="px-3 py-3">
                  <ul className="space-y-0.5">
                    {p.weaknesses.slice(0, 3).map((w) => (
                      <li key={w} className="text-xs text-destructive">
                        − {w}
                      </li>
                    ))}
                  </ul>
                </td>
                <td className="px-3 py-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      THREAT_STYLE[p.threat_level] ?? THREAT_STYLE.medium
                    }`}
                  >
                    {THREAT_LABEL[p.threat_level] ?? '中威胁'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {analysis.differentiation_opportunities.length > 0 && (
        <div className="mt-4 rounded-lg bg-secondary/60 p-3">
          <div className="mb-1.5 text-xs font-medium text-muted-foreground">
            差异化机会点
          </div>
          <ul className="space-y-1">
            {analysis.differentiation_opportunities.map((opp) => (
              <li key={opp} className="text-sm text-foreground/90">
                · {opp}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
