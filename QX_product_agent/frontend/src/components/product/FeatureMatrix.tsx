/**
 * FeatureMatrix —— 功能清单矩阵
 * 渲染 features（按优先级 P0/P1/P2 分组）。
 */

import { Layers } from 'lucide-react'
import type { Feature } from '@/types/studio'

const PRIORITY_META: Record<string, { label: string; style: string }> = {
  P0: { label: 'P0 · 必须', style: 'bg-destructive/10 text-destructive' },
  P1: { label: 'P1 · 重要', style: 'bg-yellow-500/10 text-yellow-600' },
  P2: { label: 'P2 · 可选', style: 'bg-emerald-500/10 text-emerald-600' },
}

export function FeatureMatrix({ features }: { features: Feature[] }) {
  const groups = ['P0', 'P1', 'P2']
    .map((priority) => ({
      priority,
      items: features.filter((f) => f.priority === priority),
    }))
    .filter((g) => g.items.length > 0)

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <div className="mb-4 flex items-center gap-2">
        <Layers className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold">功能清单</h3>
      </div>

      <div className="space-y-4">
        {groups.map((group) => (
          <div key={group.priority}>
            <div className="mb-2 flex items-center gap-2">
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  PRIORITY_META[group.priority]?.style ?? ''
                }`}
              >
                {PRIORITY_META[group.priority]?.label ?? group.priority}
              </span>
              {group.items[0]?.category && (
                <span className="text-xs text-muted-foreground">
                  分类示例：{group.items[0].category}
                </span>
              )}
            </div>
            <ul className="grid gap-2 sm:grid-cols-2">
              {group.items.map((feature) => (
                <li
                  key={feature.name}
                  className="rounded-lg border bg-background px-3 py-2.5"
                >
                  <div className="text-sm font-medium">{feature.name}</div>
                  {feature.description && (
                    <div className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                      {feature.description}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}
