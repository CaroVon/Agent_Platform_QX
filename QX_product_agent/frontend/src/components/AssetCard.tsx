/**
 * AssetCard —— 资产统一卡片（Productize 组件清单）
 * 用于 Workspace「Generated Assets」与各资产聚合页。
 */

import type { LucideIcon } from 'lucide-react'
import { ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'

export function AssetCard({
  icon: Icon,
  title,
  description,
  status = 'ready',
  badge,
  onClick,
  action,
}: {
  icon: LucideIcon
  title: string
  description: string
  status?: 'ready' | 'empty' | 'running'
  /** 渐进交付徽标：new=新增（高亮）/ soft=已交付 */
  badge?: { text: string; tone: 'new' | 'soft' }
  onClick?: () => void
  /** 右侧操作区（如"重新生成"），有值时替代 Chevron */
  action?: ReactNode
}) {
  const Wrapper = onClick ? 'button' : 'div'
  return (
    <Wrapper
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      className={`group flex w-full items-center gap-4 rounded-xl border bg-card p-5 text-left shadow-sm transition-all duration-150 ${
        onClick ? 'hover:-translate-y-0.5 hover:shadow-md cursor-pointer' : ''
      }`}
    >
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-secondary">
        <Icon className="h-5 w-5 text-primary" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">{title}</span>
          {status === 'empty' && (
            <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
              待生成
            </span>
          )}
          {status === 'running' && (
            <span className="rounded-full bg-yellow-500/10 px-2 py-0.5 text-[10px] text-yellow-600">
              生成中
            </span>
          )}
          {badge?.tone === 'new' && (
            <span className="animate-step-in rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-600">
              {badge.text}
            </span>
          )}
          {badge?.tone === 'soft' && (
            <span className="rounded-full bg-primary/8 px-2 py-0.5 text-[10px] text-primary">
              {badge.text}
            </span>
          )}
        </div>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">{description}</p>
      </div>
      {action ??
        (onClick && (
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
        ))}
    </Wrapper>
  )
}
