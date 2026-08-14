/**
 * WorkspaceHeader —— 页面头部（面包屑 + 标题 + 描述 + 右侧操作区）
 * Breathing UI：大标题、低噪音。
 */

import type { ReactNode } from 'react'

export function WorkspaceHeader({
  title,
  description,
  actions,
  crumb,
}: {
  title: string
  description?: string
  actions?: ReactNode
  crumb?: string
}) {
  return (
    <div className="mb-8 flex items-start justify-between gap-6">
      <div>
        {crumb && (
          <div className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {crumb}
          </div>
        )}
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && (
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-3">{actions}</div>}
    </div>
  )
}
