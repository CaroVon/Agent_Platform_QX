/**
 * research/CompetitorCard —— 单竞品卡
 */

import { Swords } from 'lucide-react'
import type { CompetitorProfile } from '@/types/studio'

const THREAT_STYLE: Record<string, string> = {
  high: 'bg-destructive/10 text-destructive',
  medium: 'bg-[#C87E4F]/10 text-[#C87E4F]',
  low: 'bg-emerald-600/10 text-emerald-700',
}

const THREAT_LABEL: Record<string, string> = {
  high: '高威胁',
  medium: '中威胁',
  low: '低威胁',
}

export function CompetitorCard({ profile }: { profile: CompetitorProfile }) {
  return (
    <div className="flex h-full flex-col rounded-2xl border bg-card px-6 py-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="font-editorial truncate text-base font-semibold tracking-tight">
            {profile.name}
          </h4>
          {profile.positioning && (
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              {profile.positioning}
            </p>
          )}
        </div>
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${
            THREAT_STYLE[profile.threat_level] ?? THREAT_STYLE.medium
          }`}
        >
          {THREAT_LABEL[profile.threat_level] ?? '中威胁'}
        </span>
      </div>

      {profile.target_segment && (
        <div className="mt-4 text-xs text-muted-foreground">
          <span className="font-medium text-foreground/70">目标客群</span>：{profile.target_segment}
        </div>
      )}
      {profile.pricing && (
        <div className="mt-1.5 text-xs text-muted-foreground">
          <span className="font-medium text-foreground/70">定价</span>：{profile.pricing}
        </div>
      )}

      <div className="mt-4 grid grid-cols-2 gap-3 border-t pt-4">
        {profile.strengths.length > 0 && (
          <div>
            <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-emerald-700">
              优势
            </div>
            <ul className="space-y-1">
              {profile.strengths.slice(0, 3).map((s) => (
                <li key={s} className="flex gap-1 text-xs text-muted-foreground">
                  <span className="text-emerald-600">+</span> {s}
                </li>
              ))}
            </ul>
          </div>
        )}
        {profile.weaknesses.length > 0 && (
          <div>
            <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-destructive">
              劣势
            </div>
            <ul className="space-y-1">
              {profile.weaknesses.slice(0, 3).map((w) => (
                <li key={w} className="flex gap-1 text-xs text-muted-foreground">
                  <span className="text-destructive">−</span> {w}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {profile.strengths.length === 0 && profile.weaknesses.length === 0 && (
        <div className="mt-4 flex items-center gap-1.5 border-t pt-4 text-xs text-muted-foreground/60">
          <Swords className="h-3 w-3" /> 暂无细节画像
        </div>
      )}
    </div>
  )
}
