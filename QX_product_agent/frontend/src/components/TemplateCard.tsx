/**
 * TemplateCard —— 模板卡片（空态，未来兼容）
 */

import type { LucideIcon } from 'lucide-react'

export function TemplateCard({
  icon: Icon,
  title,
  description,
  tag,
}: {
  icon: LucideIcon
  title: string
  description: string
  tag: string
}) {
  return (
    <div className="group flex flex-col rounded-xl border bg-card p-5 shadow-sm transition-all duration-150 hover:-translate-y-0.5 hover:shadow-md">
      <div className="flex items-start justify-between">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-secondary">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
          {tag}
        </span>
      </div>
      <h3 className="mt-4 text-sm font-semibold">{title}</h3>
      <p className="mt-1.5 flex-1 text-xs leading-relaxed text-muted-foreground">{description}</p>
      <div className="mt-4 rounded-lg bg-secondary/50 px-3 py-1.5 text-center text-[10px] text-muted-foreground">
        即将上线
      </div>
    </div>
  )
}
