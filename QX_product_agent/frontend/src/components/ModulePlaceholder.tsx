/**
 * ModulePlaceholder —— 模块空状态壳（未来兼容）
 * 各模块的「路由 + UI 结构 + 空状态 + 扩展点」通用实现。
 */

import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { WorkspaceHeader } from '@/components/WorkspaceHeader'

export function ModulePlaceholder({
  icon: Icon,
  title,
  description,
  crumb,
  children,
  headerActions,
}: {
  icon: LucideIcon
  title: string
  description: string
  crumb?: string
  children?: ReactNode
  headerActions?: ReactNode
}) {
  return (
    <div>
      <WorkspaceHeader
        title={title}
        description={description}
        crumb={crumb}
        actions={headerActions}
      />

      {children ? (
        <div className="space-y-6">{children}</div>
      ) : (
        <div className="flex min-h-[420px] flex-col items-center justify-center rounded-2xl border border-dashed bg-card/40 px-8 py-16 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-secondary">
            <Icon className="h-6 w-6 text-muted-foreground" />
          </div>
          <h3 className="mt-5 text-base font-medium">模块建设中</h3>
          <p className="mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
            {description}
          </p>
          <div className="mt-6 rounded-lg bg-secondary/60 px-4 py-2 text-xs text-muted-foreground">
            功能规划中 · 架构已预留扩展点
          </div>
        </div>
      )}
    </div>
  )
}
