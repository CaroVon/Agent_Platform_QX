/**
 * RoadmapTimeline —— 路线图时间线
 * 渲染 roadmap（结构化 JSON）。
 */

import { Milestone, Calendar } from 'lucide-react'
import type { RoadmapItem } from '@/types/studio'

export function Roadmap({ roadmap }: { roadmap: RoadmapItem[] }) {
  if (!roadmap.length) {
    return (
      <div className="rounded-xl border bg-card p-5 shadow-sm">
        <div className="mb-2 flex items-center gap-2">
          <Milestone className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold">路线图</h3>
        </div>
        <p className="text-sm text-muted-foreground">暂无路线图数据</p>
      </div>
    )
  }

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <div className="mb-5 flex items-center gap-2">
        <Milestone className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold">路线图</h3>
      </div>

      <ol className="relative space-y-6 border-l-2 border-border pl-6">
        {roadmap.map((item) => (
          <li key={`${item.phase}-${item.title}`} className="relative">
            <span className="absolute -left-[31px] top-1 flex h-4 w-4 items-center justify-center rounded-full border-2 border-primary bg-card" />
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-secondary px-2.5 py-0.5 text-xs font-semibold">
                {item.phase}
              </span>
              <span className="text-sm font-medium">{item.title}</span>
              {item.timeline && (
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Calendar className="h-3 w-3" /> {item.timeline}
                </span>
              )}
            </div>
            {item.goal && (
              <p className="mt-1.5 text-sm text-foreground/90">{item.goal}</p>
            )}
            {item.milestones.length > 0 && (
              <ul className="mt-2 space-y-1">
                {item.milestones.map((m) => (
                  <li key={m} className="text-xs text-muted-foreground">
                    ✓ {m}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}
