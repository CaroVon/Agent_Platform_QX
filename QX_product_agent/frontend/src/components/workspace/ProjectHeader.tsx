/**
 * ProjectHeader —— 项目头部（项目名/行业/状态/操作）
 */

import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react'
import type { StudioProduct } from '@/types/studio'
import { cn } from '@/lib/utils'

const STATUS_META: Record<string, { label: string; cls: string }> = {
  queued: { label: '排队中', cls: 'bg-secondary text-muted-foreground' },
  running: { label: '生成中', cls: 'bg-[#24415E]/10 text-[#24415E]' },
  completed: { label: '已完成', cls: 'bg-emerald-600/10 text-emerald-700' },
  failed: { label: '失败', cls: 'bg-destructive/10 text-destructive' },
}

export function ProjectHeader({ product }: { product: StudioProduct | null }) {
  if (!product) return null
  const meta = STATUS_META[product.status] ?? STATUS_META.queued

  return (
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div className="min-w-0">
        <div className="flex items-center gap-3">
          <h2 className="font-serif truncate text-2xl font-semibold tracking-tight">
            {product.idea}
          </h2>
          <span className={cn('shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium', meta.cls)}>
            {product.status === 'running' && (
              <Loader2 className="mr-1 inline h-3 w-3 animate-spin" />
            )}
            {product.status === 'completed' && (
              <CheckCircle2 className="mr-1 inline h-3 w-3" />
            )}
            {product.status === 'failed' && (
              <AlertCircle className="mr-1 inline h-3 w-3" />
            )}
            {meta.label}
          </span>
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>行业：智能产品</span>
          <span>创建：{product.created_at ? product.created_at.slice(0, 10) : '—'}</span>
          {product.critic_score != null && (
            <span>
              Critic 评分：
              <span
                className={cn(
                  'font-medium',
                  product.critic_score >= 80 ? 'text-emerald-700' : 'text-[#C87E4F]',
                )}
              >
                {product.critic_score}/100
              </span>
            </span>
          )}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <span className="text-[11px] text-muted-foreground/70">ID: {product.product_id.slice(0, 8)}</span>
      </div>
    </div>
  )
}
