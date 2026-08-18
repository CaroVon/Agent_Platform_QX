/**
 * SourceIndex —— 文本资产「资料来源索引」
 *
 * 强制展示每个文本类资产引用的来源（URL + 标题 + 权重），
 * 与「禁止编造内容」规则配套：所有关键论断必须可回溯到资料。
 */

import { Link2 } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface SourceItem {
  url: string
  title?: string
  weight?: number
}

function weightBadge(weight?: number) {
  const w = weight ?? 0.5
  return cn(
    'shrink-0 rounded-full px-2 py-px text-[10px] font-medium',
    w >= 0.8 && 'bg-emerald-500/10 text-emerald-700',
    w >= 0.6 && w < 0.8 && 'bg-sky-500/10 text-sky-700',
    w >= 0.45 && w < 0.6 && 'bg-amber-500/10 text-amber-700',
    w < 0.45 && 'bg-gray-400/10 text-gray-500',
  )
}

function weightLabel(weight?: number) {
  const w = weight ?? 0.5
  if (w >= 0.8) return '高'
  if (w >= 0.6) return '中高'
  if (w >= 0.45) return '中'
  return '低'
}

export function SourceIndex({
  sources,
  marketSource,
  fallbackUrls,
}: {
  sources?: SourceItem[] | null
  /** 研究资产特有：market_size.source */
  marketSource?: string | null
  /** 兜底：从竞品等字段提取的 URL 列表 */
  fallbackUrls?: Array<{ url: string; title?: string }>
}) {
  const items: SourceItem[] = []
  const seen = new Set<string>()
  const push = (s?: SourceItem | null) => {
    if (!s?.url) return
    if (seen.has(s.url)) return
    seen.add(s.url)
    items.push(s)
  }
  ;(sources ?? []).forEach(push)
  if (marketSource) push({ url: marketSource, title: '市场规模数据来源', weight: 0.9 })
  ;(fallbackUrls ?? []).forEach(push)

  if (items.length === 0) return null

  return (
    <div className="rounded-xl border border-border/70 bg-background/50 p-5">
      <div className="mb-3 flex items-center gap-2">
        <Link2 className="h-3.5 w-3.5 text-[#24415E]" />
        <h4 className="text-xs font-semibold text-foreground">资料来源索引</h4>
        <span className="text-[10px] text-muted-foreground">
          （内容基于以下 {items.length} 条资料生成，来源可回溯）
        </span>
      </div>
      <ol className="space-y-1.5">
        {items.map((s, i) => (
          <li key={`${s.url}-${i}`} className="flex items-start gap-2 text-[11px] leading-snug">
            <span className="mt-px shrink-0 font-mono text-muted-foreground/70">[{i + 1}]</span>
            <a
              href={s.url.startsWith('local://') ? undefined : s.url}
              target={s.url.startsWith('local://') ? undefined : '_blank'}
              rel="noreferrer"
              className={cn(
                'min-w-0 flex-1 truncate text-muted-foreground',
                !s.url.startsWith('local://') && 'hover:text-[#24415E] hover:underline',
              )}
              title={s.title || s.url}
            >
              {s.title || s.url}
            </a>
            <span className={weightBadge(s.weight)}>权重 {weightLabel(s.weight)}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}
