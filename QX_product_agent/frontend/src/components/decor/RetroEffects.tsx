/**
 * RetroEffects —— Tech Retro 状态指示器（v3 精简版）
 *
 * 仅有 StatusLED（业务刚需），其余装饰元素随 decor/ 整体删除。
 */

import { cn } from '@/lib/utils'

type StatusType = 'online' | 'busy' | 'offline' | 'warning' | 'processing'

const STATUS_COLOR: Record<StatusType, string> = {
  online: 'bg-success shadow-[0_0_8px_hsl(var(--success))]',
  busy: 'bg-warning shadow-[0_0_8px_hsl(var(--warning))]',
  offline: 'bg-muted-foreground',
  warning: 'bg-warning shadow-[0_0_8px_hsl(var(--warning))]',
  processing: 'bg-accent shadow-[0_0_8px_hsl(var(--accent))]',
}

const STATUS_LABEL: Record<StatusType, string> = {
  online: '在线',
  busy: '繁忙',
  offline: '离线',
  warning: '警告',
  processing: '处理中',
}

export function StatusLED({
  status = 'online',
  size = 'sm',
  label,
  className,
}: {
  status?: StatusType
  size?: 'sm' | 'md' | 'lg'
  label?: string
  className?: string
}) {
  const sizeCls =
    size === 'sm' ? 'h-1.5 w-1.5' : size === 'md' ? 'h-2 w-2' : 'h-3 w-3'
  const animate = status === 'processing' || status === 'busy'
  return (
    <span
      className={cn('inline-flex items-center gap-1.5', className)}
      title={label ?? STATUS_LABEL[status]}
    >
      <span
        className={cn(
          'inline-block rounded-full',
          sizeCls,
          STATUS_COLOR[status],
          animate && 'animate-led',
        )}
      />
      {label && (
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
          {label}
        </span>
      )}
    </span>
  )
}