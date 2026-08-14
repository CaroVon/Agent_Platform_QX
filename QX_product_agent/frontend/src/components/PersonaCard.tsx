/**
 * PersonaCard —— 用户画像卡片
 * 渲染 Persona（结构化 JSON）。
 */

import { User, Target, AlertTriangle } from 'lucide-react'
import type { Persona } from '@/types/studio'

export function PersonaCard({ persona }: { persona: Persona }) {
  return (
    <div className="flex h-full flex-col rounded-xl border bg-card p-5 shadow-sm">
      <div className="mb-3 flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-secondary">
          <User className="h-4 w-4 text-primary" />
        </div>
        <div>
          <div className="text-sm font-semibold">{persona.name}</div>
          {persona.role && (
            <div className="text-xs text-muted-foreground">{persona.role}</div>
          )}
        </div>
      </div>

      {persona.behavior && (
        <p className="mb-4 text-xs leading-relaxed text-muted-foreground">
          {persona.behavior}
        </p>
      )}

      {persona.goals.length > 0 && (
        <div className="mb-3">
          <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <Target className="h-3.5 w-3.5" /> 目标
          </div>
          <ul className="space-y-1">
            {persona.goals.map((goal) => (
              <li key={goal} className="text-sm text-foreground/90">
                · {goal}
              </li>
            ))}
          </ul>
        </div>
      )}

      {persona.pain_points.length > 0 && (
        <div>
          <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <AlertTriangle className="h-3.5 w-3.5" /> 痛点
          </div>
          <ul className="space-y-1">
            {persona.pain_points.map((pain) => (
              <li key={pain} className="text-sm text-foreground/90">
                · {pain}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
