/**
 * research/InsightCard —— 洞察卡（痛点 / 趋势 / 差异化机会）
 */

import { Lightbulb } from 'lucide-react'

export function InsightCard({
  title,
  items,
}: {
  title: string
  items: string[]
}) {
  if (!items.length) return null
  return (
    <div className="rounded-2xl border bg-card px-6 py-5">
      <div className="mb-3.5 flex items-center gap-2">
        <Lightbulb className="h-4 w-4 text-[#C87E4F]" />
        <h4 className="text-sm font-semibold tracking-tight">{title}</h4>
      </div>
      <ul className="space-y-2.5">
        {items.map((item) => (
          <li key={item} className="flex gap-2.5 text-[13px] leading-relaxed text-muted-foreground">
            <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#C87E4F]/60" />
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}
